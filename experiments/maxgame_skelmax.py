"""Stochastische skelet-maximalisatie: trek plannen (vaste triple+kolommen), replay skelet-only,
log beste. Voorloper van exacte B&B (ladder stap 1)."""
import sys, os, json, random, time
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
os.environ.setdefault('SEED', str(int(time.time()) % 100000))
src = open('experiments/maxgame_play5.py').read()
head = src[:src.index('NTRY = int(os.environ.get')]
exec(compile(head, 'p5head', 'exec'))
import maxgame_score as MGs
R0, R7, R14 = 'flauwekulexcuus', 'babyzwemmertjes', 'zelfbeschikking'
random.seed(int(os.environ['SEED']))
best = 0
t0 = time.time()
while time.time() - t0 < 3000:
    p = plan_for_triple(R0, R7, R14)
    if not p or p['cols'] != (6, 8, 5, 10): continue
    tot, ok2, out = run_one(R0, R7, R14, p)
    # skelet-only: keten (15) + slotzetten
    mv = [[tuple(c) for c in m] for m in out['moves']]
    fin = [i for i, m in enumerate(mv) if len(m) == 7 and len({c[1] for c in m}) == 1
           and m[0][1] in (0, 7, 14) and i >= 15]
    sk = {c for i in list(range(15))+fin for c in mv[i]}
    g2 = [[out['grid'][y][x] if (x, y) in sk else 0 for x in range(15)] for y in range(15)]
    bl2 = {tuple(b) for b in out['blanks'] if tuple(b) in sk}
    s0 = int(MGs.score_game(g2, [mv[i] for i in list(range(15))+fin], bl2)[0])
    if s0 > best:
        best = s0
        print(f"S*-kandidaat: {s0} plan={ {k: str(v) for k, v in p.items()} }", flush=True)
print(f"KLAAR: beste skelet = {best}", flush=True)
