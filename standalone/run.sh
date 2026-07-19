#!/usr/bin/env bash
# RegMap standalone launcher for Linux / macOS.  Usage:  ./run.sh
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo
  echo "Python 3 was not found. Install it and re-run, e.g.:"
  echo "  Debian/Ubuntu:  sudo apt update && sudo apt install -y python3 python3-venv python3-pip nmap"
  echo "  macOS:          brew install python nmap"
  echo
  exit 1
fi

exec "$PY" launcher.py "$@"
