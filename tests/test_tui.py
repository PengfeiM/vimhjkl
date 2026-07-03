"""Unit checks for tui.py's pure rendering helpers (no tty needed).

The raw-mode input paths (read_key/read_token/menu) need a real terminal and
stay manually tested; everything here is the string machinery those screens
are built from — ANSI-safe measuring, truncation, wrapping.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vimhjkl import tui

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31m✗ {name}\033[0m  {detail}")


def main():
    red = tui.RED + "abc" + tui.RESET

    # visible_len ignores ANSI codes; pad/truncate measure what's drawn.
    check("visible_len ignores colour codes", tui.visible_len(red) == 3,
          tui.visible_len(red))
    check("pad_visible pads to visible width",
          tui.visible_len(tui.pad_visible(red, 6)) == 6)
    check("pad_visible never shrinks", tui.pad_visible("abcdef", 3) == "abcdef")

    # truncate_visible: cuts at the visible width, keeps codes intact, and
    # resets colour so a cut coloured string can't bleed into the next cell.
    t = tui.truncate_visible(tui.RED + "abcdef" + tui.RESET, 4)
    check("truncate cuts to visible width", tui.visible_len(t) == 4, t)
    check("truncate resets colour at the cut", t.endswith(tui.RESET), repr(t))
    check("truncate leaves short strings alone",
          tui.truncate_visible("abc", 10) == "abc")
    check("truncate width 0 -> empty", tui.truncate_visible("abc", 0) == "")
    plain = tui.truncate_visible("abcdef", 4)
    check("plain truncate adds no codes", plain == "abcd", repr(plain))

    # wrap_plain: greedy word wrap, no mid-word splits.
    check("wrap_plain wraps at width",
          tui.wrap_plain("aa bb cc dd", 5) == ["aa bb", "cc dd"],
          tui.wrap_plain("aa bb cc dd", 5))
    check("wrap_plain keeps a long word whole",
          tui.wrap_plain("supercalifragilistic", 5) == ["supercalifragilistic"])
    check("wrap_plain empty -> no lines", tui.wrap_plain("", 10) == [])

    # rnu_gutter: relativenumber-style gutter — absolute on the cursor row,
    # distance elsewhere (what makes the menus teach {count}j/{count}k).
    sel = tui.rnu_gutter(4, 4, True)
    off = tui.rnu_gutter(1, 4, False)
    check("gutter shows absolute number on the selected row",
          "5" in sel, repr(sel))
    check("gutter shows distance off the selected row", "3" in off, repr(off))

    # progress_bar: full/empty extremes are well-formed at the given width.
    full = tui.progress_bar(1.0, width=10)
    empty = tui.progress_bar(0.0, width=10)
    check("progress bar full at 1.0",
          tui.visible_len(full) == 10 and "░" not in full, repr(full))
    check("progress bar empty at 0.0",
          tui.visible_len(empty) == 10 and "▓" not in empty, repr(empty))
    check("progress bar clamps out-of-range input",
          tui.visible_len(tui.progress_bar(7.3, width=10)) == 10)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
