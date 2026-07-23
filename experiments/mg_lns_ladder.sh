#!/bin/bash
# LNS-ladder: evolutionaire generaties — pool van beste borden, elke generatie buurt-zoeken
# (LNS backbone-recombinatie, keep 60-85%) + blanks; pool ververst met dedup op bordstring.
# args: GENS WORKERS NREST TLMS BEAMW
cd /home/bob/programming/scrabble4
GENS=${1:-10}; NW=${2:-44}; NREST=${3:-60}; TLMS=${4:-90}; BEAMW=${5:-30}
TMP=/home/bob/.claude/jobs/da7ed622/tmp
export WORDS_ALL=$TMP/wordsall.txt WORDS_CONN=$TMP/words2_8.txt PREMIUM_FLAT=$TMP/premium_flat.txt
export VALS=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['val'])))")
export BAG=$(.venv/bin/python -c "import json;print(','.join(map(str,json.load(open('$TMP/meta.json'))['bag'])))")
POOL=$TMP/lnspool.txt
LOG=experiments/results/mg_lns_ladder.log
: > "$LOG"
for g in $(seq 1 $GENS); do
  [ -s "$POOL" ] || { echo "lege pool" >>"$LOG"; break; }
  head -24 "$POOL" > $TMP/gen_in.txt
  rm -f $TMP/gen_out_*.txt
  for w in $(seq 0 $((NW-1))); do
    keep=$((42 + (w*9)%33))
    { printf 'geschenkcheques flexwerkstertje polymelkzuurtje\n%s %s\n' "$NREST" "$TLMS"; cat $TMP/gen_in.txt; } | \
      LNS=1 LNS_KEEP=$keep RUST_ENRICH=1 RUST_NBLANK=1 MGBEAMW=$BEAMW SEED_SALT=$((g*1000+w)) \
      nice -n 8 experiments/mg_full_bin 2>/dev/null > $TMP/gen_out_$w.txt &
  done
  wait
  cat $TMP/gen_out_*.txt "$POOL" | grep "^SCORED" | sort -k2 -rn | awk '!seen[$8]++' | head -40 > $TMP/pool_new.txt
  mv $TMP/pool_new.txt "$POOL"
  echo "gen $g: pool-best=$(head -1 "$POOL" | awk '{print $2}') pool-preps=$(head -3 "$POOL" | awk '{printf "%s/",$3}')" >> "$LOG"
done
echo "ladder klaar" >> "$LOG"
