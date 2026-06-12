"""Registers: delete, yank, put.

System clipboard ("+/"*) and the black-hole register ("_) are environment- or
side-effect-based (no buffer change to grade), so they're noted, not drilled.
"""

from build.common import C, S

SKILLS = [
    S("register-transpose", "Transpose with delete + put (xp, ddp)", "register",
      "Vim calls cut/copy/paste delete/yank/put. p puts the unnamed register "
      "AFTER the cursor (P before). Two famous one-liners fall out of this: xp "
      "swaps two characters, and ddp swaps two lines — delete into the register, "
      "then put it back on the other side.",
      ["p", "P", "xp", "ddp"], 2, [
        C(["hte cat"], ["the cat"],
          solution="xp",
          hint="delete the char, put it back after the next one",
          why="xp transposes the two leading characters in one breath."),
        C(["return result", "compute result"], ["compute result", "return result"],
          solution="ddp",
          hint="delete the line, put it back below",
          why="ddp swaps a line with the one beneath it — fix the wrong order fast."),
      ]),

    S("register-yank-reliable", "Yank survives a delete (\"0)", "register",
      "Every delete (x, d, c) overwrites the unnamed register, so a yank you "
      "meant to paste can get clobbered. The yank register \"0 is set ONLY by y, "
      "so it survives intervening deletes. Grab text with y, then paste it "
      "reliably with \"0p even after deleting something in the way.",
      ["\"0p", "yiw", "viw\"0p", "<C-r>0"], 4, [
        C(["primary = main", "standby = SPARE"],
          ["primary = main", "standby = main"], start_cursor=[1, 11],
          solution='yiwjviw"0p',
          hint="yank the value, drop down, replace the placeholder from \"0",
          why="\"0 still holds 'main' even though viw's delete hit unnamed."),
      ]),

    S("register-named", "Stash text in a named register (\"a)", "register",
      "The 26 named registers \"a-\"z each hold their own text: \"ay{motion} yanks "
      "into a, \"ap puts from it. A lowercase letter overwrites; the uppercase "
      "\"A APPENDS to the same register. Use them to carry several snippets at once "
      "without them stepping on each other.",
      ["\"ayy", "\"ap", "\"Ayy", "\"ad"], 4, [
        C(["boilerplate", "x", "y"], ["boilerplate", "x", "y", "boilerplate"],
          solution='"ayyG"ap',
          hint="yank line 1 into register a, go to the end, put it",
          why="A named register parks text safely until you put it."),
      ]),
]
