#!/usr/bin/env python3
"""Thin CLI alias for python -m debugger."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root or headless_harness_datagen/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debugger.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
