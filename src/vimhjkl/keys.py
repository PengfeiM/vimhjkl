"""Translate a human-readable keystroke string into the raw bytes vim consumes.

Solutions in the curriculum are written readably, e.g. ``ci"new<Esc>`` or
``:%s/x/y/g<CR>``.  This converts the ``<...>`` tokens to the actual control
bytes so the string can be fed to ``vim -s`` for verification and replay.
"""

from __future__ import annotations

import re

_TOKENS = {
    "<Esc>": "\x1b",
    "<CR>": "\r",
    "<Enter>": "\r",
    "<Tab>": "\t",
    "<BS>": "\x7f",
    "<Space>": " ",
    "<lt>": "<",
    "<Nul>": "\x00",
    "<Up>": "\x1b[A",
    "<Down>": "\x1b[B",
    "<Right>": "\x1b[C",
    "<Left>": "\x1b[D",
}

# <C-x> control chords -> the corresponding control byte.
_CTRL_RE = re.compile(r"<C-([A-Za-z\[\]\\^_])>")
_TOKEN_RE = re.compile(r"<[^>]+>")


def _ctrl_byte(ch: str) -> str:
    return chr(ord(ch.upper()) & 0x1F)


def translate(s: str) -> str:
    """Return the raw key string (with real control bytes)."""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "<":
            m = _TOKEN_RE.match(s, i)
            if m:
                tok = m.group(0)
                if tok in _TOKENS:
                    out.append(_TOKENS[tok])
                    i = m.end()
                    continue
                cm = _CTRL_RE.match(tok)
                if cm:
                    out.append(_ctrl_byte(cm.group(1)))
                    i = m.end()
                    continue
            # not a recognised token: literal '<'
            out.append("<")
            i += 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)
