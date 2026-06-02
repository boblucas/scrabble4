"""
Experiment 06 / regression test: the integrated dawg.position_independent_row_automaton
must accept EXACTLY the same row language as the old production path
  create_scrabble_automaton(automaton_words_from_list(words, n, [{T_ANY}]*n)).

Checks:
  (A) exact: on small dicts, enumerate ALL width-n rows accepted by OLD vs NEW via CP-SAT
      and assert the sets are identical.
  (B) rigorous all-strings: NEW is language-equivalent (product+BFS) to the trusted
      trie-based position-independent DFA verified in exp 01/04/05.

Run: python experiments/06_regression_dawg_integration.py   (exit code 0 = PASS)
"""
import sys
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp01 = _load("exp01", "/home/bob/programming/scrabble4/experiments/01_verify_add_automaton.py")
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
exp03 = _load("exp03", "/home/bob/programming/scrabble4/experiments/03_dawg_based_minimal.py")

from dawg import (position_independent_row_automaton, create_scrabble_automaton,
                  automaton_words_from_list, T_ANY)

enum_language = exp01.enum_language
posindep_trie = exp01.posindep_automaton
dfa_equiv = exp03.dfa_equiv

failures = []

def check_exact(words, K, n, name):
    old = create_scrabble_automaton(automaton_words_from_list(words, n, [{T_ANY}] * n))
    new = position_independent_row_automaton(words)
    lang_old = enum_language(old, n, K, f"OLD/{name}")
    lang_new = enum_language(new, n, K, f"NEW/{name}")
    same = lang_old == lang_new
    print(f"  [{name} n={n}] exact-enumeration OLD vs NEW: "
          f"{'PASS' if same else 'FAIL'} (|OLD|={len(lang_old)} |NEW|={len(lang_new)})")
    if not same:
        failures.append(f"{name} n={n}: OLD!=NEW, "
                        f"only-old={sorted(lang_old-lang_new)[:5]} only-new={sorted(lang_new-lang_old)[:5]}")

def check_equiv(words, K, name):
    new = position_independent_row_automaton(words)
    base = posindep_trie(words, minimize=False)   # trusted-correct
    w = dfa_equiv(base, new, set(range(0, K + 1)))
    ok = w is None
    print(f"  [{name}] NEW ≡ trusted base over ALL strings: {'PASS' if ok else 'FAIL @ '+str(w)}")
    if not ok:
        failures.append(f"{name}: NEW not equivalent to trusted base @ {w}")

if __name__ == '__main__':
    print("(A) exact OLD-vs-NEW enumeration on small (fully-enumerable) dicts:")
    check_exact(exp01.WORDS, exp01.K, 5, "toy")
    check_exact(exp01.WORDS, exp01.K, 7, "toy")   # wider row -> exercises multi-word composition

    print("\n(B) rigorous all-strings equivalence vs trusted base:")
    for ml in (4, 5, 7):
        wl, K = exp02.load_english(ml)
        check_equiv(wl, K, f"english<={ml}")

    print(f"\n{'ALL REGRESSION CHECKS PASSED' if not failures else 'FAILURES:'}")
    for f in failures:
        print("  -", f)
    sys.exit(1 if failures else 0)
