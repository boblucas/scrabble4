"""
Experiment 16: flow vs depth connectivity on the board-9 merged model.

Three variants:
  depth      : current single_component (depth/spanning-tree) over the FULL board
  flow_full  : single-commodity flow over the FULL board (same feasible region -> isolates encoding)
  flow_prior : single-commodity flow over the PRIOR board (excludes the final word's newly-placed
               row-0 tiles, source=center) -> the CORRECT semantics (top word can't bridge), and
               should prune harder.

For a FEASIBLE main (rugbyclub): run 180s, report best objective / best bound / gap / status.
For an INFEASIBLE main (hypoxisch): report time to prove INFEASIBLE (cap 180s).

Run: python experiments/16_flow_vs_depth_connectivity.py
"""
import sys, time, re
sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from scrabble import construct_rules
from dawg import position_independent_row_automaton, automaton_words_from_dict, T_ANY
from solve import create_board, single_component, limit_letter_count, create_word_mapping, estimate_score


def single_component_flow(model, cells, source, exclude):
    """Single-commodity flow connectivity over cells NOT in `exclude`; source must be active and
    every active network cell must receive 1 unit of flow from the source -> connected."""
    net = {p: c for p, c in cells.items() if p not in exclude}
    assert source in net, "source must be in the flow network"
    n = len(net)
    model.add(net[source].active == 1)
    def nbrs(p):
        x, y = p
        return [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]
    flow = {}
    for p in net:
        for q in nbrs(p):
            if q in net:
                flow[(p, q)] = model.new_int_var(0, n, f'f_{p}_{q}')
    for (u, v), f in flow.items():
        model.add(f <= n * net[u].active)
        model.add(f <= n * net[v].active)
    for p, c in net.items():
        inn = sum(flow[(u, p)] for u in nbrs(p) if (u, p) in flow)
        out = sum(flow[(p, v)] for v in nbrs(p) if (p, v) in flow)
        if p == source:
            model.add(out - inn == sum(net[q].active for q in net if q != source))
        else:
            model.add(inn - out == c.active)


def build_merged(rules, main_word, sp, conn):
    model = cp_model.CpModel(); model.prefix = 'ver'
    y = sp[0][1]; main_tup = rules.alphabet.to_tup(main_word)
    general_row = position_independent_row_automaton(rules.words)
    cols = []
    for x in range(len(main_word)):
        g = {0: {w for w in rules.words if w and w[0] == main_tup[x]}, 1: {},
             2: [w for w in rules.words if len(w) <= 7] + [tuple()]}
        if (x, y) in sp:
            g[0] = {w for w in g[0] if w[1:] in rules.words_lookup}
        cols.append(automaton_words_from_dict(g, [{T_ANY}] * rules.H))
    cells3 = create_board(model, [general_row] * rules.H, cols, alphabet_size=len(rules.abc))
    part = []
    for x in range(len(main_word)):
        if (x, y) not in sp: part.append(x)
        elif part: model.add(sum(cells3[(x2, y+1)].active for x2 in part) >= 1); part = []
    limit_letter_count(model, cells3, rules.counts)
    model.add(sum(c.blank for c in cells3.values()) <= rules.blank_count)
    for x in range(len(main_word)):
        model.add(cells3[(x, y)].letter[main_tup[x]] == 1)
    center = (rules.W // 2, rules.H // 2)
    if conn == 'depth':
        single_component(model, cells3, center)
    elif conn == 'flow_full':
        single_component_flow(model, cells3, center, exclude=set())
    elif conn == 'flow_prior':
        single_component_flow(model, cells3, center, exclude={(x, 0) for x in range(rules.W) if (x, 0) in sp})
    _wm = np.ones_like(rules.word_multiplier); _lm = np.ones_like(rules.letter_multiplier)
    _wm[0, :] = rules.word_multiplier[0, :]; _lm[0, :] = rules.letter_multiplier[0, :]
    slots = create_word_mapping(model, cells3, None, alphabet_size=len(rules.abc))
    score = estimate_score(model, slots, _wm, _lm, {}, rules.scores,
                           {(i, 0, 0) for i in range(rules.W) if (i, y) in sp}, bingo=False)
    model.maximize(score)
    return model, cells3


def bench(rules, main_word, sp, conn, tl=180):
    t = time.time(); model, _ = build_merged(rules, main_word, sp, conn); t_build = time.time()-t
    logs = []
    s = cp_model.CpSolver()
    s.parameters.log_search_progress = True; s.parameters.log_to_stdout = False
    s.parameters.num_search_workers = 8; s.parameters.max_time_in_seconds = tl
    s.log_callback = lambda m: logs.append(m)
    t = time.time(); res = s.Solve(model); wall = time.time()-t
    txt = "\n".join(logs)
    m = re.search(r"Starting search at ([\d.]+)s", txt)
    presolve_s = float(m.group(1)) if m else None
    st = {cp_model.OPTIMAL:'OPTIMAL', cp_model.FEASIBLE:'FEASIBLE', cp_model.INFEASIBLE:'INFEASIBLE',
          cp_model.UNKNOWN:'timeout'}.get(res, str(res))
    obj = s.objective_value if res in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    bound = s.best_objective_bound if res in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN) else None
    print(f"  {conn:11}: build={t_build:5.1f}s presolve={('%.1f'%presolve_s) if presolve_s else '   ?'}s "
          f"wall={wall:6.1f}s status={st:9} obj={obj} bound={bound}", flush=True)
    return st, obj, bound, wall


if __name__ == '__main__':
    from scrabble import get_word_score
    def top_mains(rules, k):
        W = rules.W; scored = []
        for w in rules.words:
            if len(w) == W:
                sc, _ = get_word_score(rules, w, 0, 0, 1, [True] * W)
                scored.append((sc, w))
        scored.sort(reverse=True, key=lambda t: t[0])
        return [rules.alphabet.to_str(w) for _, w in scored[:k]]

    TL = 150
    configs = [('9', ['rugbyclub', 'hypoxisch']), ('11', None)]
    for board, mains in configs:
        rules = construct_rules('dutch', board)
        sp = [(x, 0) for x in range(rules.W)]
        if mains is None:
            mains = top_mains(rules, 2)
        print(f"\n########## BOARD {board} (W={rules.W}) — {TL}s/solve ##########", flush=True)
        for mw in mains:
            print(f"\n--- main '{mw}' ---", flush=True)
            for conn in ['depth', 'flow_full', 'flow_prior']:
                bench(rules, mw, sp, conn, tl=TL)
