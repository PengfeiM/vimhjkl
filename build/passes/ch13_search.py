"""Search as an editing tool.

Search mechanics (history, incsearch preview, offsets /pat/e, count) are mostly
about live interaction; the standout editing power-move is gn.
"""

from build.common import C, S

SKILLS = [
    S("search-operate-gn", "Operate on the search match (gn)", "operator",
      "gn selects the next match of the last search (or the one under the "
      "cursor). cgn changes it, dgn deletes it — and because it's a single "
      "change, the dot command repeats it, jumping to the next match for free. "
      "Search once, then cgn<new><Esc> and tap . to roll through the rest.",
      ["cgn", "dgn", ".", "/"], 4, [
        C(["red sky", "red sea", "red rose"],
          ["blue sky", "blue sea", "blue rose"],
          solution="/red<CR>cgnblue<Esc>..",
          hint="search red, change the match with cgn, then dot for the rest",
          why="cgn + dot is the modern find-and-replace-by-hand: no n needed."),
        C(["TODO first", "ok", "TODO second"],
          ["DONE first", "ok", "DONE second"],
          solution="/TODO<CR>cgnDONE<Esc>.",
          hint="cgn skips straight to the next match, so . alone advances",
          why="gn folds the jump into the change — fewer keystrokes than n.."),
      ]),
]
