"""User PREFERENCES (separate from progress.json player state and skills.json
curriculum).

Three stores, deliberately separate:
  * skills.json    — the curriculum (data, shipped in the package).
  * progress.json  — player MASTERY state (Leitner boxes, history).
  * config.json    — player PREFERENCES (which lessons are off, key mappings).

Preferences are local and never committed (see .gitignore).  Kept apart from
progress so wiping your stats never loses your setup, and vice versa.  Lives next
to progress.json: repo root in a source checkout, the XDG user data dir when
installed; override with ``$VIMHJKL_CONFIG``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import store


def _config_path() -> Path:
    env = os.environ.get("VIMHJKL_CONFIG")
    if env:
        return Path(env)
    # Sit beside progress.json wherever that resolves (checkout root or XDG).
    return store._progress_path().with_name("config.json")


CONFIG_PATH = _config_path()


def _default() -> dict:
    return {
        # Skill ids the player has switched OFF.  Excluded from every scheduling
        # decision (and from the belt/mastery maths) but still listed, greyed, in
        # the curriculum so they can be switched back on.
        "disabled_skills": [],
        # Insert-mode escape aliases, e.g. ["jk", "jj"].  Each becomes an
        # `inoremap <alias> <Esc>` injected ONLY into interactive drills (never the
        # build's par replay).  See grader._INTERACTIVE_SETTINGS / cli.
        "escape_aliases": [],
    }


def load(path: Path | None = None) -> dict:
    path = path or CONFIG_PATH
    if not path.exists():
        return _default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default()
    # Merge over defaults so a config written by an older version still has every
    # key the current code expects.
    cfg = _default()
    if isinstance(data, dict):
        cfg.update({k: data[k] for k in cfg if k in data})
    return cfg


def save(cfg: dict, path: Path | None = None) -> None:
    path = path or CONFIG_PATH
    store._atomic_write(path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# disabled lessons
# ---------------------------------------------------------------------------

def disabled_set(cfg: dict) -> set[str]:
    return set(cfg.get("disabled_skills", []))


def is_disabled(cfg: dict, skill_id: str) -> bool:
    return skill_id in disabled_set(cfg)


def set_disabled(cfg: dict, skill_id: str, disabled: bool) -> None:
    """Switch one skill on/off (mutates ``cfg``; caller persists)."""
    cur = disabled_set(cfg)
    if disabled:
        cur.add(skill_id)
    else:
        cur.discard(skill_id)
    cfg["disabled_skills"] = sorted(cur)


def set_many_disabled(cfg: dict, skill_ids, disabled: bool) -> None:
    """Switch a whole group (e.g. a category) on/off at once."""
    cur = disabled_set(cfg)
    if disabled:
        cur |= set(skill_ids)
    else:
        cur -= set(skill_ids)
    cfg["disabled_skills"] = sorted(cur)


def enabled_skills(skills: list, cfg: dict) -> list:
    """The skills a session should actually schedule: everything not switched off.

    This is the SINGLE filter point — apply it before scheduling AND before the
    belt/mastery maths, so a disabled skill never drags the average down or stalls
    the unlock gate.  The full (unfiltered) list still feeds the curriculum view so
    disabled skills stay visible and re-enableable.
    """
    off = disabled_set(cfg)
    return [s for s in skills if s.id not in off]


# ---------------------------------------------------------------------------
# escape-key aliases (insert-mode)
# ---------------------------------------------------------------------------

# Only short, letter-only aliases are accepted: they are unambiguous to map and
# never collide with a real key sequence a drill needs.  (A digit/punct alias
# could shadow a count or a literal character mid-edit.)
def _valid_alias(alias: str) -> bool:
    return bool(alias) and 1 <= len(alias) <= 3 and alias.isalpha()


def escape_aliases(cfg: dict) -> list[str]:
    """The configured, validated insert-mode escape aliases (de-duplicated)."""
    out: list[str] = []
    for a in cfg.get("escape_aliases", []):
        if _valid_alias(a) and a not in out:
            out.append(a)
    return out


def set_escape_aliases(cfg: dict, aliases: list[str]) -> None:
    cfg["escape_aliases"] = [a for a in aliases if _valid_alias(a)]
