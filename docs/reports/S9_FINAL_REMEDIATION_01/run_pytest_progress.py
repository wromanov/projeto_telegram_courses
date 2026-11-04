from __future__ import annotations

import faulthandler
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(REPORT_DIR))

import pytest_progress_plugin  # noqa: E402


faulthandler.dump_traceback_later(5, repeat=True, file=sys.stderr)
try:
    raise SystemExit(pytest.main(sys.argv[1:], plugins=[pytest_progress_plugin]))
finally:
    faulthandler.cancel_dump_traceback_later()
