#!/bin/bash
# Regression harness for the Rust inner solver.
# 1) N=7 DECISION regression: run xfill on every n7_*.txt + h7_*.txt, compare SAT/UNSAT vs the TRUTH line.
# 2) (optional) score check is run separately via xtest.py scorecheck.
# Usage: bash experiments/xfill_rs/regress.sh   (from repo root)
set -u
BIN=experiments/xfill_rs/target/release/xfill
pass=0; fail=0
for f in experiments/xtests/n7_*.txt experiments/xtests/h7_*.txt; do
  truth=$(grep '^TRUTH' "$f" | awk '{print $2}')
  out=$("$BIN" "$f" 2>/dev/null)
  got=$(echo "$out" | awk '{print $1}')
  if [ "$got" = "$truth" ]; then
    pass=$((pass+1))
  else
    fail=$((fail+1))
    echo "FAIL $(basename "$f"): want=$truth got=$got ($out)"
  fi
done
echo "DECISION: $pass/$((pass+fail)) pass"
exit $((fail>0))
