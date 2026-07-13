"""MAXGAME zetvolgorde-constructor: decomponeer het verrijkte eindbord in legale beurten en
scoor ze ECHT met maxgame_score (multipliers+kruiswoorden tellen).  Greedy DFS: zet 1 door
center; elke zet = contigu segment van een eindbord-lijn, <=7 nieuwe cellen, raakt component,
tussenstand-runs allemaal legaal.  Hoogste-score-eerst met beperkte backtracking."""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

grid = json.load(open('experiments/results/maxgame_board_enriched.json'))['grid']
W = H = 15
lk = MG.lk

def isw_codes(t): return tuple(t) in lk

def runs_legal(pl):
    """pl = 15x15 bool geplaatst; check alle maximale runs >=2 legale woorden (letters uit grid)."""
    for y in range(H):
        x = 0
        while x < W:
            if not pl[y][x]: x += 1; continue
            x2 = x
            while x2 < W and pl[y][x2]: x2 += 1
            if x2-x >= 2 and not isw_codes([grid[y][k] for k in range(x, x2)]): return False
            x = x2
    for x in range(W):
        y = 0
        while y < H:
            if not pl[y][x]: y += 1; continue
            y2 = y
            while y2 < H and pl[y2][x]: y2 += 1
            if y2-y >= 2 and not isw_codes([grid[k][x] for k in range(y, y2)]): return False
            y = y2
    return True

# kandidaat-zetten: voor elke lijn (rij/kolom) alle contiguë segmenten van eindbord-cellen
lines = []
for y in range(H):
    x = 0
    while x < W:
        if not grid[y][x]: x += 1; continue
        x2 = x
        while x2 < W and grid[y][x2]: x2 += 1
        if x2-x >= 2: lines.append([(k, y) for k in range(x, x2)])
        x = x2
for x in range(W):
    y = 0
    while y < H:
        if not grid[y][x]: y += 1; continue
        y2 = y
        while y2 < H and grid[y2][x]: y2 += 1
        if y2-y >= 2: lines.append([(x, k) for k in range(y, y2)])
        y = y2
print(f"# {len(lines)} eindbord-lijnen", flush=True)

def solve():
    pl = [[False]*W for _ in range(H)]
    moves = []
    ncells = sum(1 for y in range(H) for x in range(W) if grid[y][x])
    t0 = time.time()
    while sum(sum(row) for row in pl) < ncells:
        if time.time() - t0 > 600: return None, moves, pl
        best = None
        for line in lines:
            # segmenten van deze lijn: alle (i,j) zodat nieuw = cellen in segment die nog niet geplaatst
            n = len(line)
            for i in range(n):
                for j in range(i, n):
                    seg = line[i:j+1]
                    new = [(x, y) for (x, y) in seg if not pl[y][x]]
                    if not (1 <= len(new) <= 7): continue
                    # zet 1: door center; anders: raakt component (via seg-cel die al geplaatst is of buur)
                    if not moves:
                        if (7, 7) not in new: continue
                    else:
                        touch = any(pl[y][x] for (x, y) in seg) or any(
                            0 <= x+dx < W and 0 <= y+dy < H and pl[y+dy][x+dx]
                            for (x, y) in new for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)))
                        if not touch: continue
                    # tussenstand legaal?
                    for (x, y) in new: pl[y][x] = True
                    ok = runs_legal(pl)
                    if ok:
                        sc = len(new) + (50 if len(new) == 7 else 0)   # snelle proxy
                        if best is None or sc > best[0]:
                            best = (sc, [tuple(c) for c in new])
                    for (x, y) in new: pl[y][x] = False
        if best is None:
            return False, moves, pl
        for (x, y) in best[1]: pl[y][x] = True
        moves.append(best[1])
    return True, moves, pl

ok, moves, pl = solve()
rest = sum(1 for y in range(H) for x in range(W) if grid[y][x] and not pl[y][x])
print(f"# decompositie: ok={ok} zetten={len(moves)} onplaatsbaar={rest}", flush=True)
if ok:
    blanks = set()
    # blanks: c/y overflow -> kies 2 cellen (1 c, 1 y) buiten de ankerrijen als blank... conservatief:
    # markeer de c en y met de laagste multiplier-positie; voor de score-engine geven we blankcells
    from collections import Counter as C
    bag = C({chr(96+c): MG.r.counts[c] for c in MG.r.counts})
    cnt = C()
    for y in range(H):
        for x in range(W):
            if grid[y][x]: cnt[chr(96+grid[y][x])] += 1
    overch = [ch for ch in cnt if cnt[ch] > bag[ch] for _ in range(cnt[ch]-bag[ch])]
    for ch in overch:
        for y in range(H):
            done = False
            for x in range(W):
                if grid[y][x] == ord(ch)-96 and (x, y) not in blanks and y not in (0, 7, 14):
                    blanks.add((x, y)); done = True; break
            if done: break
    tot, per, vok, msg = MG.score_game(grid, moves, blanks)
    print(f"ECHTE SPELSCORE: {tot} over {len(moves)} zetten (ok={vok} {msg})", flush=True)
    print("per zet:", per, flush=True)
    json.dump({'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
               'blanks': [list(b) for b in blanks], 'total': int(tot)},
              open('experiments/results/maxgame_game.json', 'w'))
