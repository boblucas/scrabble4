"""Ladder-generator: her-letteren met gedecomposeerd zetplan. Zetten worden
1-tegel-per-keer gespeeld (waar CP-SAT een ladder-woord vindt): elke stap
herscoort zijn run — triangulaire accumulatie i.p.v. eenmalige score.
Greedy per zet: probeer split (asc/desc volgorde); houd als feasible en obj
stijgt. Finals (x27) blijven heel. Arbiter verifieert eindresultaat.
Env: LDBASE, LDOUT, TLIM (per solve), TFIN (eindsolve)."""
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

D = json.load(open(os.environ.get('LDBASE', 'experiments/results/maxgame_BEST.json')))
grid0 = D['grid']; moves_init = [[tuple(c) for c in m] for m in D['moves']]
blanks0 = set(tuple(b) for b in D.get('blanks', []))
TLIM = float(os.environ.get('TLIM', '75')); TFIN = float(os.environ.get('TFIN', '400'))
occ = [(x, y) for y in range(15) for x in range(15) if grid0[y][x]]
fixed = {(x, y): grid0[y][x] for (x, y) in occ if y in (0, 7, 14)}
free = [c for c in occ if c not in fixed]

def solve_mv(mv, tlim):
    m_ = cp_model.CpModel(); L = {}
    for c in free: L[c] = m_.new_int_var(1, 26, f"L{c}")
    for c, v in fixed.items(): L[c] = m_.new_constant(v)
    placed = set(); events = []; stage_runs = set()
    for t, cells in enumerate(mv):
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
                run_ = [(x0 + i * dx, y0 + i * dy) for i in range(n)]
                if any(c in cset for c in run_): events.append((run_, cset)); stage_runs.add(tuple(run_))
    for run_ in stage_runs:
        fx = {i: fixed[c] for i, c in enumerate(run_) if c in fixed}
        tab = [w for w in bylen.get(len(run_), []) if all(w[i] == v for i, v in fx.items())]
        if not tab: return ('nowords', None, None, None)
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
        m_.add_hint(L[c], grid0[c[1]][c[0]])
        m_.add_hint(BL[c], 1 if c in blanks0 else 0)
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = tlim; sol.parameters.num_workers = 8
    st = sol.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeas' if st == cp_model.INFEASIBLE else 'unknown', None, None, None)
    g2 = [row[:] for row in grid0]
    for c in free: g2[c[1]][c[0]] = sol.value(L[c])
    blset = {c for c in free if sol.value(BL[c])}
    return ('ok', sol.objective_value, g2, blset)

fin_idx = set(i for i, m in enumerate(moves_init)
              if len(m) == 7 and len({y for (_, y) in m}) == 1 and m[0][1] in (0, 7, 14))
fin_idx = {i for i in fin_idx if i >= len(moves_init) - 12}

st0, obj0, _, _ = solve_mv(moves_init, float(os.environ.get('TBASE', '300')))
print(f"basis-obj: {obj0} ({st0})", flush=True)
if obj0 is None:
    print("basis-solve faalde; stop", flush=True); sys.exit(1)
cur_mv = list(moves_init); cur_obj = obj0
fin_moves = [tuple(sorted(moves_init[i])) for i in fin_idx]

def variants(pos, cells):
    n = len(cells)
    out = []
    if pos == 0 and (7, 7) in cells:
        # centerzet: 1-tegel-ketens die op (7,7) beginnen en aaneengesloten groeien
        rest = sorted(c for c in cells if c != (7, 7))
        lo = [c for c in rest if c < (7, 7)][::-1]; hi = [c for c in rest if c > (7, 7)]
        out.append(('c-omhoog', [[(7, 7)]] + [[c] for c in lo] + [[c] for c in hi]))
        out.append(('c-omlaag', [[(7, 7)]] + [[c] for c in hi] + [[c] for c in lo]))
        return out
    for tag, seq in (('asc', sorted(cells)), ('desc', sorted(cells, reverse=True))):
        for k in sorted({1, 2, 3, n - 2, n - 1} & set(range(1, n))):
            out.append((f'{tag}k{k}', [list(seq[:k]), list(seq[k:])]))
    return out

ronde = 0; improved = True
while improved and ronde < 6:
    ronde += 1; improved = False
    for pos in range(len(cur_mv)):
        cells = cur_mv[pos]
        if len(cells) < 2 or tuple(sorted(cells)) in fin_moves: continue
        best_var = None
        for tag, groups in variants(pos, cells):
            mv_test = cur_mv[:pos] + groups + cur_mv[pos + 1:]
            st, ob, _, _ = solve_mv(mv_test, TLIM)
            if st == 'ok' and ob > cur_obj and (best_var is None or ob > best_var[0]):
                best_var = (ob, mv_test, tag)
            if st == 'ok' and ob > cur_obj:
                print(f"r{ronde} zet@{pos} ({len(cells)}t) {tag}: obj {ob} (> {cur_obj})", flush=True)
        if best_var:
            cur_obj, cur_mv = best_var[0], best_var[1]
            improved = True
            print(f"  -> SPLIT {best_var[2]} geaccepteerd, obj {cur_obj}, zetten {len(cur_mv)}", flush=True)

print(f"eindsolve ({TFIN}s) op zetplan met {len(cur_mv)} zetten...", flush=True)
st, ob, g2, blset = solve_mv(cur_mv, TFIN)
print("eind:", st, ob, flush=True)
if st == 'ok':
    tot, per, ok, msg = MG.score_game([row[:] for row in g2], cur_mv, blset)
    print("arbiter:", int(tot), "ok:", ok, ("" if ok else msg), flush=True)
    if ok and int(tot) > int(D.get('total', 0)):
        json.dump({'grid': g2, 'moves': [[list(c) for c in m] for m in cur_mv],
                   'blanks': [list(b) for b in sorted(blset)], 'total': int(tot),
                   'triple': D['triple'], 'plan': 'ladder: gedecomposeerd zetplan + herlettering'},
                  open(os.environ.get('LDOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/ladder_best.json'), 'w'))
        print("NIEUW BEST", int(tot), flush=True)
