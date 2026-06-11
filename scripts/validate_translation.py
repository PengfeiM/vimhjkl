#!/usr/bin/env python3
"""vimhjkl Translation Validator.

Validates locale translation files against the canonical skills.json
curriculum and the i18n JSON schema. Part of vimhjkl's i18n CI pipeline.

Pure Python stdlib, zero runtime dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_TOP_LEVEL_FIELDS = frozenset({"locale", "source_sha", "generated_at", "glossary", "skills"})
ALLOWED_SKILL_FIELDS = frozenset({"title", "teach", "key_commands", "challenges"})
ALLOWED_CHALLENGE_FIELDS = frozenset({"hint", "why"})
SKILL_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]+$")
LOCALE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
TRANSLATABLE_SKILL_FIELDS = ("title", "teach")
TRANSLATABLE_CHALLENGE_FIELDS = ("hint", "why")

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_RUNTIME = 2


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class Counts:
    """Tracks error, warning, and info counts."""

    def __init__(self) -> None:
        self.errors: int = 0
        self.warnings: int = 0
        self.infos: int = 0

    def err(self, msg: str) -> None:
        print(f"  \u2717 {msg}")
        self.errors += 1

    def warn(self, msg: str) -> None:
        print(f"  \u26a0 {msg}")
        self.warnings += 1

    def info(self, msg: str) -> None:
        print(f"  \u2139 {msg}")
        self.infos += 1

    def ok(self, msg: str) -> None:
        print(f"  \u2713 {msg}")


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def load_json(path: Path, label: str) -> Any:
    """Load and parse a JSON file. Exits on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  \u2717 {label} not found: {path}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME)
    except json.JSONDecodeError as exc:
        print(f"  \u2717 {label} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME)


def check_locale_pattern(locale: str) -> Optional[str]:
    """Validate the locale string against BCP-47 pattern."""
    if not LOCALE_PATTERN.match(locale):
        return (
            f"locale '{locale}' does not match pattern "
            f"^[a-z]{{2}}(-[A-Z]{{2}})?$"
        )
    return None


def validate_schema(data: dict[str, Any], _path: str) -> list[str]:
    """Pragmatic structural validation of locale data.

    This is NOT a full JSON Schema implementation. It checks that the data
    conforms to the expected shape defined by i18n-schema.json.
    """
    issues: list[str] = []

    # --- Top-level required fields ---
    if "locale" not in data:
        issues.append("Missing required top-level field: 'locale'")
    else:
        err = check_locale_pattern(data["locale"])
        if err:
            issues.append(err)

    if "skills" not in data:
        issues.append("Missing required top-level field: 'skills'")
    elif not isinstance(data["skills"], dict):
        issues.append("'skills' must be an object (dict)")

    # --- Extra top-level fields ---
    for key in data:
        if key not in ALLOWED_TOP_LEVEL_FIELDS:
            issues.append(f"Extra top-level field not allowed: '{key}'")

    # --- Skills object validation ---
    if isinstance(data.get("skills"), dict):
        for skill_id, skill_val in data["skills"].items():
            if not SKILL_ID_PATTERN.match(skill_id):
                issues.append(
                    f"Skill key '{skill_id}' does not match pattern "
                    f"^[a-zA-Z][a-zA-Z0-9_-]+$"
                )
            if not isinstance(skill_val, dict):
                issues.append(f"Skill '{skill_id}' must be an object")
                continue

            for field in skill_val:
                if field not in ALLOWED_SKILL_FIELDS:
                    issues.append(
                        f"Skill '{skill_id}' has unexpected field: '{field}'"
                    )

            challenges = skill_val.get("challenges")
            if challenges is not None:
                if not isinstance(challenges, list):
                    issues.append(
                        f"Skill '{skill_id}': 'challenges' must be an array"
                    )
                else:
                    for idx, chal in enumerate(challenges):
                        if not isinstance(chal, dict):
                            issues.append(
                                f"Skill '{skill_id}', challenge {idx}: "
                                f"must be an object"
                            )
                            continue
                        for field in chal:
                            if field not in ALLOWED_CHALLENGE_FIELDS:
                                issues.append(
                                    f"Skill '{skill_id}', challenge {idx}: "
                                    f"unexpected field: '{field}'"
                                )

    # --- AdditionalProperties: glossary values must be strings ---
    glossary = data.get("glossary")
    if glossary is not None:
        if not isinstance(glossary, dict):
            issues.append("'glossary' must be an object")
        else:
            for k, v in glossary.items():
                if not isinstance(v, str):
                    issues.append(
                        f"Glossary entry '{k}' must be a string, "
                        f"got {type(v).__name__}"
                    )

    # --- source_sha and generated_at types ---
    if "source_sha" in data and not isinstance(data["source_sha"], str):
        issues.append("'source_sha' must be a string")
    if "generated_at" in data and not isinstance(data["generated_at"], str):
        issues.append("'generated_at' must be a string")

    return issues


def check_skill_completeness(
    skills_source: list[dict[str, Any]],
    skills_locale: dict[str, Any],
    counts: Counts,
) -> None:
    """Check that all skills in the source exist in the locale."""
    locale_skill_ids = set(skills_locale.keys())
    total = 0
    missing = 0
    for skill in skills_source:
        sid: str = skill["id"]
        total += 1
        if sid not in locale_skill_ids:
            counts.err(f"Missing skill in locale: '{sid}'")
            missing += 1
    if missing == 0:
        counts.ok(f"All {total} skills present")
    else:
        counts.info(f"{missing} of {total} skills missing from locale")


def check_challenge_completeness(
    skills_source: list[dict[str, Any]],
    skills_locale: dict[str, Any],
    counts: Counts,
) -> None:
    """Check that each skill's challenge array has enough entries."""
    total_source = 0
    total_locale = 0
    issues_found = False
    for skill in skills_source:
        sid: str = skill["id"]
        source_chal_count = len(skill.get("challenges", []))
        total_source += source_chal_count
        if sid not in skills_locale:
            continue
        locale_skill = skills_locale[sid]
        locale_chal = locale_skill.get("challenges")
        if not isinstance(locale_chal, list):
            counts.err(f"Skill '{sid}': challenges must be an array")
            issues_found = True
            continue
        locale_chal_count = len(locale_chal)
        total_locale += locale_chal_count
        if locale_chal_count < source_chal_count:
            counts.err(
                f"Skill '{sid}': {source_chal_count} challenges in source, "
                f"but {locale_chal_count} in locale"
            )
            issues_found = True
        elif locale_chal_count > source_chal_count:
            counts.warn(
                f"Skill '{sid}': {source_chal_count} challenges in source, "
                f"but {locale_chal_count} in locale (extra entries)"
            )
            issues_found = True

    if not issues_found:
        counts.ok(
            f"{total_locale} challenge entries exist (matches source)"
        )
    else:
        counts.info(
            f"Source has {total_source} challenges total; "
            f"locale has {total_locale}"
        )


def check_field_completeness(
    skills_source: list[dict[str, Any]],
    skills_locale: dict[str, Any],
    counts: Counts,
    strict: bool,
) -> None:
    """Check translatable fields for empty strings.

    In strict mode, empty fields are reported as warnings.
    Without --strict, empty strings are OK (skeleton mode).
    """
    if not strict:
        return

    empty_count = 0
    total_checked = 0
    for skill in skills_source:
        sid: str = skill["id"]
        if sid not in skills_locale:
            continue
        loc = skills_locale[sid]

        # Skill-level translatable fields
        for field in TRANSLATABLE_SKILL_FIELDS:
            if field in loc:
                total_checked += 1
                val = loc[field]
                if not isinstance(val, str) or val.strip() == "":
                    counts.warn(
                        f"Skill '{sid}': '{field}' is empty in locale"
                    )
                    empty_count += 1

        # Challenge-level translatable fields
        source_chals = skill.get("challenges", [])
        loc_chals = loc.get("challenges")
        if isinstance(loc_chals, list):
            for idx, chal in enumerate(loc_chals):
                if idx >= len(source_chals):
                    break
                if not isinstance(chal, dict):
                    continue
                for field in TRANSLATABLE_CHALLENGE_FIELDS:
                    if field in chal:
                        total_checked += 1
                        val = chal[field]
                        if not isinstance(val, str) or val.strip() == "":
                            counts.warn(
                                f"Skill '{sid}', challenge {idx}: "
                                f"'{field}' is empty in locale"
                            )
                            empty_count += 1

    if empty_count > 0:
        counts.info(
            f"{empty_count} empty translatable fields (--strict mode)"
        )
    else:
        counts.ok("All translatable fields are non-empty")


def check_stale_entries(
    skills_source: list[dict[str, Any]],
    skills_locale: dict[str, Any],
    counts: Counts,
) -> None:
    """Report skills in the locale that no longer exist in skills.json."""
    source_ids = {s["id"] for s in skills_source}
    stale: list[str] = []
    for sid in skills_locale:
        if sid not in source_ids:
            stale.append(sid)

    if stale:
        for sid in stale:
            counts.warn(f"Stale locale entry: '{sid}' not in skills.json")
    else:
        counts.ok("No stale locale entries")


def check_terminology(
    skills_source: list[dict[str, Any]],
    skills_locale: dict[str, Any],
    glossary: dict[str, str],
    counts: Counts,
) -> None:
    """Soft glossary consistency check.

    If glossary entries exist, check that each English term present in the
    source translatable fields appears in the corresponding locale
    translation (basic substring matching on skill-level fields only).
    Informational only -- not a failure.
    """
    if not glossary:
        counts.info("No glossary entries to check")
        return

    inconsistencies = 0
    terms_checked = len(glossary)

    for eng_term, loc_term in glossary.items():
        if not eng_term.strip() or not loc_term.strip():
            continue
        for skill in skills_source:
            sid: str = skill["id"]
            if sid not in skills_locale:
                continue
            loc_skill = skills_locale[sid]
            for field in TRANSLATABLE_SKILL_FIELDS:
                eng_val = skill.get(field, "")
                loc_val = loc_skill.get(field, "")
                if not isinstance(eng_val, str) or not isinstance(loc_val, str):
                    continue
                if eng_term.lower() in eng_val.lower():
                    if loc_term.lower() not in loc_val.lower():
                        inconsistencies += 1
                        if inconsistencies <= 5:
                            counts.warn(
                                f"Glossary term '{eng_term}' -> '{loc_term}' "
                                f"may be missing in {sid}.{field}"
                            )

    if inconsistencies > 5:
        counts.info(
            f"... and {inconsistencies - 5} more glossary mismatches"
        )

    counts.info(
        f"Terminology: {terms_checked} glossary terms checked, "
        f"{inconsistencies} inconsistencies"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate vimhjkl locale translation files",
    )
    parser.add_argument(
        "--locale",
        required=True,
        type=str,
        help="Path to the locale JSON file to validate",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default="src/vimhjkl/data/skills.json",
        help="Path to the canonical skills.json (default: src/vimhjkl/data/skills.json)",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="src/vimhjkl/data/i18n/i18n-schema.json",
        help="Path to the i18n JSON schema (default: src/vimhjkl/data/i18n/i18n-schema.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Report empty-string translatable fields as warnings",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    counts = Counts()
    args = parse_args(argv)

    locale_path = Path(args.locale)
    skills_path = Path(args.skills)
    schema_path = Path(args.schema)

    print("=== vimhjkl Translation Validator ===", file=sys.stderr)
    print(f"File: {locale_path.name}", file=sys.stderr)
    print(f"Validating against: {skills_path.name}", file=sys.stderr)
    print(f"Schema: {schema_path.name}", file=sys.stderr)
    print(file=sys.stderr)

    # --- 1. File exists & valid JSON ---
    locale_data: dict[str, Any] = load_json(locale_path, "Locale file")
    counts.ok("JSON is valid")

    skills_data: dict[str, Any] = load_json(skills_path, "Skills file")
    schema_data: dict[str, Any] = load_json(schema_path, "Schema file")

    skills_list: list[dict[str, Any]] = skills_data.get("skills", [])
    locale_skills: dict[str, Any] = locale_data.get("skills", {})

    # --- 2. Schema validation ---
    schema_issues = validate_schema(locale_data, args.locale)
    if schema_issues:
        for issue in schema_issues:
            counts.err(issue)
    else:
        counts.ok("Schema structure OK")

    # --- 3. Skill completeness ---
    check_skill_completeness(skills_list, locale_skills, counts)

    # --- 4. Challenge completeness ---
    check_challenge_completeness(skills_list, locale_skills, counts)

    # --- 5. Field completeness (--strict only) ---
    check_field_completeness(skills_list, locale_skills, counts, args.strict)

    # --- 6. Stale locale entries ---
    check_stale_entries(skills_list, locale_skills, counts)

    # --- 7. Terminology check ---
    glossary: dict[str, str] = locale_data.get("glossary", {})
    check_terminology(skills_list, locale_skills, glossary, counts)

    # --- Summary ---
    print(
        f"\nResults: {counts.errors} errors, "
        f"{counts.warnings} warnings, "
        f"{counts.infos} info",
    )

    if counts.errors > 0:
        return EXIT_ERRORS
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
