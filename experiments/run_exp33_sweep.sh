#!/usr/bin/env bash
# Launch the exp33 full-turn [proven-lower, sound-upper] bracket sweeps in the BACKGROUND, detached,
# persisted + resumable.  Uses the FROZEN xfill binary for stable results.  Each board writes its own
# progress JSON under experiments/results/turns/N<W>_fullturn.json and a stdout log alongside.
#
# Resume: just re-run the same command -- exp33 reads the progress file and skips evaluated main words.
#
# Usage:  experiments/run_exp33_sweep.sh <11|13|15>
set -euo pipefail
cd /home/bob/programming/scrabble4
source .venv/bin/activate

N="${1:?usage: run_exp33_sweep.sh <11|13|15>}"
OUT="experiments/results/turns/N${N}_fullturn.json"
LOG="experiments/results/turns/N${N}_fullturn.log"

# Seed the global proven_lower with the known bouwfysicus turn lower bound for N=11 (850 = 626 main +
# 224 verticals, an externally-validated real legal board -- see maxturn-n11-fastinner-result).  For
# N=13/15 there is no known seed yet; start from -1 (the inner must witness boards, which is the wall --
# the run will mostly produce sound UPPER brackets + whatever lower bounds the inner can witness).
case "$N" in
  11) SEED="--seed-lower 850" ;;
  *)  SEED="" ;;
esac

# Per-inner-call cap (VCAP) kept modest so one hard length-vector can't stall a main word; per-main-word
# overall cap (VMAXSEC) bounds the vertical search per word.  The unresolved residual contributes to the
# sound UPPER bracket (main_score + vertical_upper), which stays valid.
nohup python -u experiments/33_full_turn_bracket.py "$N" --scale-tiles --blanks \
      $SEED --vcap 90 --vmaxsec 1800 --gvub-cap 120 \
      --xfill experiments/xfill_rs/target/release/xfill_frozen \
      --out "$OUT" >> "$LOG" 2>&1 &
echo "launched exp33 N=$N  PID $!"
echo "  progress : $OUT"
echo "  log      : $LOG"
echo "  check    : tail -f $LOG    |    python -c \"import json;d=json.load(open('$OUT'));print(d['proven_lower'],d.get('sound_upper'),len(d['evaluated']))\""
