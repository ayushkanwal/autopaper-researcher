#!/usr/bin/env python3
"""Legacy wrapper for the packaged run-once ingest command."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from autopaper.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["run-once", *sys.argv[1:]]))
