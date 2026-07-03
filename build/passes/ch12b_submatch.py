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
        # 'parse' exists as a local def AND as utils.parse — only the qualified
        # uses get renamed.  The prefix is required context, so a bare :%s is
        # wrong and retyping 'utils.' in the replacement is the tax \zs waives.
        C(["from lib import utils", "", "def parse(flags):",
           "    return flags.split()", "", "value = utils.parse(raw)",
           "extra = utils.parse(headers)", "flags = parse(cli_args)",
           "debug = utils.parse(payload)"],
          ["from lib import utils", "", "def parse(flags):",
           "    return flags.split()", "", "value = utils.decode(raw)",
           "extra = utils.decode(headers)", "flags = parse(cli_args)",
           "debug = utils.decode(payload)"],
          solution=r":%s/utils\.\zsparse/decode/<CR>",
          hint=r"require the utils. prefix but start the match after it — "
               r"only the qualified calls change",
          why=r"\zs makes the prefix a requirement without making it part of "
              r"the match, so the replacement stays just 'decode'.",
          why_not=r":%s/parse/decode/ also renames the local def and its call; "
                  r":%s/utils\.parse/utils.decode/ works but retypes the "
                  r"prefix — \zs is the version that doesn't."),
        # \ze is the mirror: 'deploy' changes only when '(prod)' FOLLOWS, and
        # the context must survive unconsumed.
        C(["deploy (prod) at 09:00 after review",
           "freeze all deploys on friday",
           "deploy (staging) whenever you like",
           "deploy (prod) only from the release branch",
           "we deploy (prod) twice a week at most"],
          ["ship (prod) at 09:00 after review",
           "freeze all deploys on friday",
           "deploy (staging) whenever you like",
           "ship (prod) only from the release branch",
           "we ship (prod) twice a week at most"],
          solution=r":%s/deploy\ze (prod)/ship/<CR>",
          hint=r"\ze ends the match before ' (prod)', so the context is "
               r"required but untouched",
          why=r"\ze demands the (prod) tail without consuming it — staging "
              r"and 'deploys' never match.",
          why_not=r":%s/deploy/ship/ hits staging and friday's 'deploys'; "
                  r":%s/deploy (prod)/ship (prod)/ works but retypes the "
                  r"whole tail into the replacement."),
      ]),
]
