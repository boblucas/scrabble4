"""INVOEG-INGREEP: sloop cellen en voeg een GROEP nieuwe cellen toe als EEN zet VOOR de slotzetten.

Waarom apart van mg_ruil: die hangt toevoegingen als losse 1-tegelzetten achter de finals aan
(goed voor herscoring-extensies, fataal voor kolomopbouw). Een kolom moet juist als groep VOOR de
finals liggen, want dan kruisen de x27-slotzetten hem en scoren ze het hele kolomwoord met x3 --
bij kolom 14 zelfs drie keer (rij-7-, rij-0- en rij-14-final).

Env: IBASE, DROPSET, ADDSET, TLIM, IOUT, NW.
"""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
from ortools.sat.python import cp_model
import numpy as np, maxgame_score as MG

r = MG.r; cba = r.alphabet.cba
val = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
bag = Counter({c: r.counts[c] for c in r.counts})
bylen = {}
for w in r.words_str: bylen.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))

D = json.load(open(os.environ.get('IBASE', 'experiments/results/maxgame_BEST.json')))
grid0 = D['grid']; moves0 = [[tuple(c) for c in m] for m in D['moves']]
blanks0 = set(tuple(b) for b in D.get('blanks', []))
TLIM = float(os.environ.get('TLIM', '400')); NW = int(os.environ.get('NW', '8'))
DROPS = set(eval(os.environ.get('DROPSET', '[]')))
ADDS = eval(os.environ.get('ADDSET', '[]'))


def build(drops, adds):
    g = [row[:] for row in grid0]
    for (x, y) in drops: g[y][x] = 0
    flat = [c for gp in adds for c in gp] if adds and isinstance(adds[0][0], (list, tuple)) else list(adds)
    for (x, y) in flat: g[y][x] = 1
    occ = [(x, y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ) > 101: return None, f'cap {len(occ)}'
    mv = []
    for m in moves0:
        keep = [c for c in m if c not in drops]
        if keep: mv.append(keep)
    fin_idx = [i for i, m in enumerate(mv)
               if len(m) == 7 and len({y for (_, y) in m}) == 1 and m[0][1] in (0, 7, 14)][-3:]
    first_fin = fin_idx[0]
    pre = [m for i, m in enumerate(mv) if i < first_fin]
    rest = [m for i, m in enumerate(mv) if i >= first_fin]
    # de toegevoegde groep als EEN zet, vlak voor de eerste slotzet
    groups = adds if adds and isinstance(adds[0], (list, tuple)) and adds[0] and isinstance(adds[0][0], (list, tuple)) else [adds]
    pre = pre + [list(gp) for gp in groups]
    ordered = []; placed = set(); pool = list(pre)
    while pool:
        pick = None
        for i, m in enumerate(pool):
            if not placed and (7, 7) in m: pick = i; break
            if placed and any((x + dx, y + dy) in placed
                              for (x, y) in m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pick = i; break
        if pick is None: return None, 'geenvolgorde'
        m = pool.pop(pick); ordered.append(m); placed |= set(m)
    return (g, ordered + rest, occ), None


def solve(g, mv, occ):
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
        tab = [w for w in bylen.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab: return 'nowords', run, None, None
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
        m_.add(sum(cnt) + sum(1 for c, v in fixed.items() if v == ch) <= bag[ch])
    VV = [0] + [val[i] for i in range(1, 27)]
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
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeasible' if st == cp_model.INFEASIBLE else 'unknown'), None, None, None
    g2 = [row[:] for row in g]
    for c in free: g2[c[1]][c[0]] = sol.value(L[c])
    return 'ok', sol.objective_value, g2, {c for c in free if sol.value(BL[c])}


built, err = build(DROPS, ADDS)
if err:
    print("bouw mislukt:", err, flush=True); sys.exit(0)
g, mv, occ = built
print(f"geometrie: {len(occ)} tegels, {len(mv)} zetten, {sum(1 for m in mv if len(m)==7)} bingo's", flush=True)
st, ob, g2, blset = solve(g, mv, occ)
print("solver:", st, ob, flush=True)
if st == 'ok':
    tot, per, ok, msg = MG.score_game([row[:] for row in g2], mv, blset)
    base = int(D.get('total', 0))
    print(f"arbiter {int(tot)} ok={ok} | basis {base} | winst {int(tot)-base} {msg[:60] if not ok else ''}", flush=True)
    if ok and int(tot) > base:
        json.dump({'grid': g2, 'moves': [[list(c) for c in m] for m in mv],
                   'blanks': [list(b) for b in sorted(blset)], 'total': int(tot),
                   'triple': D.get('triple', ['geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje']),
                   'plan': f'invoeging {ADDS} tegen sloop {sorted(DROPS)}'},
                  open(os.environ.get('IOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/insert_best.json'), 'w'))
        print("NIEUW BEST", int(tot), flush=True)
