"""Autocompletion (the in-buffer, gradeable parts).

Dictionary/file/omni completion (<C-x><C-k>/<C-f>/<C-o>) depend on external
data or filetype plugins, so they're noted. Keyword (<C-n>) and whole-line
(<C-x><C-l>) completion draw from the buffer itself and are fully gradeable.
"""

from build.common import C, S

SKILLS = [
    S("autocomplete-keyword", "Keyword autocompletion (<C-n>)", "operator",
      "In Insert mode <C-n> completes the partial word before the cursor from "
      "words already in your buffers (<C-p> walks the list backward). Type enough "
      "to be unambiguous, press <C-n>, and Vim finishes a long identifier for "
      "you — no retyping, no typos.",
      ["<C-n>", "<C-p>", "<C-x><C-n>", "<C-y>"], 3, [
        C(["authentication flow", "auth"],
          ["authentication flow", "authentication"],
          solution="jA<C-n><Esc>",
          hint="append to the partial word, then <C-n> to complete it",
          why="<C-n> recalls 'authentication' from the buffer — type it once."),
      ]),

    S("autocomplete-whole-line", "Whole-line completion (<C-x><C-l>)",
      "operator",
      "<C-x><C-l> completes an ENTIRE line that matches what you've typed so far, "
      "pulled from elsewhere in the buffer. Perfect for repeating a boilerplate "
      "line — a guard clause, an import — without copy-paste.",
      ["<C-x><C-l>", "<C-n>", "<C-p>", "<C-y>"], 4, [
        C(["    return self.value", "    ret"],
          ["    return self.value", "    return self.value"],
          solution="jA<C-x><C-l><Esc>",
          hint="start the line, then complete the whole thing",
          why="<C-x><C-l> echoes a matching line verbatim from the buffer."),
      ]),
]
