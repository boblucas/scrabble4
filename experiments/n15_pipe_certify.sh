#!/bin/bash
# PIPE-CERTIFY: één ladder-trede zonder shard-bestanden.  Per worker i:
#   pinenum --onlyshard i --outdir -  |  pinbatch --emit  |  gzip > verdict_i.gz
# Schijfvoetafdruk = alleen gzipte verdicts (~1-2GB/100M combos).  MAX-regels worden na afloop
# geteld; witness via _ladder_witness (gunzip on the fly door glob op .txt -> we gunzippen MAXes
# apart).  Usage: n15_pipe_certify.sh <mask> <floor> [word] [workers]
set -u
cd /home/bob/programming/scrabble4
MASK="$1"; FLOOR="$2"; WORD="${3:-geschenkcheques}"; NW="${4:-16}"
TAG=$(echo "$MASK" | tr ',' '_'); DTAG=$(echo "$MASK" | tr -d ',')
if [ "$WORD" = geschenkcheques ]; then BASE=experiments/results/oracle_parallel/bases_2026/geschenkcheques/base_${TAG}.txt
else BASE=experiments/results/oracle_parallel/ctc/base_${TAG}.txt; fi
D=experiments/results/oracle_parallel/pipe_${WORD}_${DTAG}/f${FLOOR}
mkdir -p "$D"
ML=$(.venv/bin/python -c "w='$WORD'; print(','.join(str(ord(w[c])-96) for c in [$MASK]))")
BIN=experiments/xfill_rs/target/release/xfill
echo "[$MASK f$FLOOR] pipe-certify start: $NW workers"
for i in $(seq 0 $((NW - 1))); do
  ( "$BIN" --pinenum "$BASE" --floor "$FLOOR" --mainletters "$ML" --shards "$NW" --onlyshard "$i" --outdir - 2> "$D/enum_$i.err" \
    | PINWALL=${PINWALL:-5} "$BIN" --pinbatch "$BASE" --emit 2>/dev/null \
    | gzip > "$D/verdict_$(printf %02d $i).gz" ) &
done
wait
NRES=$(zcat "$D"/verdict_*.gz | grep -c '^RES'); NMAX=$(zcat "$D"/verdict_*.gz | grep -c ' MAX ')
NTO=$(zcat "$D"/verdict_*.gz | grep '^RES' | grep -cE ' TO ')
ENUM=$(grep -h 'PINENUM count=' "$D"/enum_0.err | sed 's/.*count=\([0-9]*\).*/\1/')
echo "[$MASK f$FLOOR] enum=$ENUM RES=$NRES MAX=$NMAX TO=$NTO"
if [ "$NMAX" -gt 0 ]; then
  zcat "$D"/verdict_*.gz | grep -B0 -A1 ' MAX ' | grep -E '^(RES .* MAX |BOARD )' > "$D/maxes.txt"
  echo "[$MASK f$FLOOR] MAXes -> $D/maxes.txt (witness apart draaien)"
  exit 10
fi
exit 0
