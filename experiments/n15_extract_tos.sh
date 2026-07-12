#!/bin/bash
cd /home/bob/programming/scrabble4
OUT=experiments/results/oracle_parallel/pipe_to_keys.txt
TMP=$(mktemp -d)
: > $OUT
for STRIP in 0378111314/f378 0378111314/f385 0379111214/f378 0379111214/f385 0379111314/f378 0379111314/f385; do
  F=${STRIP#*/f}
  D=experiments/results/oracle_parallel/pipe_geschenkcheques_$STRIP
  i=0
  for gz in $D/verdict_*.gz; do
    ( zcat "$gz" 2>/dev/null | awk -v fl="$F" '/^RES/ && / TO / {print $2 "\t" fl}' > $TMP/o_${F}_$i ) &
    i=$((i+1))
  done
  wait
  cat $TMP/o_${F}_* >> $OUT 2>/dev/null; rm -f $TMP/o_${F}_*
  echo "[extract] $STRIP klaar; cumulatief $(wc -l < $OUT) TO"
done
rmdir $TMP 2>/dev/null
echo "EXTRACT-KLAAR: $(wc -l < $OUT) TO-keys"
