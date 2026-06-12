"""AUTHORED SOURCE for the vimdojo curriculum (Phase C build loop).

The curriculum is split across build/passes/*.py — one module per chapter,
each exposing a ``SKILLS`` list.  This file auto-discovers them in sorted order
and concatenates their skills, and re-exports the source cursor from build/cursor.py.
`generate.py` renders the result into content/skills.json after machine-verifying
every challenge against real vim.

COPYRIGHT RULE: the source material is a CHECKLIST of which techniques to cover
and in what order — never a source to transcribe.  Every lesson string, example
buffer, and hint here is original, written from my own understanding of the
technique.
"""

from __future__ import annotations

import importlib
import pkgutil

# The source cursor is a local authoring artifact (not distributed); the
# build runs fine without it.
try:
    from build.cursor import SOURCE_FILE, TOTAL_LINES, LAST_LINE_READ, TOPICS_DONE
except ImportError:
    SOURCE_FILE, TOTAL_LINES, LAST_LINE_READ, TOPICS_DONE = "", 0, 0, []

from build import passes


def _collect() -> list[dict]:
    skills: list[dict] = []
    for mod in sorted(m.name for m in pkgutil.iter_modules(passes.__path__)):
        module = importlib.import_module(f"build.passes.{mod}")
        skills.extend(getattr(module, "SKILLS", []))
    return skills


SKILLS: list[dict] = _collect()
