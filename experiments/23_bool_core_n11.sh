#!/bin/bash
# Experiment 23: does bool_core (CP-SAT optimize_with_core) help PROVE optimality on the
# N=11 merged model (stage 2 with single_component), and how much memory does it eat?
#
# Controlled A/B: identical flags, toggling only --bool-core. We isolate bool_core by setting
# --extra-probing 0 (so probing_max_lp isn't also eating memory / closing the bound). N=11 is the
# merged path (W<=11 -> single_component in stage 2), i.e. the same model shape we want to prove
# at N=13 -- just small enough to measure cheaply first.
#
# Records per run: full solver log (bound trajectory) + a CSV of VmRSS(kB) sampled every 5s.
# Analyse afterwards: time of the first "status: OPTIMAL" stage-2 block, and peak/curve of RSS.
set -u
cd /home/bob/programming/scrabble4
OUT=experiments/results/turns
CAP=${CAP:-1500}          # per-run wall cap (s)
PROBING=${PROBING:-4}     # extra probing_max_lp workers; 0 isolates bool_core, 4 is the proving config
COMMON="--language dutch --board 11 --cores 24 --no-main-blanks --extra-probing $PROBING --log"
LBL="p${PROBING}"         # label prefix so different probing levels don't clobber each other

run () {
  local label="$1"; shift
  echo "=== $label START $(date '+%F %T') (epoch $(date +%s)) ==="
  # launch python DIRECTLY (no timeout wrapper) so PID is the solver itself and VmRSS is its real
  # memory; enforce the wall cap in the sampler loop.
  ./.venv/bin/python -u max_turn_score.py $COMMON "$@" \
      --output "$OUT/n11_${label}.out" > "$OUT/n11_${label}.fulllog" 2>&1 &
  local PID=$!
  local t0; t0=$(date +%s)
  : > "$OUT/n11_${label}.mem"
  while kill -0 "$PID" 2>/dev/null; do
    local el=$(( $(date +%s) - t0 ))
    if [ "$el" -ge "$CAP" ]; then echo "  (cap ${CAP}s hit, stopping $label)"; kill "$PID" 2>/dev/null; sleep 2; kill -9 "$PID" 2>/dev/null; break; fi
    local rss; rss=$(awk '/^VmRSS/{print $2}' "/proc/$PID/status" 2>/dev/null)
    echo "$el ${rss:-NA}" >> "$OUT/n11_${label}.mem"
    sleep 5
  done
  echo "=== $label END $(date '+%F %T') ==="
}

run "${LBL}_coreoff"
run "${LBL}_coreon" --bool-core
echo "ALL DONE $(date '+%F %T')"
