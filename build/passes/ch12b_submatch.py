"""Submatches, word boundaries, match boundaries."""

from build.common import C, S

SKILLS = [
    S("regex-submatch-backref", "Capture and reuse submatches (\\1)",
      "search_replace",
      "Wrap part of a pattern in () to capture it; reference the captures in the "
      "replacement as \\1, \\2, ... up to \\9 (\\0 is the whole match). This is how "
      "you reorder fields — swap 'First Last' to 'Last, First' in one substitute.",
      [r"\v(...)", r"\1", r"\2", r"\0"], 4, [
        C(["John Smith", "Jane Doe"], ["Smith, John", "Doe, Jane"],
          solution=r":%s/\v(\w+) (\w+)/\2, \1/<CR>",
          hint="capture the two names, then swap them in the replacement",
          why=r"\1 and \2 replay the captured words in any order you like."),
        C(["alpha,1", "beta,2"], ["1=alpha", "2=beta"],
          solution=r":%s/\v(\w+),(\w+)/\2=\1/<CR>",
          hint="capture both CSV fields, rebuild them swapped",
          why="Submatches turn a substitute into a field-reshuffler."),
      ]),

    S("regex-word-boundary", "Match whole words (\\< \\>)", "search_replace",
      "The zero-width items \\< and \\> (or bare < > under \\v) anchor to word "
      "boundaries, so a pattern matches a WHOLE word and not fragments inside "
      "bigger words. Essential when renaming a short identifier that appears as "
      "a substring elsewhere.",
      [r"\<", r"\>", r"\v<x>", "*"], 4, [
        C(["in into inside in"], ["X into inside X"],
          solution=r":%s/\v<in>/X/g<CR>",
          hint="anchor both ends so only the standalone word matches",
          why=r"<in> skips 'into'/'inside'; a bare 'in' would hit them all."),
        C(["id idx grid id"], ["KEY idx grid KEY"],
          solution=r":%s/\v<id>/KEY/g<CR>",
          hint="boundaries keep 'idx' and 'grid' safe",
          why="Whole-word matching prevents clobbering substrings."),
      ]),

    S("regex-match-boundary-zs", "Crop the match with \\zs", "search_replace",
      "\\zs sets where the match really STARTS and \\ze where it ENDS, so you can "
      "require context without consuming it (like a lookbehind/lookahead). Match "
      "'foo bar' but only replace the 'bar' part.",
      [r"\zs", r"\ze", "lookbehind", "lookahead"], 5, [
        C(["Silver Lake and Silver Birch"],
          ["Silver LAKE and Silver Birch"],
          solution=r":%s/Silver \zsLake/LAKE/<CR>",
          hint=r"\zs starts the match after 'Silver ', so only Lake is changed",
          why=r"\zs keeps the prefix as context but out of the replacement."),
      ]),
]
