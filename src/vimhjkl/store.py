"""Load/save the curriculum (skills.json) and player progress (progress.json).

Two stores, deliberately separate:
  * content/skills.json   — the curriculum (data).
  * progress.json         — PLAYER state (Leitner boxes, history).  Lives at the
                            project root.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .challenge import Skill


# Resolve paths relative to the project root (two levels up from this file:
# src/vimhjkl/store.py -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_PATH = PROJECT_ROOT / "content" / "skills.json"
PROGRESS_PATH = PROJECT_ROOT / "progress.json"


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
