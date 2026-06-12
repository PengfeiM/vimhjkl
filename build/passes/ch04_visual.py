"""Visual mode: prefer operators; Visual-Block columns."""

from build.common import C, S

SKILLS = [
    S("visual-prefer-operator", "Prefer operators to Visual commands", "operator",
      "Visual mode is intuitive but it doesn't play well with the dot command: a "
      "repeated Visual change reuses the SAME amount of text, not the same "
      "structure. For repetitive edits, use a Normal-mode operator instead — "
      "gUit (an operator + a text object) repeats perfectly with j.",
      ["gUit", "j.", "vit", "gU"], 3, [
        C(["<li>apples</li>", "<li>oranges</li>", "<li>pears</li>"],
          ["<li>APPLES</li>", "<li>ORANGES</li>", "<li>PEARS</li>"],
          solution="gUitj.j.",
          hint="uppercase inside the tag, then ripple with j.",
          why="gUit is operator+motion, so . repeats it on each tag's real width."),
        C(["<b>cat</b>", "<b>hippopotamus</b>"],
          ["<b>CAT</b>", "<b>HIPPOPOTAMUS</b>"],
          solution="gUitj.",
          hint="the dot respects each tag's own length",
          why="vitU would reuse a 3-char width and break on the long word."),
      ]),

    S("visual-block-insert", "Edit columns with Visual-Block mode", "operator",
      "<C-v> selects a rectangular (or ragged) block across lines. I inserts before "
      "the block on every line, A appends after it, and with $ the block traces the "
      "ragged right edge so A appends at each line's own end. Type on the top line; "
      "the change propagates to the rest on <Esc>.",
      ["<C-v>", "I", "A", "$"], 3, [
        C(["var a = 1", "var bb = 22", "var ccc = 333"],
          ["var a = 1;", "var bb = 22;", "var ccc = 333;"],
          solution="<C-v>jj$A;<Esc>",
          hint="block, $ for the ragged ends, then A to append",
          why="$ frees the block from a rectangle so A hits each true line end."),
      ]),
]
