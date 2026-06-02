"""
Experiment 09: where does a stage-3 connectivity check spend its time?
  matrix-build | automaton-compile(create_board) | single_component | CP-SAT solve

Replicates make_connectivity_solver (max_turn_score.py:214-251) standalone on a real
board-7 candidate, with per-phase timing. Decides the next fix: automaton REUSE (if
build dominates) vs a cheaper connectivity ENCODING (if the single_component solve dominates).

Run: python experiments/09_connectivity_breakdown.py
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules
from dawg import automaton_words_from_list
from solve import create_board, single_component, limit_letter_count, do_solve

CAND = [[-2, -2, -2, -2, -2, -2, -2],
        [1, 14, 8, 9, 14, 7, 1],
        [2, 9, 15, 19, -2, 1, 24],
        [1, 20, 19, -2, -1, 26, 13],
        [25, 5, -2, -1, -1, 5, 5],
        [1, 18, -1, -1, -1, -2, 14],
        [19, 19, -1, -1, -1, -1, -2]]

def main():
    rules = construct_rules('english', '7')
    partial = [[[c] for c in row] for row in CAND]
    omit_bottom_rows, max_vertical_length = 3, 5

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
    t_matrix = time.time() - t

    model = cp_model.CpModel(); model.prefix = "connect"
    t = time.time()
    cells = create_board(model, rows, columns, alphabet_size=len(rules.abc))  # compiles+minimizes automata
    t_board = time.time() - t

    t = time.time()
    for x in range(rules.W):
        for y in range(rules.H):
            if partial[y][x][0] >= 0:
                model.add(cells[(x, y)].letter[partial[y][x][0]] == 1)
    limit_letter_count(model, cells, rules.counts)
    model.add(sum(c.blank for c in cells.values()) <= rules.blank_count)
    t_constraints = time.time() - t

    t = time.time()
    single_component(model, cells, (rules.W // 2, rules.H // 2))
    t_single = time.time() - t

    t = time.time()
    status = None
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.max_time_in_seconds = 60
    res = solver.Solve(model)
    t_solve = time.time() - t
    verdict = {cp_model.OPTIMAL: 'SAT/connectable', cp_model.FEASIBLE: 'SAT/connectable',
               cp_model.INFEASIBLE: 'UNSAT/not-connectable'}.get(res, str(res))

    print(f"board-7 candidate connectivity check breakdown:")
    print(f"  matrix-build (automaton_words_from_list x rows+cols) : {t_matrix:6.2f}s")
    print(f"  create_board (compile+minimize automata, cells)      : {t_board:6.2f}s")
    print(f"  fixed-letter + tile-count constraints                : {t_constraints:6.2f}s")
    print(f"  single_component (depth encoding)                    : {t_single:6.2f}s")
    print(f"  CP-SAT solve                                         : {t_solve:6.2f}s  -> {verdict}")
    print(f"  TOTAL build (matrix+board+constraints+single)        : {t_matrix+t_board+t_constraints+t_single:6.2f}s")

if __name__ == '__main__':
    main()
