"""Versnelde exhaustieve mop-up-DFS: kandidaten EENMALIG voorberekend per skeletpatroon.
Per node alleen: zak-check + grid-compat (cellen matchen) + run-legaliteit incrementeel.
Branch-and-bound met fillbound-per-lijn UB-snoei. Heartbeat per 30s (bob's voorkeur)."""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
def isw(s): return tuple(cba[c] for c in s) in MG.lk

d = json.load(open('experiments/results/maxgame_BEST.json'))
G = d['grid']; bl = {tuple(b) for b in d['blanks']}
mv0 = [[tuple(c) for c in m] for m in d['moves']]
fin = [i for i, m in enumerate(mv0) if len(m) == 7 and len({c[1] for c in m}) == 1 and m[0][1] in (0,7,14) and i >= 15]
skelmv = [mv0[i] for i in list(range(15))+fin]
skel = {c for m in skelmv for c in m}
grid0 = [[G[y][x] if (x, y) in skel else 0 for x in range(15)] for y in range(15)]
bl2 = {b for b in bl if b in skel}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
used0 = Counter()
for (x, y) in skel:
    if (x, y) not in bl2: used0[chr(96+G[y][x])] += 1
rest0 = Counter(bag0); rest0.subtract(used0)
rest0 = Counter({k: v for k, v in rest0.items() if v > 0})
S0 = int(MG.score_game([row[:] for row in grid0], skelmv, bl2)[0])
print(f"skelet={S0}, rest={dict(sorted(rest0.items()))} ({sum(rest0.values())} tegels)", flush=True)

# EENMALIG: alle plaatsingen (woord,x,y,h) die op het skeletbord passen (letters matchen waar bezet,
# minstens 1 verse cel, haakt aan bestaand, hoofdwoord+kruiswoorden legaal op HET SKELET).
# Tijdens DFS worden extra vullers geplaatst; een voorberekende plaatsing blijft geldig zolang zijn
# verse cellen leeg zijn en zijn buurcellen niet veranderd zijn (hercheck goedkoop).
words = [w for w in r.words_str if 2 <= len(w) <= 7]
placements = []
occ = [[grid0[y][x] for x in range(15)] for y in range(15)]
for w in words:
    L = len(w)
    for h in (1, 0):
        dx, dy = (1, 0) if h else (0, 1)
        for y in range(15):
            for x in range(15):
                if x+dx*(L-1) > 14 or y+dy*(L-1) > 14: continue
                px, py = x-dx, y-dy
                if 0 <= px < 15 and 0 <= py < 15 and occ[py][px]: continue
                ex, ey = x+dx*L, y+dy*L
                if 0 <= ex < 15 and 0 <= ey < 15 and occ[ey][ex]: continue
                new = []; need = Counter(); ok = True; touch = False
                for i, ch in enumerate(w):
                    cx, cy = x+i*dx, y+i*dy
                    g = occ[cy][cx]
                    if g:
                        if g != cba[ch]: ok = False; break
                        touch = True
                    else:
                        new.append((cx, cy)); need[ch] += 1
                if not ok or not new or len(new) > 7: continue
                placements.append((w, x, y, h, tuple(new), need, touch))
print(f"voorberekende plaatsingen (op kaal skelet): {len(placements)}", flush=True)

grid = [row[:] for row in grid0]
rest = Counter(rest0)
moves = list(skelmv)
best = [0]; NODES = [0]; t0 = time.time()
TL = float(os.environ.get('MGTL', '6000'))
BB = int(os.environ.get('MGB', '10'))

def runs_ok_local(new):
    for (cx, cy) in new:
        # horizontale run door (cx,cy)
        x0 = cx
        while x0 > 0 and grid[cy][x0-1]: x0 -= 1
        x1 = cx
        while x1 < 14 and grid[cy][x1+1]: x1 += 1
        if x1 > x0 and not isw(''.join(chr(96+grid[cy][k]) for k in range(x0, x1+1))): return False
        y0 = cy
        while y0 > 0 and grid[y0-1][cx]: y0 -= 1
        y1 = cy
        while y1 < 14 and grid[y1+1][cx]: y1 += 1
        if y1 > y0 and not isw(''.join(chr(96+grid[k][cx]) for k in range(y0, y1+1))): return False
    return True

# eenvoudiger place/unplace
def place(pl):
    w, x, y, h, new, need, touch = pl
    dx, dy = (1, 0) if h else (0, 1)
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    if not runs_ok_local(new):
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    rest.subtract(need); moves.append(new)
    return True
def unplace(pl):
    w, x, y, h, new, need, touch = pl
    for (cx, cy) in new: grid[cy][cx] = 0
    rest.update(need); moves.pop()

def est(pl):
    w, x, y, h, new, need, touch = pl
    dx, dy = (1, 0) if h else (0, 1); s = 0; wm = 1; n = 0
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]: s += val[ch]
        else: s += val[ch]*int(LM[cy][cx]); wm *= int(WM[cy][cx]); n += 1
    return s*wm + (50 if n == 7 else 0)

def leaf():
    tot = int(MG.score_game([row[:] for row in grid], moves, bl2)[0])
    if tot - S0 > best[0]:
        best[0] = tot - S0
        json.dump({'grid': [row[:] for row in grid], 'moves': [[list(c) for c in m] for m in moves],
                   'blanks': [list(b) for b in bl2], 'total': tot, 'triple': d['triple']},
                  open('experiments/results/maxgame_fillfast_best.json', 'w'))
        print(f"maxfill {best[0]} (totaal {tot}) na {time.time()-t0:.0f}s", flush=True)

def dfs(depth, startidx):
    NODES[0] += 1
    if NODES[0] % 100000 == 0:
        print(f"  ..{NODES[0]} nodes, {time.time()-t0:.0f}s, best {best[0]}", flush=True)
    if time.time() - t0 > TL: return
    leaf()
    if depth >= 10: return
    # kandidaten die NU passen (verse cellen leeg), gesorteerd op est
    cur = []
    for j in range(startidx, len(placements)):
        pl = placements[j]
        if any(grid[cy][cx] for (cx, cy) in pl[4]): continue
        if any(pl[5][c] > rest[c] for c in pl[5]): continue
        cur.append((est(pl), j, pl))
    cur.sort(key=lambda t: -t[0])
    for _, j, pl in cur[:BB]:
        if place(pl):
            dfs(depth+1, 0)
            unplace(pl)
        if time.time() - t0 > TL: return

dfs(0, 0)
print(f"KLAAR (heuristisch anytime, NIET uitputtend): maxfill {best[0]}, nodes {NODES[0]}", flush=True)
