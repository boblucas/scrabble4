#!/bin/bash
set -u
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then DEFPY=.venv/bin/python; else DEFPY=python3; fi
PY=${PY:-$DEFPY}
"$PY" experiments/xfill_varmax_geschenk_stretch.py "$@"
