#!/usr/bin/env python3
"""Wrapper CLI script forwarding to gst_recon_pipeline.run_pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gst_recon_pipeline.run_pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
