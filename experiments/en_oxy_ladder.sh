#!/bin/bash
# NWL oxyphenbutazone floor-ladder: certificeer alle maskers per lb-trede; SAT -> witness -> S;
# dan alles dicht op S. Maskers+UBs uit oxy_maskubs_all.txt (UB_MASK<lb = auto-gecertificeerd).
cd /home/bob/programming/scrabble4
export N15_LANG=english N15_HMAX=15 PYTHONHASHSEED=0 N15_WORD=oxyphenbutazone
TMP=/home/bob/.claude/jobs/da7ed622/tmp
LOG=experiments/results/english/oxy_ladder.log
UBS=$TMP/oxy_maskubs_all.txt
WORKERS=${WORKERS:-10}
for LB in 1780 1750 1720 1690 1660 1630 1600; do
  echo "=== TREDE lb=$LB $(date '+%H:%M') ===" >> "$LOG"
  nopen=0
  while read -r ub mask; do
    [ "$ub" -le "$LB" ] && continue
    nopen=$((nopen+1))
    tag=$(echo "$mask" | tr -d ',')
    # SOUND combinatie: oracle (nominale+vert-blank-band; TB_COMPANION bij lage lb) EN laneB (TB-slice)
    if [ "$LB" -ge $((ub-27)) ]; then
      UB_MASK=$ub .venv/bin/python -u experiments/n15_oracle_parallel.py \
        --word oxyphenbutazone --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_or_${tag}_lb${LB}.log 2>&1
      grep -q "VERDICT: CERTIFIED" experiments/results/english/oxy_or_${tag}_lb${LB}.log && okor=1 || okor=0
      oktb=1   # turn-blank uitgesloten door 27-pt-argument bij lb>=ub-27
    else
      TB_COMPANION=1 UB_MASK=$ub .venv/bin/python -u experiments/n15_oracle_parallel.py \
        --word oxyphenbutazone --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_or_${tag}_lb${LB}.log 2>&1
      grep -q "VERDICT: CERTIFIED" experiments/results/english/oxy_or_${tag}_lb${LB}.log && okor=1 || okor=0
      .venv/bin/python -u experiments/n15_laneB_tb.py --mask "$mask" --lb "$LB" --workers "$WORKERS" --cap 900 \
        >> experiments/results/english/oxy_tb_${tag}_lb${LB}.log 2>&1
      grep -q "CERTIFIED" experiments/results/english/oxy_tb_${tag}_lb${LB}.log && oktb=1 || oktb=0
    fi
    if [ "$okor" -eq 1 ] && [ "$oktb" -eq 1 ]; then
      echo "  mask $mask ub=$ub: BEIDE-CERTIFIED <= $LB" >> "$LOG"
    else
      echo "  mask $mask ub=$ub: OPEN (oracle=$okor laneB=$oktb) — trede NIET dicht" >> "$LOG"
      echo "TREDE_OPEN_AT=$LB mask=$mask" >> "$LOG"
    fi
    if grep -qh "SAT" experiments/results/english/oxy_or_${tag}_lb${LB}.log experiments/results/english/oxy_tb_${tag}_lb${LB}.log 2>/dev/null && \
       ls -t experiments/results/turns/N15_best_1*.json 2>/dev/null | head -1 | xargs -I{} find {} -mmin -30 2>/dev/null | grep -q .; then
      echo "  *** WITNESS GEVONDEN op trede lb=$LB — ladder stopt; certificeer op S ***" >> "$LOG"
      echo "WITNESS_AT_LB=$LB" >> "$LOG"
      exit 0
    fi
  done < "$UBS"
  if grep -q "TREDE_OPEN_AT=$LB " "$LOG"; then
    echo "  trede lb=$LB: OPEN maskers aanwezig -> GEEN trede-certificaat" >> "$LOG"
  else
    echo "  trede lb=$LB: $nopen maskers behandeld, geen SAT -> ALLE maskers CERTIFIED <= $LB" >> "$LOG"
    echo "CERTIFIED_ALL_AT=$LB" >> "$LOG"
  fi
done
echo "LADDER KLAAR (ondergrens bereikt zonder SAT?)" >> "$LOG"
