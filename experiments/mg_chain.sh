#!/bin/bash
# Keten: wacht op exacte W=10M-run -> pool herwaarderen -> LNS-ladder (beam 128) -> exacte polish top-5.
cd /home/bob/programming/scrabble4
TMP=/home/bob/.claude/jobs/da7ed622/tmp
LOG=experiments/results/mg_chain.log
: > "$LOG"
while pgrep -f mg_full_bin >/dev/null; do sleep 120; done
echo "exacte optima: $(awk '{print $2}' $TMP/exact_all_out.txt 2>/dev/null | tr '\n' ' ')" >> "$LOG"
cat $TMP/exact_all_out.txt $TMP/lnspool.txt 2>/dev/null | grep '^SCORED' | sort -k2 -rn | awk '!seen[$8]++' | head -60 > $TMP/pool2.txt
cp $TMP/pool2.txt $TMP/lnspool.txt
echo "pool herbouwd, top: $(head -1 $TMP/lnspool.txt | awk '{print $2,$3,$4}')" >> "$LOG"
bash experiments/mg_lns_ladder.sh 14 44 60 100 128 >> "$LOG" 2>&1
echo "ladder klaar, pool-top: $(head -1 $TMP/lnspool.txt | awk '{print $2,$3,$4}')" >> "$LOG"
export WORDS_ALL=$TMP/wordsall.txt WORDS_CONN=$TMP/words2_8.txt PREMIUM_FLAT=$TMP/premium_flat.txt
export VALS=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['val'])))")
export BAG=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['bag'])))")
head -5 $TMP/lnspool.txt > $TMP/polish_in.txt
{ printf 'geschenkcheques flexwerkstertje polymelkzuurtje\n0 0\n'; cat $TMP/polish_in.txt; } | \
  DECOMP_ONLY=1 MGBEAMW=4000000 nice -n 5 experiments/mg_full_bin > $TMP/polish_out.txt 2>>"$LOG"
echo "polish-top: $(awk '{print $2}' $TMP/polish_out.txt | sort -rn | head -3 | tr '\n' ' ')" >> "$LOG"
echo "CHAIN KLAAR" >> "$LOG"
