"""NACHTELIJKE LNS-ZOEKTOCHT over de GEOMETRIE (large neighborhood search).

Alles wat binnen de huidige bezetting te halen viel is bewezen uitgeput: 4778 is optimaal voor
dit footprint over alle zetvolgordes en herletteringen, en de bewezen bovengrens voor deze bezetting
is 4847. Winst moet dus uit een ANDERE bezetting komen. Deze worker zoekt die autonoom:

  1. lees de huidige beste bezetting (gedeeld bestand; workers pikken elkaars vondsten op)
  2. bepaal met de m-calculus de sloopkosten per cel (incl. bingo-breuk) en de marginale
     plafondwinst van elke lege cel die het bord raakt
  3. kies willekeurig een sloopset uit de goedkope cellen en een bouwset uit de beste kandidaten
     -- afwisselend als na-final-extensie (herscoring) of als groepszet voor de slotzetten (kolommen)
  4. bouw de geometrie, herordend met de greedy-touch-regel, en laat CP-SAT de letters invullen
  5. verifieer met score_game; alleen een bord met ok=True en een hogere score telt
  6. bij winst: atomisch wegschrijven naar het gedeelde bestand, zodat alle workers verderbouwen

Env: WORKER (id), SEED, DEADLINE (unix-tijd), TLIM (per solve), NW (CP-SAT-threads),
     SHARED (gedeeld beste-bord-bestand), BASE (startbord).
"""
import sys, os, json, random, time, traceback
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
from ortools.sat.python import cp_model
import numpy as np, maxgame_score as MG
import importlib.util

spec = importlib.util.spec_from_file_location("mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)

r = MG.r; cba = r.alphabet.cba
VAL = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
BAG = Counter({c: r.counts[c] for c in r.counts})
BYLEN = {}
for w in r.words_str: BYLEN.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))

WORKER = os.environ.get('WORKER', '0')
SEED = int(os.environ.get('SEED', '0'))
DEADLINE = float(os.environ.get('DEADLINE', str(time.time() + 3600)))
TLIM = float(os.environ.get('TLIM', '180'))
NW = int(os.environ.get('NW', '4'))
SHARED = os.environ.get('SHARED', 'experiments/results/lns_best.json')
BASE = os.environ.get('BASE', 'experiments/results/maxgame_BEST.json')
rnd = random.Random(SEED * 7919 + 17)


def load_best():
    for p in (SHARED, BASE):
        try:
            D = json.load(open(p))
            if D.get('total'): return D
        except Exception:
            continue
    return json.load(open(BASE))


def publish(D):
    """atomisch, en alleen als we nog steeds de beste zijn"""
    try:
        cur = json.load(open(SHARED)).get('total', 0)
    except Exception:
        cur = 0
    if D['total'] <= cur: return False
    tmp = SHARED + f'.tmp{WORKER}'
    json.dump(D, open(tmp, 'w'))
    os.replace(tmp, SHARED)
    return True


def build(D, drops, groups, tail_singles):
    grid0 = D['grid']; moves0 = [[tuple(c) for c in m] for m in D['moves']]
    dset = set(drops)
    g = [row[:] for row in grid0]
    for (x, y) in dset: g[y][x] = 0
    for gp in groups:
        for (x, y) in gp: g[y][x] = 1
    for (x, y) in tail_singles: g[y][x] = 1
    occ = [(x, y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ) > 101: return None
    mv = []
    for m in moves0:
        keep = [c for c in m if c not in dset]
        if keep: mv.append(keep)
    fin = [i for i, m in enumerate(mv)
           if len(m) == 7 and len({y for (_, y) in m}) == 1 and m[0][1] in (0, 7, 14)][-3:]
    if len(fin) < 3: return None
    ff = fin[0]
    pre = [m for i, m in enumerate(mv) if i < ff] + [list(gp) for gp in groups]
    rest = [m for i, m in enumerate(mv) if i >= ff] + [[c] for c in tail_singles]
    ordered = []; placed = set(); pool = list(pre)
    while pool:
        pick = None
        for i, m in enumerate(pool):
            if not placed and (7, 7) in m: pick = i; break
            if placed and any((x + dx, y + dy) in placed
                              for (x, y) in m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pick = i; break
        if pick is None: return None
        m = pool.pop(pick); ordered.append(m); placed |= set(m)
    return g, ordered + rest, occ, grid0


def solve(g, mv, occ, grid0, blanks0):
    fixed = {(x, y): grid0[y][x] for (x, y) in occ if y in (0, 7, 14) and grid0[y][x]}
    free = [c for c in occ if c not in fixed]
    m_ = cp_model.CpModel(); L = {}
    for c in free: L[c] = m_.new_int_var(1, 26, f"L{c}")
    for c, v in fixed.items(): L[c] = m_.new_constant(v)
    placed = set(); events = []; runs = set()
    for cells in mv:
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
                if any(c in cset for c in run): events.append((run, cset)); runs.add(tuple(run))
    for run in runs:
        fx = {i: fixed[c] for i, c in enumerate(run) if c in fixed}
        tab = [w for w in BYLEN.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab: return None
        m_.add_allowed_assignments([L[c] for c in run], tab)
    BL = {c: m_.new_bool_var(f"bl{c}") for c in free}
    m_.add(sum(BL.values()) <= 2)
    for ch in range(1, 27):
        cnt = []
        for c in free:
            b = m_.new_bool_var(f"i{c}_{ch}")
            m_.add(L[c] == ch).only_enforce_if(b); m_.add(L[c] != ch).only_enforce_if(b.negated())
            nb = m_.new_bool_var(f"nb{c}_{ch}")
            m_.add_bool_and([b, BL[c].negated()]).only_enforce_if(nb)
            m_.add_bool_or([b.negated(), BL[c]]).only_enforce_if(nb.negated())
            cnt.append(nb)
        m_.add(sum(cnt) + sum(1 for c, v in fixed.items() if v == ch) <= BAG[ch])
    VV = [0] + [VAL[i] for i in range(1, 27)]
    vv = {}
    for c in set(q for run, _ in events for q in run):
        v = m_.new_int_var(0, 10, f"v{c}"); m_.add_element(L[c], VV, v)
        if c in BL:
            ve = m_.new_int_var(0, 10, f"ve{c}")
            m_.add(ve == v).only_enforce_if(BL[c].negated()); m_.add(ve == 0).only_enforce_if(BL[c])
            vv[c] = ve
        else: vv[c] = v
    obj = []; bingos = sum(50 for mm in mv if len(mm) == 7)
    for run, cset in events:
        wm = 1
        for (x, y) in run:
            if (x, y) in cset: wm *= int(WM[y][x])
        obj.append(sum(vv[(x, y)] * (int(LM[y][x]) if (x, y) in cset else 1) for (x, y) in run) * wm)
    m_.maximize(sum(obj) + bingos)
    for c in free:
        if grid0[c[1]][c[0]]:
            m_.add_hint(L[c], grid0[c[1]][c[0]]); m_.add_hint(BL[c], 1 if c in blanks0 else 0)
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = TLIM; sol.parameters.num_workers = NW
    st = sol.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE): return None
    g2 = [row[:] for row in g]
    for c in free: g2[c[1]][c[0]] = sol.value(L[c])
    return g2, {c for c in free if sol.value(BL[c])}


def candidates(D):
    """sloopkosten en marginale plafondwinst, met de m-calculus (microseconden)"""
    grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    fixed = {(x, y): grid[y][x] for y in (0, 7, 14) for x in range(15) if grid[y][x]}
    base, m = mc.score_of(moves, fixed)
    owner = {}
    for i, mv in enumerate(moves):
        for c in mv: owner[c] = i
    occ = {(x, y) for y in range(15) for x in range(15) if grid[y][x]}
    drops = []
    for c in occ:
        if c[1] in (0, 7, 14): continue
        v = 0 if c in blanks else VAL[grid[c[1]][c[0]]]
        cost = m[c] * v + (50 if len(moves[owner[c]]) == 7 else 0)
        drops.append((cost, c))
    drops.sort()
    fi = min(i for i, mm in enumerate(moves)
             if len(mm) == 7 and len({y for (_, y) in mm}) == 1 and mm[0][1] in (0, 7, 14)
             and i >= len(moves) - 12)
    adds = []
    for (x, y) in [(x, y) for y in range(15) for x in range(15) if not grid[y][x]]:
        if not any((x + dx, y + dy) in occ for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))): continue
        na, _ = mc.score_of(moves + [[(x, y)]], fixed)
        vo, _ = mc.score_of(moves[:fi] + [[(x, y)]] + moves[fi:], fixed)
        adds.append((max(na - base, vo - base), (x, y), na >= vo))
    adds.sort(reverse=True)
    return drops, adds, base


tried = 0; wins = 0
print(f"[w{WORKER}] start, deadline over {int((DEADLINE-time.time())/60)} min", flush=True)
while time.time() < DEADLINE:
    try:
        D = load_best()
        drops_all, adds_all, base = candidates(D)
        cheap = [c for cost, c in drops_all[:12]]
        top = [(gain, c, na) for gain, c, na in adds_all[:30] if gain > 0]
        if not top: time.sleep(5); continue
        k = rnd.choice([1, 1, 2, 2, 3, 4])
        drops = rnd.sample(cheap, min(k, len(cheap)))
        picks = rnd.sample(top, min(k, len(top)))
        groups = []; tail = []
        for gain, c, prefer_na in picks:
            if prefer_na or rnd.random() < 0.4: tail.append(c)
            else: groups.append([c])
        # af en toe: een aaneengesloten groep (kolom- of rijstuk) in plaats van losse cellen
        if rnd.random() < 0.35 and picks:
            gx, gy = picks[0][1]
            vert = rnd.random() < 0.5
            grp = [(gx, gy + i) if vert else (gx + i, gy) for i in range(rnd.choice([2, 3]))]
            grid = D['grid']
            if all(0 <= a < 15 and 0 <= b < 15 and not grid[b][a] for a, b in grp):
                groups = [grp]; tail = []
                drops = rnd.sample(cheap, min(len(grp), len(cheap)))
        built = build(D, drops, groups, tail)
        tried += 1
        if not built: continue
        g, mv, occ, grid0 = built
        res = solve(g, mv, occ, grid0, set(tuple(b) for b in D.get('blanks', [])))
        if not res: continue
        g2, blset = res
        tot, per, ok, msg = MG.score_game([row[:] for row in g2], mv, blset)
        if ok and int(tot) > int(D['total']):
            out = {'grid': g2, 'moves': [[list(c) for c in m] for m in mv],
                   'blanks': [list(b) for b in sorted(blset)], 'total': int(tot),
                   'triple': D.get('triple', ['geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje']),
                   'plan': f'LNS w{WORKER}: sloop {sorted(drops)} bouw {groups}{tail}'}
            if publish(out):
                wins += 1
                print(f"[w{WORKER}] *** NIEUW BEST {int(tot)} *** sloop {sorted(drops)} "
                      f"bouw {groups}{tail} (poging {tried})", flush=True)
        if tried % 10 == 0:
            print(f"[w{WORKER}] {tried} pogingen, {wins} treffers, basis {D['total']}", flush=True)
    except Exception:
        traceback.print_exc(); time.sleep(2)
print(f"[w{WORKER}] klaar: {tried} pogingen, {wins} treffers", flush=True)
