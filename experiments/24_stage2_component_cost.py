"""
Experiment 24: WHICH component of stage 2 (finding good verticals) is slow?

Stage 2 = columns(valid verticals) + tile budget + scoring  [the "packing" core]
          + row-1 automaton (2nd row must be valid words)
          + partial anchor (each pre-placed run needs a row-2 cell)
          + single_component (full connectivity, merge path)

We build the SAME packing core (fixed main word + scoring pattern from the real N=11 optimum
MUCOLYTICUM) and add ONE component at a time, solving each to optimality (or a time cap) so we
can see exactly where the bound stops closing. Hypothesis: the bare packing is fast/cheap.

Run: python experiments/24_stage2_component_cost.py [board] [cap_seconds]
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from scrabble import construct_rules
from dawg import position_independent_row_automaton, automaton_words_from_dict, T_ANY
from solve import (create_board, single_component, limit_letter_count,
                   create_word_mapping, estimate_score)

board = sys.argv[1] if len(sys.argv) > 1 else '11'
CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 180.0
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H

# the real N=11 optimum main word + placement (upper = newly placed = scores a vertical)
main_word = "mucolyticum"
turn_str  = "MUCOlYtiCuM"
assert len(main_word) == W, f"main word must be {W} letters for board {board}"
main_tup = rules.alphabet.to_tup(main_word)
scoring_positions = [(x, 0) for x in range(W) if turn_str[x].isupper()]
print(f"board {W}x{H}, main='{main_word}', scoring cols={[x for x,_ in scoring_positions]} "
      f"({len(scoring_positions)} verticals), {len(rules.words)} words, cap={CAP}s\n")

# ---- precompute the automatons ONCE (so per-config build is cheap) ------------------------
print("building column automatons + row DFA (once)...")
col_auts = []
for x in range(W):
    general = {0: {w for w in rules.words if w and w[0] == main_tup[x]},
               1: {},
               2: [w for w in rules.words if len(w) <= 7] + [tuple()]}
    if (x, 0) in scoring_positions:
        general[0] = {w for w in general[0] if w[1:] in rules.words_lookup}
    col_auts.append(automaton_words_from_dict(general, [{T_ANY}] * H))
row_aut = position_independent_row_automaton(rules.words)
print("done.\n")

def build(rows_mode, anchor, connectivity):
    """rows_mode: 0=none, 1=row-1 only, 2=all rows. anchor/connectivity: bool."""
    m = cp_model.CpModel(); m.prefix = 'ver'
    if rows_mode == 0:   rows = [None] * H
    elif rows_mode == 1: rows = [None] + [row_aut] + [None] * (H - 2)
    else:                rows = [row_aut] * H
    cells = create_board(m, rows, col_auts, alphabet_size=len(rules.abc))
    if anchor:
        run = []
        for x in range(W):
            if (x, 0) not in scoring_positions: run.append(x)
            elif run:
                m.add(sum(cells[(x2, 1)].active for x2 in run) >= 1); run = []
    limit_letter_count(m, cells, rules.counts)
    m.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
    for x in range(W):
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
    if connectivity:
        single_component(m, cells, (W // 2, H // 2))
    _wm = np.ones_like(rules.word_multiplier); _lm = np.ones_like(rules.letter_multiplier)
    _wm[0, :] = rules.word_multiplier[0, :]; _lm[0, :] = rules.letter_multiplier[0, :]
    slots = create_word_mapping(m, cells, None, alphabet_size=len(rules.abc))
    score = estimate_score(m, slots, _wm, _lm, {}, rules.scores,
                           {(i, 0, 0) for i in range(W) if (i, 0) in scoring_positions}, bingo=False)
    m.maximize(score)
    return m

def run_cfg(label, **kw):
    t = time.time(); m = build(**kw); bt = time.time() - t
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 24
    s.parameters.max_time_in_seconds = CAP
    s.parameters.optimize_with_core = False
    t = time.time(); r = s.Solve(m); st = time.time() - t
    name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE'}.get(r, str(r))
    obj = int(s.objective_value) if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    bnd = round(s.best_objective_bound, 1) if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    gap = (round(bnd - obj, 1) if (obj is not None and bnd is not None) else None)
    print(f"{label:24} build={bt:5.1f}s solve={st:6.1f}s {name:10} obj={obj} bound={bnd} gap={gap}", flush=True)

print(f"{'config':24} {'':5}     {'':6}    status     score / bound")
run_cfg("A bare-pack",        rows_mode=0, anchor=False, connectivity=False)
run_cfg("B +row1-automaton",  rows_mode=1, anchor=False, connectivity=False)
run_cfg("C +row1+anchor",     rows_mode=1, anchor=True,  connectivity=False)
run_cfg("D +all-rows+anchor", rows_mode=2, anchor=True,  connectivity=False)
run_cfg("E +single_component",rows_mode=2, anchor=True,  connectivity=True)
print("\nDONE")
