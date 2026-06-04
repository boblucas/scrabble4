"""
Experiment 21: WHICH component dominates the connectivity model size (the 547k vars that
OOM'd on board 13)?  Build the connectivity board under several row/column strategies and
report #Variables / #Constraints for each, so we fix the part that actually matters.

Components measured (board 13, realistic synthetic partial = real Dutch verticals):
  - rows only      : >=2-vertical rows get position_independent_row_automaton, columns None
  - cols only      : columns as in current code, rows None
  - CURRENT        : both (what produced 547k)
  - col-fix-short  : vertical columns use [short words <=L] + [the fixed vertical word] only
  - col-fix-none   : vertical columns None + force cells below the vertical inactive

Run: python experiments/21_connectivity_model_size.py [language] [board]
"""
import sys
sys.path.insert(0, '/home/bob/programming/scrabble4')
from solve import *
from scrabble import *
from dawg import T_ANY, T_NONE, position_independent_row_automaton, automaton_words_from_list

lang = sys.argv[1] if len(sys.argv) > 1 else "dutch"
board = sys.argv[2] if len(sys.argv) > 2 else "13"
rules = construct_rules(lang, board)
W, H = rules.W, rules.H
print(f"{lang} board {board}: {W}x{H}, {len(rules.words)} words")

# ---- build a realistic partial like max_turn_score does -------------------------------
# row 0: main word placed THIS turn -> all T_NONE in the setup board.
# pick ~ W//2 columns to carry a vertical setup word (rows 1..L), then a T_NONE gap, T_ANY below.
by_len = {}
for w in rules.words:
    by_len.setdefault(len(w), []).append(w)
def a_word(n):                       # a real dictionary word of length n (fallback: shorter)
    for k in range(n, 1, -1):
        if by_len.get(k):
            return by_len[k][len(by_len[k]) // 2]
    return None

partial = [[[T_NONE] for _ in range(W)]] + [[[T_ANY] for _ in range(W)] for _ in range(H - 1)]
vert_cols = list(range(0, W, 2))                       # every other column has a vertical
vlens = [7, 5, 6, 4, 7, 5, 6][:len(vert_cols)]
for ci, x in enumerate(vert_cols):
    L = vlens[ci % len(vlens)]
    word = a_word(L)
    for i, c in enumerate(word):                       # fixed vertical letters in rows 1..len(word)
        partial[1 + i][x] = [c]
    gap = 1 + len(word)
    if gap < H:
        partial[gap][x] = [T_NONE]                     # the break-cell gap, like the real code
print(f"vertical columns {vert_cols}, lengths {[len(a_word(l)) for l in vlens[:len(vert_cols)]]}")

def autstats(a):
    """(states, transitions) for an automaton: tuple (start,finals,triples) or a word-matrix."""
    if a is None:
        return (0, 0)
    if not isinstance(a, tuple):          # word matrix -> compile like create_board does
        if a.shape[0] == 0:
            return (0, 0)
        a = create_scrabble_automaton(a)
    trans = a[2]
    states = {t[0] for t in trans} | {t[2] for t in trans} | {a[0]}
    return (len(states), len(trans))

def counts(model, cells):
    return len(model.proto.variables), len(model.proto.constraints)

full_row = position_independent_row_automaton(rules.words)
active_per_row = [[x for x in range(W) if partial[y][x][0] >= 0] for y in range(H)]
ge2_rows = [y for y in range(H) if len(active_per_row[y]) >= 2]
print(f">=2-vertical rows: {ge2_rows}")

def col_current(x):
    if partial[1][x][-1] >= 0:
        return automaton_words_from_list(rules.words + [tuple()], H, list(zip(*partial))[x])
    return automaton_words_from_list([w for w in rules.words if len(w) <= 5] + [tuple()], H, list(zip(*partial))[x])

def col_fix_short(x):
    col = list(zip(*partial))[x]
    if partial[1][x][-1] >= 0:
        vword = tuple(partial[1 + i][x][0] for i in range(H - 1) if 1 + i < H and partial[1 + i][x][0] >= 0)
        wl = [w for w in rules.words if len(w) <= 5] + [vword] + [tuple()]
        return automaton_words_from_list(wl, H, col)
    return automaton_words_from_list([w for w in rules.words if len(w) <= 5] + [tuple()], H, col)

def build(rows_fn, cols_fn, force_below=False):
    m = cp_model.CpModel(); m.prefix = "c"
    rows = [full_row if (rows_fn and y in ge2_rows) else None for y in range(H)]
    cols = [cols_fn(x) if cols_fn else None for x in range(W)]
    cells = create_board(m, rows, cols, alphabet_size=len(rules.abc))
    for y in range(H):
        for x in range(W):
            if partial[y][x][0] >= 0:
                m.add(cells[(x, y)].letter[partial[y][x][0]] == 1)
            elif force_below and partial[y][x][0] == T_NONE:
                m.add(cells[(x, y)].active == 0)
    return m, cells

# row constructions to compare
def row_filtered(y):                       # ORIGINAL design: dict words filtered by fixed letters in row y
    return automaton_words_from_list(rules.words + [tuple()], W, partial[y])
def row_short(y, K=8):                      # dict words up to length K, filtered by fixed letters
    return automaton_words_from_list([w for w in rules.words if len(w) <= K] + [tuple()], W, partial[y])

# ---- per-automaton size (this is what CP-SAT expands: ~ line_length * #transitions) ----
print(f"\n{'automaton':30} {'states':>10} {'transitions':>14}")
s, t = autstats(full_row); print(f"{'row: position_independent(MONSTER)':30} {s:>10,} {t:>14,}")
yr = ge2_rows[len(ge2_rows)//2]            # a representative >=2-vertical row
print(f"  (representative row y={yr}, fixed cols {active_per_row[yr]})")
s, t = autstats(row_filtered(yr)); print(f"{'row: filtered by partial[y]':30} {s:>10,} {t:>14,}")
s, t = autstats(row_short(yr, 8)); print(f"{'row: <=8 words, filtered':30} {s:>10,} {t:>14,}")
xcw = next(x for x in range(W) if partial[1][x][-1] >= 0)
s, t = autstats(col_current(xcw)); print(f"{'col: CURRENT (vertical col)':30} {s:>10,} {t:>14,}")
xco = next(x for x in range(W) if partial[1][x][-1] < 0)
s, t = autstats(col_current(xco)); print(f"{'col: open (<=5 words)':30} {s:>10,} {t:>14,}")

# ---- expansion estimate (sum over automaton lines of line_length * #transitions) -------
def expansion(row_fn, col_fn):
    tot = 0
    if row_fn:
        for y in ge2_rows:
            _, t = autstats(row_fn(y)); tot += W * t
    if col_fn:
        for x in range(W):
            _, t = autstats(col_fn(x)); tot += H * t
    return tot

MONSTER = lambda y: full_row
print(f"\n{'config (rows x cols)':40} {'expansion (sum len*transitions)':>34}")
for name, rfn, cfn in [
    ("MONSTER rows + current cols (=my edit)",  MONSTER,      col_current),
    ("filtered rows + current cols (original)", row_filtered, col_current),
    ("filtered rows + fix-short cols",          row_filtered, col_fix_short),
    ("<=8 rows + fix-short cols",               lambda y: row_short(y, 8), col_fix_short),
]:
    print(f"{name:40} {expansion(rfn, cfn):>34,}")
