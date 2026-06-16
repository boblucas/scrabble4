#!/bin/bash
# Wrapper for the varmax knap-UB with/without check + pruning benchmark (same allowlist as regress.sh).
set -u
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then DEFPY=.venv/bin/python; else DEFPY=python3; fi
PY=${PY:-$DEFPY}
"$PY" experiments/xfill_varmax_knap_check.py "$@"
