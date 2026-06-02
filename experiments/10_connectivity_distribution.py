"""
Experiment 10: connectivity build-vs-solve time across the REAL candidate boards
the board-7 english run emitted. Characterises whether the bottleneck is the
per-candidate automaton REBUILD (candidate-independent) or the single_component SOLVE.

Run: python experiments/10_connectivity_distribution.py
"""
import sys, time, ast
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules
from dawg import automaton_words_from_list
from solve import create_board, single_component, limit_letter_count

def build_and_time(rules, CAND, omit_bottom_rows=3, max_vertical_length=5):
    partial = [[[c] for c in row] for row in CAND]
    t = time.time()
    rows = [automaton_words_from_list(rules.words + [tuple()], rules.W, partial[y])
            for y in range(rules.H - omit_bottom_rows)] + [None] * omit_bottom_rows
    columns = []
    for x in range(rules.W):
        col = list(zip(*partial))[x]
        if partial[1][x][-1] >= 0:
            columns.append(automaton_words_from_list(rules.words + [tuple()], rules.H, col))
        else:
            columns.append(automaton_words_from_list([w for w in rules.words if len(w) <= max_vertical_length] + [tuple()], rules.H, col))
    model = cp_model.CpModel(); model.prefix = "connect"
    cells = create_board(model, rows, columns, alphabet_size=len(rules.abc))
    for x in range(rules.W):
        for y in range(rules.H):
            if partial[y][x][0] >= 0:
                model.add(cells[(x, y)].letter[partial[y][x][0]] == 1)
    limit_letter_count(model, cells, rules.counts)
    model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
    single_component(model, cells, (rules.W // 2, rules.H // 2))
    t_build = time.time() - t

    t = time.time()
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.max_time_in_seconds = 120
    res = solver.Solve(model)
    t_solve = time.time() - t
    v = {cp_model.OPTIMAL: 'SAT', cp_model.FEASIBLE: 'SAT', cp_model.INFEASIBLE: 'UNSAT'}.get(res, str(res))
    return t_build, t_solve, v

def main():
    rules = construct_rules('english', '7')
    cands = [ast.literal_eval(l) for l in open('experiments/results/turns/eng7_candidates.txt') if l.strip()]
    print(f"{len(cands)} candidates; per-candidate connectivity (build = candidate-independent automaton work):")
    tb_tot = ts_tot = 0
    for i, c in enumerate(cands):
        tb, ts, v = build_and_time(rules, c)
        tb_tot += tb; ts_tot += ts
        print(f"  cand {i}: build={tb:6.2f}s  solve={ts:7.2f}s  -> {v}")
    print(f"  ---- totals: build={tb_tot:.1f}s  solve={ts_tot:.1f}s "
          f"(build is {100*tb_tot/(tb_tot+ts_tot):.0f}% of the time)")

if __name__ == '__main__':
    main()
