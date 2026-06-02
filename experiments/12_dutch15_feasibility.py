"""
Experiment 12: is an optimal Dutch N=15 merged run feasible? Probe the binding
constraint = raw CP-SAT model size.

Measures, for Dutch board 15:
  - construct_rules + word count
  - position_independent_row_automaton build time + size
  - CP-SAT expansion for ONE width-15 row line
  - extrapolated full-board row+column expansion (~2*W lines) to judge tractability

Run: python experiments/12_dutch15_feasibility.py [language] [board]
"""
import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp02 = _load("exp02", "/home/bob/programming/scrabble4/experiments/02_model_expansion.py")
from scrabble import construct_rules
from dawg import position_independent_row_automaton

def auto_size(a):
    st = {x for x,_,_ in a[2]} | {y for _,_,y in a[2]} | {a[0]} | set(a[1])
    return len(st), len(a[2])

if __name__ == '__main__':
    lang = sys.argv[1] if len(sys.argv) > 1 else 'dutch'
    board = sys.argv[2] if len(sys.argv) > 2 else '15'
    t = time.time(); rules = construct_rules(lang, board); t_rules = time.time()-t
    W, K = rules.W, len(rules.abc)
    print(f"{lang} board {board}: {len(rules.words)} words (construct_rules {t_rules:.1f}s), W={W} K={K}")

    t = time.time(); auto = position_independent_row_automaton(rules.words); tb = time.time()-t
    s, e = auto_size(auto)
    print(f"row minimal DFA: build={tb:.2f}s states={s} edges={e}")

    _, st = exp02.presolve_stats(auto, W, K, time_limit=60)
    per_line = st.get('automaton_expansion_bools')
    print(f"ONE width-{W} row line -> CP-SAT expansion bools = {per_line}")
    if per_line:
        print(f"extrapolated full board ({2*W} row+col lines, rows-only here) ~ {per_line*W//1000}k-{per_line*2*W//1000}k bools "
              f"(+ single_component + scoring). Judge tractability vs the ~few-hundred-k that solves in seconds.")
