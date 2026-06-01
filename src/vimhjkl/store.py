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

def load_skills(path: Path | None = None) -> list[Skill]:
    path = path or SKILLS_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    skills = [Skill.from_dict(s) for s in data.get("skills", [])]
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


def default_progress_entry() -> dict:
    return {
        "box": MIN_BOX,
        "seen": 0,
        "passes": 0,
        "fails": 0,
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


def record_result(progress: dict, skill_id: str, passed: bool,
                  efficiency: float) -> dict:
    """Update Leitner box + history for a drill/review outcome."""
    entry = get_entry(progress, skill_id)
    entry["seen"] += 1
    entry["last_seen"] = time.time()
    if passed:
        entry["passes"] += 1
        entry["box"] = min(MAX_BOX, entry["box"] + 1)
        entry["last_result"] = "pass"
    else:
        entry["fails"] += 1
        entry["box"] = max(MIN_BOX, entry["box"] - 1)
        entry["last_result"] = "fail"
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
