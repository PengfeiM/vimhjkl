"""Substitution: :s is one of Vim's most powerful Ex commands."""

from build.common import C, S

SKILLS = [
    S("substitute-flags", "Substitute with flags and range (:s///g)",
      "search_replace",
      ":[range]s/{pat}/{str}/[flags]. By default :s changes the FIRST match on "
      "each line of the range; the g flag changes ALL matches on a line. % is the "
      "whole file, 2,4 a line range. No g, no %: just the first match on the "
      "current line.",
      [":%s///g", ":s//", ":2,4s//", "c"], 3, [
        C(["teh cat saw teh dog and teh bird", "fix teh typos", "teh end"],
          ["the cat saw the dog and the bird", "fix the typos", "the end"],
          solution=":%s/teh/the/g<CR>",
          hint="whole file (%), every match per line (g)",
          why="g is what fixes the 2nd and 3rd 'teh' on a line, not just the first."),
        C(["name, role, team", "marisol, admin, ops", "devin, guest, web"],
          ["name: role, team", "marisol: admin, ops", "devin: guest, web"],
          solution=":%s/,/:/<CR>",
          hint="no g flag — only the FIRST comma on each line becomes a colon",
          why="Default :s is first-per-line; here that turns each row into key: value."),
        C(["keep", "swap", "swap", "keep"], ["keep", "SWAP", "SWAP", "keep"],
          solution=r":2,3s/.*/\U&/<CR>",
          hint="restrict to lines 2-3, uppercase each",
          why="A line range scopes the substitute to exactly those rows."),
      ]),

    S("substitute-whole-match-amp", "Reuse the whole match (&)", "search_replace",
      "In the replacement string, & stands for the entire matched text. It's the "
      "quickest way to WRAP or decorate matches — surround every word with "
      "brackets, quote every number — without retyping what you matched.",
      ["&", r"\0", r"[&]", r"\v\w+"], 4, [
        C(["fast simple free"], ["*fast* *simple* *free*"],
          solution=r":%s/\v\w+/*&*/g<CR>",
          hint="& is the matched word; wrap each in markdown emphasis",
          why="& replays the match, so you decorate without retyping it."),
        C(["sku 100, sku 250"], ['sku "100", sku "250"'],
          solution=r':%s/\v\d+/"&"/g<CR>',
          hint="quote every number with & inside the quotes",
          why="& makes 'wrap each match' a one-liner."),
      ]),

    S("substitute-change-case", "Change case in the replacement (\\U, \\u)",
      "search_replace",
      "Replacement escapes change case: \\u upper-cases the NEXT character, \\l "
      "lower-cases it, while \\U / \\L affect everything until \\E. Combine with & "
      "or submatches to Title-Case words or SHOUT a line.",
      [r"\u", r"\U", r"\l", r"\E"], 4, [
        # Case change riding inside a structural rewrite: gUiw per line can't
        # add the prefix or close the spacing, so the substitute earns its keys.
        C(["timeout = 30", "retries = 5", "log_level = warn",
           "cache_dir = /tmp/vh"],
          ["export TIMEOUT=30", "export RETRIES=5", "export LOG_LEVEL=warn",
           "export CACHE_DIR=/tmp/vh"],
          solution=r":%s/\v^(\w+) \= /export \U\1=/<CR>",
          hint=r"capture the key, \U\1 shouts it, the rewrite adds the rest",
          why=r"\U uppercases the captured name while the same :s reshapes "
              r"the whole line — no Normal-mode case operator can do both."),
        C(["john ronald tolkien"], ["John Ronald Tolkien"],
          solution=r":%s/\v<./\u&/g<CR>",
          hint=r"match each word's first letter, \u capitalises it",
          why=r"\u& Title-Cases by upper-casing just the leading letter."),
      ]),

    S("substitute-confirm", "Eyeball each substitution (c flag)",
      "search_replace",
      "The c flag turns :s into an interactive review: at each match Vim asks "
      "y (yes), n (no), a (all the rest), q (quit), or l (last). It's the safe way "
      "to find-and-replace when some matches are false positives.",
      [":s//gc", "y", "n", "a"], 4, [
        # The whole point of c is FALSE POSITIVES: a blind :%s/cat/bat/g would
        # wreck caterpillar, catnip and cats, so you eyeball each and reject those.
        C(["The cat dozed on the warm mat.", "A caterpillar wobbled past.",
           "The cat ignored the catnip.", "Two cats guard the cat flap."],
          ["The bat dozed on the warm mat.", "A caterpillar wobbled past.",
           "The bat ignored the catnip.", "Two cats guard the bat flap."],
          solution=":%s/cat/bat/gc<CR>ynynny",
          hint="say y to the real cats, n to caterpillar / catnip / cats",
          why="A blind :%s would maul caterpillar & catnip — c lets you skip them."),
        C(["log the request", "the login page loaded", "write to the log file",
           "read my travel blog", "log out cleanly"],
          ["trace the request", "the login page loaded", "write to the trace file",
           "read my travel blog", "trace out cleanly"],
          solution=":%s/log/trace/gc<CR>ynyny",
          hint="rename the standalone 'log', spare login and blog",
          why="c is how you rename a word but spare the ones it's hiding inside."),
      ]),

    S("substitute-expression", "Compute the replacement (\\=)", "search_replace",
      "Prefix the replacement with \\= and the rest is a Vim-script EXPRESSION "
      "whose result becomes the replacement. submatch(0) is the whole match, "
      "submatch(1) the first group. Great for bumping every number or computing "
      "values inline.",
      [r"\=", "submatch(0)", "line('.')", r"\=...+1"], 5, [
        C(["slide 9", "slide 10", "slide 11"], ["slide 10", "slide 11", "slide 12"],
          solution=r":%s/\v\d+/\=submatch(0)+1/<CR>",
          hint=r"\= runs an expression; add 1 to renumber every slide",
          why=r"\=submatch(0)+1 bumps each number in place — instant renumber."),
        C(["box 3", "box 5", "box 8"], ["box 6", "box 10", "box 16"],
          solution=r":%s/\v\d+/\=submatch(0)*2/g<CR>",
          hint=r"double each number with an expression",
          why=r"\= can do any arithmetic on the match, not just +1."),
      ]),

    S("substitute-repeat-global", "Repeat the last substitute (g&)",
      "search_replace",
      "& repeats the last :substitute on the current line (no flags). g& is "
      "smarter: it re-runs the last substitution across the WHOLE file with the "
      "same flags — equivalent to :%s//~/&. Handy after testing a :s on one line.",
      ["g&", "&", ":%s//~/&", "@:"], 4, [
        C(["TODO buy milk", "TODO walk dog", "TODO call mom", "TODO pay rent",
           "TODO water plants"],
          ["DONE buy milk", "DONE walk dog", "DONE call mom", "DONE pay rent",
           "DONE water plants"],
          solution=":s/TODO/DONE/<CR>g&",
          hint="test the :s on line 1, then g& to apply it to the whole list",
          why="g& replays the last :s over every line in two keystrokes — no retyping."),
      ]),
]
