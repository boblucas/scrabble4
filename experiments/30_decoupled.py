"""
Experiment 30: DECOUPLED max-turn solver  (sound + provable, aims to fit memory).

The holistic legal model OOM'd at N=11: validating cross-words in BOTH directions needs ~15
big <=8-word automata, and proving its score bound also hit the loose single_component LP.
Decouple, per the user's "automaton for connectivity, word-list for scoring" principle:

  Stage A (SCORE -- proven in seconds): word-choice knapsack. Pick one valid vertical per
    scoring column, tile budget + blank relaxation, MAXIMIZE score. Ignores connectivity &
    cross-words, so its optimum S is an UPPER BOUND on the legal optimum. Enumerate solutions
    in DESCENDING score via no-goods.

  Stage B (LEGALITY + CONNECTIVITY -- tiny objective, no stall): FIX Stage A's chosen
    verticals, add row+column cross-word automata + single_component + blank-aware tile budget,
    and maximize score (only the blank penalty can move now; verticals are constants). Returns
    the best LEGAL score L for that vertical set (L <= S). Because the score is essentially
    fixed, the connectivity-LP stall that blocked the holistic does not recur.

  Loop: best = max L seen. Stop when the next candidate's upper bound S <= best (no remaining
  candidate can win). The first time a candidate's L meets its own S we have a certified legal
  optimum for that main word.

KEY MEASUREMENT: does pinning the verticals let presolve collapse the row automata enough to
fit memory? Stage B prints its model size before/after presolve.

Run: python experiments/30_decoupled.py [board] [--main W --turn T] [--blanks] [--scale-tiles] [--hmax N] [--maxcand K]
"""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count

board = sys.argv[1] if len(sys.argv) > 1 else '11'
HMAX = int(sys.argv[sys.argv.index('--hmax') + 1]) if '--hmax' in sys.argv else 8
BLANKS = '--blanks' in sys.argv
MAXCAND = int(sys.argv[sys.argv.index('--maxcand') + 1]) if '--maxcand' in sys.argv else 400
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
print(f"board {W}x{H}, scoring {scoring_cols}, preplaced {preplaced}, hmax={HMAX}, blanks={rules.blank_count}")

# ---- candidate verticals per scoring column (start with main letter, w[1:] a valid word) -----
def candidates_for(x):
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H: continue
        if len(w) > 1 and w[1:] not in rules.words_lookup: continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, sc, Counter(w[1:])))
    return out
cands = {c: sorted(candidates_for(c), key=lambda t: -t[1])[:MAXCAND] for c in scoring_cols}
print(f"candidates {{c:len}} = { {c: len(cands[c]) for c in scoring_cols} }")

# ---- shared automaton (<=hmax connective words) -----------------------------------------------
hw = [w for w in rules.words if len(w) <= HMAX]
ROW_AUT = position_independent_row_automaton(hw)
newly = Counter(main_tup[c] for c in scoring_cols)        # newly-placed main tiles: not on setup board
avail_setup = Counter({code: rules.counts[code] - newly[code] for code in rules.counts})


# ============================ STAGE A : score knapsack (proven) ================================
def build_stage_a():
    m = cp_model.CpModel(); m.prefix = 'A'
    xv = {}
    for c in scoring_cols:
        vs = []
        for i, (w, sc, rq) in enumerate(cands[c]):
            v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
        m.add(sum(vs) == 1)
    over = {code: m.new_int_var(0, rules.blank_count, f'o_{code}') for code in rules.counts} if rules.blank_count else {}
    if over:
        m.add(sum(over.values()) <= rules.blank_count)
    pen = 0
    for code in rules.counts:
        cap = rules.counts[code] - main_tup.count(code)
        usage = [xv[(c, i)] * rq[code] for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= cap)
        if code in over:
            pen = pen + over[code] * rules.scores[code]
    m.maximize(sum(xv[(c, i)] * sc for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c])) - pen)
    return m, xv


# ============================ STAGE B : legality + connectivity ================================
# Fix the chosen verticals; the only free things are bridge tiles + which tiles are blanks. The
# board must be fully legal (cross-words in both directions) and a single connected component.
def stage_b(chosen, fixed_cols=None, cap=0.0, log=False):
    # fixed_cols: which scoring columns to PIN to their chosen vertical. Columns not in fixed_cols
    # are FREED (cells below row 0 unconstrained, no column automaton) -- a strict RELAXATION, so
    # if a relaxed subset is INFEASIBLE the full assignment is infeasible too (sound conflict cut).
    if fixed_cols is None:
        fixed_cols = set(scoring_cols)
    m = cp_model.CpModel(); m.prefix = 'B'
    rows = [ROW_AUT] * H                                          # every row incl. row 0
    cols = [ROW_AUT if x not in scoring_cols else None for x in range(W)]   # vertical cross-words
    cells = create_board(m, rows, cols, alphabet_size=len(rules.abc))
    # row 0 setup: pre-placed pinned, scoring cols empty (the main tile is placed *this* turn)
    for x in preplaced:
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
    for x in scoring_cols:
        m.add(cells[(x, 0)].active == 0)
    # FIX the chosen verticals on fixed_cols (w[1:] stubs in rows 1..len-1, empty below)
    grossV = 0
    for c, (w, sc, rq) in chosen.items():
        if c not in fixed_cols:
            continue                                             # freed column: cells below stay free
        grossV += sc
        for r in range(1, H):
            if r < len(w):
                m.add(cells[(c, r)].letter[w[r]] == 1)
            else:
                m.add(cells[(c, r)].active == 0)
    # blank-aware tile budget over ALL cells (pre-placed + stubs + bridges)
    limit_letter_count(m, cells, avail_setup)
    over = {code: 0 for code in rules.counts}
    penalty = 0
    if rules.blank_count:
        m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
        # penalty only on SCORING-vertical cells (bridges are score 0, so blanking them is free)
        for code in rules.counts:
            terms = []
            for c in scoring_cols:
                for r in range(1, H):
                    cell = cells[(c, r)]
                    b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                    m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                    terms.append(b)
            o = m.new_int_var(0, rules.blank_count, f'o_{code}')
            m.add(o == sum(terms)); over[code] = o
            penalty = penalty + o * rules.scores[code]
    if preplaced:
        single_component(m, cells, (preplaced[0], 0))
    full = fixed_cols == set(scoring_cols)
    if full and log:
        print(f"  stageB model: {len(m.proto.variables)} vars, {len(m.proto.constraints)} constraints", flush=True)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 24
    s.parameters.max_presolve_iterations = 1
    s.parameters.log_search_progress = log
    if cap:
        s.parameters.max_time_in_seconds = cap
    # FEASIBILITY first, NO objective -> presolve catches the unconnectable monsters fast.
    r = s.Solve(m)
    nm = {cp_model.OPTIMAL: 'FEASIBLE', cp_model.FEASIBLE: 'FEASIBLE', cp_model.INFEASIBLE: 'INFEASIBLE'}
    name = nm.get(r, 'UNKNOWN')
    legal = None
    if full and name == 'FEASIBLE':
        # legal board exists; maximize the (tiny) score = grossV - blank penalty to certify the value
        m.maximize(grossV - penalty)
        s.Solve(m)
        legal = int(s.objective_value)
    return name, legal, grossV, s, cells


# greedy minimal infeasible subset (Benders/CEGAR cut): drop columns while the relaxed subproblem
# stays INFEASIBLE. Freeing a column is a relaxation, so a relaxed-infeasible subset proves the full
# assignment infeasible -> we can forbid the whole subset at once (kills all assignments sharing it).
def find_conflict(chosen, cap=30.0):
    # Returns a minimal column subset whose words are PROVABLY jointly infeasible, or None if we
    # can't prove any subset infeasible (e.g. the full check only timed out).
    S = set(scoring_cols)
    for c in list(scoring_cols):
        trial = S - {c}
        if not trial:
            continue
        name, *_ = stage_b(chosen, fixed_cols=trial, cap=cap)
        if name == 'INFEASIBLE':
            S = trial
    # verify the surviving subset is actually proven infeasible (matters when the full was UNKNOWN)
    name, *_ = stage_b(chosen, fixed_cols=S, cap=cap)
    return S if name == 'INFEASIBLE' else None

# ============================ search loop (CEGAR) ==============================================
from solve import do_solve
maA, xvA = build_stage_a()
best_legal, best = -1, None
it, nfeas, nconf, nunknown, max_unknown_S = 0, 0, 0, 0, -1
t0 = time.time()
MAXIT = int(sys.argv[sys.argv.index('--maxit') + 1]) if '--maxit' in sys.argv else 5000
MAXSEC = float(sys.argv[sys.argv.index('--maxsec') + 1]) if '--maxsec' in sys.argv else 3600.0
for asolver in do_solve(maA, log=False, cores=24):
    S = int(asolver.objective_value)               # Stage A upper bound for this candidate
    idx = {c: next(i for i in range(len(cands[c])) if asolver.Value(xvA[(c, i)])) for c in scoring_cols}
    chosen = {c: cands[c][idx[c]] for c in scoring_cols}
    it += 1
    if S <= best_legal:
        print(f"STOP: candidate #{it} upper bound {S} <= best legal {best_legal}  ({time.time()-t0:.0f}s)")
        break
    name, legal, grossV, s, cells = stage_b(chosen, cap=90.0)
    if name == 'FEASIBLE':
        nfeas += 1
        maA.add_bool_or([~xvA[(c, idx[c])] for c in scoring_cols]) # forbid just this exact assignment
        if legal > best_legal:
            best_legal = legal; best = ({c: chosen[c] for c in scoring_cols}, legal, s, cells)
            words = {c: abc_to_str(chosen[c][0]) for c in scoring_cols}
            print(f"#{it} S={S} FEASIBLE legal={legal}  <-- NEW BEST  {words}  [{time.time()-t0:.0f}s]", flush=True)
    else:                                                          # INFEASIBLE or UNKNOWN
        conflict = find_conflict(chosen)                           # provably-infeasible subset, or None
        if conflict is not None:
            nconf += 1
            maA.add_bool_or([~xvA[(c, idx[c])] for c in conflict]) # forbid the whole conflict subset
            if it <= 25 or it % 50 == 0:
                print(f"#{it} S={S} {name}->conflict cols {sorted(conflict)} "
                      f"({ {c: abc_to_str(cands[c][idx[c]][0]) for c in conflict} })  [{time.time()-t0:.0f}s]", flush=True)
        else:
            nunknown += 1; max_unknown_S = max(max_unknown_S, S)   # couldn't prove infeasible -> gap
            maA.add_bool_or([~xvA[(c, idx[c])] for c in scoring_cols])
            print(f"#{it} S={S} UNRESOLVED (no proof) -> bracket-limiting  [{time.time()-t0:.0f}s]", flush=True)
    if it >= MAXIT or time.time() - t0 > MAXSEC:
        print(f"(stop: it={it} MAXIT={MAXIT} elapsed={time.time()-t0:.0f}s)"); break

proven = max_unknown_S <= best_legal           # every candidate above best_legal was proven infeasible
print(f"\n==== {main_word}: best LEGAL verticals = {best_legal}  "
      f"({'PROVEN OPTIMAL' if proven else f'BRACKET [{best_legal}, {max_unknown_S}] -- {nunknown} unresolved'}) ====")
print(f"     {it} candidates, {nfeas} feasible, {nconf} conflict-cuts, {nunknown} unresolved, {time.time()-t0:.0f}s")
if best:
    chosen, legal, s, cells = best
    from turn_render import chosen_from_solver, render, save
    ch = {c: (chosen[c][0], chosen[c][1]) for c in chosen}
    text = render(s, cells, ch, turn_str, rules, main_score=None, vert_score=legal)
    print("\n" + text)
    save(f'experiments/results/turns/N{W}_{main_word}_legal.txt', text,
         header=f"DECOUPLED legal optimum  board {W}x{H}  main={main_word}  verticals={legal}")
