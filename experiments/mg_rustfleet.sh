#!/bin/bash
# Rust full-pipeline fleet: elke worker = mg_full_bin met top closable masks, veel restarts, eigen seed-salt.
# args: R0 R7 R14 NWORKERS NREST TLMS BEAMW MAXCOMBOS
cd /home/bob/programming/scrabble4
R0="$1";R7="$2";R14="$3";NW="${4:-24}";NREST="${5:-60}";TLMS="${6:-120}";BEAMW="${7:-20}";MAXC="${8:-30}"
TMP=/home/bob/.claude/jobs/da7ed622/tmp
export WORDS_ALL=$TMP/wordsall.txt WORDS_CONN=$TMP/words2_8.txt PREMIUM_FLAT=$TMP/premium_flat.txt
export VALS=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['val'])))")
export BAG=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['bag'])))")
# genereer top-MAXC closable-kandidaat masker-combos via Python (finals-proxy volgorde)
.venv/bin/python experiments/mg_gen_combos.py "$R0" "$R7" "$R14" "$MAXC" > $TMP/combos_${R0}.txt
STDIN_HEAD=$(printf '%s %s %s\n%s %s' "$R0" "$R7" "$R14" "$NREST" "$TLMS")
: > experiments/results/mg_rustfleet.log
for w in $(seq 0 $((NW-1))); do
  ( { echo "$STDIN_HEAD"; cat $TMP/combos_${R0}.txt; } | SEED_SALT=$((w*100003)) MGBEAMW=$BEAMW nice -n 5 experiments/mg_full_bin 2>/dev/null ) >> experiments/results/mg_rustfleet_${w}.out &
done
wait
echo "rustfleet klaar" >> experiments/results/mg_rustfleet.log
