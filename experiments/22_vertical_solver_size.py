"""
Experiment 22: WHERE does make_vertical_word_solver's 547k-var / stuck-presolve cost come from
on board 13?  It puts general_row_automaton = position_independent_row_automaton(rules.words)
(the 178k-state full-dict monster) on solve_rows (=2) rows, plus 13 column automatons.

Measure states/transitions of:
  - the row monster (full dict) and SHORTER-word position-independent rows (<=K)
  - a representative column automaton (as built in make_vertical_word_solver)
and the expansion estimate (sum len*transitions) for the current build vs levers:
  - shorter-word row automaton on the solve_rows
  - fewer solve_rows (2 -> 1 -> 0)

Run: python experiments/22_vertical_solver_size.py [language] [board]
"""
import sys
sys.path.insert(0, '/home/bob/programming/scrabble4')
from solve import *
from scrabble import *
from dawg import T_ANY, position_independent_row_automaton, automaton_words_from_dict, create_scrabble_automaton

lang = sys.argv[1] if len(sys.argv) > 1 else "dutch"
board = sys.argv[2] if len(sys.argv) > 2 else "13"
rules = construct_rules(lang, board)
W, H = rules.W, rules.H
print(f"{lang} board {board}: {W}x{H}, {len(rules.words)} words")

def autstats(a):
    if a is None: return (0, 0)
    if not isinstance(a, tuple):
        if a.shape[0] == 0: return (0, 0)
        a = create_scrabble_automaton(a)
    trans = a[2]
    states = {t[0] for t in trans} | {t[2] for t in trans} | {a[0]}
    return (len(states), len(trans))

# representative main word (from the real board-13 run) + scoring positions
main_word = "chalcedonyxje"[:W]
main_tup = rules.alphabet.to_tup(main_word)
scoring_positions = [(x, 0) for x in range(W)]   # worst case: every column scores a vertical

print(f"\n{'row automaton':34} {'states':>10} {'transitions':>13}")
full = position_independent_row_automaton(rules.words)
s, t = autstats(full); print(f"{'position_independent FULL (monster)':34} {s:>10,} {t:>13,}")
short = {}
for K in [5, 6, 7, 8, 10]:
    a = position_independent_row_automaton([w for w in rules.words if len(w) <= K])
    short[K] = a
    s, t = autstats(a); print(f"{f'position_independent <= {K}':34} {s:>10,} {t:>13,}")

# columns exactly as make_vertical_word_solver builds them, parameterized by the
# general[2] "lower word" allowance (the dominant cost). below2=None -> no lower word.
def col_automaton(x, below2=7):
    general = {
        0: {w for w in rules.words if w and w[0] == main_tup[x]},
        1: {}}
    if below2 is not None:
        general[2] = [w for w in rules.words if len(w) <= below2] + [tuple()]
    else:
        general[2] = [tuple()]
    if (x, 0) in scoring_positions:
        general[0] = {w for w in general[0] if w[1:] in rules.words_lookup}
    return automaton_words_from_dict(general, [{T_ANY}] * H)

def col_expansion_for(below2):
    return sum(H * autstats(col_automaton(x, below2))[1] for x in range(W))

print()
for below2 in [7, 4, 3, 2, None]:
    ce = col_expansion_for(below2)
    print(f"columns expansion, general[2] <= {str(below2):4} : {ce:>14,}")
col_expansion = col_expansion_for(7)   # current

def row_exp(aut, nrows):
    _, t = autstats(aut); return nrows * W * t

print(f"\n{'stage-2 build':44} {'expansion (rows+cols)':>26}")
for name, aut, nrows in [
    ("CURRENT: monster x2 rows + cols",      full,     2),
    ("monster x1 row + cols",                full,     1),
    ("no row automaton (solve_rows=0) + cols", None,    0),
    ("<=7 x2 rows + cols",                    short[7], 2),
    ("<=7 x1 row + cols",                     short[7], 1),
    ("<=5 x2 rows + cols",                    short[5], 2),
]:
    tot = row_exp(aut, nrows) + col_expansion
    print(f"{name:44} {tot:>26,}")
