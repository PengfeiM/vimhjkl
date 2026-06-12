"""Everyday code editing: the moves programmers reach for.

Five skills that vimtutor mentions in passing but never drills at codebase
scale: replace-char (r/R), join (J/gJ), indent shifts (>>/<<), paragraph leaps
({/}), and absolute line jumps ({count}G). Buffers are deliberately multiline
and code-shaped — the payoff of each move only shows at distance.

Indent drills use tab-indented contexts (Makefiles, Go) on purpose: clean vim
(-u NONE) shifts by one literal tab ('shiftwidth' 8, 'noexpandtab'), and those
two file kinds genuinely indent with tabs.
"""

from build.common import C, S

SKILLS = [
    S("operator-replace-char", "Replace one character (r, R)", "operator",
      "r{char} overwrites the character under the cursor and immediately returns "
      "to Normal mode — no <Esc>, no Insert trip. A count replaces a run (2r| "
      "turns && into ||), and R enters Replace mode to overtype several "
      "characters in place. For one-character typos, r beats any change command.",
      ["r", "2r", "R", "f{char}r"], 1, [
        C(["matrix[i][j] = matrix[j][i};"],
          ["matrix[i][j] = matrix[j][i];"],
          solution="f}r]",
          hint="fly to the wrong bracket, then r overtypes just it",
          why="f}r] is four keys and never leaves Normal mode — cl]<Esc> is "
              "five plus a mode trip."),
        C(["for (i = 0. i < n; i++) {", "    visit(nodes[i])", "}"],
          ["for (i = 0; i < n; i++) {", "    visit(nodes[i])", "}"],
          solution="f.r;",
          hint="the dot should be a semicolon — find it, replace it",
          why="One stray character needs exactly one r, not an Insert session."),
        C(["if (debug && verbose && trace) {", "    dump_state()", "}"],
          ["if (debug || verbose || trace) {", "    dump_state()", "}"],
          solution="f&2r|;.",
          hint="2r| swaps the pair; ; refinds, . repeats",
          why="A counted r replaces a run, and it's dot-repeatable — the "
              "second && costs two keys."),
        C(["release = v1.0.3-beta"],
          ["release = v2.4.3-beta"],
          solution="f1R2.4<Esc>",
          hint="R overtypes in place — retype just the version core",
          why="Replace mode rewrites three characters without disturbing the "
              "'-beta' tail; cW would mean retyping all of it."),
      ]),

    S("operator-join-lines", "Join lines upward (J, gJ)", "operator",
      "J joins the next line onto the current one, collapsing its leading "
      "indent to a single space; a count joins that many lines (3J makes three "
      "into one). gJ joins with NO space — for when a line broke mid-token. "
      "It's the undo button for over-eager line wrapping.",
      ["J", "3J", "gJ"], 2, [
        C(["def setup():", "    cfg = load(path,", "        strict=True,",
           "        retries=3)", "    return cfg"],
          ["def setup():", "    cfg = load(path, strict=True, retries=3)",
           "    return cfg"],
          start_cursor=[2, 5],
          solution="JJ",
          hint="each J pulls the next wrapped argument up onto this line",
          why="J swallows the continuation's indent and leaves one clean "
              "space — deleting whitespace by hand can't compete."),
        C(["msg = (\"deploy failed:\"", "       \" disk full on\"",
           "       \" node-7\")", "raise DeployError(msg)"],
          ["msg = (\"deploy failed:\" \" disk full on\" \" node-7\")",
           "raise DeployError(msg)"],
          solution="3J",
          hint="a count joins the whole wrapped expression at once",
          why="3J collapses three lines in one stroke instead of J J."),
        C(["DATABASE_", "URL = os.environ.get('DATABASE_URL')",
           "connect(DATABASE_URL)"],
          ["DATABASE_URL = os.environ.get('DATABASE_URL')",
           "connect(DATABASE_URL)"],
          solution="gJ",
          hint="the identifier broke across lines — join with NO space",
          why="gJ glues the lines verbatim; J would wedge a space inside "
              "the variable name."),
      ]),

    S("operator-indent-shift", "Shift indentation (>>, <<)", "operator",
      ">> shifts the current line one 'shiftwidth' right, << shifts it left, and "
      "a count takes that many lines (3>> indents three). Like d and c they are "
      "operators, so >ip indents a paragraph and >} to the block's end. In clean "
      "vim a shift is one literal tab — exactly what Makefiles and Go want.",
      [">>", "<<", "3>>", ">ip"], 2, [
        C(["build:", "go build ./cmd/app", "test:", "go test ./..."],
          ["build:", "\tgo build ./cmd/app", "test:", "\tgo test ./..."],
          solution="j>>2j>>",
          hint="make recipes must be tab-indented — shift each command line",
          why=">> indents by one tab in clean vim, which is precisely what "
              "a Makefile recipe requires."),
        C(["func main() {", "fmt.Println(\"boot\")", "cfg := load()",
           "serve(cfg)", "}"],
          ["func main() {", "\tfmt.Println(\"boot\")", "\tcfg := load()",
           "\tserve(cfg)", "}"],
          solution="j3>>",
          hint="the pasted body lost its indent — a count fixes all three lines",
          why="3>> shifts the whole body in one operation; line-by-line "
              ">> j >> j >> is triple the work."),
        C(["if ok {", "\tship()", "\t\tlog(\"done\")", "\t\treturn nil", "}"],
          ["if ok {", "\tship()", "\tlog(\"done\")", "\treturn nil", "}"],
          solution="2j2<<",
          hint="two lines are a level too deep — dedent both with a count",
          why="2<< pulls both over-indented lines back one stop without "
              "touching their inner spacing."),
      ]),

    S("motion-paragraph-leap", "Leap by paragraph ({, })", "motion",
      "} jumps to the next blank line, { to the previous one. In code, blank "
      "lines separate functions and stanzas — so each press leaps a whole block, "
      "however long it is. Counts stack (2}), and as motions they feed operators "
      "too (d}, y}).",
      ["{", "}", "2}", "d}"], 2, [
        C(["import sqlite3", "import json", "",
           "def connect(path):", "    db = sqlite3.connect(path)",
           "    db.row_factory = dict_row", "    return db", "",
           "def dict_row(cur, row):", "    cols = [d[0] for d in cur.description]",
           "    return dict(zip(cols, row))"],
          start_cursor=[1, 1], target=[8, 1],
          solution="}}",
          hint="each } clears one whole block, however tall",
          why="Two presses cross two blocks — j would take seven."),
        C(["app.get('/health', (req, res) => {", "  res.send('ok')", "})", "",
           "app.get('/users', (req, res) => {", "  res.json(db.users())", "})",
           "", "app.listen(PORT)"],
          start_cursor=[1, 1], target=[5, 1],
          solution="}j",
          hint="} to the gap, j onto the next route's first line",
          why="}j is the two-key idiom for 'start of the next block'."),
        C(["[server]", "host = 0.0.0.0", "port = 8080", "",
           "[database]", "url = postgres://localhost/app", "pool_size = 5", "",
           "[logging]", "level = info", "file = /var/log/app.log"],
          start_cursor=[11, 8], target=[4, 1],
          solution="{{",
          hint="{ leaps backward a stanza at a time",
          why="Two { presses climb from the bottom section past [database] "
              "in two keys."),
      ]),

    S("motion-goto-line", "Jump to a line by number (G, gg)", "motion",
      "{count}G jumps straight to that line number — THE motion for 'error on "
      "line 13'. Bare G goes to the last line, gg to the first. (:13<CR> does "
      "the same from the command line.) With relative distances unknown, an "
      "absolute jump beats any amount of scrolling.",
      ["13G", "gg", "G", ":13"], 1, [
        C(["certifi==2026.4.26", "charset-normalizer==3.4.0", "click==8.1.8",
           "fastapi==0.115.6", "h11==0.14.0", "httpcore==1.0.7",
           "httpx==0.28.1", "idna==3.10", "pydantic==2.10.4",
           "sniffio==1.3.1", "starlette==0.41.3", "typing-extensions==4.12.2",
           "uvicorn==0.30.1", "uvloop==0.21.0", "watchfiles==1.0.3"],
          start_cursor=[1, 1], target=[13, 1],
          solution="13G",
          hint="the merge conflict is on line 13 — jump by number",
          why="13G lands exactly where the diff points, no counting."),
        C(["[package]", "name = 'vimhjkl'", "version = '0.4.1'", "",
           "[dependencies]", "# stdlib only", "", "[build]",
           "backend = 'uv_build'", "module-root = 'src'", "",
           "[tool.notes]", "remember = 'tabs in makefiles'"],
          start_cursor=[13, 1], target=[1, 1],
          solution="gg",
          hint="back to the top in two keys",
          why="gg is the absolute jump home — no Ctrl-U mashing."),
        C(["#!/bin/sh", "set -eu", "", "say() { printf '%s\\n' \"$1\"; }", "",
           "say 'building'", "make build", "", "say 'testing'", "make test", "",
           "say 'shipping'", "make release"],
          start_cursor=[2, 1], target=[13, 1],
          solution="G",
          hint="straight to the file's last line",
          why="G needs no count to reach the end of any file."),
      ]),
]
