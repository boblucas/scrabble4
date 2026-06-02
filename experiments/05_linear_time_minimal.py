"""
Experiment 05: Get the 6-8x model reduction in LINEAR time (no GPU, no 24h).

The 40s in exp 02/04 was naive O(n^2) Moore minimization of the cyclic row DFA.
But the minimal DFA of the row language is essentially the minimal DAFSA (DAWG) of
the dictionary, and that has a classic LINEAR-time construction (Revuz / Daciuk).

Here we:
  1. build the trie of the dictionary,
  2. minimize it with REVUZ's algorithm (bucket nodes by height, merge equal
     signatures bottom-up) -> minimal acyclic DAFSA, O(n),
  3. build the cyclic row DFA from the minimal DAFSA,
  4. measure states / build time / CP-SAT model size, and
  5. verify language-equivalence to the trusted trie-based row DFA.

Compared against exp 04's Moore result (english<=5: 2653 states, 38k CP-SAT bools).

Run: python experiments/05_linear_time_minimal.py
"""
import sys, time
from collections import defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp01 = _load("exp01", "/home/bob/programming/scrabble4/experiments/01_verify_add_automaton.py")
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
exp03 = _load("exp03", "/home/bob/programming/scrabble4/experiments/03_dawg_based_minimal.py")
posindep_automaton = exp01.posindep_automaton
automaton_size = exp02.automaton_size
presolve_stats = exp02.presolve_stats
dfa_equiv = exp03.dfa_equiv


# ---- trie as flat arrays (index-based; avoids per-node Python objects) -------
def build_trie(words):
    # node 0 = root. children[node] = {letter: child}. terminal[node] = bool.
    children = [dict()]
    terminal = [False]
    for w in words:
        n = 0
        for c in w:
            nxt = children[n].get(c)
            if nxt is None:
                nxt = len(children)
                children.append(dict()); terminal.append(False)
                children[n][c] = nxt
            n = nxt
        terminal[n] = True
    return children, terminal


# ---- Revuz minimization: linear-time acyclic-DFA minimization ----------------
def revuz_minimal_dafsa(children, terminal):
    nn = len(children)
    # heights via iterative post-order
    height = [0] * nn
    order = []
    stack = [(0, False)]
    visited = [False] * nn
    while stack:
        node, processed = stack.pop()
        if processed:
            h = 0
            for c, ch in children[node].items():
                h = max(h, 1 + height[ch])
            height[node] = h
            order.append(node)
            continue
        if visited[node]:
            continue
        visited[node] = True
        stack.append((node, True))
        for c, ch in children[node].items():
            stack.append((ch, False))
    # merge bottom-up by signature; rep[node] = canonical node id
    rep = list(range(nn))
    by_height = defaultdict(list)
    for node in range(nn):
        by_height[height[node]].append(node)
    register = {}
    for h in sorted(by_height):
        for node in by_height[h]:
            sig = (terminal[node], tuple(sorted((c, rep[ch]) for c, ch in children[node].items())))
            if sig in register:
                rep[node] = register[sig]
            else:
                register[sig] = node  # node is its own canonical
    return rep


def row_dfa_from_minimal(words):
    children, terminal = build_trie(words)
    rep = revuz_minimal_dafsa(children, terminal)
    GAP = 'G'
    # state ids: GAP -> 0, each canonical node -> 1..
    canon = sorted({rep[n] for n in range(len(children))})
    sid = {GAP: 0}
    for i, n in enumerate(canon, start=1):
        sid[n] = i
    edges = set([(0, 0, 0)])  # GAP --blank--> GAP
    finals = {0}
    # GAP --c--> rep[root.child[c]]
    for c, ch in children[0].items():
        edges.add((0, int(c), sid[rep[ch]]))
    # canonical node transitions
    for n in canon:
        s = sid[n]
        for c, ch in children[n].items():
            edges.add((s, int(c), sid[rep[ch]]))
        if terminal[n]:
            finals.add(s)
            edges.add((s, 0, 0))
    return (0, finals, edges)


def measure(words, K, name, do_cpsat=True, verify=True, widths=(7, 11, 15)):
    print(f"\n=== {name}: {len(words)} words ===")
    t0 = time.time()
    auto = row_dfa_from_minimal(words)
    tb = time.time() - t0
    s, e = automaton_size(auto)
    print(f"  Revuz minimal row DFA: states={s:>8} edges={e:>8}  build={tb:.2f}s")
    if verify:
        base = posindep_automaton(words, minimize=False)  # trusted-correct
        t0 = time.time()
        w = dfa_equiv(base, auto, set(range(0, K + 1)))
        print(f"  equivalence vs trusted base: "
              f"{'EQUIVALENT' if w is None else 'DIFFERENT @ '+str(w)}  ({time.time()-t0:.2f}s)")
    if do_cpsat:
        for n in widths:
            _, stats = presolve_stats(auto, n, K)
            print(f"    N={n:2}: CP-SAT presolved_bools={stats.get('presolved_vars')} "
                  f"(expansion={stats.get('automaton_expansion_bools')})")
    return s, tb


def load_english_all():
    words = open('/home/bob/programming/scrabble4/data/words/english').read().lower().split('\n')
    cba = {c: i + 1 for i, c in enumerate('abcdefghijklmnopqrstuvwxyz')}
    out = [tuple(cba[c] for c in w) for w in words if w and all(c in cba for c in w)]
    out += [(cba[c],) for c in 'abcdefghijklmnopqrstuvwxyz']
    return sorted(set(out)), 26


if __name__ == '__main__':
    w5, K = exp02.load_english(5)
    measure(w5, K, "english<=5 (cf. exp04: Moore=2653 states/40s, 38k bools)")
    w7, _ = exp02.load_english(7)
    measure(w7, K, "english<=7", do_cpsat=True, verify=True)
    # full dictionary, all lengths: build time + size only (CP-SAT at full width is the separate wall)
    wall, _ = load_english_all()
    measure(wall, K, "FULL english (all lengths)", do_cpsat=False, verify=False)
