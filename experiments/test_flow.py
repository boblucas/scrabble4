"""Compare depth-based vs flow-based single_component on Stage-B legality+connectivity.
For a fixed vertical set, time how long CP-SAT takes to decide feasibility / optimal score."""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, single_component_flow, limit_letter_count

rules = construct_rules('dutch', '11'); W, H = rules.W, rules.H
f = (W * W) / (15 * 15)
main = 'bouwfysicus'; turn = 'BOUWfYsiCuS'; mt = rules.alphabet.to_tup(main); mc = Counter(mt)
rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
rules.blank_count = round(rules.blank_count * f)
scoring = [x for x in range(W) if turn[x].isupper()]; pre = [x for x in range(W) if not turn[x].isupper()]
HMAX = 8
row_aut = position_independent_row_automaton([w for w in rules.words if len(w) <= HMAX])

def build(sets, conn):
    chosen = {c: rules.alphabet.to_tup(w) for c, w in sets.items()}
    grossV = sum(get_word_score(rules, w, c, 0, 0, [i == 0 for i in range(len(w))])[0] for c, w in chosen.items())
    m = cp_model.CpModel(); m.prefix = 'c'
    rows = [row_aut] * H
    cols = [row_aut if x not in scoring else None for x in range(W)]
    cells = create_board(m, rows, cols, alphabet_size=len(rules.abc))
    for x in pre: m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in scoring: m.add(cells[(x, 0)].active == 0)
    for c, w in chosen.items():
        for r in range(1, H):
            if r < len(w): m.add(cells[(c, r)].letter[w[r]] == 1)
            else: m.add(cells[(c, r)].active == 0)
    newly = Counter(mt[c] for c in scoring)
    limit_letter_count(m, cells, Counter({code: rules.counts[code] - newly[code] for code in rules.counts}))
    penalty = 0
    m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
    for code in rules.counts:
        terms = []
        for c in scoring:
            for r in range(1, H):
                cell = cells[(c, r)]
                b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                terms.append(b)
        o = m.new_int_var(0, rules.blank_count, f'o_{code}'); m.add(o == sum(terms))
        penalty = penalty + o * rules.scores[code]
    (single_component_flow if conn == 'flow' else single_component)(m, cells, (pre[0], 0))
    m.maximize(grossV - penalty)
    return m

cases = {
    "224-set (FEASIBLE)":   {0: 'boogvormpje', 1: 'om', 2: 'uh', 3: 'waze', 5: 'yentekens', 8: 'claden', 10: 'sexternen'},
    "236-set (INFEASIBLE)": {0: 'boxertjes', 1: 'om', 2: 'uh', 3: 'wazende', 5: 'yenteken', 8: 'clark', 10: 'stulpvormig'},
}
for label, sets in cases.items():
    for conn in ['depth', 'flow']:
        m = build(sets, conn)
        s = cp_model.CpSolver(); s.parameters.num_search_workers = 24; s.parameters.max_time_in_seconds = 120
        t = time.time(); r = s.Solve(m); dt = time.time() - t
        name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE', cp_model.INFEASIBLE: 'INFEASIBLE'}.get(r, str(r))
        obj = int(s.objective_value) if r in (2, 4) else None
        print(f"  {label:24} {conn:5}: {name:10} obj={obj}  [{dt:.2f}s]")
