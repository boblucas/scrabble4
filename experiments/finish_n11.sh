#!/bin/bash
# Finish the N=11 certification: resolve the 20 residual TOs at floor 226 (10-way, 2h walls)
# and emit the 226 witness board for independent verification.
cd /home/bob/programming/scrabble4
D=experiments/results/certs/n11_fixed_221

# 1. split + launch the TO rerun
split -n l/10 -d "$D/to_rerun.list" "$D/to_part_"
for i in 0 1 2 3 4 5 6 7 8 9; do
  setsid nohup env BATCHWALL=7200 experiments/xfill_rs/target/release/xfill_lev3 \
    --batchvec "$D/base.txt" "$D/to_part_0$i" \
    > "$D/to_out_$i.txt" 2>/dev/null < /dev/null &
  echo "to_part_0$i pid $!"
done

# 2. emit the 226 board (vector 9-2-2-6-8-7-11) and build the witness spec
.venv/bin/python - <<'PY'
import sys, subprocess, os, json
sys.path.insert(0,'.'); sys.path.insert(0,'experiments')
import xtest
from scrabble import construct_rules
Lvec = {c: l for c, l in zip([0,1,2,3,5,8,10], (9,2,2,6,8,7,11))}
inst, meta = xtest.build_instance('11','bouwfysicus','BOUWfYsiCuS', Lvec, scale=True)
p = '/home/bob/.claude/jobs/f990c408/tmp/w226.txt'
xtest.dump_simple(inst, 'UNKNOWN', p)
env = dict(os.environ); env['WALL'] = '900'
r = subprocess.run(['experiments/xfill_rs/target/release/xfill_lev3', p, '--maxscore','225','--emit'],
                   capture_output=True, text=True, env=env, timeout=1000)
lines = (r.stdout or '').strip().splitlines()
print(lines[0] if lines else '(none)')
board = next((l for l in lines if l.startswith('BOARD')), None)
if board:
    codes = [int(t) for t in board.split()[1:]]
    rules = construct_rules('dutch','11'); W=H=11
    grid = [codes[y*W:(y+1)*W] for y in range(H)]
    main = rules.alphabet.to_tup('bouwfysicus')
    for x in range(W):
        if grid[0][x] == 0: grid[0][x] = main[x]
    for y in range(H):
        print(' '.join(rules.alphabet.to_str([grid[y][x]]) if grid[y][x] else '.' for x in range(W)))
    spec = {"board":"11","main_word":"bouwfysicus","turn_str":"BOUWfYsiCuS","scale":True,
            "blanks":True,"require_center":False,"claimed_total":852,"grid":grid}
    json.dump(spec, open('experiments/results/certs/witness_n11_unconstrained_852.json','w'), indent=1)
    print("witness JSON written")
PY

# 3. independently verify
.venv/bin/python experiments/witness_check.py experiments/results/certs/witness_n11_unconstrained_852.json | tail -3
