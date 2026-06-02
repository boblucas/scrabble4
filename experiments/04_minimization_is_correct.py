"""
Experiment 04: Is the ~6x model reduction from minimize_dfa REAL, or does
minimize_dfa accept a WRONG (smaller) language at scale?

We take a trusted, language-correct row DFA (POSINDEP, exact-verified on the toy in
exp01) and its minimized version, and check DETERMINISTIC-DFA EQUIVALENCE over ALL
strings via product+BFS (exact, not sampled). If equivalent, the smaller state count
is a genuine minimal DFA and the CP-SAT model reduction is real. If different,
minimize_dfa is buggy and the reduction is an artifact.

We also report the true minimal size to judge plausibility.

Run: python experiments/04_minimization_is_correct.py
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp01 = _load("exp01", "/home/bob/programming/scrabble4/experiments/01_verify_add_automaton.py")
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
exp03 = _load("exp03", "/home/bob/programming/scrabble4/experiments/03_dawg_based_minimal.py")
posindep_automaton = exp01.posindep_automaton
minimize_dfa = exp01.minimize_dfa
automaton_size = exp02.automaton_size
dfa_equiv = exp03.dfa_equiv


def check(words, K, name):
    print(f"\n=== {name}: {len(words)} words, alphabet 1..{K} ===")
    t0 = time.time()
    base = posindep_automaton(words, minimize=False)   # trusted-correct (trie-based)
    tb = time.time() - t0
    sb, eb = automaton_size(base)
    print(f"  base (trie)   : states={sb:>7} edges={eb:>7}  build={tb:.2f}s")
    t0 = time.time()
    mini = minimize_dfa(base)
    tm = time.time() - t0
    sm, em = automaton_size(mini)
    print(f"  minimized     : states={sm:>7} edges={em:>7}  minimize={tm:.2f}s  (reduction {sb/max(1,sm):.1f}x)")
    alphabet = set(range(0, K + 1))
    t0 = time.time()
    w = dfa_equiv(base, mini, alphabet)
    te = time.time() - t0
    verdict = "EQUIVALENT (minimization is correct)" if w is None else f"DIFFERENT  -> minimize_dfa BUG, witness state-pair {w}"
    print(f"  equivalence   : {verdict}   ({te:.2f}s)")
    return w is None


if __name__ == '__main__':
    # small alphabet, exact + fast
    ok1 = check(exp01.WORDS, exp01.K, "toy")
    # real english subset
    words5, K5 = exp02.load_english(5)
    ok2 = check(words5, K5, "english<=5")
    words4, K4 = exp02.load_english(4)
    ok3 = check(words4, K4, "english<=4")
    print(f"\nALL EQUIVALENT: {ok1 and ok2 and ok3}")
