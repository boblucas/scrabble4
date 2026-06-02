"""
Experiment 08: can we shrink the stage-2 COLUMN automata and stage-3 CONNECTIVITY
automata (which are position-specific and carry tuned heuristics, so the cyclic
position-independent DFA does NOT apply) by MINIMIZING the automaton that
create_scrabble_automaton already produces?

This is semantics-preserving (same accepted language => heuristics untouched).
CP-SAT does not fully minimize on its own (shown in exp02), so pre-minimization
should reduce the model. We measure size, CP-SAT model, and verify equivalence.

The automaton from create_scrabble_automaton is a DAG (forward-only stitching), so
minimization is linear-time via Revuz (height-bucketed signature merge).

Run: python experiments/08_minimize_column_automata.py
"""
import sys, time
from collections import defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
exp03 = _load("exp03", "/home/bob/programming/scrabble4/experiments/03_dawg_based_minimal.py")
automaton_size = exp02.automaton_size
presolve_stats = exp02.presolve_stats
dfa_equiv = exp03.dfa_equiv

from scrabble import construct_rules
from dawg import create_scrabble_automaton, automaton_words_from_dict, T_ANY


def minimize_acyclic(automaton):
    """Revuz linear-time minimisation of an acyclic deterministic automaton given
    as (start, finals, edges). Raises on a cycle."""
    start, finals, edges = automaton
    start = int(start)
    finals = set(int(f) for f in finals)
    children = defaultdict(dict)
    states = {start}
    for a, c, b in edges:
        a, c, b = int(a), int(c), int(b)
        children[a][c] = b; states.add(a); states.add(b)
    height = {}
    onstack = set()
    def H(s):
        if s in height: return height[s]
        if s in onstack: raise ValueError("cycle detected; automaton not acyclic")
        onstack.add(s)
        h = 0
        for ch in children[s].values():
            h = max(h, 1 + H(ch))
        onstack.discard(s)
        height[s] = h; return h
    sys.setrecursionlimit(100000)
    for s in states: H(s)
    rep = {}; register = {}
    for node in sorted(states, key=lambda s: height[s]):
        sig = (node in finals, tuple(sorted((c, rep[children[node][c]]) for c in children[node])))
        r = register.get(sig)
        if r is None:
            register[sig] = node; rep[node] = node
        else:
            rep[node] = r
    new_edges = {(rep[int(a)], int(c), rep[int(b)]) for a, c, b in edges}
    new_finals = {rep[f] for f in finals}
    return (rep[start], new_finals, new_edges)


def build_column_automaton(rules, main_letter, scoring=True, short=7):
    """Replicates make_vertical_word_solver's per-column automaton (max_turn_score.py:156-164)."""
    general = {
        0: {w for w in rules.words if w and w[0] == main_letter},
        1: {},
        2: [w for w in rules.words if len(w) <= short] + [tuple()],
    }
    if scoring:
        general[0] = {w for w in general[0] if w[1:] in rules.words_lookup}
    matrix = automaton_words_from_dict(general, [{T_ANY}] * rules.H)
    return create_scrabble_automaton(matrix)


def report(rules, name, auto, K, n):
    s, e = automaton_size(auto)
    t = time.time(); mini = minimize_acyclic(auto); tm = time.time() - t
    sm, em = automaton_size(mini)
    eq = dfa_equiv(auto, mini, set(range(0, K + 1)))
    _, st0 = presolve_stats(auto, n, K, time_limit=30)
    _, st1 = presolve_stats(mini, n, K, time_limit=30)
    print(f"  {name}")
    print(f"    current  : states={s:>7} edges={e:>7}  CP-SAT bools={st0.get('presolved_vars')} (expansion={st0.get('automaton_expansion_bools')})")
    print(f"    minimized: states={sm:>7} edges={em:>7}  CP-SAT bools={st1.get('presolved_vars')} (expansion={st1.get('automaton_expansion_bools')})  [{tm:.2f}s]")
    print(f"    equivalent: {'YES' if eq is None else 'NO @ '+str(eq)}   "
          f"state-reduction={s/max(1,sm):.1f}x  model-reduction="
          f"{(st0.get('automaton_expansion_bools') or 0)/max(1,(st1.get('automaton_expansion_bools') or 1)):.1f}x")


if __name__ == '__main__':
    for board in ['11', '15']:
        rules = construct_rules('english', board)
        K = len(rules.abc)
        print(f"\n===== english board {board} (H={rules.H}, {len(rules.words)} words) =====")
        ml = rules.alphabet.cba['e']   # a representative main-word letter
        report(rules, f"column automaton (main letter 'e', scoring/prefixable)",
               build_column_automaton(rules, ml, scoring=True), K, rules.H)
