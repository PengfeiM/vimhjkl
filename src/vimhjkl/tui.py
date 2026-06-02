"""Terminal rendering for vimhjkl.

Deliberately NOT a persistent full-screen application: a long-lived
prompt_toolkit Application owns the tty and corrupts the terminal when vim is
launched as a child.  Instead we render with plain ANSI and read single keys
via termios, and use prompt_toolkit only for the one-shot main menu (it fully
exits its alt-screen before we ever hand the tty to vim).
"""

from __future__ import annotations

import contextlib
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GREY = "\033[90m"


def _supports_color() -> bool:
    return sys.stdout.isatty()


def c(text: str, color: str) -> str:
    if not _supports_color():
        return text
    return f"{color}{text}{RESET}"


def clear() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def rule(width: int = 72) -> str:
    return c("─" * width, GREY)


def banner(title: str, subtitle: str = "") -> None:
    print()
    print(c("  ⚔  " + title, BOLD + CYAN))
    if subtitle:
        print(c("     " + subtitle, GREY))
    print(rule())


def progress_bar(frac: float, width: int = 20, color: str = GREEN) -> str:
    """A filled/empty block bar, e.g. ▓▓▓▓░░░░░░."""
    frac = max(0.0, min(1.0, frac))
    fill = int(round(frac * width))
    return c("▓" * fill, color) + c("░" * (width - fill), GREY)


# ---------------------------------------------------------------------------
# Buffer rendering — show a "before"/"after" buffer in a framed box.
# ---------------------------------------------------------------------------

# Black text on a yellow background — the "land here" target cell.
HILITE = "\033[30;43m"


def _highlight_cell(text: str, col0: int) -> str:
    """Wrap the single character at 0-based ``col0`` in the target highlight.

    ``text`` must already be padded to its display width (so ``col0`` is always
    in range — a column past end-of-line lands on a padded space).
    """
    if not _supports_color() or col0 < 0 or col0 >= len(text):
        return text
    return text[:col0] + HILITE + text[col0] + RESET + text[col0 + 1:]


def render_buffer(lines: list[str], label: str = "", color: str = BLUE,
                  cursor: Optional[list[int]] = None,
                  target: Optional[list[int]] = None) -> None:
    width = max([len(l) for l in lines] + [len(label), 20])
    width = min(width, 76)
    if label:
        print(c(f"  {label}", color + BOLD))
    top = "  ┌" + "─" * (width + 2) + "┐"
    print(c(top, GREY))
    for i, line in enumerate(lines, start=1):
        shown = line if len(line) <= width else line[: width - 1] + "…"
        cell = shown.ljust(width)
        # Highlight the target cell (1-based [line, col]) so "land on the
        # highlighted target" is literally true.
        if target and target[0] == i:
            cell = _highlight_cell(cell, target[1] - 1)
        marker = ""
        if cursor and cursor[0] == i:
            marker = c(" ◀ start" if target else " ◀ cursor", YELLOW)
        print(c("  │ ", GREY) + cell + c(" │", GREY) + marker)
    bot = "  └" + "─" * (width + 2) + "┘"
    print(c(bot, GREY))


# ---------------------------------------------------------------------------
# Single-key input (no Enter needed) for review-mode self-rating.
# ---------------------------------------------------------------------------

def read_key() -> str:
    """Read a single keypress.  Returns the character (space -> ' ')."""
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[:1] if line else "q"
    try:
        import termios
        import tty
    except ImportError:  # pragma: no cover (non-unix)
        return sys.stdin.readline()[:1] or "q"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        with _suspend_guard(fd, old):
            ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == "\x03":  # Ctrl-C
        raise KeyboardInterrupt
    return ch


def pause(msg: str = "press any key to continue…") -> None:
    print(c("  " + msg, GREY))
    read_key()


def install_signal_guard() -> None:
    """Restore the tty to its cooked startup state if the process is killed by
    SIGTERM/SIGHUP — those terminate without running the try/finally restores in
    read_key/menu/pager, which would otherwise leave the terminal raw and corrupt
    the user's shell (sudo echoing until ``stty sane``).  Re-raises the default
    action so the process still dies.  Installed once, globally, for the whole run.

    SIGTSTP (Ctrl-Z) is deliberately NOT handled here: it's handled only inside
    the raw regions that own the tty (see ``_suspend_guard``), so it never
    interferes with a child like vim that manages its own job control."""
    if not sys.stdin.isatty():
        return
    try:
        import os
        import signal
        import termios
    except ImportError:  # pragma: no cover (non-unix)
        return
    fd = sys.stdin.fileno()
    cooked = termios.tcgetattr(fd)

    def _die(signum, _frame):
        termios.tcsetattr(fd, termios.TCSADRAIN, cooked)
        signal.signal(signum, signal.SIG_DFL)  # re-raise with default action
        os.kill(os.getpid(), signum)

    for _sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(_sig, _die)


@contextlib.contextmanager
def _suspend_guard(fd: int, cooked):
    """Context manager: while a raw region holds the tty, make Ctrl-Z (SIGTSTP)
    drop back to the ``cooked`` mode *before* the process stops — so the shell it
    hands control to is sane — and re-enter raw on resume.  Scoped to the ``with``
    body; the previous SIGTSTP disposition is restored on exit, so outside these
    regions (e.g. while vim runs) Ctrl-Z keeps its default behaviour."""
    try:
        import os
        import signal
        import termios
        import tty
    except ImportError:  # pragma: no cover (non-unix)
        yield
        return

    def _suspend(signum, _frame):
        termios.tcsetattr(fd, termios.TCSADRAIN, cooked)  # sane shell while stopped
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)                      # actually stop here
        # --- resumes here on SIGCONT (e.g. `fg`) ---
        signal.signal(signum, _suspend)                   # re-arm
        tty.setraw(fd)                                    # back into raw

    prev = signal.signal(signal.SIGTSTP, _suspend)
    try:
        yield
    finally:
        signal.signal(signal.SIGTSTP, prev)


def _read_raw_key(fd: int) -> str:
    """Read one keypress, decoding arrow keys.  Assumes the tty is ALREADY in raw
    mode (the menu loop holds it) — does no termios save/restore of its own.

    Returns a semantic token for special keys — ``UP`` / ``DOWN`` / ``LEFT`` /
    ``RIGHT`` / ``ENTER`` / ``ESC`` — or the literal character otherwise.
    """
    import os
    import select

    # os.read (unbuffered) — NOT sys.stdin.read, whose buffering would swallow
    # the rest of an escape sequence and make the select() peek below miss it.
    b = os.read(fd, 1)
    if not b:
        return "ESC"
    if b == b"\x03":  # Ctrl-C
        raise KeyboardInterrupt
    if b in (b"\r", b"\n"):
        return "ENTER"
    if b == b"\x1b":
        # ESC alone, or the start of an arrow-key escape sequence.  Peek with a
        # short timeout to tell them apart.
        ready, _, _ = select.select([fd], [], [], 0.03)
        if not ready:
            return "ESC"
        if os.read(fd, 1) == b"[":
            code = os.read(fd, 1)
            return {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}.get(code, "ESC")
        return "ESC"
    return b.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def _opt_parts(opt) -> tuple[str, str, str]:
    """Normalise an option to ``(key, title, description)``.

    Accepts ``(key, title)`` or ``(key, title, description)``.
    """
    if len(opt) >= 3:
        return opt[0], opt[1], opt[2]
    return opt[0], opt[1], ""


def _menu_frame(title: str, subtitle: str, header_lines: Optional[list[str]],
                options: list[tuple], idx: int) -> str:
    """Build one full menu screen as a string with raw-safe ``\\r\\n`` endings."""
    rows: list[str] = ["", c("  ⚔  " + title, BOLD + CYAN)]
    if subtitle:
        rows.append(c("     " + subtitle, GREY))
    rows.append(rule())
    if header_lines:
        rows += ["  " + line for line in header_lines]
        rows.append(rule())
    rows.append("")
    for i, opt in enumerate(options):
        _key, otitle, desc = _opt_parts(opt)
        selected = i == idx
        pointer = c(" ▸ ", CYAN + BOLD) if selected else "   "
        line = pointer + c(otitle, CYAN + BOLD if selected else RESET)
        if desc:
            line += c("  — " + desc, CYAN if selected else GREY)
        rows.append(line)
    rows.append("")
    rows.append(c("  ↑/↓ or j/k to move · Enter to choose · q to quit", GREY))
    return "\033[2J\033[H" + "\r\n".join(rows) + "\r\n"


def menu(title: str, options: list[tuple], subtitle: str = "",
         header_lines: Optional[list[str]] = None) -> Optional[str]:
    """A keyboard-driven, dojo-styled menu.

    ``options`` is a list of ``(key, title[, description])``.  Returns the chosen
    option key, or ``None`` if cancelled.  Drawn in the app's own ANSI style (no
    prompt_toolkit dialog) and navigated with ↑/↓ or j/k; Enter chooses, q/Esc
    cancels, and number keys jump straight to an option.
    """
    if not sys.stdin.isatty():
        return _menu_fallback(title, options)
    try:
        import termios
        import tty
    except ImportError:  # pragma: no cover (non-unix)
        return _menu_fallback(title, options)

    n = len(options)
    idx = 0
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    # Raw mode is held across the WHOLE loop (not per-keypress) so the terminal
    # never flaps back to cooked/echo between renders; restored on exit.
    try:
        tty.setraw(fd)
        with _suspend_guard(fd, old):
            while True:
                sys.stdout.write(_menu_frame(title, subtitle, header_lines, options, idx))
                sys.stdout.flush()
                k = _read_raw_key(fd)
                if k in ("UP", "k"):
                    idx = (idx - 1) % n
                elif k in ("DOWN", "j"):
                    idx = (idx + 1) % n
                elif k in ("ENTER", " "):
                    return _opt_parts(options[idx])[0]
                elif k in ("ESC", "q"):
                    return None
                elif k.isdigit() and 1 <= int(k) <= n:
                    return _opt_parts(options[int(k) - 1])[0]
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        clear()


def _menu_fallback(title: str, options: list[tuple]) -> Optional[str]:
    print()
    print(c("  " + title, BOLD + CYAN))
    for i, opt in enumerate(options, start=1):
        _key, otitle, desc = _opt_parts(opt)
        tail = c("  — " + desc, GREY) if desc else ""
        print(f"   {c(str(i), YELLOW)}. {otitle}{tail}")
    print()
    try:
        raw = input("  choose a number (or q to quit): ").strip()
    except EOFError:
        return None
    if raw.lower() in ("q", "quit", ""):
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return _opt_parts(options[int(raw) - 1])[0]
    return None


def prompt_line(msg: str) -> str:
    try:
        return input(c("  " + msg, CYAN))
    except (EOFError, KeyboardInterrupt):
        return ""


# ---------------------------------------------------------------------------
# Pager — a scrollable read-only view (the curriculum screen)
# ---------------------------------------------------------------------------

def _pager_frame(title: str, subtitle: str, header_lines: Optional[list[str]],
                 lines: list[str], top: int, view_h: int, footer: str) -> str:
    rows: list[str] = ["", c("  ⚔  " + title, BOLD + CYAN)]
    if subtitle:
        rows.append(c("     " + subtitle, GREY))
    rows.append(rule())
    if header_lines:
        rows += ["  " + line for line in header_lines]
        rows.append(rule())
    window = lines[top:top + view_h]
    rows += window
    rows += [""] * max(0, view_h - len(window))   # keep the box a stable height
    rows.append(rule())
    shown_to = top + len(window)
    pos = f"{(top + 1) if lines else 0}-{shown_to}/{len(lines)}"
    rows.append(c(f"  {footer}", GREY) + c(f"    [{pos}]", GREY))
    return "\033[2J\033[H" + "\r\n".join(rows) + "\r\n"


def pager(title: str, lines: list[str], *, subtitle: str = "",
          header_lines: Optional[list[str]] = None,
          footer: str = "j/k or ↑/↓ scroll · g/G top/bottom · Esc/q back") -> None:
    """Scroll a list of (already-rendered) lines.  Esc or q returns."""
    if not sys.stdin.isatty():
        print()
        print(c("  ⚔  " + title, BOLD + CYAN))
        for line in (header_lines or []):
            print("  " + line)
        for line in lines:
            print(line)
        return
    try:
        import shutil
        import termios
        import tty
    except ImportError:  # pragma: no cover (non-unix)
        for line in lines:
            print(line)
        return

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    top = 0
    try:
        tty.setraw(fd)
        with _suspend_guard(fd, old):
            while True:
                size = shutil.get_terminal_size((80, 24))
                chrome = 5 + (len(header_lines) + 1 if header_lines else 0)
                view_h = max(3, size.lines - chrome)
                max_top = max(0, len(lines) - view_h)
                top = min(top, max_top)
                sys.stdout.write(_pager_frame(title, subtitle, header_lines, lines,
                                              top, view_h, footer))
                sys.stdout.flush()
                k = _read_raw_key(fd)
                if k in ("DOWN", "j"):
                    top = min(max_top, top + 1)
                elif k in ("UP", "k"):
                    top = max(0, top - 1)
                elif k == " ":
                    top = min(max_top, top + view_h)
                elif k in ("b", "B"):
                    top = max(0, top - view_h)
                elif k == "g":
                    top = 0
                elif k == "G":
                    top = max_top
                elif k in ("ESC", "q", "Q"):
                    return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        clear()
