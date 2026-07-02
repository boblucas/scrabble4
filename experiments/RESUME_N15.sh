#!/bin/bash
# RESUME the N=15 oracle certification after a crash/reboot.        (v2 pipeline, 2026-07-02)
# v2 ledgers are CONTENT-KEYED (combo_key), so resume is sound across processes -- the v1
# positional-id ledgers had PYTHONHASHSEED-dependent id->combo mappings (coverage holes) and are
# quarantined; v2 ignores keyless records.
#
# Usage:  bash experiments/RESUME_N15.sh                    # current open mask (default below)
#         bash experiments/RESUME_N15.sh 0,3,7,8,11,12,14   # a specific mask
#
# Verified state: LB = 2008 (N15_best_2008.json, witness-checked).  ALL FOUR {3,11} masks are
# OPEN under v2 (the v1 mask-(8,12) "EXACTLY 2008" claim was WITHDRAWN 2026-07-02: id-holes +
# blank-score semantics).  Masks: 0,3,7,8,11,12,14 / 0,3,7,9,11,12,14 / 0,3,7,8,11,13,14 /
# 0,3,7,9,11,13,14.
cd /home/bob/programming/scrabble4
source .venv/bin/activate 2>/dev/null
export PYTHONHASHSEED=0            # defense-in-depth; v2 correctness does NOT depend on it
MASK="${1:-0,3,7,8,11,12,14}"
LB=2008
TAG=$(echo "$MASK" | tr -d ',')
LOG="experiments/results/oracle_parallel/run_${TAG}_lb${LB}_v2.log"
echo "Resuming v2 oracle: mask=$MASK LB=$LB (content-keyed resume). Log: $LOG"
nohup python -u experiments/n15_oracle_parallel.py \
  --word geschenkcheques --mask "$MASK" --lb "$LB" --workers 20 --cap 1200 \
  >> "$LOG" 2>&1 &
echo "launched PID $! — tail -f $LOG; a board >$LB lands in experiments/results/turns/N15_best_<n>.json"
