#!/bin/bash
# RESUME the N=15 oracle certification after a crash/reboot.
# The JSONL ledgers are line-buffered + git-committed, so re-running this RESUMES from the last
# decided combo (skips everything already in the ledger) — no work lost beyond ~20 in-flight solves.
#
# Usage:  bash experiments/RESUME_N15.sh            # resumes the current open mask (9,12) at LB 2008
#         bash experiments/RESUME_N15.sh 0,3,7,8,11,13,14   # resume a different open mask
#
# Current verified state (see memory + experiments/results/oracle_parallel/FINISH*.log):
#   LB = 2008 (N15_best_2008.json, witness-checked).  Bracket [2008, 2028].
#   mask (0,3,7,8,11,12,14) CERTIFIED = 2008.  OPEN masks (each ~4M+ combos):
#     0,3,7,9,11,12,14   0,3,7,8,11,13,14   0,3,7,9,11,13,14
cd /home/bob/programming/scrabble4
source .venv/bin/activate 2>/dev/null
MASK="${1:-0,3,7,9,11,12,14}"
LB=2008
TAG=$(echo "$MASK" | tr -d ',')
LOG="experiments/results/oracle_parallel/run_${TAG}_lb${LB}.log"
echo "Resuming oracle: mask=$MASK LB=$LB (skips combos already in the ledger). Log: $LOG"
nohup python -u experiments/n15_oracle_parallel.py \
  --word geschenkcheques --mask "$MASK" --lb "$LB" --workers 20 --cap 1200 \
  >> "$LOG" 2>&1 &
echo "launched PID $! — tail -f $LOG to watch; a board >2008 lands in experiments/results/turns/N15_best_<n>.json"
