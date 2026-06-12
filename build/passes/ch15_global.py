"""Global commands: run an Ex command on every matching line.

:g/{pattern}/[cmd] is, alongside the Dot Formula and macros, one of Vim's power
tools for repetitive work. :print is the default cmd; the real power is pairing
:g with :d, :normal, :t, :m, :s, or :sort.

Buffers here are deliberately several lines with the pattern scattered through
them — that's the whole point of :g, and a 2-line example makes it look pointless.
"""

from build.common import C, S

SKILLS = [
    S("global-delete", "Delete lines by pattern (:g/re/d, :v/re/d)", "ex_command",
      ":g/{pat}/d deletes every line matching a pattern; :v/{pat}/d (a.k.a. "
      ":g!/{pat}/d) deletes every line that does NOT match — i.e. it KEEPS only "
      "the matches. One command filters a whole file.",
      [":g//d", ":v//d", ":g!//d", ":g//"], 4, [
        C(["fetch the payload", "# debug: drop later", "parse the payload",
           "# TODO: handle errors", "store the result", "# note to self",
           "return the result", "# end of hacks"],
          ["fetch the payload", "parse the payload", "store the result",
           "return the result"],
          solution=":g/^#/d<CR>",
          hint="delete every line that starts with #",
          why=":g//d sweeps out all matching lines in a single pass."),
        C(["error: disk full", "info: backup ok", "error: socket closed",
           "debug: retrying", "warn: low memory", "error: timeout", "info: done"],
          ["error: disk full", "error: socket closed", "error: timeout"],
          solution=":v/error/d<CR>",
          hint="delete every line that does NOT contain 'error'",
          why=":v keeps only the matches — an inverse filter over the whole file."),
      ]),

    S("global-normal", "Run a Normal command on matches (:g/re/normal)",
      "ex_command",
      "Combine :g with :normal to fire a Normal-mode edit on every matching line. "
      ":g/{pat}/normal {cmds} is the surgical version of :%normal — it touches "
      "only the lines you care about.",
      [":g//normal", ":g//normal A", ":g//normal I", "."], 5, [
        C(["fn connect()", "  socket.open = true", "fn disconnect()",
           "  socket.open = false", "fn reconnect()", "  retry(3)", "done"],
          ["// fn connect()", "  socket.open = true", "// fn disconnect()",
           "  socket.open = false", "// fn reconnect()", "  retry(3)", "done"],
          solution=":g/fn/normal I// <CR>",
          hint="only the fn lines get the comment prefix",
          why=":g picks the lines, :normal makes the edit — far apart and precise."),
        C(["total = 0", "# running tally", "total = total + tax",
           "# apply discount", "total = total - coupon", "log done"],
          ["total = 0;", "# running tally", "total = total + tax;",
           "# apply discount", "total = total - coupon;", "log done"],
          solution=":g/=/normal A;<CR>",
          hint="append ; only to the assignment lines, skip the prose",
          why=":g/=/ targets the code lines and leaves the comments alone."),
      ]),

    S("global-copy-collect", "Collect matching lines (:g/re/t$)", "ex_command",
      "Pair :g with :t (copy) to gather every matching line at the end of the "
      "file: :g/{pat}/t$ copies each match to the bottom, so you can review all "
      "the TODOs (or headings, or errors) in one place.",
      [":g//t$", ":g//yank A", ":g//m$", ":t$"], 4, [
        C(["TODO: wire up auth", "shipped the login form", "TODO: write the tests",
           "fixed the css", "TODO: delete this hack", "deployed to staging",
           "all green"],
          ["TODO: wire up auth", "shipped the login form", "TODO: write the tests",
           "fixed the css", "TODO: delete this hack", "deployed to staging",
           "all green", "TODO: wire up auth", "TODO: write the tests",
           "TODO: delete this hack"],
          solution=":g/TODO/t$<CR>",
          hint="copy each TODO line to the end of the file",
          why=":g//t$ harvests every match into one spot to scan at a glance."),
        C(["# Introduction", "some prose here", "# Installation", "more prose",
           "# Usage", "final prose", "# Gotchas"],
          ["# Introduction", "some prose here", "# Installation", "more prose",
           "# Usage", "final prose", "# Gotchas", "# Introduction",
           "# Installation", "# Usage", "# Gotchas"],
          solution=":g/^#/t$<CR>",
          hint="copy every heading line to the bottom",
          why="A pattern + :t$ builds a table of contents in one command."),
      ]),

    S("global-substitute", "Substitute only on matching lines (:g/re/s)",
      "ex_command",
      "Nest a :substitute inside :global to transform only the lines that match "
      "an outer pattern: :g/{pat}/s/{a}/{b}/. The first pattern selects the "
      "lines; the substitute reshapes them.",
      [":g//s///", ":g//s/$//", ":v//s///", "&"], 5, [
        C(["user: priya", "admin: root", "user: carol", "guest: anon",
           "user: dave", "service: cron"],
          ["user: priya [member]", "admin: root", "user: carol [member]",
           "guest: anon", "user: dave [member]", "service: cron"],
          solution=":g/user/s/$/ [member]/<CR>",
          hint="on user lines only, append a tag at end-of-line",
          why="The outer :g scopes the substitute to just the user rows."),
        C(["log: boot ok", "err: panic", "log: load config", "warn: slow",
           "log: ready", "err: retry"],
          ["log => boot ok", "err: panic", "log => load config", "warn: slow",
           "log => ready", "err: retry"],
          solution=":g/log/s/:/ =>/<CR>",
          hint="only on log lines, rewrite the first colon",
          why=":g+:s reshapes a subset without touching the err/warn lines."),
      ]),

    S("global-block-range", "Act inside each block (:g with a sub-range)",
      "ex_command",
      "Ex commands under :g can take their OWN range, measured from the matching "
      "line. :g/{/ .+1,/}/-1 sort runs :sort on the lines BETWEEN each { and its "
      "} — alphabetising the body of every block in the file at once.",
      [":g/{/", ".+1,/}/-1", "sort", ":g//normal"], 5, [
        C(["box {", "  z: 1;", "  m: 2;", "  a: 3;", "}"],
          ["box {", "  a: 3;", "  m: 2;", "  z: 1;", "}"],
          solution=r":g/{/.+1,/}/-1 sort<CR>",
          hint="for each {, sort the lines up to the matching }",
          why="A per-match sub-range lets :g reach inside every block."),
        C(["a {", "  cat;", "  ant;", "}", "b {", "  dog;", "  bee;", "}"],
          ["a {", "  ant;", "  cat;", "}", "b {", "  bee;", "  dog;", "}"],
          solution=r":g/{/.+1,/}/-1 sort<CR>",
          hint="the same command sorts the body of EVERY block",
          why="One :g handles arbitrarily many blocks — it scales for free."),
      ]),
]
