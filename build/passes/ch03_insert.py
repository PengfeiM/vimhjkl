"""Insert mode: paste a register & calculate without leaving insert.

Pure insert-mode correction chords (<C-w>, <C-u>, <C-h>, insert-normal <C-o>)
are muscle-memory aids whose optimal-par form wouldn't use them, so they are
teaching notes rather than graded drills.
"""

from build.common import C, S

SKILLS = [
    S("insert-paste-register", "Paste a register without leaving Insert mode",
      "register",
      "Mid-flow in Insert mode you can paste a register with <C-r>{reg} — no trip "
      "back to Normal mode. <C-r>0 pastes the yank register (what you last "
      "y-anked, untouched by deletes), which is perfect for echoing text you "
      "already grabbed.",
      ["<C-r>0", "<C-r>\"", "y$", "yiw"], 3, [
        C(["Bright Harbor", "Visit "], ["Bright Harbor", "Visit Bright Harbor"],
          solution="y$jA<C-r>0<Esc>",
          hint="yank the title, drop to line 2, append, then <C-r>0",
          why="<C-r>0 replays the yank register straight into Insert mode."),
        C(["status: ACTIVE", "flag = "], ["status: ACTIVE", "flag = ACTIVE"],
          solution="$yiwjA<C-r>0<Esc>",
          hint="yank the word, then paste it into the next line from Insert",
          why="Grab once with yiw, echo it anywhere with <C-r>0."),
      ]),

    S("insert-expression-calc", "Calculate in place (<C-r>=)", "register",
      "The expression register, reached with <C-r>= from Insert mode, evaluates "
      "any Vim expression and inserts the result. It turns the editor into a "
      "back-of-the-envelope calculator without breaking your flow.",
      ["<C-r>=", "A", "<CR>"], 3, [
        C(["answer: "], ["answer: 42"],
          solution="A<C-r>=6*7<CR><Esc>",
          hint="append, open the expression register, type the sum",
          why="<C-r>= evaluates 6*7 and drops 42 right where you're typing."),
        C(["items x price = "], ["items x price = 1450"],
          solution="A<C-r>=29*50<CR><Esc>",
          hint="let Vim do the arithmetic for you",
          why="No mental math: <C-r>= computes and inserts the total."),
      ]),
]
