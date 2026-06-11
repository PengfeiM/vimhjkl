"""i18n locale overlay tests (no vim needed)."""

import sys
import json
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vimhjkl.challenge import Skill
from vimhjkl import store, config

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m\u2713\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31m\u2717 {name}\033[0m  {detail}")


def _make_skills_json() -> dict:
    """Return a minimal skills.json dict for testing."""
    return {
        "version": 1,
        "skills": [
            {
                "id": "motion-word-forward",
                "title": "Jump forward by word",
                "category": "motion",
                "teach": "w moves forward by word",
                "key_commands": ["w", "b", "e"],
                "difficulty": 1,
                "challenges": [
                    {
                        "start": ["deploy the staging build"],
                        "par_keys": 2,
                        "hint": "a count in front of w repeats it",
                        "start_cursor": [1, 1],
                        "target": [1, 12],
                        "solution": "2w",
                        "why": "Two word-jumps land on 'staging'.",
                    },
                    {
                        "start": ["restart the failed worker"],
                        "par_keys": 2,
                        "hint": "count then w",
                        "start_cursor": [1, 1],
                        "target": [1, 12],
                        "solution": "2w",
                        "why": "Quick word navigation.",
                    },
                ],
            },
            {
                "id": "operator-delete-line",
                "title": "Delete a line",
                "category": "operator",
                "teach": "dd deletes the current line",
                "key_commands": ["dd", "d2d"],
                "difficulty": 1,
                "challenges": [
                    {
                        "start": ["line one", "line two"],
                        "goal": ["line two"],
                        "par_keys": 2,
                        "hint": "dd deletes one line",
                        "solution": "dd",
                        "why": "Two identical keystrokes act on the line.",
                    }
                ],
            },
        ],
    }


def english_baseline():
    """Verify load_skills(locale='en') returns English without overlay."""
    data = _make_skills_json()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "skills.json"
        p.write_text(json.dumps(data))
        skills = store.load_skills(path=p, locale="en")
        check("en locale returns both skills", len(skills) == 2)
        check("en locale: skill 0 title is English",
              skills[0].title == "Jump forward by word")
        check("en locale: skill 1 title is English",
              skills[1].title == "Delete a line")
        check("en locale: teach is English",
              skills[0].teach == "w moves forward by word")
        check("en locale: hint is English",
              skills[0].challenges[0].hint == "a count in front of w repeats it")
        check("en locale: why is English",
              skills[0].challenges[1].why == "Quick word navigation.")
    # Also test that _load_locale("en") returns None directly
    check("_load_locale('en') returns None",
          store._load_locale("en") is None)


def locale_overlay_applied():
    """Verify locale overlay replaces English fields."""
    data = _make_skills_json()
    locale_data = {
        "locale": "zh-CN",
        "skills": {
            "motion-word-forward": {
                "title": "\u6309\u8bcd\u5411\u524d\u8df3",
                "teach": "w \u5c06\u5149\u6807\u79fb\u52a8\u5230\u4e0b\u4e00\u4e2a\u5355\u8bcd\u7684\u5f00\u5934",
                "key_commands": ["w", "3w", "b", "e"],
                "challenges": [
                    {"hint": "\u7528\u8ba1\u6570\u914d\u5408 w", "why": "\u4e24\u6b21\u8bcd\u8df3"},
                    {"hint": "\u8ba1\u6570\u52a0 w"},
                ],
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        skills_p = Path(tmp) / "skills.json"
        skills_p.write_text(json.dumps(data))
        i18n_dir = Path(tmp) / "i18n"
        i18n_dir.mkdir()
        locale_p = i18n_dir / "zh-CN.json"
        locale_p.write_text(json.dumps(locale_data))

        with mock.patch.object(store, "I18N_DIR", i18n_dir):
            skills = store.load_skills(path=skills_p, locale="zh-CN")
            check("overlay: title translated",
                  skills[0].title == "\u6309\u8bcd\u5411\u524d\u8df3")
            check("overlay: teach translated",
                  skills[0].teach == "w \u5c06\u5149\u6807\u79fb\u52a8\u5230\u4e0b\u4e00\u4e2a\u5355\u8bcd\u7684\u5f00\u5934")
            check("overlay: key_commands translated",
                  skills[0].key_commands == ["w", "3w", "b", "e"])
            check("overlay: challenge[0] hint translated",
                  skills[0].challenges[0].hint == "\u7528\u8ba1\u6570\u914d\u5408 w")
            check("overlay: challenge[0] why translated",
                  skills[0].challenges[0].why == "\u4e24\u6b21\u8bcd\u8df3")
            check("overlay: challenge[1] hint translated",
                  skills[0].challenges[1].hint == "\u8ba1\u6570\u52a0 w")
            # Non-overlaid skill unchanged
            check("overlay: skill 1 title unchanged",
                  skills[1].title == "Delete a line")
            check("overlay: skill 1 teach unchanged",
                  skills[1].teach == "dd deletes the current line")


def locale_partial_overlay():
    """Verify partial overlay only affects specified fields."""
    data = _make_skills_json()
    locale_data = {
        "locale": "zh-CN",
        "skills": {
            "motion-word-forward": {
                "title": "\u6309\u8bcd\u5411\u524d\u8df3",
                # teach omitted -> should stay English
                "challenges": [
                    {"hint": "\u7528\u8ba1\u6570\u914d\u5408 w"}
                    # why omitted -> should stay English
                ]
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        skills_p = Path(tmp) / "skills.json"
        skills_p.write_text(json.dumps(data))
        i18n_dir = Path(tmp) / "i18n"
        i18n_dir.mkdir()
        locale_p = i18n_dir / "zh-CN.json"
        locale_p.write_text(json.dumps(locale_data))

        with mock.patch.object(store, "I18N_DIR", i18n_dir):
            skills = store.load_skills(path=skills_p, locale="zh-CN")
            check("partial: title translated",
                  skills[0].title == "\u6309\u8bcd\u5411\u524d\u8df3")
            check("partial: teach stays English (no overlay)",
                  skills[0].teach == "w moves forward by word")
            check("partial: challenge[0] hint translated",
                  skills[0].challenges[0].hint == "\u7528\u8ba1\u6570\u914d\u5408 w")
            check("partial: challenge[0] why stays English (no overlay)",
                  skills[0].challenges[0].why == "Two word-jumps land on 'staging'.")


def locale_missing_file():
    """Verify nonexistent locale falls back gracefully (no exception)."""
    data = _make_skills_json()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "skills.json"
        p.write_text(json.dumps(data))
        skills = store.load_skills(path=p, locale="nonexistent")
        check("missing locale: no error, both skills loaded",
              len(skills) == 2)
        check("missing locale: title is English",
              skills[0].title == "Jump forward by word")
        check("missing locale: teach is English",
              skills[0].teach == "w moves forward by word")


def locale_unknown_skill():
    """Verify overlay for a non-existent skill_id is silently skipped."""
    data = _make_skills_json()
    locale_data = {
        "locale": "zh-CN",
        "skills": {
            "no-such-skill-id": {
                "title": "\u4e0d\u5b58\u5728\u7684\u6280\u80fd",
                "teach": "\u8fd9\u4e2a\u6280\u80fd\u4e0d\u5b58\u5728",
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        skills_p = Path(tmp) / "skills.json"
        skills_p.write_text(json.dumps(data))
        i18n_dir = Path(tmp) / "i18n"
        i18n_dir.mkdir()
        locale_p = i18n_dir / "zh-CN.json"
        locale_p.write_text(json.dumps(locale_data))

        with mock.patch.object(store, "I18N_DIR", i18n_dir):
            skills = store.load_skills(path=skills_p, locale="zh-CN")
            check("unknown skill: no error, both skills loaded",
                  len(skills) == 2)
            check("unknown skill: first skill title unchanged",
                  skills[0].title == "Jump forward by word")
            check("unknown skill: second skill title unchanged",
                  skills[1].title == "Delete a line")


def locale_challenge_index_mismatch():
    """Verify fewer challenge overlays than challenges is handled gracefully."""
    data = _make_skills_json()
    # motion-word-forward has 2 challenges, overlay only has 1
    locale_data = {
        "locale": "zh-CN",
        "skills": {
            "motion-word-forward": {
                "title": "\u6309\u8bcd\u5411\u524d\u8df3",
                "challenges": [
                    {"hint": "\u7528\u8ba1\u6570\u914d\u5408 w", "why": "\u4e24\u6b21\u8bcd\u8df3\u5b8c\u6210"}
                    # second challenge overlay omitted
                ]
            }
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        skills_p = Path(tmp) / "skills.json"
        skills_p.write_text(json.dumps(data))
        i18n_dir = Path(tmp) / "i18n"
        i18n_dir.mkdir()
        locale_p = i18n_dir / "zh-CN.json"
        locale_p.write_text(json.dumps(locale_data))

        with mock.patch.object(store, "I18N_DIR", i18n_dir):
            skills = store.load_skills(path=skills_p, locale="zh-CN")
            check("index mismatch: no error, both skills loaded",
                  len(skills) == 2)
            check("index mismatch: challenge[0] hint translated",
                  skills[0].challenges[0].hint == "\u7528\u8ba1\u6570\u914d\u5408 w")
            check("index mismatch: challenge[0] why translated",
                  skills[0].challenges[0].why == "\u4e24\u6b21\u8bcd\u8df3\u5b8c\u6210")
            check("index mismatch: challenge[1] hint stays English",
                  skills[0].challenges[1].hint == "count then w")
            check("index mismatch: challenge[1] why stays English",
                  skills[0].challenges[1].why == "Quick word navigation.")


# ---------------------------------------------------------------------------
# Phase 3 — config lang integration
# ---------------------------------------------------------------------------

def config_lang_default():
    """Verify config._default() includes lang and get_lang returns "en"."""
    cfg = config._default()
    check("config default has lang key", "lang" in cfg)
    check("config default lang is 'en'", cfg["lang"] == "en")
    check("get_lang() returns 'en' for empty cfg",
          config.get_lang({}) == "en")
    check("get_lang() returns 'en' for default",
          config.get_lang(cfg) == "en")


def config_lang_get_set():
    """Verify get_lang returns the stored lang value."""
    cfg = config._default()
    cfg["lang"] = "zh-CN"
    check("get_lang returns 'zh-CN' after set",
          config.get_lang(cfg) == "zh-CN")
    cfg["lang"] = "fr"
    check("get_lang returns 'fr'",
          config.get_lang(cfg) == "fr")


def config_lang_old_config_no_key():
    """Verify old configs without 'lang' key fall back gracefully."""
    old_cfg = {"disabled_skills": ["motion-word-forward"], "remaps": []}
    check("old config without lang key defaults to 'en'",
          config.get_lang(old_cfg) == "en")


def main():
    english_baseline()
    locale_overlay_applied()
    locale_partial_overlay()
    locale_missing_file()
    locale_unknown_skill()
    locale_challenge_index_mismatch()
    config_lang_default()
    config_lang_get_set()
    config_lang_old_config_no_key()

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
