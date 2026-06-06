"""
Experiment 31: LENGTH-LEVEL decoupled proof search.

Two walls killed exp30's word-level descent: (1) the big word knapsack slows to PROVE optimality
as no-good cuts accumulate; (2) huge candidate count. Both vanish if we enumerate at the LENGTH
level, because geometric connectivity depends ONLY on the vertical lengths (occupied cells are
letter-independent):

  OUTER  -- tiny length model: pick a length per scoring column, maximise sum of the best per-(col,
            length) word score (an optimistic, tile-blind UPPER bound). ~ (cols x lengths) bools, so
            it re-solves instantly even with thousands of no-goods. Enumerate length-vectors in
            descending optimistic UB.
            * geometric prune (Rust oracle, ~1ms): if lengths can't connect even with free bridges
              within the leftover tile budget -> cut the whole length-vector (sound; letter-indep).
            * STOP when optimistic UB <= best legal found (nothing left can beat it -> PROVEN).
  INNER  -- for a geometrically-connectable length-vector, find its BEST LEGAL score: descend the
            (small, fixed-length) word knapsack and, for each word-selection, check legal connected
            placement with the fixed-vertical Stage-B model (feasibility -> fast, no objective stall).
            First feasible word-selection (descending) = best legal score for that length-vector.

All models are SMALL (fixed positions), so nothing stalls. Sound: optimistic UB is a valid upper
bound; best legal is a real achieved board; we stop only when UB <= best legal.

Run: python experiments/31_length_level.py [board] [--main W --turn T] [--blanks] [--scale-tiles]
     [--hmax N] [--maxcand K] [--maxsec S]
"""
import sys, time
from collections import Counter, defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count, do_solve
from connectivity import setup_fixed_cells, RustOracle, components as _components
from turn_render import render, save

board = sys.argv[1] if len(sys.argv) > 1 else '11'
HMAX = int(sys.argv[sys.argv.index('--hmax') + 1]) if '--hmax' in sys.argv else 8
BLANKS = '--blanks' in sys.argv
MAXCAND = int(sys.argv[sys.argv.index('--maxcand') + 1]) if '--maxcand' in sys.argv else 600
MAXSEC = float(sys.argv[sys.argv.index('--maxsec') + 1]) if '--maxsec' in sys.argv else 3600.0
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
main_word = sys.argv[sys.argv.index('--main') + 1] if '--main' in sys.argv else "bouwfysicus"
turn_str  = sys.argv[sys.argv.index('--turn') + 1] if '--turn' in sys.argv else "BOUWfYsiCuS"
assert len(main_word) == W and len(turn_str) == W
main_tup = rules.alphabet.to_tup(main_word)
if '--scale-tiles' in sys.argv:
    f = (W * W) / (15 * 15)
    mc = Counter(main_tup)
    rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
    rules.blank_count = round(rules.blank_count * f)
    print(f"--scale-tiles {f:.3f}: bag {sum(rules.counts.values())} tiles, {rules.blank_count} blanks")
if not BLANKS:
    rules.blank_count = 0
scoring_cols = [x for x in range(W) if turn_str[x].isupper()]
preplaced    = [x for x in range(W) if not turn_str[x].isupper()]
abc_to_str = rules.alphabet.to_str
TOTAL_PHYSICAL = sum(rules.counts.values()) + rules.blank_count
ORACLE = RustOracle(W, H)
print(f"board {W}x{H}, scoring {scoring_cols}, preplaced {preplaced}, hmax={HMAX}, "
      f"blanks={rules.blank_count}, total tiles={TOTAL_PHYSICAL}")

# ---- candidate verticals, grouped by length -------------------------------------------------
def candidates_for(x):
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H: continue
        if len(w) > 1 and w[1:] not in rules.words_lookup: continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, sc, Counter(w[1:])))
    return out
cands = {c: sorted(candidates_for(c), key=lambda t: -t[1])[:MAXCAND] for c in scoring_cols}
by_len = {c: defaultdict(list) for c in scoring_cols}     # c -> length -> [(w,sc,rq)] desc by score
best_at = {c: {} for c in scoring_cols}                   # c -> length -> best score
for c in scoring_cols:
    for w, sc, rq in cands[c]:
        by_len[c][len(w)].append((w, sc, rq))
    for l, lst in by_len[c].items():
        best_at[c][l] = lst[0][1]
lengths = {c: sorted(by_len[c]) for c in scoring_cols}
print(f"lengths per col = { {c: lengths[c] for c in scoring_cols} }")

hw = [w for w in rules.words if len(w) <= HMAX]
ROW_AUT = position_independent_row_automaton(hw)
MINB_GLOBAL = len(_components({(x, 0) for x in preplaced}, W, H))

def bridge_budget_lengths(Lvec):
    stub = sum(l - 1 for l in Lvec.values())
    return TOTAL_PHYSICAL - len(main_tup) - stub


# ==================== OUTER: length model (optimistic UB, descending) =========================
def build_outer():
    m = cp_model.CpModel(); m.prefix = 'L'
    lv = {}
    for c in scoring_cols:
        vs = []
        for l in lengths[c]:
            v = m.new_bool_var(f'l_{c}_{l}'); lv[(c, l)] = v; vs.append(v)
        m.add(sum(vs) == 1)
    # SOUND tile reserve (cheap on this tiny model): the verticals' stub tiles must leave room for
    # the unavoidable bridges (>= MINB_GLOBAL). Eliminates all over-budget length-vectors at once.
    m.add(sum(lv[(c, l)] * (l - 1) for c in scoring_cols for l in lengths[c])
          <= TOTAL_PHYSICAL - len(main_tup) - MINB_GLOBAL)
    m.maximize(sum(lv[(c, l)] * best_at[c][l] for c in scoring_cols for l in lengths[c]))
    return m, lv


# ==================== INNER: best legal score for a fixed length-vector =======================
def stage_b_feasible(chosen_words, cap=60.0):
    """chosen_words: {col: word_tuple}. Build the full LEGAL board with these verticals fixed and
    check a legal connected placement exists; return (feasible, legal_score, solver, cells)."""
    m = cp_model.CpModel(); m.prefix = 'B'
    rows = [ROW_AUT] * H
    cols = [ROW_AUT if x not in scoring_cols else None for x in range(W)]
    cells = create_board(m, rows, cols, alphabet_size=len(rules.abc))
    for x in preplaced:
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
    for x in scoring_cols:
        m.add(cells[(x, 0)].active == 0)
    grossV = 0
    for c, w in chosen_words.items():
        sc, _ = get_word_score(rules, w, c, 0, 0, [i == 0 for i in range(len(w))]); grossV += sc
        for r in range(1, H):
            if r < len(w):
                m.add(cells[(c, r)].letter[w[r]] == 1)
            else:
                m.add(cells[(c, r)].active == 0)
    newly = Counter(main_tup[c] for c in scoring_cols)
    limit_letter_count(m, cells, Counter({code: rules.counts[code] - newly[code] for code in rules.counts}))
    penalty = 0
    if rules.blank_count:
        m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
        for code in rules.counts:
            terms = []
            for c in scoring_cols:
                for r in range(1, H):
                    cell = cells[(c, r)]
                    b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                    m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                    terms.append(b)
            o = m.new_int_var(0, rules.blank_count, f'o_{code}'); m.add(o == sum(terms))
            penalty = penalty + o * rules.scores[code]
    if preplaced:
        single_component(m, cells, (preplaced[0], 0))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_presolve_iterations = 1
    if cap: s.parameters.max_time_in_seconds = cap
    r = s.Solve(m)                                       # feasibility first (no objective)
    if r not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return (r == cp_model.INFEASIBLE), None, s, cells, 'INFEASIBLE' if r == cp_model.INFEASIBLE else 'UNKNOWN'
    m.maximize(grossV - penalty)                         # tiny: only blank penalty moves
    s.Solve(m)
    return True, int(s.objective_value), s, cells, 'FEASIBLE'


def inner_best_legal(Lvec, floor, cap=180.0):
    """Best LEGAL score for fixed lengths Lvec as ONE optimization: word-choice among same-length
    words, channeled to a legal connected board, maximise score (>= floor+1 cut so it's INFEASIBLE-
    fast when nothing beats the incumbent). Returns (legal, chosen, solver, cells, status)."""
    m = cp_model.CpModel(); m.prefix = 'i'
    rows = [ROW_AUT] * H
    cols = [ROW_AUT if x not in scoring_cols else None for x in range(W)]
    cells = create_board(m, rows, cols, alphabet_size=len(rules.abc))
    for x in preplaced:
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
    for x in scoring_cols:
        m.add(cells[(x, 0)].active == 0)
    xv = {}
    items = {c: by_len[c][Lvec[c]] for c in scoring_cols}
    for c in scoring_cols:
        vs = []
        for i, (w, sc, rq) in enumerate(items[c]):
            v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
            for r in range(1, H):
                if r < len(w):
                    m.add(cells[(c, r)].letter[w[r]] == 1).only_enforce_if(v)
                else:
                    m.add(cells[(c, r)].active == 0).only_enforce_if(v)
        m.add(sum(vs) == 1)
    newly = Counter(main_tup[c] for c in scoring_cols)
    limit_letter_count(m, cells, Counter({code: rules.counts[code] - newly[code] for code in rules.counts}))
    penalty = 0
    if rules.blank_count:
        m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
        for code in rules.counts:
            terms = []
            for c in scoring_cols:
                for r in range(1, H):
                    cell = cells[(c, r)]
                    b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                    m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                    terms.append(b)
            o = m.new_int_var(0, rules.blank_count, f'o_{code}'); m.add(o == sum(terms))
            penalty = penalty + o * rules.scores[code]
    if preplaced:
        single_component(m, cells, (preplaced[0], 0))
    obj = sum(xv[(c, i)] * sc for c in scoring_cols for i, (w, sc, rq) in enumerate(items[c])) - penalty
    m.add(obj >= floor + 1)                              # only care about beating the incumbent -> fast UNSAT
    m.maximize(obj)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_presolve_iterations = 1
    if cap: s.parameters.max_time_in_seconds = cap
    r = s.Solve(m)
    name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE', cp_model.INFEASIBLE: 'INFEASIBLE'}.get(r, 'UNKNOWN')
    if name in ('OPTIMAL', 'FEASIBLE'):
        legal = int(s.objective_value)
        chosen = {c: items[c][next(i for i in range(len(items[c])) if s.Value(xv[(c, i)]))][0] for c in scoring_cols}
        return legal, chosen, s, cells, name
    return None, None, s, cells, name


# ==================== OUTER CEGAR loop ========================================================
mo, lv = build_outer()
best_legal, best = -1, None
it, ngeom, ninner, nfeas, nunres, max_unres = 0, 0, 0, 0, 0, -1
t0 = time.time()
for osolver in do_solve(mo, log=False, cores=4):
    UB = int(osolver.objective_value)
    if UB <= best_legal:
        print(f"STOP: outer UB {UB} <= best legal {best_legal} -> PROVEN ({time.time()-t0:.0f}s)")
        break
    Lvec = {c: next(l for l in lengths[c] if osolver.Value(lv[(c, l)])) for c in scoring_cols}
    it += 1
    mo.add_bool_or([lv[(c, Lvec[c])].Not() for c in scoring_cols])   # resolve this length-vector
    # geometric prune (letter-independent, sound)
    fx = setup_fixed_cells(W, H, turn_str, main_tup, {c: tuple([0] * Lvec[c]) for c in scoring_cols})
    if not ORACLE.can_connect(fx, bridge_budget_lengths(Lvec)):
        ngeom += 1
        if it <= 20 or it % 500 == 0:
            print(f"#{it} UB={UB} GEOM-infeasible lengths {Lvec} [{time.time()-t0:.0f}s]", flush=True)
        if time.time() - t0 > MAXSEC: print("(maxsec)"); break
        continue
    ninner += 1
    # Re-call inner with the rising floor until Lvec is proven resolved (OPTIMAL/INFEASIBLE) or we
    # give up (UNKNOWN, or too many cap-hits). Each capped FEASIBLE raises best_legal, tightening the
    # `obj >= floor+1` cut so the final "nothing beats it" check is a fast infeasibility proof.
    resolved = False
    for _try in range(12):
        legal, chosen, s, cells, name = inner_best_legal(Lvec, best_legal, cap=45.0)
        if name == 'OPTIMAL':
            if legal > best_legal:
                best_legal = legal; best = (chosen, legal, s, cells)
                print(f"#{it} UB={UB} -> LEGAL {legal} (proved best for lengths)  <-- NEW BEST  "
                      f"{ {c: abc_to_str(chosen[c]) for c in scoring_cols} }  [{time.time()-t0:.0f}s]", flush=True)
            resolved = True; nfeas += 1; break
        if name == 'INFEASIBLE':
            resolved = True; break                       # no legal board for Lvec beats best_legal
        if name == 'FEASIBLE':                           # capped incumbent: raise floor, re-try
            nfeas += 1
            if legal > best_legal:
                best_legal = legal; best = (chosen, legal, s, cells)
                print(f"#{it} UB={UB} -> LEGAL {legal} (incumbent)  <-- NEW BEST  "
                      f"{ {c: abc_to_str(chosen[c]) for c in scoring_cols} }  [{time.time()-t0:.0f}s]", flush=True)
            continue
        break                                            # UNKNOWN
    if not resolved:
        nunres += 1; max_unres = max(max_unres, UB)
        print(f"#{it} UB={UB} inner UNRESOLVED (cap) -> bracket-limiting [{time.time()-t0:.0f}s]", flush=True)
    if time.time() - t0 > MAXSEC:
        print(f"(maxsec at it={it})"); break

dt = time.time() - t0
proven = (max_unres <= best_legal)
verdict = "PROVEN OPTIMAL" if proven else f"BRACKET [{best_legal}, {max_unres}] ({nunres} unresolved)"
print(f"\n==== {main_word}: best LEGAL verticals = {best_legal}  --  {verdict} ====")
print(f"     {it} length-vectors, {ngeom} geom-cut, {ninner} inner, {nfeas} feasible, {nunres} unresolved, {dt:.0f}s")
if best:
    chosen, legal, s, cells = best
    ch = {c: (chosen[c], 0) for c in chosen}
    text = render(s, cells, ch, turn_str, rules, main_score=None, vert_score=legal)
    print("\n" + text)
    save(f'experiments/results/turns/N{W}_{main_word}_legal.txt', text,
         header=f"LENGTH-LEVEL legal optimum  board {W}x{H}  main={main_word}  verticals={legal}")
