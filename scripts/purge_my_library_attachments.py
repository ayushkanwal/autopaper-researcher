#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from autopaper.cli import main  # noqa: E402


def _translated_args(argv: list[str]) -> list[str]:
    args = ["purge-attachments", *argv]
    if "--dry-run" not in argv and "--confirm-my-library" not in argv:
        args.append("--confirm-my-library")
    return args


if __name__ == "__main__":
    raise SystemExit(main(_translated_args(sys.argv[1:])))
