"""MAXGAME verrijker: leg greedy extra woorden op het 3-anker-bord tot de zak op is.
Prioriteit: lange horizontale woorden op de x4-rijen (4/10, DWS kol 4&10), dan overige rijen.
Elk nieuw woord: kruist >=1 bestaande tegel (verbonden), alle H+V-runs blijven legaal, zak-geteld.
Herbereken de losse SPEL-LB (ankers + face + bingo's).  Meerdere seeds; beste bewaard."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
from scrabble import construct_rules

r = construct_rules('dutch2026', '15')
W = H = 15
cba = r.alphabet.cba
lk = r.words_lookup
val = {chr(96+i): r.scores[i] for i in range(1, 27)}
def isw(s): return tuple(cba[ch] for ch in s) in lk

base = json.load(open('experiments/results/maxgame_board_final.json'))['grid']
words_by_len = {}
for w in r.words_str:
    if 2 <= len(w) <= 15:
        words_by_len.setdefault(len(w), []).append(w)

FINAL = {(c,0) for c in (0,3,7,8,11,12,14)} | {(c,7) for c in (0,1,2,3,11,12,14)} | {(c,14) for c in (0,1,3,5,7,11,14)}


def runs_ok(grid):
    for y in range(H):
        x = 0
        while x < W:
            if not grid[y][x]: x += 1; continue
            x2 = x
            while x2 < W and grid[y][x2]: x2 += 1
            if x2-x >= 2 and not isw(''.join(chr(96+grid[y][k]) for k in range(x, x2))): return False
            x = x2
    for x in range(W):
        y = 0
        while y < H:
            if not grid[y][x]: y += 1; continue
            y2 = y
            while y2 < H and grid[y2][x]: y2 += 1
            if y2-y >= 2 and not isw(''.join(chr(96+grid[k][x]) for k in range(y, y2))): return False
            y = y2
    return True


def try_place(grid, used, bag, word, x, y, h):
    """Leg word op (x,y,h) als: past op bord, elke cel leeg of al juiste letter, >=1 nieuwe cel,
    >=1 kruising met bestaand, zak ok, alle runs legaal.  Return nieuwe cellen of None."""
    dx, dy = (1, 0) if h else (0, 1)
    if x + dx*(len(word)-1) > 14 or y + dy*(len(word)-1) > 14: return None
    # cel voor/na moet leeg zijn (anders langere run -> die checken we via runs_ok toch; sneller pre-filter)
    px, py = x-dx, y-dy
    if 0 <= px < W and 0 <= py < H and grid[py][px]: return None
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < W and 0 <= ey < H and grid[ey][ex]: return None
    newcells = []; cross = False
    need = Counter()
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        g = grid[cy][cx]
        if g:
            if g != cba[ch]: return None
            cross = True
        else:
            newcells.append((cx, cy, cba[ch]))
            need[ch] += 1
    if not newcells or not cross: return None
    for ch, n in need.items():
        if used[ch] + n > bag[ch]: return None
    for (cx, cy, code) in newcells:
        grid[cy][cx] = code
    if not runs_ok(grid):
        for (cx, cy, _) in newcells: grid[cy][cx] = 0
        return None
    for ch, n in need.items(): used[ch] += n
    return newcells


def enrich(seed):
    random.seed(seed)
    grid = [row[:] for row in base]
    bag = Counter({chr(96+c): r.counts[c] for c in r.counts})
    used = Counter()
    for y in range(H):
        for x in range(W):
            if grid[y][x]: used[chr(96+grid[y][x])] += 1
    used['c'] -= 1; used['y'] -= 1                # 2 blanks dekken c,y-overflow
    total_new = 0
    rows_pri = [4, 10, 2, 12, 1, 13, 3, 11, 5, 9, 6, 8]
    for ln in range(15, 2, -1):
        ws = words_by_len.get(ln, [])
        random.shuffle(ws)
        placed_this = 0
        for w in ws[:20000]:
            if sum(bag.values()) - sum(used.values()) < 1: break
            for y in rows_pri:
                res = try_place(grid, used, bag, w, random.randint(0, max(0, 15-ln)), y, 1)
                if res: total_new += len(res); placed_this += 1; break
            else:
                for x in random.sample(range(15), 8):
                    res = try_place(grid, used, bag, w, x, random.randint(0, max(0, 15-ln)), 0)
                    if res: total_new += len(res); placed_this += 1; break
            if placed_this > 6: break
    nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
    # LB
    setup_face = sum(val[chr(96+grid[y][x])] for y in range(H) for x in range(W)
                     if grid[y][x] and (x, y) not in FINAL) - val['c'] - val['y']
    nsetup = nt - 21
    lb = 3876 + setup_face + 50*(nsetup//7)
    return lb, nt, grid


best = (0, 0, None)
for seed in range(120):
    lb, nt, grid = enrich(seed)
    if lb > best[0]:
        best = (lb, nt, grid)
        print(f"seed {seed}: tegels {nt} -> LB {lb}", flush=True)
lb, nt, grid = best
print(f"\nBESTE: {nt} tegels, SPEL-LB >= {lb}")
json.dump({'grid': grid, 'lb': lb}, open('experiments/results/maxgame_board_enriched.json', 'w'))
for y in range(H):
    print('  ' + ' '.join(chr(96+grid[y][x]) if grid[y][x] else '.' for x in range(W)))
