"""Keten-decompositie van het zetplan: zelfde bord (grid+blanks), maar elke
meertegel-zet waar mogelijk opgeknipt in deelzetten. Elke deelzet moet legaal
zijn (alle maximale runs >=2 woorden, touch met bestaande structuur behalve
zet 1) en herscoort zijn runs — zak-neutraal, puur herscoringswinst.
Per zet exacte DP over subsets (<=2^7): best-splitsing incl. 50-bonus bij 7.
Arbiter (score_game) verifieert het volledige gedecomposeerde spel.
Env: CHBASE (json), CHOUT (json out)."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
import numpy as np, maxgame_score as MG
from functools import lru_cache
from itertools import combinations

r = MG.r; lk = MG.lk
LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
val = {i: r.scores[i] for i in range(1, 27)}

D = json.load(open(os.environ.get('CHBASE', 'experiments/results/maxgame_BEST.json')))
grid = D['grid']; moves0 = [[tuple(c) for c in m] for m in D['moves']]
blanks = set(tuple(b) for b in D['blanks'])

def cellval(c):
    return 0 if c in blanks else val[grid[c[1]][c[0]]]

def move_score(newcells, placed_before):
    """score van een zet volgens spelregels (nieuwe woorden door nieuwe cellen)."""
    pl = placed_before | set(newcells); cset = set(newcells)
    seen = set(); tot = 0; words_ok = True
    for (x, y) in newcells:
        for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
            x0, y0 = x, y
            while x0 - dx >= 0 and y0 - dy >= 0 and (x0 - dx, y0 - dy) in pl: x0 -= dx; y0 -= dy
            x1, y1 = x, y
            while x1 + dx < 15 and y1 + dy < 15 and (x1 + dx, y1 + dy) in pl: x1 += dx; y1 += dy
            n = max(x1 - x0, y1 - y0) + 1
            if (tag, x0, y0) in seen: continue
            seen.add((tag, x0, y0))
            run = [(x0 + i * dx, y0 + i * dy) for i in range(n)]
            if n < 2:
                continue
            if not any(c in cset for c in run): continue
            w = tuple(grid[cy][cx] for (cx, cy) in run)
            if w not in lk: words_ok = False
            wm = 1; s = 0
            for (cx, cy) in run:
                v = cellval((cx, cy))
                if (cx, cy) in cset:
                    s += v * int(LM[cy][cx]); wm *= int(WM[cy][cx])
                else:
                    s += v
            tot += s * wm
    if len(newcells) == 7: tot += 50
    return tot, words_ok

def touches(newcells, placed_before):
    if not placed_before: return True
    for (x, y) in newcells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) in placed_before: return True
    return False

def best_split(cells, placed_before):
    """exacte DP: beste opdeling van deze zet in deelzetten."""
    n = len(cells)
    if n == 1:
        s, ok = move_score(cells, placed_before)
        return (s, [cells]) if ok else (None, None)
    idx = {c: i for i, c in enumerate(cells)}
    full = (1 << n) - 1

    @lru_cache(maxsize=None)
    def dp(mask):
        if mask == full: return (0, ())
        placed = placed_before | {cells[i] for i in range(n) if mask >> i & 1}
        rem = [i for i in range(n) if not (mask >> i & 1)]
        best = None
        for k in range(1, len(rem) + 1):
            for sub in combinations(rem, k):
                sc = [cells[i] for i in sub]
                if not touches(sc, placed) and placed: continue
                s, ok = move_score(sc, placed)
                if not ok: continue
                nxt = mask
                for i in sub: nxt |= 1 << i
                rest = dp(nxt)
                if rest[0] is None: continue
                cand = (s + rest[0], ((tuple(sc),) + rest[1]))
                if best is None or cand[0] > best[0]: best = cand
        return best if best else (None, None)

    res = dp(0)
    if res[0] is None: return (None, None)
    return res[0], [list(g) for g in res[1]]

placed = set(); out_moves = []; gained = 0
for t, cells in enumerate(moves0):
    base_s, base_ok = move_score(cells, placed)
    if len(cells) <= 1 or len(cells) > 8:
        out_moves.append(cells); placed |= set(cells); continue
    s, split = best_split(tuple(cells), frozenset(placed))
    if split is None or s <= base_s:
        out_moves.append(cells)
    else:
        print(f"zet {t}: {len(cells)} tegels {base_s} -> {s} (+{s-base_s}) via {len(split)} deelzetten", flush=True)
        gained += s - base_s
        out_moves.extend(split)
    placed |= set(cells)

print(f"totaal ketenwinst (model): +{gained}", flush=True)
tot, per, ok, msg = MG.score_game([row[:] for row in grid], out_moves, blanks)
print("arbiter:", int(tot), "ok:", ok, ("" if ok else msg), flush=True)
if ok and int(tot) > int(D.get('total', 0)):
    json.dump({'grid': grid, 'moves': [[list(c) for c in m] for m in out_moves],
               'blanks': [list(b) for b in sorted(blanks)], 'total': int(tot),
               'triple': D['triple'], 'plan': 'chainify: zetplan-decompositie'},
              open(os.environ.get('CHOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/chain_best.json'), 'w'))
    print("NIEUW BEST", int(tot), flush=True)
