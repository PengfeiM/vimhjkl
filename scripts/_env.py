"""Tiny stdlib .env loader for the i18n scripts.

Reads KEY=VALUE lines from the repo-root .env (if present) into os.environ.
Existing environment variables win — .env only fills gaps. No dependency,
no shell expansion; quotes around the value are stripped.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    p = path or (REPO_ROOT / ".env")
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
