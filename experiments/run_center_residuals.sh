#!/bin/bash
# Re-run center-constrained residual vectors (that timed out proving LE <floor> at the shard cap)
# at a HIGH cap, in parallel, to either prove LE <floor> (close toward the proven optimum) or
# witness a board > floor (which would RAISE the constrained lower bound).  No MAXNODES -> a
# printed "LE <floor>" is a sound, naturally-completed exhaustion proof.
cd /home/bob/programming/scrabble4
BIN=experiments/xfill_rs/target/release/xfill_lev3
FLOOR=${FLOOR:-173}
CAP=${CAP:-1800}
MAXC=${MAXC:-24}
VFILE=${VFILE:-/home/bob/.claude/jobs/f990c408/tmp/center_unresolved_uniq.txt}
OUT=experiments/results/turns/center_residuals
mkdir -p "$OUT"
export BIN FLOOR CAP OUT
# xargs -P enforces concurrency in a non-interactive shell (the `jobs -rp` throttle does NOT --
# job control is off when detached, so it launches everything at once: a real runaway).
grep -avE '^[[:space:]]*$' "$VFILE" | xargs -P "$MAXC" -I {} bash -c '
  v="$1"; d=$(printf "%s" "$v" | tr "," "-"); f="experiments/xtests/o11_bouwfysicus_${d}_sc.txt"
  if [ -f "$f" ]; then r=$(timeout "$CAP" "$BIN" "$f" --maxscore "$FLOOR" 2>/dev/null | head -1); else r="MISSING_INSTANCE"; fi
  printf "%s -> %s\n" "$v" "${r:-TIMEOUT$CAP}" > "$OUT/$d.out"
' _ {}
echo "===== CENTER RESIDUALS DONE (floor=$FLOOR cap=$CAP) ====="
tot=$(ls "$OUT"/*.out 2>/dev/null | wc -l)
le=$(grep -l "LE $FLOOR" "$OUT"/*.out 2>/dev/null | wc -l)
mx=$(grep -l "MAX " "$OUT"/*.out 2>/dev/null | wc -l)
to=$(grep -l "TIMEOUT" "$OUT"/*.out 2>/dev/null | wc -l)
echo "  total=$tot  LE-$FLOOR(closed)=$le  MAX>$FLOOR(lower-rises)=$mx  TIMEOUT(wall)=$to"
echo "  --- any MAX (raises the constrained lower) ---"; grep -h "MAX " "$OUT"/*.out 2>/dev/null | head
echo "  --- timeouts still open (residual wall) ---"; for f in $(grep -l "TIMEOUT" "$OUT"/*.out 2>/dev/null); do basename "$f" .out; done | head -20
if [ "$le" = "$tot" ] && [ "$tot" -gt 0 ]; then
  echo "  ==> ALL residuals LE $FLOOR  =>  center-constrained bouwfysicus vertical = $FLOOR PROVEN (turn $((626+FLOOR)))"
fi
