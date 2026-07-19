"""Anytime-exacte maxfill-DFS op skelet van BEST (mop-up-subklasse: vullers na slotzetten).
Snapshot/restore-DFS, est-gesorteerde branching (cap MGB), exacte leaf-score via score_game."""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
def isw(s): return tuple(cba[ch] for ch in s) in MG.lk
d = json.load(open('experiments/results/maxgame_BEST.json'))
G = d['grid']; bl = {tuple(b) for b in d['blanks']}
mv0 = [[tuple(c) for c in m] for m in d['moves']]
fin = [i for i, m in enumerate(mv0) if len(m) == 7 and len({c[1] for c in m}) == 1 and m[0][1] in (0,7,14) and i >= 15]
skelmv = [mv0[i] for i in list(range(15))+fin]
skel = {c for m in skelmv for c in m}
grid = [[G[y][x] if (x, y) in skel else 0 for x in range(15)] for y in range(15)]
bl2 = {b for b in bl if b in skel}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
used0 = Counter()
for (x, y) in skel:
    if (x, y) not in bl2: used0[chr(96+G[y][x])] += 1
rest = Counter(bag0); rest.subtract(used0)
rest = Counter({k: v for k, v in rest.items() if v > 0})
S0 = int(MG.score_game([row[:] for row in grid], skelmv, bl2)[0])
print(f"skelet={S0}, rest={dict(sorted(rest.items()))}", flush=True)
words = [w for w in r.words_str if 2 <= len(w) <= 8]
moves = list(skelmv)
def play(w, x, y, h):
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(w)-1) > 14 or y+dy*(len(w)-1) > 14: return None
    px, py = x-dx, y-dy
    if 0 <= px < 15 and 0 <= py < 15 and grid[py][px]: return None
    ex, ey = x+dx*len(w), y+dy*len(w)
    if 0 <= ex < 15 and 0 <= ey < 15 and grid[ey][ex]: return None
    new = []; need = Counter(); cross = False
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return None
            cross = True
        else: new.append((cx, cy)); need[ch] += 1
    if not new or len(new) > 7: return None
    if not cross and not any(0 <= a < 15 and 0 <= b < 15 and grid[b][a]
                             for (nx, ny) in new for a, b in ((nx+1,ny),(nx-1,ny),(nx,ny+1),(nx,ny-1))):
        return None
    if any(need[c] > rest[c] for c in need): return None
    if sum(rest.values()) - sum(need.values()) < 1: return None
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    ok = True
    for yy in range(15):
        xx = 0
        while xx < 15:
            if not grid[yy][xx]: xx += 1; continue
            x2 = xx
            while x2 < 15 and grid[yy][x2]: x2 += 1
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx, x2))): ok = False
            xx = x2
        if not ok: break
    if ok:
        for xx in range(15):
            yy = 0
            while yy < 15:
                if not grid[yy][xx]: yy += 1; continue
                y2 = yy
                while y2 < 15 and grid[y2][xx]: y2 += 1
                if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy, y2))): ok = False
                yy = y2
    if not ok:
        for (cx, cy) in new: grid[cy][cx] = 0
        return None
    rest.subtract(need); moves.append(new)
    return new
def undo(new, w):
    for (cx, cy) in new: grid[cy][cx] = 0
    moves.pop()
    for i, ch in enumerate(w):
        pass
    for (cx, cy) in new: pass
    # letters terug
    dxy = None
def cands():
    out = []
    anchors = [(x, y) for y in range(15) for x in range(15) if grid[y][x]]
    for w in words:
        wc = Counter(w)
        if sum(max(0, wc[c]-rest[c]-4) for c in set(w)): continue
        for (ax, ay) in anchors:
            achr = chr(96+grid[ay][ax])
            if achr not in wc: continue
            for i, ch2 in enumerate(w):
                if ch2 != achr: continue
                for (px, py, h) in ((ax-i, ay, 1), (ax, ay-i, 0)):
                    dx, dy = (1, 0) if h else (0, 1)
                    if px < 0 or py < 0 or px+dx*(len(w)-1) > 14 or py+dy*(len(w)-1) > 14: continue
                    e = 0; n = 0; bad = False
                    for j, c3 in enumerate(w):
                        cx, cy = px+j*dx, py+j*dy
                        if grid[cy][cx]:
                            if grid[cy][cx] != cba[c3]: bad = True; break
                            e += val[c3]
                        else:
                            e += val[c3]*int(LM[cy][cx]); n += 1
                    if bad or n == 0: continue
                    out.append((e, w, px, py, h))
    out.sort(key=lambda t: -t[0])
    seen = set(); ded = []
    for t in out:
        k = (t[1], t[2], t[3], t[4])
        if k not in seen: seen.add(k); ded.append(t)
    return ded
BB = int(os.environ.get('MGB', '8'))
best = [0]
t0 = time.time(); TL = float(os.environ.get('MGTL', '3300'))
def leaf():
    tot = int(MG.score_game([row[:] for row in grid], moves, bl2)[0])
    if tot - S0 > best[0]:
        best[0] = tot - S0
        print(f"maxfill LB: {best[0]} (totaal {tot}) na {time.time()-t0:.0f}s", flush=True)
        json.dump({'grid': [row[:] for row in grid], 'moves': [[list(c) for c in m] for m in moves],
                   'blanks': [list(b) for b in bl2], 'total': tot, 'triple': d['triple']},
                  open('experiments/results/maxgame_fillexact_best.json', 'w'))
def dfs(depth):
    if time.time() - t0 > TL: return
    leaf()
    if depth >= 8: return
    tried = 0
    for (e, w, px, py, h) in cands():
        if tried >= BB: break
        restsnap = Counter(rest)
        new = play(w, px, py, h)
        if new is None: continue
        tried += 1
        dfs(depth+1)
        for (cx, cy) in new: grid[cy][cx] = 0
        moves.pop()
        rest.clear(); rest.update(restsnap)
        if time.time() - t0 > TL: return
dfs(0)
print(f"KLAAR: maxfill-LB {best[0]}; volledig doorzocht: {time.time()-t0 < TL}", flush=True)
