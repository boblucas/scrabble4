"""Ruil-extensie: sloop een goedkope VRIJE binnencel (niet-ankerrij, 1-tegel-zet)
en voeg met de vrijgekomen cap-ruimte een of meer extensiecellen toe. Volledige
herlettering per variant (CP-SAT + blanco's + zak), arbiter verifieert.
Env: RBASE (json), BASE0 (drempel), DROPS ("[(11,2)]"), ADDS ("[[(7,11)],[(7,3)]]"),
     ROUT (json out), TLIM (per solve, default 150)."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
from ortools.sat.python import cp_model
import numpy as np, maxgame_score as MG

r = MG.r; cba = r.alphabet.cba
val = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
bag = Counter({c: r.counts[c] for c in r.counts})
bylen = {}
for w in r.words_str: bylen.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))

D = json.load(open(os.environ.get('RBASE', 'experiments/results/maxgame_BEST.json')))
grid0 = D['grid']; moves0 = [[tuple(c) for c in m] for m in D['moves']]
blanks0 = set(tuple(b) for b in D.get('blanks', []))
BASE0 = int(os.environ.get('BASE0', '0')); TLIM = float(os.environ.get('TLIM', '150'))


def run(drops, adds):
    dset = set(drops)
    g = [row[:] for row in grid0]
    for (x, y) in dset: g[y][x] = 0
    for (x, y) in adds: g[y][x] = 1
    mv = []
    for m in moves0:
        keep = [c for c in m if c not in dset]
        if not keep: continue
        if len(keep) != len(m): return ('splitzet',)   # sloop binnen een meertegelzet: niet toegestaan
        mv.append(keep)
    # stabiele greedy-touch-herordening van het PRE-FINAL-deel; finals en de
    # post-final-extensiestaart houden hun plaats (extensies werken pas na de finals)
    fin_idx = [i for i, m in enumerate(mv)
               if len(m) == 7 and len({y for (_, y) in m}) == 1 and m[0][1] in (0, 7, 14)][-3:]
    first_fin = fin_idx[0]
    fin = [m for i, m in enumerate(mv) if i >= first_fin]
    tail = [[c] for c in adds]
    pre = [m for i, m in enumerate(mv) if i < first_fin]
    ordered = []; placed_o = set()
    pool = list(pre)
    while pool:
        pick = None
        for i, m in enumerate(pool):
            if not placed_o and (7, 7) in m: pick = i; break
            if placed_o and any((x + dx, y + dy) in placed_o
                                for (x, y) in m for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                pick = i; break
        if pick is None: return ('geenvolgorde',)
        m = pool.pop(pick); ordered.append(m); placed_o |= set(m)
    mv = ordered + fin + tail
    occ = [(x, y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ) > 101: return ('cap',)
    # connectiviteit + center
    seen = {(7, 7)} if g[7][7] else set()
    stack = list(seen)
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < 15 and 0 <= n[1] < 15 and g[n[1]][n[0]] and n not in seen:
                seen.add(n); stack.append(n)
    if len(seen) != len(occ): return ('los',)

    fixed = {(x, y): grid0[y][x] for (x, y) in occ if y in (0, 7, 14) and grid0[y][x]}
    free = [c for c in occ if c not in fixed]
    m_ = cp_model.CpModel(); L = {}
    for c in free: L[c] = m_.new_int_var(1, 26, f"L{c}")
    for c, v in fixed.items(): L[c] = m_.new_constant(v)
    placed = set(); events = []; stage_runs = set()
    for cells in mv:
        placed |= set(cells); cset = set(cells); seen2 = set()
        for (x, y) in cells:
            for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
                x0, y0 = x, y
                while x0 - dx >= 0 and y0 - dy >= 0 and (x0 - dx, y0 - dy) in placed: x0 -= dx; y0 -= dy
                x1, y1 = x, y
                while x1 + dx < 15 and y1 + dy < 15 and (x1 + dx, y1 + dy) in placed: x1 += dx; y1 += dy
                n = max(x1 - x0, y1 - y0) + 1
                if n < 2 or (tag, x0, y0) in seen2: continue
                seen2.add((tag, x0, y0))
                run_ = [(x0 + i * dx, y0 + i * dy) for i in range(n)]
                if any(c in cset for c in run_): events.append((run_, cset)); stage_runs.add(tuple(run_))
    for run_ in stage_runs:
        fx = {i: fixed[c] for i, c in enumerate(run_) if c in fixed}
        tab = [w for w in bylen.get(len(run_), []) if all(w[i] == v for i, v in fx.items())]
        if not tab: return ('nowords', run_)
        m_.add_allowed_assignments([L[c] for c in run_], tab)
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
        base = sum(1 for c, v in fixed.items() if v == ch)
        m_.add(sum(cnt) + base <= bag[ch])
    VV = [0] + [val[i] for i in range(1, 27)]
    valvar = {}
    for c in set(q for run_, _ in events for q in run_):
        v = m_.new_int_var(0, 10, f"v{c}"); m_.add_element(L[c], VV, v)
        if c in BL:
            ve = m_.new_int_var(0, 10, f"ve{c}")
            m_.add(ve == v).only_enforce_if(BL[c].negated()); m_.add(ve == 0).only_enforce_if(BL[c])
            valvar[c] = ve
        else:
            valvar[c] = v
    obj = []; bingos = sum(50 for mm in mv if len(mm) == 7)
    for run_, cset in events:
        wm = 1
        for (x, y) in run_:
            if (x, y) in cset: wm *= int(WM[y][x])
        obj.append(sum(valvar[(x, y)] * (int(LM[y][x]) if (x, y) in cset else 1) for (x, y) in run_) * wm)
    m_.maximize(sum(obj) + bingos)
    for c in free:
        if grid0[c[1]][c[0]]:
            m_.add_hint(L[c], grid0[c[1]][c[0]]); m_.add_hint(BL[c], 1 if c in blanks0 else 0)
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = TLIM; sol.parameters.num_workers = 8
    st = sol.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeas' if st == cp_model.INFEASIBLE else 'unknown',)
    g2 = [row[:] for row in g]
    for c in free: g2[c[1]][c[0]] = sol.value(L[c])
    blset = {c for c in free if sol.value(BL[c])}
    tot, per, ok, msg = MG.score_game([row[:] for row in g2], mv, blset)
    return ('ok' if ok else 'rej', int(tot), g2, mv, sorted(blset), msg)


DROPS = eval(os.environ.get('DROPS', '[(11,2)]'))
ADDS = eval(os.environ.get('ADDS', '[[(7,11)],[(7,3)]]'))
best = (BASE0, None)
for drop in DROPS:
    for add in ADDS:
        res = run([drop], list(add))
        print(f"sloop {drop} + add {add} -> {res[0]}", res[1] if res[0] in ('ok', 'rej') else '',
              (res[5] if res[0] == 'rej' else ''), flush=True)
        if res[0] == 'ok' and res[1] > best[0]:
            best = (res[1], (drop, add))
            json.dump({'grid': res[2], 'moves': [[list(c) for c in m] for m in res[3]],
                       'blanks': [list(b) for b in res[4]], 'total': res[1], 'triple': D['triple'],
                       'plan': f'ruil: sloop {drop} + extensie {add}'},
                      open(os.environ.get('ROUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/ruil_best.json'), 'w'))
            print("NIEUW BEST", res[1], flush=True)
print("BEST:", best, flush=True)
