"""
Experiment 26: the FUNDAMENTAL model, stripped of all board/automaton infrastructure.

Stage-2 scoring, distilled to its combinatorial core = a multiple-choice multidimensional knapsack:
  - each scoring column offers candidate vertical words (start with the main-word letter, the part
    below the placed tile is itself a valid word). Each candidate is an ITEM with:
       * score  = the cross-word's points (top tile placed, gets the row-0 multipliers)
       * req    = letter multiset of the tiles it consumes BELOW row 0 (w[1:]) -- the shared budget
  - pick exactly one word per column (length-1 = just the placed tile, req = {}, always available)
  - subject to: sum of reqs <= available tiles (rules.counts minus the fixed main word)
  - maximize total score.

This should reproduce the loose bound (LP ~= sum of per-column maxima = no-contention UB) while the
integer optimum is lower (tile contention). If so, it's our fast sandbox for scarce-tile
branching / cuts. Reports candidate sizes, the no-contention UB, and the IP obj/bound/gap.

Run: python experiments/26_pure_mmkp.py [board] [cap_seconds] [--prune]
"""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score

board = sys.argv[1] if len(sys.argv) > 1 else '11'
CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
PRUNE = '--prune' in sys.argv
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
main_word, turn_str = "mucolyticum", "MUCOlYtiCuM"
assert len(main_word) == W
main_tup = rules.alphabet.to_tup(main_word)
scoring_cols = [x for x in range(W) if turn_str[x].isupper()]
print(f"board {W}x{H}, scoring cols {scoring_cols}, {len(rules.words)} words\n")

# available tiles = bag minus the fixed main word (its 15 tiles are on the board)
avail = Counter(rules.counts)
for code in main_tup:
    avail[code] -= 1

# ---- candidate verticals per scoring column ----------------------------------------------
def candidates_for(x):
    L = main_tup[x]
    out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H:
            continue
        if len(w) > 1 and w[1:] not in rules.words_lookup:   # below-tile part must be a valid word
            continue
        score, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, score, Counter(w[1:])))
    return out

def prune_dominated(cands):
    # keep only Pareto-optimal items: drop w if some other w' has score' >= score and req' <= req
    items = sorted(cands, key=lambda t: -t[1])          # high score first
    kept = []
    for w, sc, rq in items:
        dominated = False
        for w2, sc2, rq2 in kept:                       # kept all have score >= sc
            if all(rq2[c] <= rq[c] for c in rq) and len(rq2) <= len(set(list(rq2)+list(rq))):
                if sum(rq2.values()) <= sum(rq.values()) and all(rq2[c] <= rq[c] for c in rq):
                    dominated = True; break
        if not dominated:
            kept.append((w, sc, rq))
    return kept

cands = {}
for x in scoring_cols:
    c = candidates_for(x)
    if PRUNE:
        c = prune_dominated(c)
    cands[x] = c
sizes = {x: len(cands[x]) for x in scoring_cols}
print(f"candidates per column{' (pruned)' if PRUNE else ''}: {sizes}  total={sum(sizes.values())}")

# no-contention upper bound = best word per column, tiles ignored
nc_ub = sum(max(sc for _, sc, _ in cands[x]) for x in scoring_cols)
print(f"no-contention UB (sum of per-column maxima, tiles ignored) = {nc_ub}\n")

# ---- multiple-choice multidimensional knapsack -------------------------------------------
m = cp_model.CpModel()
xv = {}
for x in scoring_cols:
    vs = []
    for i, (w, sc, rq) in enumerate(cands[x]):
        v = m.new_bool_var(f'x_{x}_{i}'); xv[(x, i)] = v; vs.append(v)
    m.add(sum(vs) == 1)
for code, cap in avail.items():
    usage = []
    for x in scoring_cols:
        for i, (w, sc, rq) in enumerate(cands[x]):
            if rq[code]:
                usage.append(xv[(x, i)] * rq[code])
    if usage:
        m.add(sum(usage) <= cap)
m.maximize(sum(xv[(x, i)] * sc for x in scoring_cols for i, (w, sc, rq) in enumerate(cands[x])))

s = cp_model.CpSolver()
s.parameters.num_search_workers = 24
s.parameters.max_time_in_seconds = CAP
s.parameters.log_search_progress = True
t = time.time(); r = s.Solve(m); st = time.time() - t
name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE'}.get(r, str(r))
obj = int(s.objective_value); bnd = s.best_objective_bound
print(f"\nRESULT  solve={st:.1f}s {name}  obj={obj}  bound={bnd:.1f}  gap={bnd-obj:.1f} "
      f"({100*(bnd-obj)/bnd:.1f}%)  [no-contention UB was {nc_ub}]")
if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print("chosen:")
    for x in scoring_cols:
        for i, (w, sc, rq) in enumerate(cands[x]):
            if s.value(xv[(x, i)]):
                print(f"  col {x}: {rules.alphabet.to_str(w):14} score={sc:4d} tiles_below={dict(rq)}")
