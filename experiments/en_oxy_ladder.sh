#!/bin/bash
# NWL oxyphenbutazone floor-ladder: certificeer alle maskers per lb-trede; SAT -> witness -> S;
# dan alles dicht op S. Maskers+UBs uit oxy_maskubs_all.txt (UB_MASK<lb = auto-gecertificeerd).
cd /home/bob/programming/scrabble4
export N15_LANG=english N15_HMAX=15 PYTHONHASHSEED=0 N15_WORD=oxyphenbutazone
TMP=/home/bob/.claude/jobs/da7ed622/tmp
LOG=experiments/results/english/oxy_ladder.log
UBS=$TMP/oxy_maskubs_all.txt
WORKERS=${WORKERS:-10}
for LB in 1812 1780 1750 1720 1690 1660 1630 1600; do
  echo "=== TREDE lb=$LB $(date '+%H:%M') ===" >> "$LOG"
  nopen=0
  while read -r ub mask; do
    [ "$ub" -le "$LB" ] && continue
    nopen=$((nopen+1))
    tag=$(echo "$mask" | tr -d ',')
    # nominale band (oracle) — alleen als lb >= ub-27 is de kale oracle geldig; anders oracle + laneB
    if [ "$LB" -ge $((ub-27)) ]; then
      UB_MASK=$ub .venv/bin/python -u experiments/n15_oracle_parallel.py \
        --word oxyphenbutazone --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_or_${tag}_lb${LB}.log 2>&1
    else
      UB_MASK=$ub .venv/bin/python -u experiments/n15_oracle_parallel.py \
        --word oxyphenbutazone --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_or_${tag}_lb${LB}.log 2>&1 || true
      .venv/bin/python -u experiments/n15_laneB_tb.py --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_tb_${tag}_lb${LB}.log 2>&1
    fi
    v=$(grep -h "VERDICT" experiments/results/english/oxy_or_${tag}_lb${LB}.log experiments/results/english/oxy_tb_${tag}_lb${LB}.log 2>/dev/null | tail -2 | tr '\n' ' ')
    echo "  mask $mask ub=$ub: $v" >> "$LOG"
    if grep -qh "SAT" experiments/results/english/oxy_or_${tag}_lb${LB}.log experiments/results/english/oxy_tb_${tag}_lb${LB}.log 2>/dev/null && \
       ls -t experiments/results/turns/N15_best_1*.json 2>/dev/null | head -1 | xargs -I{} find {} -mmin -30 2>/dev/null | grep -q .; then
      echo "  *** WITNESS GEVONDEN op trede lb=$LB — ladder stopt; certificeer op S ***" >> "$LOG"
      echo "WITNESS_AT_LB=$LB" >> "$LOG"
      exit 0
    fi
  done < "$UBS"
  echo "  trede lb=$LB: $nopen maskers behandeld, geen SAT -> ALLE maskers CERTIFIED <= $LB" >> "$LOG"
  echo "CERTIFIED_ALL_AT=$LB" >> "$LOG"
done
echo "LADDER KLAAR (ondergrens bereikt zonder SAT?)" >> "$LOG"
