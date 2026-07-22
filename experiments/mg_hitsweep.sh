#!/bin/bash
# Fleet-shard: loop triplets in rank order (stride), run mask-pool joint solver per triple.
# Op elke 1-component HIT: decompose+score_game-arbiter -> ECHTE score. Log valide scores.
# Stop globaal zodra een VALIDE score > RECORD (mg_BEAT flag). args: SHARD NSHARD [T_ALL] [RANK_MAX]
cd /home/bob/programming/scrabble4
SHARD=$1; NSHARD=$2; TALL=${3:-90}; RANKMAX=${4:-4000}
RECORD=3974
LOG=experiments/results/mg_hitsweep_${SHARD}.log
VALID=experiments/results/mg_valid_scores.log
: > "$LOG"
tail -n +2 experiments/results/maxgame_triplerank.tsv | awk -v s="$SHARD" -v n="$NSHARD" -v rmax="$RANKMAX" 'NR<=rmax && NR%n==s' | \
while IFS=$'\t' read -r rank score R0 R14 R7 rest; do
  if [ -f experiments/results/mg_BEAT ]; then echo "stop: record verslagen elders" >>"$LOG"; break; fi
  tag="R${rank}"
  res=$(MGR0="$R0" MGR14="$R14" MGR7="$R7" MGTAG="$tag" \
        MGKMASK=6 MGSEEDS=3 MGTL=15 MGTALL="$TALL" \
        nice -n 12 .venv/bin/python -u experiments/mg_solver3.py 2>&1 | tail -1)
  if echo "$res" | grep -q '\*\*\* HIT'; then
    dec=$(MGTAG="$tag" nice -n 12 .venv/bin/python -u experiments/mg_decompose.py 2>&1 | grep "DECOMP")
    echo "#${rank} core${score} ${R0}/${R7}/${R14}: HIT -> ${dec}" >> "$LOG"
    sc=$(echo "$dec" | grep -oE "SPELSCORE=[0-9]+" | grep -oE "[0-9]+")
    okv=$(echo "$dec" | grep -oE "ok=(True|False)")
    if [ "$okv" = "ok=True" ] && [ -n "$sc" ]; then
      echo "$(date +%H:%M:%S) rank${rank} score=${sc} ${R0}/${R7}/${R14}" >> "$VALID"
      if [ "$sc" -gt "$RECORD" ]; then
        echo ">>> RECORD VERSLAGEN: rank ${rank} score ${sc} > ${RECORD} <<<" >> "$LOG"
        cp experiments/results/mg_game_${tag}.json experiments/results/mg_BEAT_${tag}_${sc}.json
        touch experiments/results/mg_BEAT
        break
      fi
    fi
  else
    echo "#${rank} core${score} ${R0}/${R7}/${R14}: ${res}" >> "$LOG"
  fi
done
echo "shard ${SHARD} klaar" >> "$LOG"
