"""Shared constructors for authoring curriculum passes.

Keeps each pass module terse and consistent.  `par_keys` is auto-computed from
`solution` during generation, so it is normally omitted here.
"""

from __future__ import annotations


def C(start, goal=None, solution="", hint="", why="",
      start_cursor=None, target=None, par_keys=None):
    d: dict = {"start": list(start), "solution": solution, "hint": hint, "why": why}
    if goal is not None:
        d["goal"] = list(goal)
    if start_cursor is not None:
        d["start_cursor"] = list(start_cursor)
    if target is not None:
        d["target"] = list(target)
    if par_keys is not None:
        d["par_keys"] = par_keys
    return d


def S(id, title, category, teach, key_commands, difficulty, challenges):
    return {
        "id": id,
        "title": title,
        "category": category,
        "teach": teach,
        "key_commands": list(key_commands),
        "difficulty": difficulty,
        "challenges": challenges,
    }
