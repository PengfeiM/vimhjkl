"""Command-line mode: Ex commands strike far and wide.

Quality note: :t and :m only beat yy/dd+p when there is DISTANCE between the
source line, the destination, and the cursor — every buffer here keeps the
three apart so the Ex form is the shortest correct path, not just one option.
"""

from build.common import C, S

SKILLS = [
    S("ex-normal-range", "Run Normal commands across a range (:normal)",
      "ex_command",
      ":[range]normal {cmds} runs any Normal-mode sequence on every line in the "
      "range — the fastest way to make the same edit on many lines without a "
      "macro. Pair it with the Dot Formula's repeatable changes (A;, I//) over a "
      "whole file (%) or a line range (2,5).",
      [":%normal", ":'<,'>normal", ":normal", "."], 4, [
        C(["let total = 0", "let rate = 0.05", "let tax = total * rate",
           "let net = total - tax", "print(net)", "return net"],
          ["let total = 0;", "let rate = 0.05;", "let tax = total * rate;",
           "let net = total - tax;", "print(net);", "return net;"],
          solution=":%normal A;<CR>",
          hint="append ; to every line in one command",
          why="Six lines means six A;j by hand — :%normal A; does the lot at once."),
        C(["import sys", "def deploy():", "    check_env()", "    push_build()",
           "    notify_team()", "    return True", "deploy()"],
          ["import sys", "def deploy():", "    # check_env()", "    # push_build()",
           "    # notify_team()", "    # return True", "deploy()"],
          solution=":3,6normal I# <CR>",
          hint="comment only the function body — lines 3 to 6",
          why="A line range hits exactly the body and spares the def and the call."),
        # Eight lines of data, and the edit (wrap in quotes, add comma) is two
        # inserts — too many lines for hand-repeats, no regex needed for :s.
        C(["mirrors = [", "ams.cdn.example", "fra.cdn.example", "lhr.cdn.example",
           "nyc.cdn.example", "sfo.cdn.example", "syd.cdn.example", "]"],
          ["mirrors = [", "  'ams.cdn.example',", "  'fra.cdn.example',",
           "  'lhr.cdn.example',", "  'nyc.cdn.example',", "  'sfo.cdn.example',",
           "  'syd.cdn.example',", "]"],
          solution=":2,7normal I  '<CR>:2,7normal A',<CR>",
          hint="two :normal passes over the host lines: prefix, then suffix",
          why="Quoting six list entries by hand is twelve inserts — two ranged "
              ":normal commands do it in two."),
      ]),

    S("ex-copy-line", "Duplicate lines with :t (copy)", "ex_command",
      ":[range]t{address} copies the range to just below {address} (think 'copy "
      "to'). The win is distance: the source line, the destination, and your "
      "cursor can be three different places — :5t12 touches none of them. :t$ "
      "sends a copy to the end, :t0 to the top, :t. to right here.",
      [":t", ":copy", ":t.", ":t$"], 3, [
        # Source at line 1, destination after line 8, cursor parked mid-file:
        # gg yy 8G p is four moves and loses your place — :1t8 is one command.
        C(["/* ================================ */", "/* Buttons */",
           ".btn { padding: 8px; }", ".btn:hover { background: #eee; }",
           ".btn:active { transform: scale(.98); }", "",
           "/* Cards (needs the banner line above) */",
           ".card { border: 1px solid #ddd; }", ".card h2 { margin-top: 0; }"],
          ["/* ================================ */", "/* Buttons */",
           ".btn { padding: 8px; }", ".btn:hover { background: #eee; }",
           ".btn:active { transform: scale(.98); }", "",
           "/* ================================ */",
           "/* Cards (needs the banner line above) */",
           ".card { border: 1px solid #ddd; }", ".card h2 { margin-top: 0; }"],
          start_cursor=[4, 1],
          solution=":1t6<CR>",
          hint="copy the banner (line 1) to below line 6 — without going to either",
          why="Source, destination and cursor are three different places — "
              ":1t6 visits none of them."),
        # The template row lives near the top; the next entry goes at the bottom
        # of a file you're already at the top of editing.
        C(["# deploy targets", "[target.staging]", "host = 'stage.internal'",
           "port = 22", "", "[target.prod]", "host = 'prod.internal'"],
          ["# deploy targets", "[target.staging]", "host = 'stage.internal'",
           "port = 22", "", "[target.prod]", "host = 'prod.internal'",
           "port = 22"],
          start_cursor=[1, 1],
          solution=":4t$<CR>",
          hint="the prod block needs its port line — copy line 4 to the end",
          why=":4t$ duplicates a distant line to the file's end while the "
              "cursor stays parked on line 1."),
      ]),

    S("ex-move-line", "Relocate lines with :m (move)", "ex_command",
      ":[range]m{address} moves the range to just below {address}. Use :m0 to send "
      "a line to the very top, :m$ to the bottom, or :m{n} to slot it after line n. "
      "It rearranges lines from afar without cut-and-paste — no travel, no "
      "register, no lost cursor position.",
      [":m", ":move", ":m0", ":m$"], 3, [
        # The stray import sits at line 7 of a file you're editing at line 3 —
        # 7Gdd ggP `` is a round trip; :7m1 never leaves the line you're on.
        C(["import os", "import sys", "", "def main():", "    args = parse()",
           "    run(args)", "import json", "", "if __name__ == '__main__':",
           "    main()"],
          ["import os", "import json", "import sys", "", "def main():",
           "    args = parse()", "    run(args)", "", "if __name__ == '__main__':",
           "    main()"],
          start_cursor=[5, 5],
          solution=":7m1<CR>",
          hint="the stray import on line 7 belongs after line 1 — move it from here",
          why="dd would mean travelling there and back; :7m1 moves a far line "
              "while your cursor stays put."),
        # A debug print left above the function must drop to the very bottom.
        C(["print('DEBUG: remove me')", "def checkout(cart):",
           "    total = sum(cart.values())", "    apply_discount(total)",
           "    charge(total)", "    return receipt(total)", "",
           "log = setup_logger()"],
          ["def checkout(cart):", "    total = sum(cart.values())",
           "    apply_discount(total)", "    charge(total)",
           "    return receipt(total)", "", "log = setup_logger()",
           "print('DEBUG: remove me')"],
          start_cursor=[4, 5],
          solution=":1m$<CR>",
          hint="banish the debug print from line 1 to the bottom — no travel",
          why=":1m$ relocates the line across the whole file in one command."),
      ]),

    S("ex-repeat-last", "Repeat the last Ex command (@:)", "ex_command",
      "The dot command repeats the last NORMAL-mode change, but to repeat the "
      "last Ex command you use @: instead. After running it once, @@ repeats that "
      "in turn. Bonus: :s sets the search pattern, so n hops to the next match "
      "and @: re-runs the substitute right there.",
      ["@:", "@@", "n", ":s"], 4, [
        # Three scattered image tags need the bump; the comment must keep its
        # 'v1', so a blind :%s//g is wrong — n finds each, @: repeats the :s.
        C(["# rolling upgrade from v1, one service at a time",
           "api:", "  image: registry/api:v1", "  replicas: 3",
           "worker:", "  image: registry/worker:v1", "  replicas: 2",
           "cron:", "  image: registry/cron:v1"],
          ["# rolling upgrade from v1, one service at a time",
           "api:", "  image: registry/api:v2", "  replicas: 3",
           "worker:", "  image: registry/worker:v2", "  replicas: 2",
           "cron:", "  image: registry/cron:v2"],
          start_cursor=[3, 1],
          solution=":s/v1/v2/<CR>n@:n@:",
          hint=":s on the first image, then n to the next match and @: again",
          why="A bare :%s//g would also hit the comment — n + @: repeats the "
              "substitute only where you point it."),
        C(["x = 1", "y = 1", "z = 1"],
          ["x = 0", "y = 0", "z = 0"],
          solution=":s/1/0/<CR>j@:j@:",
          hint="substitute on line 1, then @: repeats it down each line",
          why="@: replays the :s — one j@: per remaining line, no retyping."),
      ]),
]
