"""Macros: record a sequence of keystrokes, replay it everywhere.

Buffers here are several lines on purpose — a macro's whole value is replaying one
recorded edit across many lines, which a 2-line example can't show.
"""

from build.common import C, S

SKILLS = [
    S("macro-record-replay", "Record and replay a macro (q, @)", "macro",
      "q{reg} starts recording your keystrokes into a register; q stops. @{reg} "
      "replays them, and a count replays many times (3@a). Golden rule: normalize "
      "first (0 or ^), strike with repeatable motions (f., w), so each replay "
      "lands correctly on the next line.",
      ["qa", "q", "@a", "3@a"], 4, [
        C(["1. wash the car", "2. mow the lawn", "3. paint the fence",
           "4. fix the gate", "5. trim the hedge"],
          ["1) Wash the car", "2) Mow the lawn", "3) Paint the fence",
           "4) Fix the gate", "5) Trim the hedge"],
          solution="qa0f.r)w~jq4@a",
          hint="record the edit on line 1 (end with j), then 4@a",
          why="One recorded edit replays down the whole list."),
        # Six lines, and the edit (lowercase the first WORD) needs a case
        # operator + motion — :s can't say it without \L gymnastics.
        C(["GET /api/users", "POST /api/users", "GET /api/orders",
           "DELETE /api/orders/1", "PUT /api/users/7", "PATCH /api/users/7"],
          ["get /api/users", "post /api/users", "get /api/orders",
           "delete /api/orders/1", "put /api/users/7", "patch /api/users/7"],
          solution="qa0guwjq5@a",
          hint="lowercase the method on line 1 (end with j), then 5@a",
          why="guw + j recorded once turns six edits into one count."),
        # Strip the review column from every row: $daW eats the last WORD and
        # the spaces before it — a motion-shaped edit made for a macro.
        C(["grader.py        413 lines   REVIEWED",
           "engine.py        388 lines   REVIEWED",
           "cli.py           512 lines   REVIEWED",
           "store.py         301 lines   REVIEWED",
           "tui.py           446 lines   REVIEWED",
           "config.py        129 lines   REVIEWED"],
          ["grader.py        413 lines", "engine.py        388 lines",
           "cli.py           512 lines", "store.py         301 lines",
           "tui.py           446 lines", "config.py        129 lines"],
          solution="qa$daWjq5@a",
          hint="$daW removes the last WORD and its padding; record, then 5@a",
          why="The edit is a motion ($, aW), so a macro replays it perfectly."),
      ]),

    S("macro-multistep", "Record a multi-step edit (q)", "macro",
      "A macro shines when one 'unit of work' is several commands. Record the "
      "whole sequence once on the first line — entering and leaving Insert mode is "
      "fine — then replay with a count. Keep motions repeatable (0, A) so each "
      "line gets the identical treatment.",
      ["qa", "@a", "I", "A"], 4, [
        C(["apple", "banana", "cherry", "mango", "peach"],
          ['"apple",', '"banana",', '"cherry",', '"mango",', '"peach",'],
          solution='qaI"<Esc>A",<Esc>jq4@a',
          hint="wrap line 1 in quotes-and-comma, end with j, then 4@a",
          why="One recorded unit (prefix + suffix + advance) replays as a count."),
        C(["buy groceries", "call the dentist", "renew passport", "water plants"],
          ["- [ ] buy groceries", "- [ ] call the dentist",
           "- [ ] renew passport", "- [ ] water plants"],
          solution="qaI- [ ] <Esc>jq3@a",
          hint="prefix a checkbox on line 1, then replay down the to-do list",
          why="Macros turn fiddly multi-key prefixes into one replayable action."),
      ]),

    S("macro-parallel-normal", "Run a macro in parallel (:normal @a)", "macro",
      "Replaying a macro in series (5@a) stops dead if one line makes a motion "
      "fail. Running it in parallel — :[range]normal @a — executes the macro "
      "independently on each line, so a line that aborts is skipped while the "
      "rest still get done. A failing motion (f.) doubles as a per-line guard.",
      [":%normal @a", ":'<,'>normal @a", "qa", "q"], 5, [
        C(["1. draft the intro", "2. outline the plot", "// leave this note alone",
           "3. write the ending"],
          ["1) Draft the intro", "2) Outline the plot", "// leave this note alone",
           "3) Write the ending"],
          solution="qa0f.r)w~q:%normal @a<CR>",
          hint="record without the j, then :%normal @a over every line",
          why="f. fails on the comment, so :%normal skips it instead of stalling."),
        C(["1- buy milk", "2- buy eggs", "done already", "3- buy bread"],
          ["1) Buy milk", "2) Buy eggs", "done already", "3) Buy bread"],
          solution="qa0f-r)w~q:%normal @a<CR>",
          hint="the failing f- guards the 'done already' line and re-runs",
          why="A non-matching line aborts only its own replay — :%normal is safe."),
      ]),
]
