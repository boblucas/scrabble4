#!/bin/bash
# Scan top-N triples via Rust pipeline; report best verified-able total per triple.
cd /home/bob/programming/scrabble4
NTRIP="${1:-30}"; NREST="${2:-50}"; TLMS="${3:-90}"; BEAMW="${4:-24}"; MAXC="${5:-16}"
TMP=/home/bob/.claude/jobs/da7ed622/tmp
export WORDS_ALL=$TMP/wordsall.txt WORDS_CONN=$TMP/words2_8.txt PREMIUM_FLAT=$TMP/premium_flat.txt
export VALS=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['val'])))")
export BAG=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['bag'])))")
RES=experiments/results/mg_triple_scan.log; : > "$RES"
# tsv: rank score R0 R14 R7  -> we want R0 R7 R14
tail -n +2 experiments/results/maxgame_triplerank.tsv | awk '!seen[$3" "$5" "$4]++' | awk -v s="${SKIP:-0}" 'NR>s' | head -"$NTRIP" | \
while IFS=$'\t' read -r rank score R0 R14 R7 rest; do
  ( combos=$(.venv/bin/python experiments/mg_gen_combos.py "$R0" "$R7" "$R14" "$MAXC" 2>/dev/null)
    if [ -z "$combos" ]; then echo "#$rank $R0/$R7/$R14 core$score: geen maskers" >>"$RES"; exit; fi
    out=$( { printf '%s %s %s\n%s %s\n%s\n' "$R0" "$R7" "$R14" "$NREST" "$TLMS" "$combos"; } | MGBEAMW=$BEAMW SEED_SALT=$rank nice -n 8 experiments/mg_full_bin 2>/dev/null )
    best=$(echo "$out" | grep SCORED | awk '{print $2}' | sort -rn | head -1)
    echo "#$rank $R0/$R7/$R14 core$score best=${best:-none}" >>"$RES"
  ) &
  # cap concurrency
  while [ "$(jobs -r | wc -l)" -ge 22 ]; do sleep 0.5; done
done
wait
echo "scan klaar" >>"$RES"
