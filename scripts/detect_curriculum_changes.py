#!/usr/bin/env python3
"""Detect changes between current skills.json and a reference version.

Outputs a JSON change manifest used by vimhjkl's i18n CI pipeline to
determine which translatable fields need re-translation.

Usage:
    python scripts/detect_curriculum_changes.py
    python scripts/detect_curriculum_changes.py --reference HEAD
    python scripts/detect_curriculum_changes.py --reference /path/to/skills.json
    python scripts/detect_curriculum_changes.py --format text
    python scripts/detect_curriculum_changes.py --locale zh-CN
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_PATH = PROJECT_ROOT / "src" / "vimhjkl" / "data" / "skills.json"
I18N_DIR = PROJECT_ROOT / "src" / "vimhjkl" / "data" / "i18n"

TRANSLATABLE_SKILL_FIELDS: tuple[str, ...] = ("title", "teach", "key_commands")
TRANSLATABLE_CHALLENGE_FIELDS: tuple[str, ...] = ("hint", "why", "why_not")


# ---------------------------------------------------------------------------
# Reference loading
# ---------------------------------------------------------------------------

def load_reference_from_git(ref: str = "HEAD") -> dict[str, Any]:
    """Load skills.json from a git revision using ``git show``."""
    git_path = f"{ref}:src/vimhjkl/data/skills.json"
    try:
        result = subprocess.run(
            ["git", "show", git_path],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"Failed to load '{git_path}' from git: {exc.stderr.strip()}"
        raise RuntimeError(msg) from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            "git is not available on PATH; provide a file path via --reference"
        ) from exc
    return json.loads(result.stdout)


def load_reference_from_file(path: str) -> dict[str, Any]:
    """Load skills.json from a local file path."""
    ref_path = Path(path).resolve()
    if not ref_path.is_file():
        raise RuntimeError(f"Reference file not found: {ref_path}")
    with ref_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_current_skills() -> dict[str, Any]:
    """Load the working-tree skills.json."""
    if not SKILLS_PATH.is_file():
        raise RuntimeError(f"skills.json not found at {SKILLS_PATH}")
    with SKILLS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def get_current_sha() -> str:
    """Return the current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_ROOT,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo or git unavailable
        return ""


def is_git_repo() -> bool:
    """Check whether the project root is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

def compare_skills(
    current: list[dict[str, Any]],
    reference: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deep-compare two skill lists on translatable fields only.

    Returns a change dictionary with the keys described in the module docstring.
    """
    cur_by_id: dict[str, dict[str, Any]] = {s["id"]: s for s in current}
    ref_by_id: dict[str, dict[str, Any]] = {s["id"]: s for s in reference}

    cur_ids: set[str] = set(cur_by_id.keys())
    ref_ids: set[str] = set(ref_by_id.keys())

    added_ids: list[str] = sorted(cur_ids - ref_ids)
    removed_ids: list[str] = sorted(ref_ids - cur_ids)
    common_ids: set[str] = cur_ids & ref_ids

    modified_skills: dict[str, dict[str, Any]] = {}
    added_challenges: dict[str, list[dict[str, int]]] = {}
    removed_challenges: dict[str, list[dict[str, int]]] = {}

    for sid in common_ids:
        cur_skill = cur_by_id[sid]
        ref_skill = ref_by_id[sid]

        # -- Skill-level translatable fields ---------------------------------
        changed_skill_fields = [
            f
            for f in TRANSLATABLE_SKILL_FIELDS
            if cur_skill.get(f) != ref_skill.get(f)
        ]

        # -- Challenge-level translatable fields ------------------------------
        cur_challenges: list[dict[str, Any]] = cur_skill.get("challenges", [])
        ref_challenges: list[dict[str, Any]] = ref_skill.get("challenges", [])

        changed_challenges: list[dict[str, Any]] = []
        self_added: list[dict[str, int]] = []
        self_removed: list[dict[str, int]] = []

        # Common challenges (index-for-index comparison)
        for i in range(min(len(cur_challenges), len(ref_challenges))):
            cc = cur_challenges[i]
            rc = ref_challenges[i]
            diff = [
                f
                for f in TRANSLATABLE_CHALLENGE_FIELDS
                if cc.get(f) != rc.get(f)
            ]
            if diff:
                changed_challenges.append({"index": i, "fields": diff})

        # Extra challenges in current (added)
        if len(cur_challenges) > len(ref_challenges):
            for i in range(len(ref_challenges), len(cur_challenges)):
                self_added.append({"index": i})

        # Extra challenges in reference (removed)
        if len(ref_challenges) > len(cur_challenges):
            for i in range(len(cur_challenges), len(ref_challenges)):
                self_removed.append({"index": i})

        # Build entry
        entry: dict[str, Any] = {}
        if changed_skill_fields:
            entry["fields_changed"] = changed_skill_fields
        if changed_challenges:
            entry["challenges_changed"] = changed_challenges
        if entry:
            modified_skills[sid] = entry

        if self_added:
            added_challenges[sid] = self_added
        if self_removed:
            removed_challenges[sid] = self_removed

    return {
        "added_skills": added_ids,
        "removed_skills": removed_ids,
        "modified_skills": modified_skills,
        "added_challenges": added_challenges,
        "removed_challenges": removed_challenges,
    }


# ---------------------------------------------------------------------------
# Locale staleness
# ---------------------------------------------------------------------------

def load_locale(locale: str) -> dict[str, Any]:
    """Load a locale file from the i18n directory."""
    locale_path = I18N_DIR / f"{locale}.json"
    if not locale_path.is_file():
        raise RuntimeError(f"Locale file not found: {locale_path}")
    with locale_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_locale_staleness(
    locale_data: dict[str, Any],
    current_sha: str,
    changes: dict[str, Any],
    current_skills: list[dict[str, Any]],
) -> dict[str, Any]:
    """Determine locale staleness indicators.

    Returns a dict with keys ``locale_stale``, ``locale_missing_skills``,
    and ``locale_stale_skills``.
    """
    locale_skills: dict[str, Any] = locale_data.get("skills", {})
    locale_sha: str = locale_data.get("source_sha", "")

    # A locale is stale if its recorded SHA doesn't match HEAD, or if there
    # are any curriculum changes.
    sha_mismatch = bool(current_sha) and (locale_sha != current_sha)
    has_changes = (
        bool(changes["added_skills"])
        or bool(changes["removed_skills"])
        or bool(changes["modified_skills"])
        or bool(changes["added_challenges"])
        or bool(changes["removed_challenges"])
    )
    locale_stale = sha_mismatch or has_changes

    # Missing skills: in curriculum but not in locale
    locale_skill_ids: set[str] = set(locale_skills.keys())
    cur_ids: set[str] = {s["id"] for s in current_skills}
    missing_skills: list[str] = sorted(cur_ids - locale_skill_ids)

    # Stale skills: subset of modified_skills that exist in the locale
    stale_skills: dict[str, list[str]] = {}
    modified: dict[str, Any] = changes.get("modified_skills", {})
    for sid, mod in modified.items():
        if sid in locale_skills:
            stale_skills[sid] = list(mod.get("fields_changed", []))

    return {
        "locale_stale": locale_stale,
        "locale_missing_skills": missing_skills,
        "locale_stale_skills": stale_skills,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def build_manifest(
    changes: dict[str, Any],
    current_sha: str,
    locale_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble the full output JSON manifest."""
    changed = (
        bool(changes["added_skills"])
        or bool(changes["removed_skills"])
        or bool(changes["modified_skills"])
        or bool(changes["added_challenges"])
        or bool(changes["removed_challenges"])
    )

    manifest: dict[str, Any] = {
        "changed": changed,
        "current_sha": current_sha,
        "changes": changes,
    }

    if locale_result is not None:
        manifest["locale_stale"] = locale_result["locale_stale"]
        manifest["locale_missing_skills"] = locale_result["locale_missing_skills"]
        manifest["locale_stale_skills"] = locale_result["locale_stale_skills"]

    return manifest


def format_text(manifest: dict[str, Any]) -> str:
    """Render the manifest as human-readable text."""
    lines: list[str] = []
    changes = manifest["changes"]

    if manifest["changed"]:
        lines.append(f"Curriculum changed (HEAD: {manifest['current_sha']})")
        lines.append("")
    else:
        lines.append("Curriculum unchanged.")
        lines.append("")
        return "\n".join(lines)

    if changes["added_skills"]:
        lines.append("--- Added skills ---")
        for sid in changes["added_skills"]:
            lines.append(f"  + {sid}")
        lines.append("")

    if changes["removed_skills"]:
        lines.append("--- Removed skills ---")
        for sid in changes["removed_skills"]:
            lines.append(f"  - {sid}")
        lines.append("")

    if changes["modified_skills"]:
        lines.append("--- Modified skills (translatable fields) ---")
        for sid, mod in sorted(changes["modified_skills"].items()):
            fields = ", ".join(mod.get("fields_changed", []))
            if fields:
                lines.append(f"  ~ {sid}  [{fields}]")
            for cc in mod.get("challenges_changed", []):
                ch_fields = ", ".join(cc["fields"])
                lines.append(f"      challenge[{cc['index']}]  [{ch_fields}]")
        lines.append("")

    if changes["added_challenges"]:
        lines.append("--- Added challenges ---")
        for sid, chs in sorted(changes["added_challenges"].items()):
            indices = ", ".join(str(c["index"]) for c in chs)
            lines.append(f"  + {sid}  challenge[{indices}]")
        lines.append("")

    if changes["removed_challenges"]:
        lines.append("--- Removed challenges ---")
        for sid, chs in sorted(changes["removed_challenges"].items()):
            indices = ", ".join(str(c["index"]) for c in chs)
            lines.append(f"  - {sid}  challenge[{indices}]")
        lines.append("")

    if "locale_stale" in manifest:
        lines.append(
            f"Locale stale: {manifest['locale_stale']}"
        )
        if manifest["locale_missing_skills"]:
            lines.append("  Missing skills in locale:")
            for sid in manifest["locale_missing_skills"]:
                lines.append(f"    - {sid}")
        if manifest["locale_stale_skills"]:
            lines.append("  Stale translations (fields changed):")
            for sid, fields in sorted(manifest["locale_stale_skills"].items()):
                lines.append(f"    ~ {sid}  [{', '.join(fields)}]")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect translatable-field changes between the current skills.json "
            "and a reference version."
        ),
    )
    parser.add_argument(
        "--reference",
        default="HEAD",
        help=(
            "Path to a reference skills.json, or 'HEAD' to compare the working "
            "tree against the git HEAD revision (default: HEAD). If not in a git "
            "repo, a file path must be provided."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--locale",
        default=None,
        help=(
            "Locale code (e.g. zh-CN). When provided, the script also checks "
            "the locale file's source_sha for staleness detection."
        ),
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    args = parse_args(argv)

    # -- Load reference ------------------------------------------------------
    if args.reference == "HEAD":
        if not is_git_repo():
            print(
                "error: --reference HEAD requires a git repository; "
                "provide a file path instead",
                file=sys.stderr,
            )
            return 1
        try:
            ref_data = load_reference_from_git("HEAD")
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            ref_data = load_reference_from_file(args.reference)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    # -- Load current --------------------------------------------------------
    try:
        cur_data = load_current_skills()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # -- SHA -----------------------------------------------------------------
    current_sha = get_current_sha()

    # -- Compare -------------------------------------------------------------
    ref_skills: list[dict[str, Any]] = ref_data.get("skills", [])
    cur_skills: list[dict[str, Any]] = cur_data.get("skills", [])
    changes = compare_skills(cur_skills, ref_skills)

    # -- Locale (optional) ---------------------------------------------------
    locale_result: dict[str, Any] | None = None
    if args.locale is not None:
        try:
            locale_data = load_locale(args.locale)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        locale_result = check_locale_staleness(
            locale_data, current_sha, changes, cur_skills,
        )

    # -- Build output --------------------------------------------------------
    manifest = build_manifest(changes, current_sha, locale_result)

    if args.format == "json":
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print(format_text(manifest))

    return 0


if __name__ == "__main__":
    sys.exit(main())
