"""
Experiment 20: validate that a 'Can connect' board from a log has ALL maximal runs
(horizontal AND vertical) being valid dictionary words (single letters allowed).
Proves the omit_bottom_rows fix produces legal boards (no more "ezzzo").

Run: python experiments/20_validate_board.py <logfile> [language] [board]
"""
import sys
sys.path.insert(0, '/home/bob/programming/scrabble4')
from scrabble import construct_rules

LOG = sys.argv[1] if len(sys.argv) > 1 else "experiments/results/turns/bottomfix7.log"
lang = sys.argv[2] if len(sys.argv) > 2 else "dutch"
board = sys.argv[3] if len(sys.argv) > 3 else "7"
rules = construct_rules(lang, board)

# parse the first "Can connect" board diagram into a grid of letters (' ' = empty)
lines = open(LOG, errors="ignore").read().splitlines()
grid = []
inblk = False
for ln in lines:
    if "Can connect, final solution" in ln:
        inblk = True; grid = []; continue
    if inblk and ln.startswith("│"):
        body = ln.strip("│")
        grid.append([body[i] if i < len(body) else ' ' for i in range(0, len(body), 2)])
    elif inblk and ln.startswith("└"):
        break
W = max(len(r) for r in grid); H = len(grid)
grid = [r + [' '] * (W - len(r)) for r in grid]
print(f"parsed board {W}x{H} from {LOG}")

def runs(seq):  # maximal runs of non-space cells
    out, cur = [], []
    for c in seq + [' ']:
        if c == ' ':
            if cur: out.append(''.join(cur)); cur = []
        else:
            cur.append(c)
    return out

bad = []
def check(word, where):
    if len(word) == 1:
        return  # single letters count as words in this solver
    try:
        tup = rules.alphabet.to_tup(word.lower())
    except KeyError:
        bad.append((where, word, "non-alpha")); return
    if tup not in rules.words_lookup:
        bad.append((where, word, "NOT IN DICT"))

for y, row in enumerate(grid):
    for w in runs(row):
        check(w, f"row {y}")
for x in range(W):
    col = [grid[y][x] for y in range(H)]
    for w in runs(col):
        check(w, f"col {x}")

print("\n".join(f"  {y if (y:=w) else ''}".strip() for w in []) or "", end="")
if bad:
    print(f"INVALID runs found ({len(bad)}):")
    for where, word, why in bad:
        print(f"  {where}: '{word}'  -> {why}")
else:
    print("ALL maximal runs are valid dictionary words (or single letters). Board is LEGAL.")
