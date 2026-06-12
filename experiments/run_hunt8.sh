#!/bin/bash
# 8-way parallel floor-raise hunt over the top-UB list (split parts hunt_part_00..07).
cd /home/bob/programming/scrabble4
D=experiments/results/certs/n11_fixed_221
for i in 0 1 2 3 4 5 6 7; do
  setsid nohup env BATCHWALL=900 experiments/xfill_rs/target/release/xfill_lev3 \
    --batchvec "$D/base.txt" "$D/hunt_part_0$i" \
    > "$D/hunt_out_$i.txt" 2> "$D/hunt_err_$i.txt" < /dev/null &
  echo "launched part $i pid $!"
done
exit 0
