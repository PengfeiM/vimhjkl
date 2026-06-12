"""Counts do arithmetic: <C-a> / <C-x>."""

from build.common import C, S

SKILLS = [
    S("increment-number", "Increment numbers (<C-a>, <C-x>)", "operator",
      "<C-a> adds to the number at or after the cursor; <C-x> subtracts. With no "
      "count they step by one, but a count adds that amount: 180<C-x> subtracts "
      "180. If the cursor isn't on a digit, Vim jumps forward to the next one on "
      "the line — so you rarely need to aim first.",
      ["<C-a>", "<C-x>", "10<C-a>", "180<C-x>"], 2, [
        C(["count = 41"], ["count = 42"],
          solution="<C-a>",
          hint="bump the number — Vim finds it for you",
          why="<C-a> adds 1 to the next number without any cursor aiming."),
        C(["version 7"], ["version 10"],
          solution="3<C-a>",
          hint="a count adds that much",
          why="3<C-a> adds three in one stroke — repeatable in a macro."),
        C(["margin: 0px"], ["margin: -180px"],
          solution="180<C-x>",
          hint="subtract with a count; the cursor jumps to the digit",
          why="180<C-x> reaches the 0 and subtracts 180 — same keys every line."),
      ]),
]
