"""MULTIPLICITEITSCALCULUS (optie 2).

Kern-identiteit: de totaalscore van een spel is LINEAIR in de letterwaarden:

    score = SOM_cellen  m(c) * waarde(letter op c)  +  50 * #bingo's

waarbij m(c) alleen van de GEOMETRIE en de ZETVOLGORDE afhangt, niet van de letters:
voor elke scorende gebeurtenis (run, nieuwe cellen) met woordmultiplier wm draagt cel c
bij met  wm * (lm(c) als c nieuw is in die zet, anders 1).

Dat geeft twee dingen:
  1. een exacte zak-bovengrens voor een gegeven geometrie (herschikkingsongelijkheid:
     hoogste tegelwaarden op hoogste m-coefficienten), zonder woordenboek;
  2. een lineaire doelfunctie voor elke letter-fitter (optie 1).

Env: MBASE (spel-json, default record), DUMP (optioneel pad voor m-profiel json).
"""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import numpy as np, maxgame_score as MG

r = MG.r
val = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)

D = json.load(open(os.environ.get('MBASE', 'experiments/results/maxgame_BEST.json')))
grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
blanks = set(tuple(b) for b in D.get('blanks', []))


def events_of(moves):
    """(run_cellen, nieuwe_cellen) per scorende gebeurtenis, in zetvolgorde."""
    placed = set(); out = []
    for cells in moves:
        placed |= set(cells); cset = set(cells); seen = set()
        for (x, y) in cells:
            for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
                x0, y0 = x, y
                while x0 - dx >= 0 and y0 - dy >= 0 and (x0 - dx, y0 - dy) in placed: x0 -= dx; y0 -= dy
                x1, y1 = x, y
                while x1 + dx < 15 and y1 + dy < 15 and (x1 + dx, y1 + dy) in placed: x1 += dx; y1 += dy
                n = max(x1 - x0, y1 - y0) + 1
                if n < 2 or (tag, x0, y0) in seen: continue
                seen.add((tag, x0, y0))
                run = [(x0 + i * dx, y0 + i * dy) for i in range(n)]
                if any(c in cset for c in run): out.append((run, cset))
    return out


def multiplicity(moves):
    m = Counter()
    for run, cset in events_of(moves):
        wm = 1
        for (x, y) in run:
            if (x, y) in cset: wm *= int(WM[y][x])
        for (x, y) in run:
            m[(x, y)] += wm * (int(LM[y][x]) if (x, y) in cset else 1)
    return m


m = multiplicity(moves)
bingos = 50 * sum(1 for mv in moves if len(mv) == 7)
recon = sum(m[c] * (0 if c in blanks else val[grid[c[1]][c[0]]]) for c in m) + bingos
tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blanks)
print(f"arbiter {int(tot)} (ok={ok}) | m-reconstructie {recon} | bingo-constante {bingos}")
assert recon == int(tot), "multipliciteitsidentiteit klopt niet"

occ = [(x, y) for y in range(15) for x in range(15) if grid[y][x]]
anchor = [c for c in occ if c[1] in (0, 7, 14)]
free = [c for c in occ if c[1] not in (0, 7, 14)]
bag = Counter({c: r.counts[c] for c in r.counts})
used_anchor = Counter(grid[c[1]][c[0]] for c in anchor if c not in blanks)
rest = bag - used_anchor
pool = sorted((val[ch] for ch, n in rest.items() for _ in range(n)), reverse=True)

fixed_part = sum(m[c] * (0 if c in blanks else val[grid[c[1]][c[0]]]) for c in anchor)
mfree = sorted((m[c] for c in free), reverse=True)
ceiling = fixed_part + sum(a * b for a, b in zip(mfree, pool)) + bingos

print(f"cellen: {len(occ)} ({len(anchor)} anker vast, {len(free)} vrij) | zakrest {len(pool)} tegels")
print(f"ZAK-PLAFOND van deze geometrie (zonder woordenboek): {ceiling}")
print(f"gerealiseerd {int(tot)} = {100*int(tot)/ceiling:.1f}% | woordenboekverlies {ceiling-int(tot)}")

top = sorted(m.items(), key=lambda kv: -kv[1])[:12]
print("hoogste m-coefficienten:", [(c, v, ('anker' if c[1] in (0, 7, 14) else 'vrij')) for c, v in top])
tail = sorted(((m[c], c) for c in free))[:8]
print("laagste vrije m:", tail)

if os.environ.get('DUMP'):
    json.dump({'m': {f"{x},{y}": v for (x, y), v in m.items()}, 'bingos': bingos,
               'ceiling': ceiling, 'total': int(tot)}, open(os.environ['DUMP'], 'w'))
    print("m-profiel weggeschreven ->", os.environ['DUMP'])
