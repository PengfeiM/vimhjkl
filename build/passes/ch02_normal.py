"""Normal mode: counts and the operator+motion grammar."""

from build.common import C, S

SKILLS = [
    S("count-vs-repeat", "Count, or repeat?", "operator",
      "d2w and 2dw both delete two words; dw. deletes one then repeats. Prefer "
      "dw. when you want fine-grained undo and the freedom to stop early; reach "
      "for a count when you'll continue into Insert mode (c3w) so undo stays one "
      "clean chunk.",
      ["d2w", "2dw", "dw.", "d3w"], 2, [
        C(["the legacy auth module is dead"], ["is dead"],
          solution="d4w",
          hint="delete the four stale words as one undo-chunk",
          why="A count keeps undo a single chunk — handy before more edits."),
        C(["really very urgent ticket"], ["urgent ticket"],
          solution="dw.",
          hint="delete a word, then repeat with the dot",
          why="dw. gives word-at-a-time undo; back out with one u if you overshoot."),
      ]),

    S("case-operators", "Operate on case (gU, gu, g~)", "operator",
      "Case change is an operator, so it follows the operator+motion grammar. "
      "gU makes UPPERCASE, gu makes lowercase, g~ swaps case. Combine with any "
      "motion or text object (gUaw, guap), or double it to act on the line "
      "(gUU, guu, g~~).",
      ["gU", "gu", "g~", "g~~"], 2, [
        C(["http_method = get"], ["http_method = GET"],
          solution="$gUiw",
          hint="HTTP verbs are constants — uppercase the value",
          why="gU is the operator, iw its motion: turn a word into a constant."),
        C(["warning: do not edit below"], ["WARNING: DO NOT EDIT BELOW"],
          solution="gUU",
          hint="double the operator to shout the whole banner line",
          why="A doubled operator (gUU) acts linewise, like dd or >>."),
        C(["the SERVER restarted cleanly"], ["the server restarted cleanly"],
          solution="wguiw",
          hint="tame the one word left in caps-lock",
          why="guiw lowercases just the stray all-caps word, not the line."),
        C(["hELLO tEAM, gOOD mORNING"], ["Hello Team, Good Morning"],
          solution="g~~",
          hint="caps-lock was inverted for the whole line",
          why="g~~ flips every character's case — undo a stuck caps-lock at once."),
      ]),
]
