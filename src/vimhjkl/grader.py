"""Grade an attempt by launching *real* vim/nvim and inspecting the result.

The keystroke-counting contract (verified empirically against ``vim -W``):

  * ``vim -W scriptout`` logs every typed key as RAW BYTES.  ``<Esc>`` is one
    byte (0x1b); arrow keys / special keys serialize as multi-byte escape
    sequences, so byte-counting gently penalises them — which is the point
    (efficiency caps at 1.0 so it never helps to use them).
  * The session-ending quit (``:wq<CR>`` / ``:q<CR>`` / ``ZZ`` / ``:x<CR>``)
    also lands in the log; we strip a recognised trailing quit sequence so it
    is NOT counted against par.  Users are told to quit with exactly ``:wq``
    (edits) or ``:q`` (motion-only).
  * keystrokes = len(scriptout bytes) - len(trailing quit sequence).

Cursor position (for ``motion`` grading) is captured with a ``VimLeave``
autocmd that writes ``line('.') col('.')`` to a side file — this works for both
interactive sessions and ``-s`` playback, and does NOT pollute the scriptout.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from .challenge import Challenge, CATEGORIES, is_cursor_category, wants_command


# Trailing quit sequences to strip from the keystroke count, longest first.
_QUIT_SEQUENCES = [
    b":wq!\r", b":wq\r", b":x!\r", b":x\r", b":w\r:q\r",
    b":q!\r", b":q\r", b"ZZ", b"ZQ",
]


@dataclass
class GradeResult:
    correct: bool
    keystrokes: int
    par_keys: int
    efficiency: float                 # par/actual, capped 1.0 (1.0 if 0 keys)
    final_buffer: list[str]
    final_cursor: Optional[list[int]]   # [line, col] or None
    command_line: Optional[str]       # the (last) typed ex command, if any
    saved: bool                       # did the user write the buffer?
    aborted: bool                     # vim failed to run at all
    message: str = ""
    keys_typed: str = ""              # the player's own moves, readable (no quit)

    @property
    def stars(self) -> str:
        if not self.correct:
            return "✗ incorrect"
        pct = int(round(self.efficiency * 100))
        return f"✓ correct · {self.keystrokes} keys vs par {self.par_keys} ({pct}% efficient)"


# ---------------------------------------------------------------------------
# vim discovery / launch
# ---------------------------------------------------------------------------

def find_editor() -> Optional[str]:
    """Prefer nvim, fall back to vim."""
    for cand in ("nvim", "vim"):
        path = shutil.which(cand)
        if path:
            return path
    return None


# Display-only niceties for an INTERACTIVE drill.  Injected via -c at startup,
# which is NOT logged to the scriptout — so they never change keystroke counts.
# We deliberately do NOT load the user's real vimrc: a config that auto-formats
# or strips whitespace on save would rewrite the buffer and break grading.  This
# is plain nvim with the handful of things a practice session actually wants.
#
# The q:/q//q? mappings disable the command-line WINDOW — a notorious beginner
# trap (pressing q then : opens a tiny editor that looks frozen).  Macro
# recording (q{a-z}) is untouched, and no challenge solution uses q:.
_INTERACTIVE_SETTINGS = (
    "set number relativenumber showcmd ruler cursorline scrolloff=3 "
    "laststatus=2 incsearch hlsearch | syntax on "
    "| nnoremap q: <Nop> | nnoremap q/ <Nop> | nnoremap q? <Nop>"
)


def _vim_list(lines: list[str]) -> str:
    """A Vimscript single-quoted list literal of ``lines`` (own quotes doubled)."""
    return "[" + ",".join("'" + ln.replace("'", "''") + "'" for ln in lines) + "]"


def _goal_window_script(goal: list[str]) -> str:
    """A small vim script (to be ``:source``d) that pins the GOAL beside the
    edit buffer during an interactive drill, so the target is in view instead of
    held in memory.

    Layout: edit buffer on the LEFT, a read-only GOAL pane on the RIGHT.  The
    pane is a throwaway ``nofile`` scratch buffer (never written, wiped on
    close) and is stripped of numbers/cursorline so it reads as reference, not
    something to edit.

    Because there are now two windows, a bare ``:wq`` / ``:q`` would close only
    one and leave vim open — so every quit form is remapped to its ``…all``
    sibling: commit (``:wq`` ``:x`` ``ZZ``) writes the edit buffer and quits
    BOTH; abandon (``:q!`` ``ZQ``) drops both with no write.  The ``<expr>``
    guards fire ONLY when the whole command line is exactly that quit word, so a
    substitution pattern containing ``q``/``x``/``wq`` is never touched.

    Delivered as a single ``-c source`` (nvim caps ``-c`` flags at ten) and run
    at startup, so it is never logged to the scriptout — keystroke counts are
    unchanged.
    """
    # The pane is decorative (never graded — grading reads the edit buffer on
    # disk), so it carries a little wording above the target to say what it is.
    pane = [
        "  GOAL — make it look like this:",
        "  (edit the buffer on the left to match)",
        "",
    ] + list(goal)
    return "\n".join([
        "cnoreabbrev <expr> wq (getcmdtype()==':'&&getcmdline()=~#'^wq$')?'xall':'wq'",
        "cnoreabbrev <expr> x  (getcmdtype()==':'&&getcmdline()=~#'^x$')?'xall':'x'",
        "cnoreabbrev <expr> q  (getcmdtype()==':'&&getcmdline()=~#'^q$')?'qall':'q'",
        "nnoremap ZZ :xall<CR>",
        "nnoremap ZQ :qall!<CR>",
        "botright vnew",
        f"call setline(1, {_vim_list(pane)})",
        "setlocal buftype=nofile bufhidden=wipe nomodifiable "
        "nonumber norelativenumber nocursorline nolist nospell",
        "let &l:statusline=' ── GOAL ──   :wq save · :q! bail · read-only '",
        # Snug to the pane's own widest line (header or goal), but never wider
        # than half the terminal — the edit window keeps a fair share so its
        # lines don't wrap while you work.
        "let s:gw = max(map(getline(1,'$'), 'strdisplaywidth(v:val)')) + 2",
        "execute 'vertical resize' min([s:gw, &columns/2])",
        "wincmd p",
        "",
    ])


def _build_argv(editor: str, tmpfile: str, scriptout: str, cursorfile: str,
                playback: Optional[str],
                start_cursor: Optional[list[int]] = None,
                interactive: bool = False,
                goal_script: Optional[str] = None) -> list[str]:
    # -u NONE / -i NONE : clean config so par counts are stable and no user
    #   autocmd (format-on-save, trim-whitespace, …) can mangle the buffer.
    # -N : nocompatible (matters for vim; harmless for nvim).
    # The autocmd records the final cursor position on exit for motion grading.
    autocmd = (
        "autocmd VimLeave * call writefile("
        f"[line('.').' '.col('.')], '{cursorfile}')"
    )
    argv = [editor, "-u", "NONE", "-i", "NONE", "-N", "-c", autocmd]
    # `-c` commands run at startup and are NOT logged to the scriptout, so none
    # of these affect key counts.  Niceties only when a human is watching.
    if interactive:
        argv += ["-c", _INTERACTIVE_SETTINGS]
        # Pin the goal beside the buffer (buffer-graded categories only — cursor
        # drills already highlight their target and have no goal buffer).  The
        # script ends focused back on the edit window, so the start-cursor jump
        # below lands there.
        if goal_script:
            argv += ["-c", f"source {goal_script}"]
    if start_cursor and list(start_cursor) != [1, 1]:
        argv += ["-c", f"call cursor({int(start_cursor[0])},{int(start_cursor[1])})"]
    argv += ["-W", scriptout]
    if playback is not None:
        argv += ["-s", playback]
    argv.append(tmpfile)
    return argv


# ---------------------------------------------------------------------------
# core: run vim on a challenge
# ---------------------------------------------------------------------------

def run_attempt(challenge: Challenge, category: str,
                playback: Optional[str] = None,
                editor: Optional[str] = None) -> GradeResult:
    """Launch vim on ``challenge.start`` and grade the outcome.

    If ``playback`` is given (a string of keystrokes, ``\\x1b`` for Esc), vim
    runs headlessly via ``-s`` — used by the test suite and the build's par
    computation, with no display niceties so counts stay byte-stable.  Otherwise
    vim runs interactively (a human edits by hand) on a clean ``-u NONE`` base
    plus display-only niceties (relativenumber, syntax, showcmd, …).
    """
    interactive = playback is None
    editor = editor or find_editor()
    if editor is None:
        return GradeResult(False, 0, challenge.par_keys, 0.0, list(challenge.start),
                           None, None, False, True,
                           "No vim or nvim found on PATH.")

    workdir = tempfile.mkdtemp(prefix="vimhjkl_")
    tmpfile = os.path.join(workdir, "buffer.txt")
    scriptout = os.path.join(workdir, "keys.log")
    cursorfile = os.path.join(workdir, "cursor")
    playback_file: Optional[str] = None

    # The start buffer.  Trailing newline so vim sees N complete lines.
    with open(tmpfile, "w", encoding="utf-8") as fh:
        fh.write("\n".join(challenge.start))
        if challenge.start:
            fh.write("\n")

    if playback is not None:
        playback_file = os.path.join(workdir, "play.keys")
        with open(playback_file, "wb") as fh:
            fh.write(playback.encode("utf-8"))

    # Show the goal in a side pane during interactive drills, but not for cursor
    # (motion) categories — those navigate a fixed buffer to a highlighted target
    # and carry no goal buffer to display.
    goal_script: Optional[str] = None
    if interactive and not is_cursor_category(category) and challenge.goal:
        goal_script = os.path.join(workdir, "goal.vim")
        with open(goal_script, "w", encoding="utf-8") as fh:
            fh.write(_goal_window_script(challenge.goal))
    argv = _build_argv(editor, tmpfile, scriptout, cursorfile, playback_file,
                       start_cursor=challenge.start_cursor, interactive=interactive,
                       goal_script=goal_script)

    try:
        if playback is not None:
            subprocess.run(argv, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30, check=False)
        else:
            # Interactive: inherit the real tty so vim draws normally.
            subprocess.run(argv, check=False)
    except subprocess.TimeoutExpired:
        return GradeResult(False, 0, challenge.par_keys, 0.0, list(challenge.start),
                           None, None, False, True, "vim timed out.")
    except OSError as exc:
        return GradeResult(False, 0, challenge.par_keys, 0.0, list(challenge.start),
                           None, None, False, True, f"could not launch vim: {exc}")

    # --- read back results -------------------------------------------------
    final_buffer = _read_buffer(tmpfile)
    raw_keys = clean_scriptout(_read_bytes(scriptout))
    final_cursor = _read_cursor(cursorfile)
    norm_keys = _normalized_bytes(raw_keys)   # typo/Esc-normalised, quit intact
    keystrokes = count_keystrokes(raw_keys)
    keys_typed = _render_tokens(_effective_tokens(raw_keys))
    # `saved` / command detection run on the normalised stream so a ':wq' typed
    # with a corrected typo is still recognised as a write / quit.
    command_line = _last_command_line(norm_keys)
    saved = _has_write(norm_keys)

    _cleanup(workdir)

    return _score(challenge, category, final_buffer, final_cursor,
                  keystrokes, command_line, saved, keys_typed)


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _score(challenge: Challenge, category: str, final_buffer: list[str],
           final_cursor: Optional[list[int]], keystrokes: int,
           command_line: Optional[str], saved: bool,
           keys_typed: str = "") -> GradeResult:
    spec = CATEGORIES.get(category)
    correct = False
    message = ""

    if spec is not None and spec.grade_kind == "cursor":
        # Motion: cursor must land on target; buffer must be untouched.
        if challenge.target is not None and final_cursor is not None:
            correct = list(final_cursor) == list(challenge.target)
        if final_buffer != list(challenge.start):
            correct = False
            message = "buffer was modified — a motion should not change text."
        elif not correct and final_cursor is not None:
            message = (f"landed at {final_cursor}, target was {challenge.target}.")
    else:
        # Buffer transform.
        correct = final_buffer == list(challenge.goal)
        if not saved and final_buffer == list(challenge.start) and challenge.goal != challenge.start:
            message = "you quit without saving (:wq writes the buffer)."
        # Command categories (:g, :s, :normal, ranges) drill the EX command
        # itself — reaching the goal by hand-editing (no ':') doesn't count,
        # even if the resulting buffer matches.  This is the one place a
        # technique is hard-enforced: there is no non-command path here worth
        # rewarding.  We require only that *a* command did it, not its exact
        # form (`:3s` vs `:'a,'b s` are both valid), so clever paths still pass.
        if correct and wants_command(category) and command_line is None:
            correct = False
            message = ("this drill wants the change made with ONE :ex command "
                       "(:s, :g, :normal …) — you edited it by hand.")

    efficiency = _efficiency(challenge.par_keys, keystrokes)
    return GradeResult(
        correct=correct,
        keystrokes=keystrokes,
        par_keys=challenge.par_keys,
        efficiency=efficiency,
        final_buffer=final_buffer,
        final_cursor=final_cursor,
        command_line=command_line,
        saved=saved,
        aborted=False,
        message=message.strip(),
        keys_typed=keys_typed,
    )


def _efficiency(par: int, actual: int) -> float:
    if actual <= 0:
        return 1.0
    return min(1.0, par / actual)


# ---------------------------------------------------------------------------
# scriptout parsing
# ---------------------------------------------------------------------------

# nvim/vim write internal pseudo-keys to the scriptout using the special-key
# encoding 0x80 KS1 KS2.  The KS_EXTRA bucket (KS1 == 0xfd) holds non-keystroke
# events such as CursorHold/focus, which leak into the log after some commands
# (notably f/t character searches).  They are not keys the user pressed, so we
# drop them before counting.  Real special keys (Esc=0x1b, <C-r>=0x12, arrows
# encoded as 0x80 'k' '..') do not use the 0xfd bucket and survive untouched.
_INTERNAL_KEY = re.compile(rb"\x80\xfd.", re.DOTALL)


def clean_scriptout(raw: bytes) -> bytes:
    return _INTERNAL_KEY.sub(b"", raw)


# Efficiency should measure the *technique*, not typing accuracy.  Keys are
# processed as logical TOKENS, not raw bytes, because some keys serialise as
# multi-byte sequences: nvim's termcap special keys (Backspace = 0x80 'k' 'b',
# arrows = 0x80 'k' {u,d,l,r}) and, under -s playback, ANSI escapes (arrows =
# 0x1b '[' {A..D}).  Counting bytes would over-count those AND miss the
# command-line Backspace entirely (which is why a typo'd ':wq' used to be
# counted in full).

def _tokenize(raw: bytes) -> list[bytes]:
    """Split a key stream into one-keystroke tokens."""
    toks: list[bytes] = []
    i, n = 0, len(raw)
    while i < n:
        b = raw[i]
        if b == 0x80 and i + 3 <= n:                          # nvim special key
            toks.append(raw[i:i + 3]); i += 3
        elif b == 0x1b and i + 3 <= n and raw[i + 1] == 0x5b:  # ANSI escape (arrows)
            toks.append(raw[i:i + 3]); i += 3
        else:
            toks.append(raw[i:i + 1]); i += 1
    return toks


# Tokens that erase the previous keystroke (Backspace), across editing contexts:
# insert mode logs DEL (0x7f) or BS (0x08 == <C-h>); the command line logs the
# termcap key 0x80 'k' 'b'.  A run of repeated <Esc> collapses to one press.
_BACKSPACE_TOKENS = {b"\x7f", b"\x08", b"\x80kb"}
_ESC_TOKEN = b"\x1b"


def _normalize_tokens(toks: list[bytes]) -> list[bytes]:
    out: list[bytes] = []
    for t in toks:
        if t in _BACKSPACE_TOKENS:
            if out:
                out.pop()            # a Backspace undoes the keystroke before it
            continue                 # the Backspace itself is not counted
        if t == _ESC_TOKEN and out and out[-1] == _ESC_TOKEN:
            continue                 # collapse a run of repeated Esc
        out.append(t)
    return out


def _normalized_bytes(raw: bytes) -> bytes:
    """Cleaned + typo/Esc-normalised key stream (trailing quit NOT yet stripped)."""
    return b"".join(_normalize_tokens(_tokenize(clean_scriptout(raw))))


def _effective_tokens(raw: bytes) -> list[bytes]:
    """The logical keys we score: normalised, with a recognised trailing quit gone."""
    return _tokenize(strip_quit(_normalized_bytes(raw)))


def count_keystrokes(raw: bytes) -> int:
    """Effective keystrokes: logical keys after typo/Esc-normalisation, minus quit."""
    return len(_effective_tokens(raw))


# Readable names for multi-byte tokens; 0x1c–0x1f have no clean <C-letter> form.
_TOKEN_NAMES = {
    b"\x80kb": "<BS>", b"\x80kD": "<Del>",
    b"\x80ku": "<Up>", b"\x80kd": "<Down>",
    b"\x80kl": "<Left>", b"\x80kr": "<Right>",
    b"\x80kh": "<Home>", b"\x80@7": "<End>",
    b"\x1b[A": "<Up>", b"\x1b[B": "<Down>", b"\x1b[C": "<Right>", b"\x1b[D": "<Left>",
}
_CTRL_SPECIAL = {0x1c: "<C-\\>", 0x1d: "<C-]>", 0x1e: "<C-^>", 0x1f: "<C-_>"}


def _render_token(t: bytes) -> str:
    if t in _TOKEN_NAMES:
        return _TOKEN_NAMES[t]
    if len(t) == 3:
        return f"<k{t[1:].decode('latin1')}>" if t[0] == 0x80 else "<Esc>"
    b = t[0]
    if b == 0x1b:
        return "<Esc>"
    if b == 0x0d:
        return "<CR>"
    if b == 0x09:
        return "<Tab>"
    if b in (0x7f, 0x08):
        return "<BS>"
    if b == 0x00:
        return "<Nul>"
    if 0x01 <= b <= 0x1a:
        return f"<C-{chr(b + 0x60)}>"
    if b in _CTRL_SPECIAL:
        return _CTRL_SPECIAL[b]
    if 0x20 <= b <= 0x7e:
        return chr(b)
    return f"<{b:#04x}>"


def _render_tokens(toks: list[bytes]) -> str:
    return "".join(_render_token(t) for t in toks)


def render_keys(raw: bytes) -> str:
    """Render a key stream as readable tokens (``Cfoo<Esc>``, ``jdd``, ``2w<Up>``)."""
    return _render_tokens(_tokenize(raw))


def strip_quit(raw: bytes) -> bytes:
    for seq in _QUIT_SEQUENCES:
        if raw.endswith(seq):
            return raw[: -len(seq)]
    return raw


def _has_write(raw: bytes) -> bool:
    # Any of the writing quits, or a bare :w.
    return bool(re.search(rb":(?:wq?|x|wq!|update)\b|ZZ", raw))


def _last_command_line(raw: bytes) -> Optional[str]:
    """Return the last typed ex command line (text between ':' and <CR>),
    ignoring the trailing quit command."""
    body = strip_quit(raw)
    # Find ':...\r' command lines.  Naive but adequate: split on \r, take
    # segments that start with ':'.
    text = body.decode("utf-8", errors="replace")
    matches = re.findall(r":([^\r\n]*)\r", text)
    # filter out pure quit/write commands
    cmds = [m for m in matches if not re.fullmatch(r"\s*w?q!?\s*|x!?\s*|w\s*", m)]
    return cmds[-1] if cmds else None


# ---------------------------------------------------------------------------
# file IO helpers
# ---------------------------------------------------------------------------

def _read_buffer(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return []
    if text.endswith("\n"):
        text = text[:-1]
    if text == "":
        return [""] if _file_nonempty(path) else []
    return text.split("\n")


def _file_nonempty(path: str) -> bool:
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def _read_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _read_cursor(path: str) -> Optional[list[int]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            parts = fh.read().split()
    except OSError:
        return None
    if len(parts) != 2:
        return None
    try:
        return [int(parts[0]), int(parts[1])]
    except ValueError:
        return None


def _cleanup(workdir: str) -> None:
    try:
        shutil.rmtree(workdir, ignore_errors=True)
    except OSError:
        pass
