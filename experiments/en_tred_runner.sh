#!/bin/bash
# Trede-runner: certificeer ALLE maskers met UB>LB op deze LB (oracle TB_COMPANION + laneB),
# sla maskers met bestaand CERTIFIED-verdict of in SKIP over. args: LB [ORACLE_WORKERS] [SKIP_CSV]
cd /home/bob/programming/scrabble4
export N15_LANG=english N15_HMAX=15 PYTHONHASHSEED=0 N15_WORD=oxyphenbutazone
LB=$1; W=${2:-36}; SKIP="${3:-}"
TMP=/home/bob/.claude/jobs/da7ed622/tmp
ST=experiments/results/english/tred${LB}_status.log
while read -r ub mask; do
  [ "$ub" -le "$LB" ] && continue
  tag=$(echo "$mask" | tr -d ',')
  case ",$SKIP," in *",$tag,"*) echo "mask $mask: OVERGESLAGEN (elders bezig)" >> "$ST"; continue;; esac
  or_ok=$(grep -l "VERDICT: CERTIFIED" experiments/results/english/oxy_or_${tag}_lb${LB}*.log 2>/dev/null | head -1)
  tb_need=1; [ "$LB" -ge $((ub-27)) ] && tb_need=0
  tb_ok=$(grep -l "CERTIFIED" experiments/results/english/oxy_tb_${tag}_lb${LB}*.log 2>/dev/null | head -1)
  if [ -n "$or_ok" ] && { [ "$tb_need" -eq 0 ] || [ -n "$tb_ok" ]; }; then
    echo "mask $mask ub=$ub: AL-CERTIFIED" >> "$ST"; continue
  fi
  if [ -z "$or_ok" ]; then
    TB_COMPANION=1 UB_MASK=$ub .venv/bin/python -u experiments/n15_oracle_parallel.py \
      --word oxyphenbutazone --mask "$mask" --lb "$LB" --workers "$W" --cap 900 --collect 60000000 \
      >> experiments/results/english/oxy_or_${tag}_lb${LB}_r.log 2>&1
  fi
  if [ "$tb_need" -eq 1 ] && [ -z "$tb_ok" ]; then
    .venv/bin/python -u experiments/n15_laneB_tb.py --mask "$mask" --lb "$LB" --workers 8 --cap 900 \
      >> experiments/results/english/oxy_tb_${tag}_lb${LB}_r.log 2>&1
  fi
  or2=$(grep -h "VERDICT" experiments/results/english/oxy_or_${tag}_lb${LB}*.log 2>/dev/null | tail -1)
  tb2=$(grep -h "VERDICT" experiments/results/english/oxy_tb_${tag}_lb${LB}*.log 2>/dev/null | tail -1)
  echo "mask $mask ub=$ub: OR[$or2] TB[$tb2]" >> "$ST"
  if find experiments/results/turns -name "N15_best_1*.json" -mmin -30 2>/dev/null | grep -q .; then
    echo "WITNESS GEVONDEN - runner stopt" >> "$ST"; exit 0
  fi
done < $TMP/oxy_maskubs_all.txt
echo "TREDE $LB RUNNER KLAAR" >> "$ST"
