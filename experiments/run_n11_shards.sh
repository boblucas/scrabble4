#!/bin/bash
# Sharded bouwfysicus N=11 vertical closure on the LEVER-3 inner (xfill==xfill_lev3).
# Shard the exp32 descending-UB enumeration by col0 length (1..11): each shard runs the IDENTICAL
# per-vector logic (geom + tile-knapsack + xfill --maxscore) on a disjoint slice.  The UNION of col0
# values = the full geom-feasible space, so "all shards PROVEN" => bouwfysicus vertical = 224 is PROVEN.
# Sharding also CAPS each shard's outer clause-accumulation (the descending sweep's scaling bottleneck),
# so no shard balloons the way the single full run does.
cd /home/bob/programming/scrabble4
PY=.venv/bin/python
SEED=224; SLVEC="11,3,2,7,3,5,11"
MAXC=${MAXC:-3}                       # concurrency cap (polite on the shared/loaded box)
OUT=experiments/results/turns/shards
mkdir -p "$OUT"

for K in $(seq 1 11); do
  while [ "$(jobs -rp | wc -l)" -ge "$MAXC" ]; do sleep 5; done
  echo "[launch] col0=$K -> $OUT/c0-$K.log"
  "$PY" -u experiments/32_fast_inner.py 11 --scale-tiles --blanks --main bouwfysicus \
    --seed-best $SEED --seed-lvec "$SLVEC" --fix "0:$K" --workers 2 --cap 120 \
    > "$OUT/c0-$K.log" 2>&1 &
done
wait

echo "===== ALL 11 SHARDS DONE ====="
allproven=1; gmax=$SEED
for K in $(seq 1 11); do
  log="$OUT/c0-$K.log"
  if grep -qa "PROVEN OPTIMAL" "$log"; then st="PROVEN"; else st="OPEN  "; allproven=0; fi
  m=$(grep -aoE "MAX [0-9]+" "$log" | awk '{print $2}' | sort -n | tail -1)
  if [ -n "$m" ] && [ "$m" -gt "$gmax" ]; then gmax=$m; fi
  v=$(grep -aE "PROVEN OPTIMAL|BRACKET \[|UNRESOLVED|Traceback" "$log" | tail -1)
  echo "  col0=$K: $st  ${v}"
done
echo "--------------------------------------------------------------"
if [ "$allproven" = 1 ]; then
  echo "GLOBAL VERDICT: PROVEN  bouwfysicus N=11 vertical = $gmax  =>  full turn = 626 + $gmax = $((626+gmax))"
else
  echo "GLOBAL VERDICT: NOT FULLY CLOSED (some shards OPEN/unresolved -- inspect above; raise --cap and re-run those)"
fi
