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
COMMON="--language dutch --board 11 --cores 24 --no-main-blanks --extra-probing 0 --log"

run () {
  local label="$1"; shift
  echo "=== $label START $(date '+%F %T') (epoch $(date +%s)) ==="
  timeout "$CAP" ./.venv/bin/python -u max_turn_score.py $COMMON "$@" \
      --output "$OUT/n11_${label}.out" > "$OUT/n11_${label}.fulllog" 2>&1 &
  local PID=$!
  local t0; t0=$(date +%s)
  : > "$OUT/n11_${label}.mem"
  while kill -0 "$PID" 2>/dev/null; do
    local rss; rss=$(awk '/^VmRSS/{print $2}' "/proc/$PID/status" 2>/dev/null)
    echo "$(( $(date +%s) - t0 )) ${rss:-NA}" >> "$OUT/n11_${label}.mem"
    sleep 5
  done
  echo "=== $label END $(date '+%F %T') ==="
}

run coreoff
run coreon --bool-core
echo "ALL DONE $(date '+%F %T')"
