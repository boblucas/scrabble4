#!/bin/bash
# Soundness gate suite for the xfill inner solver.  Run after EVERY solver change; all gates must
# pass before any new LE/MAX verdict is trusted.  Usage:
#   experiments/regress.sh [BIN]        (default experiments/xfill_rs/target/release/xfill)
# Gates:
#   1. N=7 decision regression: every n7_*/h7_* instance's first output token == its TRUTH line
#      (CP-SAT-established ground truth).  26/26 expected.
#   2. deep-col10 score gate: the 3 unconstrained N=11 hard vectors must prove "LE 224"
#      (the Lever-3 joint-knapsack family; a regression here breaks the 850 proof).
#   3. center col0=1 score gate: the 15 center-constrained wall vectors must prove "LE 173"
#      (the place_ok left-span panic family; a regression here breaks the 799 proof).
# All score-gate runs are UNCAPPED in nodes (no MAXNODES -- it would fake LE) with a generous
# wall timeout; "LE" must come from natural completion.
set -u
cd "$(dirname "$0")/.."
BIN=${1:-experiments/xfill_rs/target/release/xfill}
export BIN
fail=0

echo "== gate 1: N=7 decision regression =="
pass=0; tot=0
for f in experiments/xtests/n7_*.txt experiments/xtests/h7_*.txt; do
  tot=$((tot+1))
  truth=$(grep -a '^TRUTH' "$f" | awk '{print $2}')
  got=$(timeout 30 "$BIN" "$f" 2>/dev/null | head -1 | awk '{print $1}')
  if [ "$got" == "$truth" ]; then pass=$((pass+1)); else echo "  FAIL $(basename "$f"): want=$truth got=${got:-none}"; fi
done
echo "  $pass/$tot"
[ "$pass" -eq "$tot" ] || fail=1

echo "== gate 2: deep-col10 LE-224 (unconstrained N=11 proof family) =="
g2=$(printf '%s\n' 11-3-2-7-3-5-11 11-3-2-8-3-5-10 10-3-2-7-4-5-11 | xargs -P 3 -I {} bash -c '
  v="$1"; out=$(timeout 180 "$BIN" "experiments/xtests/r11_bouwfysicus_${v}_sc.txt" --maxscore 224 2>/dev/null | head -1)
  case "$out" in "LE 224"*) echo "  ok   $v ($out)";; *) echo "  FAIL $v: ${out:-no-output}";; esac
' _ {})
echo "$g2" | sort
echo "$g2" | grep -aq FAIL && fail=1

echo "== gate 3: center col0=1 LE-173 (center-constrained proof family) =="
g3=$(printf '%s\n' 1-10-3-10-6-6-10 1-10-3-8-9-6-10 1-10-5-6-9-6-10 1-10-5-8-6-6-10 1-10-5-8-8-6-10 \
              1-10-6-7-6-6-10 1-10-7-6-8-6-10 1-11-3-10-6-6-10 1-11-5-8-6-6-10 1-11-7-6-6-6-10 \
              1-9-3-10-8-6-10 1-9-5-8-8-6-10 1-9-6-8-8-6-10 1-9-7-8-6-6-10 1-9-8-7-6-6-10 \
| xargs -P 6 -I {} bash -c '
  v="$1"; out=$(timeout 180 "$BIN" "experiments/xtests/o11_bouwfysicus_${v}_sc.txt" --maxscore 173 2>/dev/null | head -1)
  case "$out" in "LE 173"*) echo "  ok   $v";; *) echo "  FAIL $v: ${out:-no-output}";; esac
' _ {})
echo "$g3" | sort
echo "$g3" | grep -aq FAIL && fail=1

if [ "$fail" -eq 0 ]; then echo "ALL GATES GREEN"; else echo "GATE FAILURE -- do NOT trust new verdicts"; fi
exit "$fail"
