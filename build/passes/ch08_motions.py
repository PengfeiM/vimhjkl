"""Motions: navigate inside a file.

Real-vs-display line motions (gj/gk/g0/g$) depend on window width and 'wrap',
so they're noted, not drilled.
"""

from build.common import C, S

SKILLS = [
    S("motion-find-char", "Find by character (f, t, ;)", "motion",
      "f{char} flies the cursor to the next {char} on the line; t{char} stops "
      "just before it. ; repeats the last find, , reverses it. Aim at rare "
      "characters (punctuation, capitals) so you strike in one hop.",
      ["f", "t", ";", ","], 2, [
        C(["find the X spot"], start_cursor=[1, 1], target=[1, 10],
          solution="fX",
          hint="fly straight to a rare character",
          why="A capital X is unique here, so f hits it in one move."),
        C(["a-b-c-d-e"], start_cursor=[1, 1], target=[1, 6],
          solution="f-;;",
          hint="find the first dash, then ; to repeat the find",
          why="; repeats f{char} so you don't respell the search."),
        C(["stop right|here now"], start_cursor=[1, 1], target=[1, 10],
          solution="t|",
          hint="t stops one short of the target",
          why="t{char} lands BEFORE the char — ideal in front of an operator."),
      ]),

    S("operator-to-char", "Operate up to a character (dt, df, ct)", "operator",
      "Character searches shine in Operator-Pending mode. d/c/y followed by "
      "t{char} acts up to (but not including) the char; f{char} includes it. "
      "f,dt. — jump to the comma, then delete the rest of the clause — is a "
      "classic 'finger macro'.",
      ["dt", "df", "ct", "yt"], 3, [
        C(["finish lunch, then nap soon."], ["finish lunch."],
          solution="f,dt.",
          hint="jump to the comma, then delete up to the period",
          why="dt. deletes the clause but leaves the period in place."),
        C(["scores[0].push(x)"], ["scores.push(x)"], start_cursor=[1, 7],
          solution="df]",
          hint="delete the index, bracket and all",
          why="df] includes the bracket; dt] would leave it behind."),
        C(["name: OLD; rest"], ["name: NEW; rest"], start_cursor=[1, 7],
          solution="ct;NEW<Esc>",
          hint="change everything up to the semicolon",
          why="ct; swaps the value and stops cleanly before the ;."),
        C(["git push origin main"], ["git push main"], start_cursor=[1, 10],
          solution="dtm",
          hint="delete the remote, stopping before 'main'",
          why="dt{char} deletes up to a landmark you can see, no counting."),
      ]),

    S("motion-line-anchors", "Jump to line anchors (0, ^, $)", "motion",
      "0 snaps to the very first column, ^ to the first non-blank character, and "
      "$ to the end of the line. These three are far quicker than holding h or l.",
      ["0", "^", "$"], 1, [
        C(["    indented line"], start_cursor=[1, 1], target=[1, 5],
          solution="^",
          hint="land on the first real character, past the indent",
          why="^ skips leading whitespace; 0 would stop at column 1."),
        C(["go to the end"], start_cursor=[1, 1], target=[1, 13],
          solution="$",
          hint="one key to the last character",
          why="$ reaches the line end regardless of its length."),
        C(["return to home"], start_cursor=[1, 8], target=[1, 1],
          solution="0",
          hint="snap back to column one",
          why="0 always hits the hard left edge."),
      ]),

    S("motion-WORD-wise", "Move by WORDs (W, B, E)", "motion",
      "A 'word' breaks on punctuation, but a WORD (capital) is any run of "
      "non-blank characters — so WORD-wise motions skip over dots, slashes and "
      "brackets in one leap. W/B/E mirror w/b/e but on the bigger unit.",
      ["W", "B", "E", "w"], 2, [
        C(["e.g. we're going slow"], start_cursor=[1, 1], target=[1, 6],
          solution="W",
          hint="one WORD jump clears 'e.g.' in a single bound",
          why="w would stop on every dot; W treats 'e.g.' as one WORD."),
        C(["node.js runs fast"], start_cursor=[1, 1], target=[1, 9],
          solution="W",
          hint="the dotted run is a single WORD",
          why="W leaps past 'node.js' that w would crawl through dot by dot."),
      ]),

    S("operator-WORD-change", "Change a WORD / append at word end (cW, ea)",
      "operator",
      "cW changes a whole WORD, punctuation and all — handy for things like "
      "contractions or paths that w-based motions would split. ea ('append at end "
      "of word') drops you into Insert mode right after the current word.",
      ["cW", "ea", "cw", "gea"], 3, [
        C(["e.g. we're going slow"], ["e.g. it's going slow"],
          solution="WcWit's<Esc>",
          hint="jump a WORD, then change the whole WORD",
          why="cW swallows the apostrophe; cw would stop at it."),
        C(["make slow"], ["make slower"],
          solution="eeaer<Esc>",
          hint="hop to the word's end, then append",
          why="ea appends right after a word without hunting for its end."),
      ]),

    S("motion-search-navigate", "Search to navigate (/)", "motion",
      "For distances beyond the current line, search IS a motion. Type / and just "
      "enough characters to be unique, then <CR> — Vim jumps to the first match. "
      "n repeats forward, N backward. It's often the fewest keystrokes to anywhere.",
      ["/", "n", "N", "?"], 2, [
        C(["import os", "import json", "from db import pool"],
          start_cursor=[1, 1], target=[3, 16],
          solution="/pool<CR>",
          hint="search a couple of unique letters to leap there",
          why="/pool is unique, so one short search lands on it."),
        C(["def parse():", "    return None", "def render():"],
          start_cursor=[1, 1], target=[3, 5],
          solution="/render<CR>",
          hint="search the word to fly straight to it",
          why="A search motion crosses lines that f{char} cannot."),
      ]),
]
