"""Shared pytest setup: put the backend and control-advisor packages on the
import path so tests can import them without installing anything."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "control-advisor"))
