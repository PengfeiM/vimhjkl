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

## Layout

```
src/vimhjkl/
  cli.py            # menu, modes, session orchestration
  engine.py         # scheduling and scoring — knows nothing about specific tricks
  challenge.py      # Challenge/Skill model + the category registry
  grader.py         # launches real vim, captures result + keystrokes, scores
  store.py          # JSON persistence
  tui.py            # ANSI rendering and input
  data/skills.json  # the curriculum (data, not code)
tests/              # headless grader and engine checks
```

The engine is generic: a technique is a **data entry**, never an engine edit.

## Code changes

Keep PRs small and focused, match the surrounding style, and make sure both test
suites pass. If you change grading behaviour, add a check to `tests/test_grader.py`.

## Adding or fixing a lesson

A lesson lives in `src/vimhjkl/data/skills.json`. Each skill has a `category` (one
of the keys in `CATEGORIES` in `challenge.py`) that decides how it's graded, and a
list of `challenges`:

```json
{
  "id": "marks-as-ex-range",
  "title": "Use marks as an Ex range ('a,'b)",
  "category": "ex_command",
  "teach": "Two or three sentences explaining the move.",
  "key_commands": [":'a,'b", "ma", "mb"],
  "difficulty": 4,
  "challenges": [
    {
      "start": ["lines the user starts with"],
      "goal":  ["lines the buffer must equal when done"],
      "solution": "the literal keystrokes, <Esc>/<CR> spelled out",
      "par_keys": 25,
      "hint": "a short nudge",
      "why": "one line on why this is the idiomatic path"
    }
  ]
}
```

`motion` challenges use `start_cursor` + `target` (a 1-based `[line, col]`) instead
of `goal`. See `CATEGORIES` in `challenge.py` for every category.

What makes a **good** challenge:

- **The example must need the technique.** Size the buffer so the lesson's move is
  the shortest correct path. A `:g`/macro/sort/range drill on a 2-line buffer is
  pointless — a simpler move would beat it. For range/marks drills, put a match
  *outside* the range so a whole-file `:%…` would change the wrong lines.
- **Original, concrete text.** No `foo`/`bar`, no `one/two/three`. Vivid, specific
  example text; never copy real book/song/source text.
- **`solution` is the optimal path** (`par_keys` is the optimal keystroke count,
  excluding the final save/quit) and must reproduce `goal` exactly when replayed in
  real vim. Run your keystrokes in a clean editor (`vim -u NONE`) to confirm.

## Reporting issues

Open an [issue](https://github.com/S-Sigdel/vimhjkl/issues) for bugs or lesson
ideas. For a new lesson, the most useful report is the **start buffer**, the
**goal buffer**, and the **keystrokes** — that's everything needed to verify it.

By contributing you agree your work is licensed under the [MIT License](LICENSE).
