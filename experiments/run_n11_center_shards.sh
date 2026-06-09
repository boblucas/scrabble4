#!/bin/bash
# Sharded CENTER-CONSTRAINED bouwfysicus N=11 closure (Lever-3 inner).
# --center forces col5 (the center column) length >= 6 so the center cell (5,5) is occupied+connected.
# Shard by col0 to avoid the descending-sweep clause-accumulation balloon.  Seeded with a witnessed
# center-valid board (best=SEED at SLVEC) so the fast LE direction prunes and the improver pushes the
# lower up.  CONSTRAINED upper is already <= 224 (subset of the proven unconstrained set); this run
# pushes the constrained LOWER (best witnessed center-valid vertical) toward it.
cd /home/bob/programming/scrabble4
PY=.venv/bin/python
SEED=${SEED:-173}; SLVEC=${SLVEC:-"8,5,2,6,6,5,8"}
MAXC=${MAXC:-3}
OUT=experiments/results/turns/center_shards
mkdir -p "$OUT"
for K in $(seq 1 11); do
  while [ "$(jobs -rp | wc -l)" -ge "$MAXC" ]; do sleep 5; done
  echo "[launch] col0=$K (center, seed=$SEED)"
  "$PY" -u experiments/32_fast_inner.py 11 --center --scale-tiles --blanks --main bouwfysicus \
    --seed-best "$SEED" --seed-lvec "$SLVEC" --fix "0:$K" --workers 2 --cap 90 --maxsec 7200 \
    > "$OUT/c0-$K.log" 2>&1 &
done
wait
echo "===== CENTER SHARDS DONE ====="
best=$SEED; bestvec=""
for K in $(seq 1 11); do
  m=$(grep -aoE "MAX [0-9]+|incumbent=[0-9]+" "$OUT/c0-$K.log" 2>/dev/null | grep -oE "[0-9]+" | sort -n | tail -1)
  if [ -n "$m" ] && [ "$m" -gt "$best" ]; then best=$m; bestvec="col0=$K"; fi
  v=$(grep -aE "PROVEN OPTIMAL|BRACKET \[|winning length" "$OUT/c0-$K.log" 2>/dev/null | tail -1)
  echo "  col0=$K: local_best=$m  $v"
done
echo "--------------------------------------------------------------"
echo "CONSTRAINED LOWER (best witnessed center-valid vertical) = $best ($bestvec)"
echo "center-constrained bouwfysicus bracket: vertical [$best, 224], turn [$((626+best)), 850]"
