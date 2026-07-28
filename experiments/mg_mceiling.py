"""M-CEILING-MOTOR: geometrie-evaluatie zonder woordenboek.

score(spel) = SOM_c m(c)*waarde(c) + 50*#bingo's,  met m(c) puur uit geometrie+zetvolgorde.
Daarmee is de bovengrens van een geometrie exact te berekenen (herschikkingsongelijkheid:
hoogste zaktegels op hoogste m), en kunnen we geometrieen vergelijken zonder ook maar
een woord te fitten. Woordenboek komt pas in de laatste stap.

Publieke functies:
  events_of(moves)                  -> [(run_cellen, nieuwe_cellen)]
  multiplicity(moves)               -> Counter cel -> m
  ceiling(m, fixed, blanks, bingos) -> exacte zak-bovengrens van dit m-profiel
  best_schedule(occ, seed_moves)    -> lokale zoektocht naar het schema met hoogste plafond

CLI: MBASE=<spel.json> [SCHED=1] python experiments/mg_mceiling.py
"""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import numpy as np, maxgame_score as MG

r = MG.r
VAL = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier).tolist()
WM = np.array(r.word_multiplier).tolist()
BAG = Counter({c: r.counts[c] for c in r.counts})
NB = ((1, 0), (-1, 0), (0, 1), (0, -1))


def events_of(moves):
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
            if (x, y) in cset: wm *= WM[y][x]
        for (x, y) in run:
            m[(x, y)] += wm * (LM[y][x] if (x, y) in cset else 1)
    return m


def ceiling(m, fixed=None, bingos=0, cap=101, zero=None):
    """Exacte zak-bovengrens: vaste cellen tellen hun echte waarde, vrije cellen krijgen
    de beste resterende tegels (hoogste waarde op hoogste m). fixed: {cel: letter-id}.
    zero: cellen met een BLANCO (waarde 0, kosten geen zaktegel)."""
    fixed = fixed or {}
    zero = set(zero or ())
    rest = Counter(BAG)
    val_fixed = 0
    for c, ch in fixed.items():
        if c in zero: continue
        val_fixed += m.get(c, 0) * VAL[ch]
        rest[ch] -= 1
    pool = sorted((VAL[ch] for ch, n in rest.items() for _ in range(max(0, n))), reverse=True)
    freem = sorted((v for c, v in m.items() if c not in fixed and c not in zero), reverse=True)
    return val_fixed + sum(a * b for a, b in zip(freem, pool)) + bingos


def score_of(moves, fixed=None, cap=101, zero=None):
    m = multiplicity(moves)
    bingos = 50 * sum(1 for mv in moves if len(mv) == 7)
    return ceiling(m, fixed, bingos, cap, zero), m


def shape_ok(mv, placed):
    """ZETVORM: alle nieuwe tegels op EEN lijn, en de run tussen min en max moet volledig
    gevuld zijn (door de zet zelf of door al liggende tegels).  Zonder deze check zou een
    'zet' een willekeurige celverzameling mogen zijn -> geen enkel woord."""
    s = set(mv)
    xs = {x for x, y in s}; ys = {y for x, y in s}
    if len(xs) > 1 and len(ys) > 1: return False
    if len(xs) == 1:
        x = next(iter(xs)); a, b = min(ys), max(ys)
        return all((x, y) in placed or (x, y) in s for y in range(a, b + 1))
    y = next(iter(ys)); a, b = min(xs), max(xs)
    return all((x, y) in placed or (x, y) in s for x in range(a, b + 1))


def legal_schedule(moves, need_center=True, shape=True):
    """touch-regels: zet 1 dekt center, elke volgende raakt bestaand bord, <=7 tegels,
    en (shape=True) elke zet heeft een echte zetvorm (een lijn, aaneengesloten run)."""
    placed = set()
    for i, mv in enumerate(moves):
        if not mv or len(mv) > 7: return False
        if i == 0:
            if need_center and (7, 7) not in mv: return False
        elif not any((x + dx, y + dy) in placed for (x, y) in mv for dx, dy in NB):
            return False
        if any(c in placed for c in mv): return False
        if shape and not shape_ok(mv, placed): return False
        placed |= set(mv)
    return True


def best_schedule(seed_moves, fixed=None, iters=4000, seed=0, keep_tail=True):
    """Lokale zoektocht over SCHEMA's bij vaste bezetting: splits/hersorteer zetten om het
    m-plafond te maximaliseren. Woordenboek wordt genegeerd -> dit is een bovengrens
    voor wat deze bezetting bij enige legale zetvolgorde kan opleveren."""
    rnd = random.Random(seed)
    cur = [list(m) for m in seed_moves]
    best, _ = score_of(cur, fixed)
    bestmv = [list(m) for m in cur]
    for it in range(iters):
        cand = [list(m) for m in cur]
        op = rnd.random()
        idx = [i for i, m in enumerate(cand) if len(m) > 1]
        if op < 0.5 and idx:                       # splits een zet in tweeen
            i = rnd.choice(idx); m = cand[i]
            k = rnd.randrange(1, len(m))
            m = sorted(m, key=lambda c: (c[1], c[0]))   # langs de lijn -> deelruns blijven heel
            if rnd.random() < 0.5: m = m[::-1]
            cand[i:i + 1] = [m[:k], m[k:]]
        elif op < 0.8 and len(cand) > 2:           # verplaats een zet naar achteren
            i = rnd.randrange(len(cand) - 1)
            j = rnd.randrange(i + 1, len(cand))
            mv = cand.pop(i); cand.insert(j, mv)
        else:                                       # voeg twee opeenvolgende zetten samen
            i = rnd.randrange(max(1, len(cand) - 1))
            if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                cand[i:i + 2] = [cand[i] + cand[i + 1]]
        if not legal_schedule(cand): continue
        sc, _ = score_of(cand, fixed)
        if sc >= best:
            if sc > best: bestmv = [list(m) for m in cand]
            best = sc; cur = cand
    return best, bestmv


if __name__ == '__main__':
    D = json.load(open(os.environ.get('MBASE', 'experiments/results/maxgame_BEST.json')))
    grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    fixed = {(x, y): grid[y][x] for y in (0, 7, 14) for x in range(15) if grid[y][x]}
    alle = {(x, y): grid[y][x] for y in range(15) for x in range(15) if grid[y][x]}
    cap, m = score_of(moves, fixed)
    exact, _ = score_of(moves, alle, zero=blanks)
    tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blanks)
    print(f"gerealiseerd {int(tot)} | plafond huidig schema {cap} | verschil {cap - int(tot)}")
    # identiteit: met ALLE letters vast is het 'plafond' geen grens meer maar de score zelf
    print(f"m-calculus EXACT {exact} (== {int(tot)}? {exact == int(tot)}) | "
          f"vorm-legaal schema: {legal_schedule(moves)}")
    if os.environ.get('SCHED'):
        b, bmv = best_schedule(moves, fixed, iters=int(os.environ.get('ITERS', '4000')))
        print(f"BESTE SCHEMA bij dezelfde bezetting: plafond {b} (+{b - cap} t.o.v. huidig schema)")
        print(f"  zetten: {len(moves)} -> {len(bmv)}")
        if os.environ.get('SCHEDOUT'):
            json.dump({'moves': [[list(c) for c in m] for m in bmv], 'ceiling': b},
                      open(os.environ['SCHEDOUT'], 'w'))
