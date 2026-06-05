"""
Experiment 27: the HOLISTIC model — knapsack objective channeled onto the board.

Insight (user): the automaton is great for CONNECTIVITY (any feasible filling will do, loose LP is
fine) but a fixed precomputed WORD LIST is better for SCORE MAXIMIZATION (tight bound, see exp26).
So build ONE model that uses both:
  - word-choice vars x[col,word] carry the SCORE and the TILE BUDGET  -> tight objective bound
  - they are CHANNELED into the board cells (x[c,w]=1 => column c spells w, empty below)
  - the board carries horizontal row-automatons (and later single_component) for validity/connectivity
The bound comes from the x-knapsack (proved in 4s in exp26); the cells only add feasibility.

Compare: pure MMKP (exp26) proved in 4s; the cell+automaton scoring model (exp24/25) never proved
in 600s. Does channeling x onto the board keep it fast?

Run: python experiments/27_holistic_knapsack_board.py [board] [cap] [--connect] [--rows N]
"""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count

board = sys.argv[1] if len(sys.argv) > 1 else '11'
CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
CONNECT = '--connect' in sys.argv
ROWS = int(sys.argv[sys.argv.index('--rows') + 1]) if '--rows' in sys.argv else 1   # 0=none,1=row1,2=all
HMAX = int(sys.argv[sys.argv.index('--hmax') + 1]) if '--hmax' in sys.argv else None # cap horizontal-word length
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
main_word, turn_str = "mucolyticum", "MUCOlYtiCuM"
assert len(main_word) == W
main_tup = rules.alphabet.to_tup(main_word)
scoring_cols = [x for x in range(W) if turn_str[x].isupper()]

print(f"board {W}x{H}, scoring cols {scoring_cols}, connect={CONNECT}, rows={ROWS}, cap={CAP}s")
print("gathering candidates...")
def candidates_for(x):
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H: continue
        if len(w) > 1 and w[1:] not in rules.words_lookup: continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, sc, Counter(w[1:])))
    return out
cands = {c: candidates_for(c) for c in scoring_cols}
print(f"candidates: { {c: len(cands[c]) for c in scoring_cols} } total={sum(len(v) for v in cands.values())}")
nc_ub = sum(max(sc for _, sc, _ in cands[c]) for c in scoring_cols)
print(f"no-contention UB = {nc_ub}\n")

m = cp_model.CpModel(); m.prefix = 'hol'
hwords = rules.words if HMAX is None else [w for w in rules.words if len(w) <= HMAX]
print(f"horizontal automaton over {len(hwords)} words (<= {HMAX})" if HMAX else "horizontal automaton over all words")
row_aut = position_independent_row_automaton(hwords)
rows = ([None] * H if ROWS == 0 else
        [None] + [row_aut] + [None] * (H - 2) if ROWS == 1 else
        [None] + [row_aut] * (H - 1))   # row 0 is the pinned main word (often > hmax); never automaton it
cells = create_board(m, rows, [None] * W, alphabet_size=len(rules.abc))

for x in range(W):                                   # main word pinned in row 0
    m.add(cells[(x, 0)].letter[main_tup[x]] == 1)

# word-choice vars channeled into the scoring columns
xv = {}
for c in scoring_cols:
    vs = []
    for i, (w, sc, rq) in enumerate(cands[c]):
        v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
        for r in range(H):
            if r < len(w):
                m.add(cells[(c, r)].letter[w[r]] == 1).only_enforce_if(v)
            else:
                m.add(cells[(c, r)].active == 0).only_enforce_if(v)
    m.add(sum(vs) == 1)

# non-scoring columns: just the placed main tile, empty below (unless we need them for bridges)
for c in range(W):
    if c not in scoring_cols and not CONNECT:
        for r in range(1, H):
            m.add(cells[(c, r)].active == 0)

# TIGHT tile budget on the word vars (avail = bag minus the fixed main word)
avail = Counter(rules.counts)
for code in main_tup:
    avail[code] -= 1
for code, cap in avail.items():
    usage = [xv[(c, i)] * rq[code] for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
    if usage:
        m.add(sum(usage) <= cap)

if CONNECT:
    # correct, cell-based budget counts EVERYTHING (incl. bridge tiles); the x-budget above is a
    # redundant-but-tightening view that keeps the OBJECTIVE bound tight.
    limit_letter_count(m, cells, rules.counts)
    single_component(m, cells, (W // 2, H // 2))

m.maximize(sum(xv[(c, i)] * sc for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c])))

print(f"model: {len(m.proto.variables)} vars, {len(m.proto.constraints)} constraints")
s = cp_model.CpSolver()
s.parameters.num_search_workers = 24
s.parameters.max_time_in_seconds = CAP
s.parameters.max_presolve_iterations = 1     # match do_solve: multi-iter presolve is slow on the monster, no benefit
s.parameters.log_search_progress = True
t = time.time(); r = s.Solve(m); st = time.time() - t
name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE'}.get(r, str(r))
obj = int(s.objective_value) if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
bnd = s.best_objective_bound if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
print(f"\nRESULT  solve={st:.1f}s {name}  obj={obj}  bound={bnd}  "
      f"gap={(bnd-obj) if obj is not None else '?'}")
