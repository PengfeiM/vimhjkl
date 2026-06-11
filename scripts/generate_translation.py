#!/usr/bin/env python3
"""Generate translations for vimhjkl i18n locale files via an OpenAI-compatible API.

This script is part of vimhjkl's CI pipeline. It reads the English curriculum
(skills.json) and an existing locale overlay, detects fields needing translation
(empty or missing), batches translatable fields by skill, calls an AI translation
API, and writes the updated locale file atomically.

Usage:
    python scripts/generate_translation.py --locale zh-CN [options]

Environment variables:
    OPENAI_API_KEY  — API key (alternative to --api-key)
    OPENAI_BASE_URL — API base URL (alternative to --api-base)
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SKILLS_PATH = Path("src/vimhjkl/data/skills.json")
DEFAULT_I18N_DIR = Path("src/vimhjkl/data/i18n")
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
API_RATE_LIMIT_SECONDS = 1.0
API_TIMEOUT_SECONDS = 180
TRANSLATION_SPEC_RELPATH = Path("src/vimhjkl/data/i18n/TRANSLATION_SPEC.md")

TRANSLATABLE_SKILL_FIELDS = ("title", "teach", "key_commands")
TRANSLATABLE_CHALLENGE_FIELDS = ("hint", "why")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict[str, Any]:
    """Load and return a JSON file's content."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write *data* as pretty-printed JSON to *path* using an atomic rename.

    A temporary file is written first, then atomically renamed over the
    target to avoid partial writes.
    """
    tmp = path.with_suffix(".tmp")
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def get_git_head_sha() -> str:
    """Return the current git HEAD commit SHA (short form), or empty string."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


# ---------------------------------------------------------------------------
# Source-of-truth index
# ---------------------------------------------------------------------------

def build_skill_index(skills_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a dict mapping skill_id → full skill object from skills.json."""
    return {s["id"]: s for s in skills_data.get("skills", [])}


# ---------------------------------------------------------------------------
# Computing what needs translation
# ---------------------------------------------------------------------------

def _locale_skill(
    locale: dict[str, Any], skill_id: str
) -> dict[str, Any]:
    """Return the existing locale overlay for *skill_id* (empty dict if absent)."""
    return locale.get("skills", {}).get(skill_id, {})


def _challenge_count(skill: dict[str, Any]) -> int:
    """Return the number of challenges in the English skill."""
    return len(skill.get("challenges", []))


def _locale_challenges(
    locale_skill: dict[str, Any], english_count: int
) -> list[dict[str, Any]]:
    """Return locale challenges list padded to *english_count* with empty dicts."""
    existing = locale_skill.get("challenges", [])
    padded = list(existing)
    while len(padded) < english_count:
        padded.append({})
    return padded


def compute_updates(
    skills_index: dict[str, dict[str, Any]],
    locale: dict[str, Any],
    skill_filter: str | None,
) -> list[dict[str, Any]]:
    """Return a list of update descriptors for fields needing translation.

    Each descriptor contains:
      - skill_id
      - fields: list of skill-level fields needing translation
      - challenges: list of {index, fields} for challenge-level fields
    """
    updates: list[dict[str, Any]] = []

    for skill_id, skill in skills_index.items():
        if skill_filter is not None and skill_id != skill_filter:
            continue

        lskill = _locale_skill(locale, skill_id)

        # Skill-level fields
        fields: list[str] = []
        for field in TRANSLATABLE_SKILL_FIELDS:
            val = lskill.get(field)
            if field == "key_commands":
                # Empty-list key_commands also needs translation
                if not val or (isinstance(val, list) and len(val) == 0):
                    fields.append(field)
            else:
                if not val:  # None, empty string, or missing
                    fields.append(field)

        # Challenge-level fields
        english_count = _challenge_count(skill)
        locale_chs = _locale_challenges(lskill, english_count)
        challenges: list[dict[str, Any]] = []
        for i in range(english_count):
            ch_fields: list[str] = []
            for cf in TRANSLATABLE_CHALLENGE_FIELDS:
                if not locale_chs[i].get(cf):
                    ch_fields.append(cf)
            if ch_fields:
                challenges.append({"index": i, "fields": ch_fields})

        if fields or challenges:
            updates.append({
                "skill_id": skill_id,
                "fields": fields,
                "challenges": challenges,
            })

    return updates


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def _field_char_count(skill: dict[str, Any], field: str) -> int:
    """Return character count of a skill-level field from the English source."""
    val = skill.get(field)
    if isinstance(val, str):
        return len(val)
    if isinstance(val, list):
        return sum(len(str(item)) for item in val)
    return 0


def estimate_tokens(
    skills_index: dict[str, dict[str, Any]],
    updates: list[dict[str, Any]],
) -> int:
    """Rough token estimate for all API calls needed.

    Uses ~4 characters per token for English text, adds a fixed overhead
    for system prompt and message framing.
    """
    total_chars = 0
    for upd in updates:
        skill = skills_index[upd["skill_id"]]
        for f in upd["fields"]:
            total_chars += _field_char_count(skill, f)
        for ch_up in upd["challenges"]:
            ch = skill.get("challenges", [])[ch_up["index"]]
            for f in ch_up["fields"]:
                total_chars += _field_char_count(ch, f)

    # ~4 characters per token for English, plus ~2000 overhead per call
    per_call_overhead = 2000 * len(updates)
    return max(500, total_chars // 4 + per_call_overhead)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Build the system prompt from TRANSLATION_SPEC.md translation rules."""
    return (
        "You are a professional Vim teaching-content translator. "
        "Follow these rules strictly.\n"
        "\n"
        "## RULE 1 — Vim Native Key/Command Literals (NEVER TRANSLATE)\n"
        "The following Vim-internal notation must remain in raw form:\n"
        "- Chevron-delimited key names: <Esc>, <CR>, <Tab>, <C-p>, <C-w>h, etc.\n"
        "- Ex commands: :wq, :%s/foo/bar/g, :g/pattern/d, :normal, :sort n, etc.\n"
        "- Operator+motion sequences: dd, ci\", gU, daw, 2w, ;., xp, ddp, etc.\n"
        "- Register references: \"a, \"0, \"=, \"ap, etc.\n"
        "- Range notation: %s, 1,5s, '<,'>normal, .+1,/}/-1, etc.\n"
        "- Mark names: ma, `a, 'a, ``\n"
        "- Regex metacharacters: \\v, \\V, \\c, \\zs, \\ze, \\< \\>, \\1, \\2, &, \\u, \\U\n"
        "These are NOT natural language. Never translate, localize, or modify them.\n"
        "\n"
        "## RULE 2 — Vim Mode Names (Translate Consistently)\n"
        "Use these standard translations for mode names:\n"
        "  Normal mode → 普通模式\n"
        "  Insert mode → 插入模式\n"
        "  Visual mode → 可视模式\n"
        "  Visual-Block mode → 可视块模式\n"
        "  Command-line mode → 命令行模式\n"
        "  Operator-Pending mode → 操作符待决模式\n"
        "\n"
        "## RULE 3 — Term Glossary Consistency\n"
        "Use these standard translations consistently:\n"
        "  operator → 操作符\n"
        "  motion → 动作\n"
        "  text object → 文本对象\n"
        "  register → 寄存器\n"
        "  macro → 宏\n"
        "  buffer → 缓冲区\n"
        "  mark → 标记\n"
        "  range → 范围\n"
        "  count → 计数\n"
        "  dot command → 点命令\n"
        "  delete → 删除\n"
        "  change → 修改\n"
        "  yank → 复制\n"
        "  put → 粘贴\n"
        "  substitute → 替换\n"
        "  undo → 撤销\n"
        "  word → 单词\n"
        "  WORD → 字串\n"
        "  inside → 内部\n"
        "  around → 周围\n"
        "\n"
        "## RULE 4 — key_commands Handling\n"
        "The key_commands array contains bare Vim keystroke notation. "
        "Keep each item exactly as-is. Do not translate or modify the keystrokes.\n"
        "\n"
        "## RULE 5 — Output Format\n"
        "Respond with a JSON object containing the translated fields. "
        "Include ONLY the fields that were requested for translation. "
        "Never add extra fields. "
        "The JSON structure must match the input structure:\n"
        '{"title": "...", "teach": "...", "key_commands": [...], '
        '"challenges": [{"hint": "...", "why": "..."}, ...]}\n'
        "\n"
        "## RULE 6 — Half-Width Symbols and Spacing Conventions\n"
        "- Use ONLY half-width (ASCII) punctuation and parentheses: (\") . , : ; ! ?\n"
        "- NEVER use full-width parentheses （）or other full-width punctuation.\n"
        "- Add a space between Chinese characters and adjacent non-Chinese content\n"
        "  (English, numbers, Vim notation, keyboard keys).\n"
        "  Examples:\n"
        "    ✅ \"点命令 (.) 重放你的上一次修改\"\n"
        "    ❌ \"点命令(.)重放你的上一次修改\"\n"
        "    ✅ \"f{char} 查找目标，再用 ; 重复\"\n"
        "    ❌ \"f{char}查找目标，再用;重复\"\n"
        "- Do NOT add spaces between consecutive non-Chinese tokens\n"
        "  (Vim notation spacing is literal).\n"
        "- Chinese punctuation （， 。、）stays as-is on its own; spacing rules above\n"
        "  apply at the boundary between Chinese and non-Chinese text.\n"
        "\n"
        "## Quality Checklist\n"
        "- Vim key notation (<Esc>, :wq, dd, ci\", \"a, etc.) is preserved EXACTLY.\n"
        "- Technical accuracy over literary elegance — precise > fluent.\n"
        "- Mode names and glossary terms are translated consistently.\n"
        "- Half-width symbols and spacing conventions are followed strictly.\n"
        "- Explanatory text around commands can be translated, but the command itself stays raw.\n"
        "- If unsure about a term, prefer a technically accurate but slightly awkward translation."
    )


def _format_challenges(skill: dict[str, Any], indices: list[int]) -> str:
    """Return a formatted string of challenge fields for the given indices."""
    parts: list[str] = []
    challenges = skill.get("challenges", [])
    for i in indices:
        if i < len(challenges):
            ch = challenges[i]
            hint = ch.get("hint", "")
            why = ch.get("why", "")
            parts.append(f"CHALLENGE {i + 1}:")
            if hint:
                parts.append(f'  HINT: {hint}')
            if why:
                parts.append(f'  WHY: {why}')
    return "\n".join(parts)


def build_user_prompt(
    skill_id: str,
    skill: dict[str, Any],
    fields: list[str],
    challenges: list[dict[str, Any]],
    target_lang: str,
) -> str:
    """Build the user prompt for a single skill translation request.

    Includes full English source for context but marks which fields to translate.
    """
    lines: list[str] = [
        f"Translate the following Vim skill content into {target_lang}.",
        "",
        f"SKILL ID: {skill_id}",
    ]

    for f in TRANSLATABLE_SKILL_FIELDS:
        if f in fields:
            val = skill.get(f, "")
            if isinstance(val, list):
                formatted = ", ".join(f'"{item}"' for item in val)
                lines.append(f"{f.upper()}: [{formatted}]")
            else:
                lines.append(f"{f.upper()}: {val}")

    challenge_indices = [c["index"] for c in challenges]
    if challenge_indices:
        lines.append("")
        lines.append("CHALLENGES:")
        lines.append(_format_challenges(skill, challenge_indices))

    lines.extend([
        "",
        "Return a JSON object containing ONLY the fields listed above, "
        "translated into the target language. "
        "Preserve all Vim keystrokes, commands, and notation exactly as they are. "
        "The JSON keys must match exactly: title, teach, key_commands, challenges.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI API call
# ---------------------------------------------------------------------------


def _extract_json_fenced(text: str) -> dict[str, Any] | None:
    """Extract JSON from text, handling markdown ```json ... ``` fences."""
    import re as _re

    # Try markdown code fence first
    m = _re.search(r"```(?:json)?\s*\n(.*?)\n```", text, _re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try extracting anything that looks like a JSON object
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def call_api(
    api_key: str,
    api_base: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any] | None:
    """Call the OpenAI-compatible API and return the parsed JSON response.

    Returns None on failure (network error, bad JSON, etc.).
    """
    url = f"{api_base.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        result = json.loads(raw)
        content = result["choices"][0]["message"]["content"]
        # Attempt JSON parse directly; fallback to extracting from ```json ... ``` fences
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return _extract_json_fenced(content)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(
            f"API HTTP error {e.code} for {url}: {body}",
            file=sys.stderr,
        )
        return None
    except urllib.error.URLError as e:
        print(f"API URL error: {e.reason}", file=sys.stderr)
        return None
    except (TimeoutError, socket.timeout) as e:
        print(f"API timeout: {e}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"API response parse error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Merge translated data into locale
# ---------------------------------------------------------------------------

def ensure_locale_skill(
    locale: dict[str, Any], skill_id: str
) -> dict[str, Any]:
    """Ensure the locale has a 'skills' dict and an entry for *skill_id*."""
    if "skills" not in locale:
        locale["skills"] = {}
    if skill_id not in locale["skills"]:
        locale["skills"][skill_id] = {}
    return locale["skills"][skill_id]


def merge_skill_translation(
    locale: dict[str, Any],
    skill_id: str,
    translated: dict[str, Any],
    fields: list[str],
    challenges: list[dict[str, Any]],
) -> None:
    """Merge *translated* JSON into the locale for the given skill.

    Only updates fields listed in *fields* and challenge fields listed in
    *challenges*.  Existing non-empty locale values for other fields are
    preserved untouched.
    """
    lskill = ensure_locale_skill(locale, skill_id)

    # Skill-level fields
    for f in fields:
        if f in translated and translated[f] is not None and translated[f] != "":
            lskill[f] = translated[f]
        elif f == "key_commands":
            # For key_commands, even an empty list is a valid input; preserve
            # whatever was returned
            if f in translated:
                lskill[f] = translated[f]

    # Challenge-level fields
    if "challenges" not in lskill:
        # Determine the correct length from the number of challenge updates
        max_idx = max((c["index"] for c in challenges), default=-1)
        lskill["challenges"] = [{} for _ in range(max_idx + 1)]

    t_challenges = translated.get("challenges", [])
    for ch_up in challenges:
        idx = ch_up["index"]
        # Extend the locale challenges array if needed
        while len(lskill["challenges"]) <= idx:
            lskill["challenges"].append({})
        for cf in ch_up["fields"]:
            if idx < len(t_challenges) and cf in t_challenges[idx]:
                val = t_challenges[idx][cf]
                if val is not None and val != "":
                    lskill["challenges"][idx][cf] = val


# ---------------------------------------------------------------------------
# Dry-run output
# ---------------------------------------------------------------------------

def locale_to_language_name(locale_code: str) -> str:
    """Map a locale code to a human-readable language name."""
    mapping: dict[str, str] = {
        "zh-CN": "Chinese (Simplified)",
        "zh-TW": "Chinese (Traditional)",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "pt-BR": "Portuguese (Brazilian)",
        "ru": "Russian",
        "ar": "Arabic",
        "tr": "Turkish",
        "vi": "Vietnamese",
        "th": "Thai",
        "id": "Indonesian",
    }
    return mapping.get(locale_code, locale_code)


def print_dry_run(
    locale_code: str,
    target_lang: str,
    skills_index: dict[str, dict[str, Any]],
    updates: list[dict[str, Any]],
) -> None:
    """Print the dry-run JSON plan to stdout."""
    is_tl = target_lang if target_lang != locale_code else locale_to_language_name(locale_code)
    report: dict[str, Any] = {
        "locale": locale_code,
        "target_language": is_tl,
        "update_count": len(updates),
        "updates": [
            {
                "skill_id": u["skill_id"],
                "fields": u["fields"],
                "challenges": u["challenges"],
            }
            for u in updates
        ],
        "api_calls_needed": len(updates),
        "estimated_tokens": estimate_tokens(skills_index, updates),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate or update translations for vimhjkl locale files "
            "via an OpenAI-compatible API."
        ),
    )
    parser.add_argument(
        "--locale",
        required=True,
        help="Locale code, e.g. zh-CN. Reads src/vimhjkl/data/i18n/{locale}.json.",
    )
    parser.add_argument(
        "--skills",
        default=str(DEFAULT_SKILLS_PATH),
        help=f"Path to skills.json (default: {DEFAULT_SKILLS_PATH}).",
    )
    parser.add_argument(
        "--target-lang",
        default="zh-CN",
        help=(
            "Human language description passed to the AI "
            '(default: "zh-CN", use e.g. "Chinese (Simplified)" for clarity).'
        ),
    )
    parser.add_argument(
        "--skill",
        default=None,
        help="Only translate this specific skill ID.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Output planned translations as JSON to stdout without calling the API.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI-compatible API key (env: OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help=f"API base URL (env: OPENAI_BASE_URL, default: {DEFAULT_API_BASE}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point.  Returns 0 on success, 1 on total failure."""
    args = parse_args(argv)
    locale_code = args.locale
    skills_path = Path(args.skills)
    i18n_dir = DEFAULT_I18N_DIR
    locale_path = i18n_dir / f"{locale_code}.json"
    target_lang = args.target_lang
    skill_filter = args.skill
    dry_run = args.dry_run

    # API credentials
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    api_base = args.api_base or os.environ.get("OPENAI_BASE_URL", "") or DEFAULT_API_BASE
    model = args.model

    if not dry_run and not api_key:
        print(
            "Error: API key is required. Provide --api-key or set OPENAI_API_KEY.",
            file=sys.stderr,
        )
        return 1

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------
    if not skills_path.exists():
        print(f"Error: skills.json not found at {skills_path}", file=sys.stderr)
        return 1

    skills_data = load_json(skills_path)
    skills_index = build_skill_index(skills_data)

    # Load or create locale
    if locale_path.exists():
        locale = load_json(locale_path)
    else:
        locale: dict[str, Any] = {
            "locale": locale_code,
            "source_sha": "",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "glossary": {},
            "skills": {},
        }
        if dry_run:
            print(
                f"Info: locale file {locale_path} does not exist; "
                "will create a new one.",
                file=sys.stderr,
            )

    # -----------------------------------------------------------------------
    # Compute updates
    # -----------------------------------------------------------------------
    updates = compute_updates(skills_index, locale, skill_filter)

    if not updates:
        print(
            "No translatable fields found. Everything is up to date.",
            file=sys.stderr if dry_run else sys.stdout,
        )
        return 0

    # -----------------------------------------------------------------------
    # Dry run
    # -----------------------------------------------------------------------
    if dry_run:
        print_dry_run(locale_code, target_lang, skills_index, updates)
        return 0

    # -----------------------------------------------------------------------
    # Translate
    # -----------------------------------------------------------------------
    spec_path = Path(TRANSLATION_SPEC_RELPATH)
    system_prompt = build_system_prompt()
    failed_count = 0
    success_count = 0

    for i, upd in enumerate(updates):
        skill_id = upd["skill_id"]
        skill = skills_index[skill_id]
        user_prompt = build_user_prompt(
            skill_id, skill, upd["fields"], upd["challenges"], target_lang,
        )

        # Rate limiting: delay between calls
        if i > 0:
            time.sleep(API_RATE_LIMIT_SECONDS)

        print(
            f"[{i + 1}/{len(updates)}] Translating skill '{skill_id}' "
            f"({len(upd['fields'])} fields, "
            f"{len(upd['challenges'])} challenges)...",
            file=sys.stdout,
        )

        result = call_api(api_key, api_base, model, system_prompt, user_prompt)

        if result is None:
            print(
                f"  ✗ Failed for skill '{skill_id}'. Skipping.",
                file=sys.stderr,
            )
            failed_count += 1
            continue

        merge_skill_translation(
            locale, skill_id, result, upd["fields"], upd["challenges"],
        )
        success_count += 1
        # Incremental save: checkpoint after each successful translation
        # so partial progress is not lost if the script crashes or times out.
        write_json_atomic(locale_path, locale)
        print(f"  ✓ Translated skill '{skill_id}'.", file=sys.stdout)

    # -----------------------------------------------------------------------
    # Update metadata
    # -----------------------------------------------------------------------
    head_sha = get_git_head_sha()
    if head_sha:
        locale["source_sha"] = head_sha
    locale["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    locale["locale"] = locale_code

    # -----------------------------------------------------------------------
    # Write
    # -----------------------------------------------------------------------
    # Ensure the i18n directory exists
    i18n_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(locale_path, locale)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(
        f"\nDone. {success_count} skill(s) translated, "
        f"{failed_count} failed.",
        file=sys.stdout,
    )

    return 1 if success_count == 0 and failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
