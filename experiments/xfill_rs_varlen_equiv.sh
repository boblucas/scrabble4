#!/bin/bash
# Wrapper: run the variable-length equivalence battery (Python harness) + the artificial-problem
# benchmark.  Kept as a shell entrypoint so it runs under the same allowlist as regress.sh.
set -u
cd "$(dirname "$0")/.."
# Prefer the project venv (has the `toml`/`ortools`/`scrabble` deps the real-board harness needs);
# the synthetic battery + Rust binary need no deps so a bare python3 also works for those.
if [ -x .venv/bin/python ]; then DEFPY=.venv/bin/python; else DEFPY=python3; fi
PY=${PY:-$DEFPY}
echo "=== SYNTHETIC EQUIVALENCE BATTERY ==="
"$PY" experiments/xfill_rs_varlen_equiv.py
eq=$?
echo
echo "=== REAL-BOARD EQUIVALENCE BATTERY ==="
"$PY" experiments/xfill_rs_varlen_equiv_real.py
rl=$?
echo
echo "=== ARTIFICIAL-PROBLEM SPEEDUP BENCHMARK ==="
"$PY" experiments/xfill_rs_varlen_bench.py
bm=$?
[ "$eq" -eq 0 ] && [ "$rl" -eq 0 ] && [ "$bm" -eq 0 ] && echo "VARLEN: ALL OK" || echo "VARLEN: FAILURE"
exit $(( eq || rl || bm ))
