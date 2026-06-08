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
# Seed the proven_lower with a VERIFIED legal-turn lower bound.  exp34 (the seed finder) writes the best
# verified turn it has witnessed to experiments/results/turns/N<W>_seed.json as `best_total` (a real legal
# 4-connected board, independently re-checked).  We read that as the seed if present; else fall back to the
# known N=11 bouwfysicus 850.  Seeding is what lets exp33 prove `LE` fast (the inner can't witness high
# boards from scratch -- the documented improver wall), so a good seed is essential for a tight LOWER.
SEEDFILE="experiments/results/turns/N${N}_seed.json"
SEED=""
if [ -f "$SEEDFILE" ]; then
  SVAL=$(python -c "import json;d=json.load(open('$SEEDFILE'));print(d.get('best_total',-1) or -1)" 2>/dev/null || echo -1)
  if [ "${SVAL:-0}" -gt 0 ] 2>/dev/null; then SEED="--seed-lower $SVAL"; fi
fi
if [ -z "$SEED" ] && [ "$N" = "11" ]; then SEED="--seed-lower 850"; fi
echo "seed for N=$N: ${SEED:-<none>}"

# Per-inner-call cap (VCAP) kept modest so one hard length-vector can't stall a main word; per-main-word
# overall cap (VMAXSEC) bounds the vertical search per word.  The unresolved residual contributes to the
# sound UPPER bracket (main_score + vertical_upper), which stays valid.
# setsid -> a fresh session fully detached from this shell (immune to SIGHUP when the launching shell
# exits).  CORES kept modest (8) so multiple board sweeps + any concurrent track coexist on the box
# without oversubscribing; persistence after every main word makes a kill harmless (just re-run to resume).
CORES="${CORES:-8}"
setsid python -u experiments/33_full_turn_bracket.py "$N" --scale-tiles --blanks \
      $SEED --vcap 90 --vmaxsec 1800 --gvub-cap 120 --cores "$CORES" \
      --xfill experiments/xfill_rs/target/release/xfill_frozen \
      --out "$OUT" >> "$LOG" 2>&1 < /dev/null &
echo "launched exp33 N=$N  PID $!  (cores=$CORES, setsid-detached)"
echo "  progress : $OUT"
echo "  log      : $LOG"
echo "  check    : tail -f $LOG    |    python -c \"import json;d=json.load(open('$OUT'));print(d['proven_lower'],d.get('sound_upper'),len(d['evaluated']))\""
