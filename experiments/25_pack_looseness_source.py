"""
Experiment 25: WHAT makes the bare vertical-pack bound loose (exp24 config A: gap 87 / 22%)?
Two suspects: the shared TILE BUDGET (limit_letter_count couples the columns) and the MULTIPLIER
scoring (word/letter x2/x3 on row 0). Toggle each on the bare pack (columns + scoring, no rows /
anchor / single_component) and see which one, when removed, lets CP-SAT close.

  tiles ON,  mult ON   = exp24 config A (baseline, gap ~87)
  tiles OFF, mult ON   = columns independent -> should be trivial if the budget is the coupling
  tiles ON,  mult OFF  = does flat (raw letter) scoring close the tile-packing bound?
  tiles OFF, mult OFF  = sanity (separable, trivial)

Run: python experiments/25_pack_looseness_source.py [board] [cap_seconds]
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from scrabble import construct_rules
from dawg import automaton_words_from_dict, T_ANY
from solve import create_board, limit_letter_count, create_word_mapping, estimate_score

board = sys.argv[1] if len(sys.argv) > 1 else '11'
CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
main_word, turn_str = "mucolyticum", "MUCOlYtiCuM"
assert len(main_word) == W
main_tup = rules.alphabet.to_tup(main_word)
scoring_positions = [(x, 0) for x in range(W) if turn_str[x].isupper()]
print(f"board {W}x{H}, {len(scoring_positions)} scoring verticals, cap={CAP}s\n")

print("compiling column automatons (once)...")
col_auts = []
for x in range(W):
    general = {0: {w for w in rules.words if w and w[0] == main_tup[x]},
               1: {}, 2: [w for w in rules.words if len(w) <= 7] + [tuple()]}
    if (x, 0) in scoring_positions:
        general[0] = {w for w in general[0] if w[1:] in rules.words_lookup}
    col_auts.append(automaton_words_from_dict(general, [{T_ANY}] * H))
print("done.\n")

def build(tile_budget, multipliers):
    m = cp_model.CpModel(); m.prefix = 'ver'
    cells = create_board(m, [None] * H, col_auts, alphabet_size=len(rules.abc))
    for x in range(W):
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
    if tile_budget:
        limit_letter_count(m, cells, rules.counts)
        m.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
    _wm = np.ones_like(rules.word_multiplier); _lm = np.ones_like(rules.letter_multiplier)
    if multipliers:                                   # else leave as all-ones (flat raw scoring)
        _wm[0, :] = rules.word_multiplier[0, :]; _lm[0, :] = rules.letter_multiplier[0, :]
    slots = create_word_mapping(m, cells, None, alphabet_size=len(rules.abc))
    score = estimate_score(m, slots, _wm, _lm, {}, rules.scores,
                           {(i, 0, 0) for i in range(W) if (i, 0) in scoring_positions}, bingo=False)
    m.maximize(score)
    return m

def run_cfg(label, **kw):
    print(f"\n##### CONFIG {label} #####", flush=True)
    m = build(**kw)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 24
    s.parameters.max_time_in_seconds = CAP
    s.parameters.log_search_progress = True       # emit the #Bound trajectory so we see close-vs-plateau
    t = time.time(); r = s.Solve(m); st = time.time() - t
    name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE'}.get(r, str(r))
    obj = int(s.objective_value); bnd = s.best_objective_bound
    gap = bnd - obj
    pct = (100.0 * gap / bnd) if bnd else 0.0
    print(f"RESULT {label:26} solve={st:6.1f}s {name:9} obj={obj:4d} bound={bnd:7.1f} gap={gap:6.1f} ({pct:4.1f}%)", flush=True)

print(f"{'config':26} {'solve':>11}  {'status':9} score / bound / gap")
run_cfg("tiles ON,  mult ON  (A)", tile_budget=True,  multipliers=True)
run_cfg("tiles OFF, mult ON",      tile_budget=False, multipliers=True)
run_cfg("tiles ON,  mult OFF",     tile_budget=True,  multipliers=False)
run_cfg("tiles OFF, mult OFF",     tile_budget=False, multipliers=False)
print("\nDONE")
