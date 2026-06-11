"""Emit + spec the best-known center-constrained witness board (vector (8,3,2,7,6,5,8), best=191
seen in the probe).  Writes witness_n11_center.json for independent verification."""
import sys, subprocess, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.chdir('/home/bob/programming/scrabble4')
import xtest
from scrabble import construct_rules

Lvec = {c: l for c, l in zip([0, 1, 2, 3, 5, 8, 10], (8, 3, 2, 7, 6, 5, 8))}
inst, meta = xtest.build_instance('11', 'bouwfysicus', 'BOUWfYsiCuS', Lvec, scale=True)
p = '/home/bob/.claude/jobs/f990c408/tmp/center191.txt'
xtest.dump_simple(inst, 'UNKNOWN', p)
env = dict(os.environ); env['WALL'] = '900'
r = subprocess.run(['experiments/xfill_rs/target/release/xfill_lev3', p,
                    '--maxscore', '150', '--emit'],
                   capture_output=True, text=True, env=env, timeout=1000)
lines = (r.stdout or '').strip().splitlines()
print(lines[0] if lines else '(none)', flush=True)
board = next((l for l in lines if l.startswith('BOARD')), None)
if board:
    codes = [int(t) for t in board.split()[1:]]
    rules = construct_rules('dutch', '11')
    W = H = 11
    grid = [codes[y * W:(y + 1) * W] for y in range(H)]
    main = rules.alphabet.to_tup('bouwfysicus')
    for x in range(W):
        if grid[0][x] == 0:
            grid[0][x] = main[x]
    tok = lines[0].split()
    val = int(tok[1]) if tok[0] == 'MAX' else int(tok[-1].split('=')[1])
    spec = {"board": "11", "main_word": "bouwfysicus", "turn_str": "BOUWfYsiCuS", "scale": True,
            "blanks": True, "require_center": True, "claimed_total": 626 + val, "grid": grid}
    json.dump(spec, open('experiments/results/certs/witness_n11_center.json', 'w'), indent=1)
    print(f'center witness JSON written (claimed {626 + val})', flush=True)
else:
    print('NO BOARD (result above) -- raise wall or try another vector', flush=True)
