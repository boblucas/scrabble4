"""
Experiment 01: Does CP-SAT add_automaton accept EXACTLY the intended Scrabble-row
language for different automaton constructions?

We compare three constructions on a tiny, fully-enumerable dictionary:
  (A) CURRENT  : create_scrabble_automaton(automaton_words_from_list(words, n))  [known-good baseline]
  (B) POSINDEP : a small position-INDEPENDENT row DFA built straight from a trie  [the thing the plan wants to use]
  (C) MINIMIZED: (B) put through DFA minimization                                 [the thing the user recalls FAILING]

For each we feed the automaton to model.add_automaton over n int vars (domain 0..K),
enumerate ALL accepted strings, and compare the set against a brute-force ground truth.

Ground truth: a width-n row s in {0,1..K}^n is valid iff every maximal non-zero run
is a dictionary word (0 = empty cell / gap; leading/trailing/multiple gaps allowed;
the all-empty row is valid).

Run: python experiments/01_verify_add_automaton.py
"""
import sys, itertools
from collections import defaultdict

sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from dawg import create_scrabble_automaton, automaton_words_from_list

# ---- tiny dictionary ---------------------------------------------------------
# alphabet a=1 b=2 c=3 t=4 ; words chosen for shared prefixes (cat/cab),
# shared suffixes (at/cat/tab share trailing letters), and a 1-letter word (a).
A = {'a': 1, 'b': 2, 'c': 3, 't': 4}
K = len(A)
WORDS_STR = ['a', 'ab', 'at', 'cat', 'cab', 'tab', 'tac']
WORDS = [tuple(A[c] for c in w) for w in WORDS_STR]
WORDSET = set(WORDS)
N = 5  # board width


# ---- ground truth ------------------------------------------------------------
def is_valid_row(s):
    run = []
    for v in list(s) + [0]:
        if v == 0:
            if run:
                if tuple(run) not in WORDSET:
                    return False
                run = []
        else:
            run.append(v)
    return True

def ground_truth(n):
    return {s for s in itertools.product(range(K + 1), repeat=n) if is_valid_row(s)}


# ---- CP-SAT enumeration of an automaton's accepted language ------------------
def enum_language(automaton, n, K, label):
    start, finals, edges = automaton
    edges = [(int(a), int(c), int(b)) for (a, c, b) in edges]
    finals = [int(f) for f in finals]
    # determinism report (add_automaton requires a DETERMINISTIC automaton)
    by_key = defaultdict(set)
    for a, c, b in edges:
        by_key[(a, c)].add(b)
    nondet = {k: v for k, v in by_key.items() if len(v) > 1}
    states = {a for a, _, _ in edges} | {b for _, _, b in edges} | {int(start)} | set(finals)
    print(f"  [{label}] states={len(states)} edges={len(edges)} finals={len(finals)} "
          f"nondeterministic_keys={len(nondet)}")
    if nondet:
        sample = list(nondet.items())[:3]
        print(f"      e.g. {sample}")

    model = cp_model.CpModel()
    xs = [model.new_int_var(0, K, f'x{i}') for i in range(n)]
    try:
        model.add_automaton(xs, int(start), finals, edges)
    except Exception as e:
        print(f"      add_automaton RAISED: {type(e).__name__}: {e}")
        return None

    sols = []
    class CB(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()
        def on_solution_callback(self):
            sols.append(tuple(self.Value(x) for x in xs))

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model, CB())
    return set(sols)


# ---- (B) position-independent row DFA straight from a trie -------------------
class TrieNode:
    __slots__ = ('children', 'terminal', 'sid')
    def __init__(self):
        self.children = {}
        self.terminal = False
        self.sid = None

def build_trie(words):
    root = TrieNode()
    for w in words:
        n = root
        for c in w:
            n = n.children.setdefault(c, TrieNode())
        n.terminal = True
    return root

def posindep_automaton(words, minimize=False):
    """
    Row language: (word (0+ word)* )?  with optional leading/trailing 0s.
    State 0 = GAP (start + accepting). Each trie node gets its own state id.
    GAP --0--> GAP ; GAP --c--> root.child[c] ; node --c--> node.child[c] ;
    terminal node --0--> GAP. Accepting = {GAP} U {terminal nodes}.
    Deterministic by construction.
    """
    root = build_trie(words)
    GAP = 0
    next_id = [1]
    def sid(node):
        if node.sid is None:
            node.sid = next_id[0]; next_id[0] += 1
        return node.sid
    edges = set()
    finals = {GAP}
    # GAP self-loop on blank
    edges.add((GAP, 0, GAP))
    stack = [root]
    seen = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for c, child in node.children.items():
            frm = GAP if node is root else sid(node)
            edges.add((frm, c, sid(child)))
            if child.terminal:
                finals.add(sid(child))
                edges.add((sid(child), 0, GAP))  # finish word, back to gap
            stack.append(child)
    auto = (GAP, finals, edges)
    if minimize:
        auto = minimize_dfa(auto)
    return auto


# ---- (C) DFA minimization (Hopcroft-style partition refinement) --------------
def minimize_dfa(automaton):
    start, finals, edges = automaton
    finals = set(int(f) for f in finals)
    states = {int(s) for s, _, _ in edges} | {int(t) for _, _, t in edges} | {int(start)} | finals
    alphabet = {int(c) for _, c, _ in edges}
    trans = {}
    for a, c, b in edges:
        trans[(int(a), int(c))] = int(b)
    # A "dead" sink to make the DFA complete (so partition refinement is sound)
    SINK = max(states) + 1
    states = states | {SINK}
    for s in states:
        for c in alphabet:
            trans.setdefault((s, c), SINK)
    # initial partition: accepting vs non-accepting
    P = [finals & states, states - finals]
    P = [b for b in P if b]
    changed = True
    while changed:
        changed = False
        newP = []
        for block in P:
            # split block by transition-signature into the current partition
            sig = defaultdict(set)
            def block_of(s):
                for i, b in enumerate(P):
                    if s in b:
                        return i
                return -1
            groups = defaultdict(set)
            for s in block:
                key = tuple(block_of(trans[(s, c)]) for c in sorted(alphabet))
                groups[key].add(s)
            if len(groups) > 1:
                changed = True
            newP.extend(groups.values())
        P = newP
    # build minimized automaton
    rep = {}
    for i, block in enumerate(P):
        for s in block:
            rep[s] = i
    new_start = rep[int(start)]
    new_finals = {rep[f] for f in finals}
    new_edges = set()
    for (a, c), b in trans.items():
        if b == SINK:
            continue
        if a == SINK:
            continue
        new_edges.add((rep[a], c, rep[b]))
    # drop transitions into the sink-block (block that is non-accepting & only self-loops)
    return (new_start, new_finals, new_edges)


# ---- run ---------------------------------------------------------------------
def report(name, lang, truth):
    if lang is None:
        print(f"  => {name}: BUILD/SOLVE FAILED")
        return
    missing = truth - lang
    extra = lang - truth
    ok = not missing and not extra
    print(f"  => {name}: {'PASS' if ok else 'FAIL'}  "
          f"(accepted={len(lang)} truth={len(truth)} missing={len(missing)} extra={len(extra)})")
    def show(s):
        inv = {v: k for k, v in A.items()}
        return ''.join(inv.get(v, '.') if v else '_' for v in s)
    if missing:
        print(f"     MISSING (valid rows the automaton rejects): {[show(s) for s in sorted(missing)][:8]}")
    if extra:
        print(f"     EXTRA   (invalid rows the automaton accepts): {[show(s) for s in sorted(extra)][:8]}")

def main():
    print(f"dictionary={WORDS_STR}  alphabet={A}  width N={N}")
    truth = ground_truth(N)
    print(f"ground-truth valid rows: {len(truth)}\n")

    print("(A) CURRENT positionally-encoded automaton:")
    cur = create_scrabble_automaton(automaton_words_from_list(WORDS, N))
    report("CURRENT", enum_language(cur, N, K, "CURRENT"), truth)
    print()

    print("(B) POSITION-INDEPENDENT row DFA (unminimized):")
    b = posindep_automaton(WORDS, minimize=False)
    report("POSINDEP", enum_language(b, N, K, "POSINDEP"), truth)
    print()

    print("(C) MINIMIZED position-independent row DFA:")
    c = posindep_automaton(WORDS, minimize=True)
    report("MINIMIZED", enum_language(c, N, K, "MINIMIZED"), truth)

if __name__ == '__main__':
    main()
