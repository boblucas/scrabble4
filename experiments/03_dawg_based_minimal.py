"""
Experiment 03: Can we get the ~6x smaller CP-SAT model CHEAPLY?

Exp 02 showed a fully MINIMIZED row DFA gives a ~6x smaller CP-SAT model than the
current/posindep automaton -- BUT naive Hopcroft minimization is far too slow to
build (40s for a 15k-word toy dict; hopeless for 197k/1.1M-word real dicts). That
build cost is almost certainly why "minimized DAWGs didn't work" before.

Idea: dawg.py already has a fast incremental-minimization DAWG class. Build the row
DFA straight from that *suffix-merged* DAWG (instead of a plain trie). That should
get most of the state reduction for ~free.

We measure POSINDEP_DAWG vs POSINDEP(trie) vs MINIMIZED, and we RIGOROUSLY verify
language-equivalence two ways:
  (1) full enumeration on a tiny dict (exact set equality), and
  (2) deterministic-DFA equivalence via product+BFS between the two small automata.

Run: python experiments/03_dawg_based_minimal.py
"""
import sys, time, re
from collections import defaultdict, deque
sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from dawg import create_scrabble_automaton, automaton_words_from_list, DAWG, is_valid_string

import importlib.util
def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
exp01 = _load("exp01", "/home/bob/programming/scrabble4/experiments/01_verify_add_automaton.py")
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
posindep_automaton = exp01.posindep_automaton
minimize_dfa = exp01.minimize_dfa
automaton_size = exp02.automaton_size
presolve_stats = exp02.presolve_stats


def posindep_from_dawg(words, also_minimize=False):
    """
    Row DFA built from the suffix-merged minimal DAWG (dawg.py DAWG class).
    State 0 = GAP (start + accepting). Each DAWG node -> its own state.
    GAP --0--> GAP ; GAP --c--> root.child[c] ; node --c--> node.child[c] ;
    terminal node (count>0) --0--> GAP. Accepting = {GAP} U {terminal nodes}.
    """
    d = DAWG(sorted(words))
    root = d.root
    GAP = 0
    ids = {}
    nxt = [1]
    def sid(node):
        k = id(node)
        if k not in ids:
            ids[k] = nxt[0]; nxt[0] += 1
        return ids[k]
    edges = set([(GAP, 0, GAP)])
    finals = {GAP}
    seen = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for c, child in node.children.items():
            frm = GAP if node is root else sid(node)
            edges.add((frm, int(c), sid(child)))
            if child.count > 0:          # terminal in DAWG = end of a word
                finals.add(sid(child))
                edges.add((sid(child), 0, GAP))
            stack.append(child)
    auto = (GAP, finals, edges)
    if also_minimize:
        auto = minimize_dfa(auto)
    return auto


# ---- rigorous DFA equivalence via product + BFS (both must be deterministic) --
def dfa_equiv(a, b, alphabet):
    """Return None if equivalent, else a witness (state-path note). Completes both with a sink."""
    def tabulate(auto):
        start, finals, edges = auto
        finals = set(int(f) for f in finals)
        trans = {}
        states = {int(start)} | finals
        for x, c, y in edges:
            trans[(int(x), int(c))] = int(y)
            states.add(int(x)); states.add(int(y))
        return int(start), finals, trans, states
    sa, fa, ta, A = tabulate(a)
    sb, fb, tb, B = tabulate(b)
    SINK = -999
    def step(t, s, c):
        return t.get((s, c), SINK)
    start = (sa, sb)
    seen = {start}
    q = deque([start])
    while q:
        qa, qb = q.popleft()
        acc_a = qa in fa
        acc_b = qb in fb
        if acc_a != acc_b:
            return (qa, qb, acc_a, acc_b)
        for c in alphabet:
            na = step(ta, qa, c) if qa != SINK else SINK
            nb = step(tb, qb, c) if qb != SINK else SINK
            ns = (na, nb)
            if ns not in seen:
                seen.add(ns); q.append(ns)
    return None  # equivalent on all strings (over alphabet, all lengths)


def main():
    # ---- (1) exact correctness on the toy dict from exp01 ----
    WORDS = exp01.WORDS
    A = exp01.A
    K = exp01.K
    N = exp01.N
    truth = exp01.ground_truth(N)
    print(f"[toy] dict={exp01.WORDS_STR} width={N} ground-truth={len(truth)}")
    for label, auto in [
        ("POSINDEP_trie", posindep_automaton(WORDS, minimize=False)),
        ("POSINDEP_dawg", posindep_from_dawg(WORDS)),
        ("DAWG+min",      posindep_from_dawg(WORDS, also_minimize=True)),
    ]:
        lang = exp01.enum_language(auto, N, K, label)
        ok = lang == truth
        s, e = automaton_size(auto)
        print(f"  {label:14} states={s:>4} edges={e:>4}  exact-language={'PASS' if ok else 'FAIL'}")

    # ---- (2) rigorous equivalence: DAWG-based vs fully-minimized (both small) ----
    alphabet = set(range(0, K + 1))
    a = posindep_from_dawg(WORDS)
    b = posindep_automaton(WORDS, minimize=True)
    w = dfa_equiv(a, b, alphabet)
    print(f"  [equiv] POSINDEP_dawg vs MINIMIZED over all strings: "
          f"{'EQUIVALENT' if w is None else 'DIFFERENT @ '+str(w)}")

    # ---- (3) size on a real dict: build cost + CP-SAT model size ----
    words, K2 = exp02.load_english(5)
    print(f"\n[english<=5] {len(words)} words")
    for n in [7, 11, 15]:
        print(f"--- width N={n} ---")
        for label, fn in [
            ("POSINDEP_dawg", lambda: posindep_from_dawg(words)),
            ("DAWG+min",      lambda: posindep_from_dawg(words, also_minimize=True)),
        ]:
            t0 = time.time(); auto = fn(); tb = time.time() - t0
            s, e = automaton_size(auto)
            _, stats = presolve_stats(auto, n, K2)
            ax = stats.get("automaton_expansion_bools", "?")
            pv = stats.get("presolved_vars", "?")
            print(f"  {label:14} build={tb:6.2f}s states={s:>7} edges={e:>7}  => "
                  f"presolved_bools={pv} (expansion={ax})")
    print("\n(Real-dict correctness rests on the exact toy enumeration + the all-strings "
          "dawg-vs-minimized equivalence above. CURRENT is a length-fixed acyclic automaton, "
          "so an all-lengths product check against the cyclic DFA is not apples-to-apples.)")


if __name__ == '__main__':
    main()
