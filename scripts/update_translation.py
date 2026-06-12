#!/usr/bin/env python3
"""
update_translation.py — End-to-end locale update orchestrator for vimhjkl i18n.

Ties together detect_curriculum_changes, generate_translation, and
validate_translation into a single CI/dev workflow:

  1. Detect: compare skills.json vs reference for translatable-field changes
  2. Generate: call AI translation for skills that need updating
  3. Validate: verify the resulting locale file against schema + completeness

Exit codes:
  0 — locale is up-to-date and valid (no changes needed, or all steps succeeded)
  1 — one or more steps failed (errors printed to stderr)

Usage:
  uv run python scripts/update_translation.py --locale zh-CN
  uv run python scripts/update_translation.py --locale zh-CN --api-key "$OPENAI_API_KEY"
  uv run python scripts/update_translation.py --locale zh-CN --skill motion-word-forward
  uv run python scripts/update_translation.py --locale zh-CN --dry-run
  uv run python scripts/update_translation.py --locale zh-CN --skip-validate
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SKILLS_JSON = REPO_ROOT / "src" / "vimhjkl" / "data" / "skills.json"
I18N_DIR = REPO_ROOT / "src" / "vimhjkl" / "data" / "i18n"
DETECT_SCRIPT = SCRIPTS_DIR / "detect_curriculum_changes.py"
GENERATE_SCRIPT = SCRIPTS_DIR / "generate_translation.py"
VALIDATE_SCRIPT = SCRIPTS_DIR / "validate_translation.py"


def _run(cmd: list[str], desc: str) -> "subprocess.CompletedProcess[str]":
    """Run a subprocess, print description, capture output."""
    print(f"  [{desc}]", file=sys.stderr)
    return subprocess.run(cmd, capture_output=True, text=True)


def _check_scripts_exist() -> None:
    """Verify all dependency scripts exist before starting."""
    missing = [p for p in [DETECT_SCRIPT, GENERATE_SCRIPT, VALIDATE_SCRIPT] if not p.is_file()]
    if missing:
        names = [p.name for p in missing]
        print(
            f"error: required script(s) not found: {', '.join(names)}",
            file=sys.stderr,
        )
        sys.exit(1)


def step_detect(locale: str, format_out: str = "json") -> dict[str, Any] | None:
    """
    Run detect_curriculum_changes.py and return the parsed manifest.

    Returns None if the detect script itself failed (exit code != 0 and != 1).
    """
    cmd = [
        sys.executable,
        str(DETECT_SCRIPT),
        "--format",
        format_out,
    ]
    if locale:
        cmd += ["--locale", locale]

    proc = _run(cmd, "detect   — checking for curriculum changes")

    if proc.returncode not in (0, 1):
        print(f"  detect failed (exit {proc.returncode}):", file=sys.stderr)
        if proc.stderr:
            for line in proc.stderr.strip().splitlines():
                print(f"    {line}", file=sys.stderr)
        return None

    if not proc.stdout.strip():
        print("  detect produced no output", file=sys.stderr)
        return None

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        print(f"  detect output is not valid JSON: {exc}", file=sys.stderr)
        print(f"  raw: {proc.stdout[:500]}", file=sys.stderr)
        return None


def step_generate(
    locale: str,
    api_key: str | None,
    skill: str | None,
    target_lang: str | None,
    dry_run: bool,
) -> bool:
    """
    Run generate_translation.py.

    Returns True on success (or dry-run completed).
    """
    cmd = [
        sys.executable,
        str(GENERATE_SCRIPT),
        "--locale",
        locale,
    ]
    if api_key:
        cmd += ["--api-key", api_key]
    if skill:
        cmd += ["--skill", skill]
    if target_lang:
        cmd += ["--target-lang", target_lang]
    if dry_run:
        cmd += ["--dry-run"]

    label = "generate  — "
    if skill:
        label += f"translating skill '{skill}'"
    elif dry_run:
        label += "dry-run (no API calls)"
    else:
        label += "translating all skills"

    proc = _run(cmd, label)

    if proc.returncode != 0:
        print(f"  generate failed (exit {proc.returncode}):", file=sys.stderr)
        if proc.stderr:
            for line in proc.stderr.strip().splitlines():
                print(f"    {line}", file=sys.stderr)
        return False

    if proc.stderr:
        for line in proc.stderr.strip().splitlines():
            print(f"    {line}", file=sys.stderr)
    return True


def step_validate(locale: str, strict: bool = False) -> bool:
    """
    Run validate_translation.py on the locale file.

    Returns True if validation passes (exit 0, possibly with warnings).
    """
    locale_file = I18N_DIR / f"{locale}.json"
    cmd = [
        sys.executable,
        str(VALIDATE_SCRIPT),
        "--locale",
        str(locale_file),
        "--skills",
        str(SKILLS_JSON),
        "--schema",
        str(I18N_DIR / "i18n-schema.json"),
    ]
    if strict:
        cmd += ["--strict"]

    proc = _run(cmd, "validate  — checking locale file" + (" (strict)" if strict else ""))

    for line in proc.stdout.strip().splitlines():
        print(f"    {line}", file=sys.stderr)
    if proc.stderr:
        for line in proc.stderr.strip().splitlines():
            print(f"    {line}", file=sys.stderr)

    if proc.returncode == 0:
        return True

    print(f"  validate failed (exit {proc.returncode})", file=sys.stderr)
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end vimhjkl locale update orchestrator",
    )
    parser.add_argument(
        "--locale",
        default="zh-CN",
        help="Locale code (e.g. zh-CN, fr). Default: zh-CN.",
    )
    parser.add_argument(
        "--skill",
        default=None,
        help="Translate only a single skill ID (instead of all changed).",
    )
    parser.add_argument(
        "--target-lang",
        default=None,
        help="Target language name for AI prompt (e.g. 'Simplified Chinese'). "
        "Auto-derived from locale if not set.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the translation service. Falls back to OPENAI_API_KEY env.",
    )
    parser.add_argument(
        "--skip-detect",
        action="store_true",
        help="Skip the detection step and always regenerate.",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip the validation step after generation.",
    )
    parser.add_argument(
        "--strict-validate",
        action="store_true",
        help="Run validate with --strict (warns on empty fields).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making API calls or writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _check_scripts_exist()

    locale_file = I18N_DIR / f"{args.locale}.json"
    if not locale_file.is_file():
        print(
            f"error: locale file not found: {locale_file}",
            file=sys.stderr,
        )
        return 1

    print(f"── vimhjkl i18n update: {args.locale} ──", file=sys.stderr)
    print(file=sys.stderr)

    # ── Resolve API key ──
    # generate_translation.py also reads OPENAI_API_KEY / DEEPSEEK_API_KEY from
    # the environment itself (DeepSeek implies its own base URL and model), so
    # an unset --api-key is fine as long as one of those is exported.
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY") \
        or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and not args.dry_run:
        print(
            "warning: no API key set (--api-key, OPENAI_API_KEY, or "
            "DEEPSEEK_API_KEY env). Generation will fail if needed.",
            file=sys.stderr,
        )

    # ── Step 1: Detect ──
    needs_generation = args.skip_detect or bool(args.skill)
    manifest = None

    if not needs_generation:
        manifest = step_detect(args.locale)
        if manifest is None:
            print("error: detection step failed", file=sys.stderr)
            return 1

        if not manifest.get("changed", False):
            locale_stale = manifest.get("locale_stale", None)
            if locale_stale is not False:
                print(
                    f"  locale {args.locale} is stale (source_sha mismatch), "
                    f"regenerating anyway",
                    file=sys.stderr,
                )
                needs_generation = True
            else:
                print(
                    f"  ✓ curriculum unchanged, locale {args.locale} is current",
                    file=sys.stderr,
                )
        else:
            needs_generation = True

    print(file=sys.stderr)

    # ── Step 2: Generate ──
    if needs_generation:
        # Forward only an EXPLICIT --api-key; env keys (OPENAI_API_KEY /
        # DEEPSEEK_API_KEY) reach the child via the environment, where
        # generate_translation picks the matching base URL and model.
        ok = step_generate(
            locale=args.locale,
            api_key=args.api_key,
            skill=args.skill,
            target_lang=args.target_lang,
            dry_run=args.dry_run,
        )
        if not ok:
            return 1
    else:
        print("  [generate]  skipped — no changes detected", file=sys.stderr)

    print(file=sys.stderr)

    # ── Step 3: Validate ──
    if not args.skip_validate:
        ok = step_validate(
            locale=args.locale,
            strict=args.strict_validate,
        )
        if not ok:
            return 1
    else:
        print("  [validate]  skipped (--skip-validate)", file=sys.stderr)

    print(file=sys.stderr)
    print("── done ──", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
