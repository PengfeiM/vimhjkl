"""The dot command and the Dot Formula."""

from build.common import C, S

SKILLS = [
    S("dot-command-repeat", "Repeat a change with the dot command", "operator",
      "The dot command (.) replays your last change — anything from entering "
      "Insert mode and typing, to a delete. The Dot Formula is the ideal: make "
      "the first change so it is repeatable, then it takes one keystroke to MOVE "
      "(j) and one to EXECUTE (.). Append with A so the cursor's column never "
      "matters.",
      ["A", ".", "j.", "u"], 2, [
        C(["margin = 0", "padding = 8", "radius = 4", "border = 1", "shadow = 2"],
          ["margin = 0;", "padding = 8;", "radius = 4;", "border = 1;", "shadow = 2;"],
          solution="A;<Esc>j.j.j.j.",
          hint="A; on the first line, then j. all the way down",
          why="A appends at the line end from anywhere, so . repeats cleanly down the block."),
        C(["validate()", "transform()", "persist()", "notify()", "cleanup()"],
          ["// validate()", "// transform()", "// persist()", "// notify()",
           "// cleanup()"],
          solution="I// <Esc>j.j.j.j.",
          hint="comment the first call, then j. ripples it through the rest",
          why="I// is a repeatable change; one move + one execute comments each line."),
        C(["DROP TABLE users", "DROP TABLE orders", "DROP TABLE carts"],
          ["-- DROP TABLE users", "-- DROP TABLE orders", "-- DROP TABLE carts"],
          solution="I-- <Esc>j.j.",
          hint="I-- to comment out the first scary line, then j. for the rest",
          why="Make the first change repeatable and the dot does the rest for free."),
      ]),

    S("insert-entry-points", "Enter Insert mode in the right place", "operator",
      "Don't waste motions getting to where you want to type. A appends at end "
      "of line, I inserts before the first non-blank, o opens a line below, O "
      "opens above. Each compounds a motion and a mode-switch into one key, and "
      "each is dot-repeatable.",
      ["A", "I", "o", "O"], 1, [
        C(["total = 5"], ["total = 5;"], solution="A;<Esc>",
          hint="append at end of line, wherever the cursor is",
          why="A = $a: jump to the end and append in one key."),
        C(["the headline"], ["# the headline"], solution="I# <Esc>",
          hint="insert before the first character",
          why="I = ^i: insert at the start without pressing 0 first."),
        C(["first"], ["first", "second"], solution="osecond<Esc>",
          hint="open a new line below and type",
          why="o opens below and enters Insert mode in one stroke."),
        C(["second"], ["first", "second"], solution="Ofirst<Esc>",
          hint="open a new line above",
          why="O opens above — no need to go up then o."),
      ]),

    S("change-to-eol-C", "Change to end of line (C)", "operator",
      "C deletes from the cursor to the end of the line and drops you into Insert "
      "mode — it is shorthand for c$. Land on the first character you want to "
      "replace, hit C, and retype the tail.",
      ["C", "c$", "D", "d$"], 2, [
        C(["color = OLD"], ["color = NEW"], start_cursor=[1, 9],
          solution="CNEW<Esc>",
          hint="from the cursor, blow away the rest of the line",
          why="C clears to end-of-line and starts Insert in one move."),
        C(["url = http://stale"], ["url = http://fresh.io"], start_cursor=[1, 14],
          solution="Cfresh.io<Esc>",
          hint="C eats to EOL; type the replacement",
          why="One key replaces everything from the cursor onward."),
      ]),

    S("substitute-char-dot", "One back, three forward (s + dot)", "operator",
      "s deletes the character under the cursor and enters Insert mode (it is "
      "cl). Combined with f{char} to find the target and ; to repeat that find, "
      "you get a fully repeatable edit: f to land, s to swap, then ;. to march "
      "through the rest.",
      ["s", "f", ";", "."], 3, [
        C(["1+2+3+4"], ["1 + 2 + 3 + 4"],
          solution="f+s + <Esc>;.;.",
          hint="find a +, substitute it with ' + ', then ;. repeats",
          why="Making BOTH the find (;) and the change (.) repeatable wins."),
        C(["mon|tue|wed"], ["mon / tue / wed"],
          solution="f|s / <Esc>;.",
          hint="f| to the bar, s to ' / ', ;. for the rest",
          why="The Dot Formula again: one find-repeat, one change-repeat."),
      ]),

    S("compose-delete-word", "Compose a repeatable word delete (daw)", "operator",
      "There is more than one way to delete a word; pick the repeatable one. db "
      "then x leaves you unable to repeat. daw ('delete a word') removes the word "
      "AND an adjacent space as a single, dot-repeatable change.",
      ["daw", "diw", "db", "."], 2, [
        C(["close the stale connection"], ["close the connection"],
          start_cursor=[1, 11], solution="daw",
          hint="delete A word — it takes the trailing/leading space too",
          why="daw is one tidy change you can repeat; db then x is not."),
        C(["drop the redundant flag now"], ["drop the flag now"],
          solution="2wdaw",
          hint="hop to the word, then daw",
          why="aw grabs the word plus a space so no double space is left."),
      ]),

    S("search-word-under-cursor", "Search the word under the cursor (*)", "motion",
      "* searches for the whole word under the cursor and jumps to its next "
      "occurrence — no typing the word out. n then repeats the search forward, N "
      "backward. It pairs beautifully with a repeatable change.",
      ["*", "#", "n", "N"], 2, [
        C(["the budget is tight", "trim the budget now"], start_cursor=[1, 5],
          target=[2, 10], solution="*",
          hint="one key searches for the word you're sitting on",
          why="* spares you from typing /budget — just point and jump."),
        C(["total here", "skip", "use total now"], start_cursor=[1, 1],
          target=[3, 5], solution="*",
          hint="* finds the next 'total' for you",
          why="Point-and-search beats spelling the word into /."),
      ]),
]
