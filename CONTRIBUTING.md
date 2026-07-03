# Contributing to vimhjkl

Thanks for helping out! Bug fixes, new lessons, and better example buffers are all
welcome.

## Setup

You need [uv](https://docs.astral.sh/uv/) and `vim` or `nvim` on `PATH`. There are
no other dependencies — the package is pure standard library.

```sh
git clone https://github.com/S-Sigdel/vimhjkl && cd vimhjkl
uv sync
uv run vimhjkl            # run it
```

Run the test suites before opening a PR (the grader suite plays keystrokes back
through real vim):

```sh
uv run python -m tests.test_grader
uv run python -m tests.test_engine
```

## Workflow

Work on a branch, never directly on `main` — a named branch keeps your pull
request reviewable and lets you pull upstream changes without conflicts.

1. **Fork** the repo and clone your fork.

2. **Branch, named for the change.** Use a short prefix so the intent is obvious:
   `fix/` for a bug, `lesson/` for a new or reworked lesson, `feature/` for
   anything else.

   ```sh
   git switch -c fix/ctrl-j-quit-counted
   ```

3. **Make one focused change.** One bug fix or one lesson per branch — small PRs
   get reviewed and merged faster. Match the surrounding style (the package is
   stdlib-only; no new dependencies without discussion).

4. **Run both test suites** (commands above) and confirm they pass. If you touched
   grading behaviour, add a check to `tests/test_grader.py`; if you touched
   selection/scoring, add one to `tests/test_engine.py`.

5. **Commit in the repo's style** — a short, lowercase, imperative summary with no
   `type:` prefix, e.g.

   ```
   count the save keystrokes correctly when Enter sends <NL>
   ```

   Keep each commit a single logical change; squash noise before pushing.

6. **Push and open a pull request** against `main`. In the description, say what
   changed and why. For a lesson, paste the **start buffer**, the **goal**, and the
   **keystrokes** so a reviewer can verify it in one paste.

## Layout

```
src/vimhjkl/
  cli.py            # menu, modes, session orchestration
  engine.py         # scheduling and scoring — knows nothing about specific tricks
  challenge.py      # Challenge/Skill model + the category registry
  grader.py         # launches real vim, captures result + keystrokes, scores
  store.py          # JSON persistence
  tui.py            # ANSI rendering and input
  data/skills.json  # the curriculum (GENERATED — do not hand-edit)
build/
  passes/*.py       # the lesson source — author here
  generate.py       # verifies every challenge in real vim, writes skills.json
content/
  llm_pool.json     # extra verified challenge instances, merged by skill id
tests/              # headless grader and engine checks
```

The engine is generic: a technique is a **data entry**, never an engine edit. A new
trick should be a lesson in a `build/passes/` module, not a special case in
`grader.py` or `engine.py` — if you find yourself editing those to teach one
specific move, stop and reconsider.

## Adding or fixing a lesson

Lessons are authored in `build/passes/*.py` with the `S` (skill) and `C`
(challenge) helpers from `build/common.py`, then rendered into
`src/vimhjkl/data/skills.json` by:

```sh
uv run python -m build.generate
```

The generator replays every `solution` through real vim, computes `par_keys`
from it, and refuses to write if anything fails to verify — so a wrong solution
or goal cannot ship.

```python
S("marks-as-ex-range", "Use marks as an Ex range ('a,'b)", "ex_command",
  "Two or three sentences explaining the move.",
  [":'a,'b", "ma", "mb"], 4, [
    C(["lines the user starts with"],
      ["lines the buffer must equal when done"],
      solution="the literal keystrokes, <Esc>/<CR> spelled out",
      hint="a short nudge",
      why="one line on why this is the idiomatic path",
      why_not="the obvious cheaper-looking path, and why it loses HERE"),
  ]),
```

Each skill has a `category` (a key of `CATEGORIES` in `challenge.py`) that
decides how it's graded. `motion` challenges use `start_cursor` + `target`
(1-based `[line, col]`) instead of a goal buffer.

What makes a **good** challenge:

- **The example must need the technique.** Size the buffer so the lesson's move is
  the shortest correct path. A `:g`/macro/sort/range drill on a 2-line buffer is
  pointless — a simpler move would beat it. For range/marks drills, put a match
  *outside* the range so a whole-file `:%…` would change the wrong lines.
- **Name the rejected alternative.** If a learner would reach for a simpler
  command first (`:%s//g`, `dd`+`p`, plain `yy`), fill `why_not` with that exact
  command and the concrete way it fails on *this* buffer. If you can't write an
  honest `why_not`, the buffer probably doesn't motivate the technique — fix the
  buffer, not the prose.
- **Original, concrete text.** No `foo`/`bar`, no `one/two/three`. Vivid, specific
  example text; never copy real book/song/source text.
- **`solution` is the optimal path** and must reproduce the goal exactly when
  replayed in clean vim (`vim -u NONE`) — `build.generate` checks this and
  computes `par_keys` for you.

## Reporting issues

Open an [issue](https://github.com/S-Sigdel/vimhjkl/issues) for bugs or lesson
ideas. For a new lesson, the most useful report is the **start buffer**, the
**goal buffer**, and the **keystrokes** — that's everything needed to verify it.

By contributing you agree your work is licensed under the [MIT License](LICENSE).
