#!/bin/bash
# Certify the 19 thin dutch2026 pairs (UB <= 2127) at LB=2100, sequentially.
cd /home/bob/programming/scrabble4
source .venv/bin/activate 2>/dev/null
export N15_LANG=dutch2026 N15_HMAX=15 XHMAX=15 XDICT=experiments/xtests/dict_2026_15.txt
export PYTHONHASHSEED=0
LOG=experiments/results/oracle_parallel/run_2026_thin.log
while IFS=$'\t' read -r WORD MASK UB; do
  case "$WORD" in geschenkcheques) continue;; esac
  echo "=== $WORD $MASK (UB $UB) ===" >> "$LOG"
  UB_MASK=$UB python -u experiments/n15_oracle_parallel.py \
    --word "$WORD" --mask "$MASK" --lb 2100 --workers 20 --cap 1200 >> "$LOG" 2>&1
  grep -qE "NEW-LB" "$LOG" && { echo "NEW LB FOUND -- stopping sweep" >> "$LOG"; break; }
done < experiments/results/n15_2026_open_pairs.txt
echo "THIN SWEEP DONE" >> "$LOG"
