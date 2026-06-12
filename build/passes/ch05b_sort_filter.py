"""Sort & filter ranges.

:!{cmd}, :read !{cmd}, and filtering a motion through an external program
(!{motion}, e.g. !Gsort) are environment-dependent (they shell out), so they
are teaching notes rather than drills. Vim's built-in :sort needs no external
program and is fully gradeable.
"""

from build.common import C, S

SKILLS = [
    S("ex-sort", "Sort lines with :sort", "ex_command",
      ":[range]sort orders the lines in a range. Bare :sort sorts the whole file "
      "alphabetically; :sort! reverses it; :sort n sorts by the first number "
      "(numeric, so 10 follows 2); :sort u sorts and removes duplicate lines.",
      [":sort", ":sort!", ":sort n", ":sort u"], 3, [
        C(["ripgrep", "fzf", "bat", "eza", "fd", "tmux", "neovim", "zoxide",
           "htop", "jq"],
          ["bat", "eza", "fd", "fzf", "htop", "jq", "neovim", "ripgrep", "tmux",
           "zoxide"],
          solution=":sort<CR>",
          hint="one command alphabetises the whole list",
          why="Reordering ten lines by hand is a chore — :sort is instant."),
        C(["issue 12", "issue 3", "issue 100", "issue 7", "issue 45", "issue 1",
           "issue 23", "issue 8", "issue 60", "issue 2"],
          ["issue 1", "issue 2", "issue 3", "issue 7", "issue 8", "issue 12",
           "issue 23", "issue 45", "issue 60", "issue 100"],
          solution=":sort n<CR>",
          hint="sort by the numbers, not as text",
          why="As text '100' sorts before '23' — n reads them as numbers."),
        C(["apples", "milk", "bread", "apples", "eggs", "milk", "butter",
           "bread", "apples", "cheese"],
          ["apples", "bread", "butter", "cheese", "eggs", "milk"],
          solution=":sort u<CR>",
          hint="sort and drop the duplicate lines in one pass",
          why=":sort u sorts and removes the repeats in one go."),
      ]),
]
