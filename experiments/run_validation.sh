#!/bin/bash
# One-shot validation of this cycle's changes (l=1 phantom fix, OPTIMAL asserts, new tools).
cd /home/bob/programming/scrabble4
echo "===== 1. compile checks ====="
.venv/bin/python -m py_compile experiments/32_fast_inner.py experiments/33_full_turn_bracket.py \
  experiments/xtest.py experiments/witness_check.py experiments/35_certify.py \
  experiments/36_game_script.py && echo ALL-COMPILE-OK || echo COMPILE-FAIL

echo "===== 2. soundness gate suite (~2-3 min) ====="
bash experiments/regress.sh

echo "===== 3. independent witness check: unconstrained 850 board ====="
.venv/bin/python experiments/witness_check.py experiments/results/certs/witness_n11_unconstrained_850.json

echo "===== 4. game-reachability on the 850 witness (expect center REJECT: pre-center witness) ====="
timeout 700 .venv/bin/python experiments/36_game_script.py \
  experiments/results/certs/witness_n11_unconstrained_850.json --deadline 600

echo "===== 5. Phase-0 center re-run status ====="
pgrep -f run_n11_center_shards.sh >/dev/null 2>&1 && echo "launcher: RUNNING" || echo "launcher: DONE"
for K in $(seq 1 11); do
  st=$(grep -aoE "PROVEN OPTIMAL  vertical = [0-9-]+|BRACKET \[[0-9]+, [0-9]+\]" \
       experiments/results/turns/center_shards/c0-$K.log 2>/dev/null | tail -1)
  printf "  col0=%-2s %s\n" "$K" "${st:-(running/queued)}"
done
tail -3 experiments/results/turns/N11_center_shards_v2_master.log 2>/dev/null
uptime
