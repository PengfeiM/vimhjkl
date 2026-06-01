# vimhjkl

A terminal trainer for advanced Vim technique. It picks up where `vimtutor`
stops — the dot command, operator + motion grammar, text objects, registers,
macros, ex commands (`:g`, `:normal`, ranges), and substitution — and drills
them inside **real vim/nvim**, grading the actual keystrokes you type against an
optimal par.

The practice happens in a real editor, not an emulator: each challenge launches
vim on a start buffer, logs your keystrokes, and scores the result on
correctness and efficiency.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python toolchain and the venv)
- Python ≥ 3.11 — provisioned by uv; you do not need a system Python
- `vim` or `nvim` on `PATH` (nvim is preferred, vim is the fallback)

There are no third-party Python dependencies. The package is pure standard
library; the only external requirement is the editor binary.

## Setup

```sh
uv sync
```

This creates `.venv` using the pinned interpreter (`.python-version`) and
installs the `vimhjkl` package from the lockfile.

## Usage

```sh
uv run vimhjkl                       # interactive menu
uv run vimhjkl --drill               # Learn mode: read the move, then drill it
uv run vimhjkl --drill --mode blind  # Blind mode: no hints, recall only
uv run vimhjkl --practice            # retry the skills you keep failing
uv run vimhjkl --reps 6              # Grind: drill ONE skill 6x back-to-back
uv run vimhjkl --review              # no-editor flashcard recall
uv run vimhjkl --list                # curriculum, mastery, and belt
```

`uv run vimhjkl` invokes the console script; `uv run python -m vimhjkl` is
equivalent.

### Modes

| Mode     | Behavior                                                              |
|----------|-----------------------------------------------------------------------|
| Learn    | Shows the technique, the idiomatic command, and why, before you edit. |
| Blind    | Shows only the before/after buffers. Recall the move yourself.        |
| Practice | Selects your weakest skills and lets you retry each until you pass.   |
| Grind    | Drills ONE skill N times back-to-back (`--reps N`) to build muscle memory; every rep counts toward the groove target. |
| Review   | Read-only flashcards (front/back), self-rated. No editor launched.    |

## How grading works

1. The challenge's start buffer is written to a temp file. vim launches on it
   with `-W` to log every keystroke to a scriptout.
2. On exit, the resulting buffer is diffed against the goal for **correctness**;
   for motion challenges, the final cursor position is compared against the
   target instead.
3. The logged keystrokes are counted for **efficiency** (`par / actual`, capped
   at 1.0). The result screen then shows your own keystrokes (`your moves`)
   alongside the `optimal` solution, so you can see where they diverged. Pass
   `--hide-moves` to suppress your keystrokes.

The keystroke count measures technique, not typing accuracy. Before counting,
the log is normalized: a backspace cancels the keystroke it corrected, and a run
of repeated `<Esc>` counts as one. A typo you fix therefore costs the same as
typing it correctly the first time.

### Editor configuration

Drills run a clean `-u NONE` editor — never your personal config. This is
deliberate: a config that reformats or trims whitespace on save would rewrite
the buffer and invalidate grading, and key remaps would skew par. Interactive
sessions layer on a few display-only options (relative line numbers, syntax,
`showcmd`, `cursorline`, `incsearch`/`hlsearch`) via startup commands that are
not written to the scriptout, so they never affect keystroke counts. The set
lives in `_INTERACTIVE_SETTINGS` in `src/vimhjkl/grader.py`.

## Progression

Mastery is tracked per technique with a Leitner spaced-repetition box (1–5),
shared by drills and review. A correct, efficient solve promotes a skill; a
genuine miss (a wrong answer you saved) demotes it. Quitting without saving is
treated as an abstention, not a failure: the box is left untouched, so you can
stop a session and resume later without losing ground. Sessions pull your
weakest and most-due skills first, then introduce new ones gated by an overall
rank ("belt"), which rises as your boxes fill and unlocks harder material
gradually.

Player state lives in `progress.json` at the project root and is written after
every graded attempt, so an interrupt never loses completed work. `Ctrl-C`
saves and exits cleanly from anywhere.

## Architecture

```
content/
  skills.json         # the curriculum (data, not code)
progress.json         # player mastery state
src/vimhjkl/
  cli.py              # entry point: menu, modes, session orchestration
  engine.py           # scheduling and scoring; knows nothing about specific tricks
  challenge.py        # Challenge/Skill model and the category registry
  grader.py           # launches real vim, captures result + keystrokes, scores
  store.py            # JSON persistence for the curriculum and progress
  tui.py              # ANSI rendering and terminal input
tests/                # headless grader and engine verification
```

The engine is generic. Adding a technique means adding a data entry in
`skills.json` — driven by the category registry in `challenge.py` — not editing
the engine.

## Development

Run the test suites (real-vim keystroke playback for the grader, headless checks
for the engine):

```sh
uv run python -m tests.test_grader
uv run python -m tests.test_engine
```

The curriculum lives in `content/skills.json`, keyed by the category registry in
`challenge.py`. Each entry stores a technique's lesson, key commands, and several
example challenge instances with their optimal keystroke par.
