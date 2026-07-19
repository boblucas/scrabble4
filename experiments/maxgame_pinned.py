"""Vulfase-lotto op GEPIND 3738-skelet (S* skelmax r1)."""
import sys, os, json, random, time, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
src = open('experiments/maxgame_play5.py').read()
head = src[:src.index('NTRY = int(os.environ.get')]
exec(compile(head, 'p5head', 'exec'))
R0, R7, R14 = 'flauwekulexcuus', 'babyzwemmertjes', 'zelfbeschikking'
PLAN = {'span1': 'ampere', 'up6': 'ketentje', 'span13': 'gepas', 'dn5': 'wegdanse',
        'up8': 'leervorm', 'dn10': 'reestrik', 'span8': ('heia', 9, 'A'),
        'cols': (6, 8, 5, 10), 'over': {'u': 1, 'b': 1}}
random.seed(int(os.environ.get('SEED', '1')))
tag = os.environ.get('SEED', '1')
t0 = time.time(); best = 0
while time.time() - t0 < 3000:
    tot, ok2, out = run_one(R0, R7, R14, dict(PLAN))
    if ok2 and tot > best:
        best = tot
        f = f'experiments/results/maxgame_pinned_{tag}.json'
        json.dump(out, open(f, 'w'))
        subprocess.run(['.venv/bin/python', 'experiments/maxgame_extend.py', f, 'dutch2026'],
                       capture_output=True, timeout=400)
        print(f"pinned best {best} (pre-ext)", flush=True)
print(f"KLAAR: {best}", flush=True)
