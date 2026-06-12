"""Curation pass for the LLM pool's `why` lines.

Tone = "light spark": mechanic-first, a little zing — but SHORT.  The in-vim goal
pane is ~26 columns, so a why wraps every ~26 chars; keep each ≤ ~2 lines (~52
chars) so it reads as a hint, not a wall of text.

Only the `why` field is touched.  Re-run after editing, then `build.generate`.

Run:  uv run python -m build._fix_why
"""
import json
import re
from pathlib import Path

POOL = Path(__file__).resolve().parents[1] / "content" / "llm_pool.json"


def _strip(sol: str) -> str:
    return sol.replace("<CR>", "").replace("<Esc>", "")


def _where(addr: str) -> str:
    return {"0": "the top", "$": "the end",
            ".": "below the cursor"}.get(addr, f"below line {addr}")


def new_why(sid: str, sol: str) -> str | None:
    """A short (≤ ~52 char) knowledge-based why for `sol`, or None to keep existing."""

    if sid == "autocomplete-keyword":
        return "<C-n> completes the word from ones already in the buffer."

    if sid == "case-operators":
        return "gUU uppercases the whole line in one stroke."

    if sid == "count-vs-repeat":
        if sol.endswith("."):
            return "dw, then . repeats it — each delete its own undo."
        return f"{sol} deletes both words as one change — one u undoes it."

    if sid == "ex-copy-line":
        m = re.match(r":(\d+)t(\S+)", _strip(sol))
        if m:
            return f":{m.group(1)}t{m.group(2)} copies line {m.group(1)} to {_where(m.group(2))}."

    if sid == "ex-move-line":
        m = re.match(r":(\d+)m(\S+)", _strip(sol))
        if m:
            return f":{m.group(1)}m{m.group(2)} moves line {m.group(1)} to {_where(m.group(2))}."

    if sid == "ex-normal-range":
        rng = re.match(r":(\S*)normal", _strip(sol))
        scope = rng.group(1) if rng and rng.group(1) else "%"
        if scope in ("", "%"):
            return ":%normal runs the same keys on every line."
        return f":{scope}normal runs the keys on just that range."

    if sid == "ex-sort":
        s = _strip(sol)
        if s == ":sort!":
            return ":sort! orders the lines in reverse."
        flags = s.split("sort", 1)[1]
        if "n" in flags:
            return ":sort n sorts by number (9 before 80)."
        if "u" in flags:
            return ":sort u sorts and drops duplicates."
        return ":sort orders the lines alphabetically."

    if sid == "global-block-range":
        return "Sorts the lines inside each { } block, braces untouched."

    if sid == "global-copy-collect":
        return ":g/pat/t$ copies every matching line to the end."

    if sid == "global-delete":
        if _strip(sol).startswith(":v"):
            return ":v/pat/d deletes every line that does NOT match."
        return ":g/pat/d deletes every line that matches."

    if sid == "global-normal":
        return ":g/pat/normal runs the keys on each matching line."

    if sid == "global-substitute":
        return ":g/pat/s/// substitutes only on matching lines."

    if sid == "increment-number":
        m = re.match(r"(\d*)<C-([ax])>", sol)
        if m:
            n = m.group(1) or "1"
            verb = "adds" if m.group(2) == "a" else "subtracts"
            prep = "to" if m.group(2) == "a" else "from"
            return f"{sol} {verb} {n} {prep} the number under the cursor."

    if sid == "insert-expression-calc":
        return "<C-r>= inserts the result of a sum, mid-insert."

    if sid == "marks-set-and-snap":
        if "``" in sol:
            return "`` jumps back to before the last jump."
        if "''" in sol:
            return "'' returns to the line you jumped from."
        m = re.match(r"m([a-z])", sol)
        if m:
            return f"m{m.group(1)} marks the spot; `{m.group(1)} jumps right back."

    if sid == "motion-line-anchors":
        return {
            "^": "^ lands on the first non-blank character.",
            "$": "$ jumps to the end of the line.",
            "0": "0 jumps to the very first column.",
            "G$": "G to the last line, $ to its end.",
            "G0": "G to the last line, 0 to column one.",
            "2G0": "2G to line 2, 0 to column one.",
            "3G0": "3G to line 3, 0 to column one.",
            "2G$": "2G to line 2, $ to its end.",
            "j^": "j down a line, ^ to its first non-blank.",
        }.get(sol)

    if sid == "motion-match-pair":
        return "% jumps to the matching bracket."

    if sid == "motion-word-forward":
        m = re.match(r"(\d*)w$", sol)
        if m:
            return (f"{sol} moves forward {m.group(1)} words." if m.group(1)
                    else "w moves to the start of the next word.")

    if sid == "operator-delete-line":
        if sol.startswith("2j"):
            return "2j down two lines, dd deletes it."
        if sol.startswith("jj"):
            return "jj down two lines, dd deletes it."
        return "j down to the line, dd deletes it."

    if sid == "operator-search-motion":
        return "d/pat deletes up to the next match of the search."

    if sid == "register-transpose":
        return "dd cuts the line, p puts it back below — a swap."

    if sid == "regex-case-toggle":
        return "\\c makes the pattern case-insensitive."

    if sid == "regex-match-boundary-zs":
        return "\\zs starts the match later, so only the tail changes."

    if sid == "regex-submatch-backref":
        return "\\1 and \\2 replay the () groups in any order."

    if sid == "regex-word-boundary":
        return "\\v< > match whole words, skipping longer ones."

    if sid == "search-operate-gn":
        return "cgn changes the next match; . repeats it down the file."

    if sid == "search-word-under-cursor":
        return "* jumps to the next time this word appears."

    if sid == "substitute-change-case":
        if "\\U&" in sol:
            return "\\U& uppercases the whole match."
        if "\\l&" in sol:
            return "\\l& lowercases each match's first letter."
        return "\\u& capitalises each match's first letter."

    if sid == "substitute-char-dot":
        return "s swaps the char; ; finds the next, . repeats it."

    if sid == "substitute-confirm":
        return "The c flag asks y/n at each match."

    if sid == "substitute-expression":
        return "\\= computes each replacement; submatch(0) is the match."

    if sid == "substitute-repeat-global":
        return "g& repeats the last :s on every line."

    if sid == "textobj-change-in-quotes":
        q = "single" if "ci'" in sol else "double"
        verb = "ci'" if "ci'" in sol else "ci\""
        return f"{verb} changes the text inside the {q} quotes."

    if sid == "visual-block-insert":
        return "<C-v>, then I types the prefix onto every line."

    return None


# Skills whose pooled HINTS ran long / story-flavored — replace with one short,
# pane-fitting nudge per skill (the why-tone pass only touched `why`).
HINT_BY_SKILL = {
    "global-block-range": "sort each braced block's interior",
    "global-copy-collect": "copy all matching lines to the end",
    "global-substitute": "run :s only on matching lines",
    "marks-set-and-snap": "mark the spot, wander, then jump back",
    "motion-word-forward": "w to the next word; a count skips several",
    "regex-case-toggle": "add \\c so the pattern ignores case",
    "regex-submatch-backref": "capture with (), replay with \\1 \\2",
    "regex-word-boundary": "anchor with \\v< > to whole words",
    "register-named": "stash with \"a, drop it with \"ap",
    "substitute-change-case": "\\u& / \\U& change case in the replacement",
    "substitute-repeat-global": "do :s on one line, then g& everywhere",
    "visual-prefer-operator": "use the operator so . can repeat it",
}


# Short touch-ups for flourish lines in otherwise-fine skills.
SPOT_FIXES = {
    ("motion-search-navigate", "/Unicorn<CR>"):
        "/Unicorn jumps to the next 'Unicorn' line.",
    ("motion-search-navigate", "/Swordfish<CR>"):
        "/Swordfish jumps to the next 'Swordfish' line.",
    ("visual-prefer-operator", "jgUiwj.j."):
        "gUiw uppercases the word; j. repeats it down the lines.",
}


def main() -> int:
    data = json.loads(POOL.read_text(encoding="utf-8"))
    pool = data["pool"]
    changed = 0
    for sid, insts in pool.items():
        for c in insts:
            sol = c.get("solution", "")
            spot = SPOT_FIXES.get((sid, sol))
            nw = spot if spot is not None else new_why(sid, sol)
            if nw is not None and c.get("why", "") != nw:
                c["why"] = nw
                changed += 1
            hint = HINT_BY_SKILL.get(sid)
            if hint is not None and c.get("hint", "") != hint:
                c["hint"] = hint
                changed += 1
    POOL.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"rewrote {changed} why/hint lines in {POOL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
