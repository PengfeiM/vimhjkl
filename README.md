<div align="center">

# ⚔ vimhjkl

**The Vim techniques `vimtutor` never taught you — drilled in real vim/nvim, graded on your actual keystrokes.**

[![AUR version](https://img.shields.io/aur/version/vimhjkl?label=AUR)](https://aur.archlinux.org/packages/vimhjkl)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Lessons](https://img.shields.io/badge/lessons-61-success)
![Pure stdlib](https://img.shields.io/badge/deps-stdlib%20only-informational)

</div>

⭐ Star it if it makes you faster — it helps a lot!

The dot command, operator + motion grammar, text objects, registers, macros, ex
commands (`:g`, `:normal`, ranges), and substitution — **61 lessons, 563
challenges**, every one replayed through real vim so the "optimal" it shows you
actually works. While you edit, the goal sits in a pane beside the buffer, so you
practise the move instead of remembering it.

![the menu](img/homepage.png)

## Contents

- [Install](#install)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)

## Install

### macOS / Linux ([Homebrew](https://brew.sh))

```sh
brew install S-Sigdel/tap/vimhjkl
```

### Arch Linux ([AUR](https://aur.archlinux.org/packages/vimhjkl))

```sh
paru -S vimhjkl      # or: yay -S vimhjkl
```

### From source

Needs [uv](https://docs.astral.sh/uv/) and `vim` or `nvim` on `PATH` — no other
dependencies.

```sh
git clone https://github.com/S-Sigdel/vimhjkl && cd vimhjkl
uv sync && uv run vimhjkl
```

## Usage

```sh
vimhjkl              # interactive menu   (from source: uv run vimhjkl)
vimhjkl --drill      # Learn: read the move, then drill it
vimhjkl --practice   # retry the skills you keep missing
vimhjkl --reps 6     # Grind: one skill, 6× back-to-back
vimhjkl --review     # no-editor flashcards
vimhjkl --list       # curriculum, mastery, belt
```

| Mode     | What it does                                            |
|----------|--------------------------------------------------------|
| Learn    | Shows the technique and idiomatic move before you edit |
| Blind    | Before/after only — recall the move yourself           |
| Practice | Your weakest skills, retry until you pass              |
| Grind    | One skill, N times back-to-back (`--reps N`)           |
| Review   | Read-only flashcards, self-rated, no editor            |

## How it works

You edit in **real vim**, not an emulator, with the goal pinned in a read-only
pane beside the buffer:

![the goal sits beside the buffer](img/actualedit.png)

Keystrokes are logged with `-W` and scored on correctness *and* efficiency
against a verified par. Command drills (`:s`, `:g`, `:normal`) require an actual
ex command — you can't hand-edit your way to the goal. Mastery is tracked per
skill with Leitner spaced repetition and a belt rank that unlocks harder material
as your boxes fill.

<details>
<summary>More screenshots</summary>

A lesson in Learn mode:

![Learn mode](img/learnmode.png)

The curriculum and your mastery:

![Curriculum](img/curriculum.png)

</details>

## Contributing

Adding a technique is a data change, not an engine change. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the setup, the challenge schema, and how to
run the tests.

## License

[MIT](LICENSE)
