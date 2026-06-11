"""Load/save the curriculum (skills.json) and player progress (progress.json).

Two stores, deliberately separate:
  * skills.json    — the curriculum (data), bundled inside the package at
                     src/vimhjkl/data/skills.json so installed wheels are
                     self-contained.
  * progress.json  — PLAYER state (Leitner boxes, history).  Repo root in a
                     source checkout, XDG user data dir when installed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .challenge import Skill


# The curriculum ships INSIDE the package (src/vimhjkl/data/skills.json) so an
# installed wheel is self-contained.  A __file__-relative path resolves correctly
# both in a source checkout and in site-packages (wheels install as plain files).
_PKG_DIR = Path(__file__).resolve().parent
SKILLS_PATH = _PKG_DIR / "data" / "skills.json"
I18N_DIR = _PKG_DIR / "data" / "i18n"

# PROJECT_ROOT and content/ exist only in a source checkout — the build writes its
# cursor + LLM pools into content/.  Both are absent in an installed package.
PROJECT_ROOT = _PKG_DIR.parents[1]
CONTENT_DIR = PROJECT_ROOT / "content"


def _is_source_checkout() -> bool:
    """True when running from the repo (not an installed wheel)."""
    return (PROJECT_ROOT / "pyproject.toml").exists()


def _progress_path() -> Path:
    """Player state must live somewhere writable.  In a source checkout keep the
    historical repo-root location; installed, use the XDG user data dir so we
    never try to write inside read-only site-packages."""
    env = os.environ.get("VIMHJKL_PROGRESS")
    if env:
        return Path(env)
    if _is_source_checkout():
        return PROJECT_ROOT / "progress.json"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "vimhjkl" / "progress.json"


PROGRESS_PATH = _progress_path()


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------

def _load_locale(locale: str) -> dict | None:
    """Load a locale overlay file from data/i18n/{locale}.json.
    Returns None if the file doesn't exist (graceful fallback to English)."""
    if locale == "en":
        return None
    path = I18N_DIR / f"{locale}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_overlay(skills: list[Skill], overlay: dict) -> None:
    """Overlay translated fields from a locale file onto Skill/Challenge objects.

    - Iterates skills by skill.id matching overlay["skills"] keys
    - Only overlays fields that exist in the overlay entry
    - Challenges are matched by array index (challenges[i] <-> overlay.challenges[i])
    - Missing skill entries or challenge entries are silently skipped (fallback to English)
    - The overlay modifies objects in-place; no return value needed
    """
    locale_skills = overlay.get("skills", {})
    for skill in skills:
        if skill.id not in locale_skills:
            continue
        entry = locale_skills[skill.id]
        if "title" in entry:
            skill.title = entry["title"]
        if "teach" in entry:
            skill.teach = entry["teach"]
        if "key_commands" in entry:
            skill.key_commands = entry["key_commands"]
        if "challenges" in entry and skill.challenges:
            for i, chal_overlay in enumerate(entry["challenges"]):
                if i < len(skill.challenges):
                    if "hint" in chal_overlay:
                        skill.challenges[i].hint = chal_overlay["hint"]
                    if "why" in chal_overlay:
                        skill.challenges[i].why = chal_overlay["why"]


def load_skills(path: Path | None = None, locale: str = "en") -> list[Skill]:
    path = path or SKILLS_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    skills = [Skill.from_dict(s) for s in data.get("skills", [])]
    overlay = _load_locale(locale)
    if overlay:
        _apply_overlay(skills, overlay)
    return skills


def save_skills(skills: list[Skill], path: Path | None = None) -> None:
    path = path or SKILLS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "skills": [s.to_dict() for s in skills]}
    _atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Player progress  (Leitner spaced repetition, boxes 1..5)
# ---------------------------------------------------------------------------

MIN_BOX = 1
MAX_BOX = 5

# A drill is graded by EFFICIENCY, not just pass/fail, because this is a fluency
# trainer — being fast/idiomatic is the goal, not bare recall:
#   correct & >= GREAT_EFF  -> "great": promote + earn a longer rest (ease up)
#   correct & >= PROMOTE_EFF-> "good":  promote a box
#   correct &  < PROMOTE_EFF-> "slow":  hold the box, resurface sooner (ease down)
#   not correct             -> "miss":  demote (with one grace at the top box)
PROMOTE_EFF = 0.5
GREAT_EFF = 0.95
# `ease` is a lightweight per-skill interval multiplier (a mini stability factor):
# fluent solves stretch the next rest, slow ones pull it in, a miss resets it.
_EASE_STEP = 1.3            # great solve multiplies ease by this …
_EASE_DECAY = 0.7          # … a slow one multiplies by this
_EASE_MIN, _EASE_MAX = 0.5, 2.5


def default_progress_entry() -> dict:
    return {
        "box": MIN_BOX,
        "seen": 0,
        "passes": 0,
        "fails": 0,
        "ease": 1.0,             # interval multiplier (fluency); 1.0 == neutral
        "last_seen": 0.0,        # epoch seconds; 0 == never
        "last_result": None,     # "pass" | "fail" | None
        "best_efficiency": 0.0,
    }


def load_progress(path: Path | None = None) -> dict:
    path = path or PROGRESS_PATH
    if not path.exists():
        return {"skills": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_progress(progress: dict, path: Path | None = None) -> None:
    path = path or PROGRESS_PATH
    _atomic_write(path, json.dumps(progress, indent=2, ensure_ascii=False) + "\n")


def get_entry(progress: dict, skill_id: str) -> dict:
    skills = progress.setdefault("skills", {})
    if skill_id not in skills:
        skills[skill_id] = default_progress_entry()
    return skills[skill_id]


def record_result(progress: dict, skill_id: str, correct: bool,
                  efficiency: float) -> dict:
    """Update the Leitner box + history for a drill/review outcome, graded by how
    FLUENT the solve was (see the PROMOTE_EFF/GREAT_EFF notes above), not merely
    whether it was correct.  Slow-but-correct holds the box (and shortens the next
    rest) instead of demoting; a fast solve earns a longer rest; a single miss at
    the top box is forgiven (a hard-won skill shouldn't fall to one slip)."""
    entry = get_entry(progress, skill_id)
    entry["seen"] += 1
    entry["last_seen"] = time.time()
    ease = entry.get("ease", 1.0)
    if not correct:
        entry["fails"] += 1
        # Soften demotion: the first miss at the top box keeps it (a slip isn't
        # forgetting); only a SECOND consecutive miss demotes.
        grace = entry["box"] >= MAX_BOX and entry.get("last_result") != "fail"
        if not grace:
            entry["box"] = max(MIN_BOX, entry["box"] - 1)
        entry["last_result"] = "fail"
        entry["ease"] = 1.0
    else:
        entry["passes"] += 1
        entry["last_result"] = "pass"
        if efficiency >= GREAT_EFF:                  # great: promote + rest longer
            entry["box"] = min(MAX_BOX, entry["box"] + 1)
            entry["ease"] = min(_EASE_MAX, ease * _EASE_STEP)
        elif efficiency >= PROMOTE_EFF:              # good: promote
            entry["box"] = min(MAX_BOX, entry["box"] + 1)
        else:                                        # slow: hold box, rest sooner
            entry["ease"] = max(_EASE_MIN, ease * _EASE_DECAY)
    entry["best_efficiency"] = max(entry.get("best_efficiency", 0.0), efficiency)
    return entry


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
