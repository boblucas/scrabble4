"""
Experiment 07: benchmark the real stage-2 call site (max_turn_score.py:152's
general_row_automaton) on bigger dictionaries -- OLD vs NEW.

  OLD: create_scrabble_automaton(automaton_words_from_list(words+[()], W, [T_ANY]*W))
  NEW: position_independent_row_automaton(words)

Measures automaton build time + size, and the resulting CP-SAT model size after
add_automaton unrolls it over the W cells.

Usage (run each under its own `timeout` so a slow OLD build can't block NEW):
  python experiments/07_benchmark_callsite.py <old|new> <language> <board>
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")

from scrabble import construct_rules
from dawg import (position_independent_row_automaton, create_scrabble_automaton,
                  automaton_words_from_list, T_ANY)

def auto_size(a):
    s = {x for x, _, _ in a[2]} | {y for _, _, y in a[2]} | {a[0]} | set(a[1])
    return len(s), len(a[2])

if __name__ == '__main__':
    which, language, board = sys.argv[1], sys.argv[2], sys.argv[3]
    rules = construct_rules(language, board)
    K, W = len(rules.abc), rules.W
    print(f"{which.upper():4} | {language} board {board} | {len(rules.words)} words | W={W} K={K}")

    t = time.time()
    if which == 'old':
        auto = create_scrabble_automaton(
            automaton_words_from_list([w for w in rules.words] + [tuple()], W, [{T_ANY}] * W))
    else:
        auto = position_independent_row_automaton(rules.words)
    tb = time.time() - t
    s, e = auto_size(auto)
    print(f"     build={tb:7.2f}s  states={s:>9}  edges={e:>9}")

    _, stats = exp02.presolve_stats(auto, W, K, time_limit=30.0)
    print(f"     CP-SAT model: presolved_bools={stats.get('presolved_vars')} "
          f"constraints={stats.get('presolved_constraints')} "
          f"(automaton_expansion_bools={stats.get('automaton_expansion_bools')}, "
          f"presolve={stats.get('presolve_s')}s)")
