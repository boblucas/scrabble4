"""Verleng een afgerond maxgame-spel: speel resttegels na de slotzetten (mop-up).
Usage: maxgame_extend.py <game.json> [lexicon]"""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
if len(sys.argv) > 2: os.environ['N15_LANG'] = sys.argv[2]
else: os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[ch] for ch in s) in lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
d = json.load(open(sys.argv[1]))
grid = [row[:] for row in d['grid']]
moves = [[tuple(c) for c in mv] for mv in d['moves']]
bl = {tuple(b) for b in d['blanks']}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
used = Counter()
for y in range(15):
    for x in range(15):
        if grid[y][x] and (x, y) not in bl: used[chr(96+grid[y][x])] += 1
rest = Counter(bag0); rest.subtract(used)
rest = Counter({ch: n for ch, n in rest.items() if n > 0})
print(f"rest: {dict(sorted(rest.items()))} ({sum(rest.values())} tegels)")

def play(word, x, y, h):
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < 15 and 0 <= py < 15 and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < 15 and 0 <= ey < 15 and grid[ey][ex]: return False
    new = []; need = Counter(); cross = False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return False
            cross = True
        else:
            new.append((cx, cy)); need[ch] += 1
    if not new or len(new) > 7: return False
    if not cross and not any(0 <= nx+a < 15 and 0 <= ny+b < 15 and grid[ny+b][nx+a]
                             for (nx, ny) in new for a, b in ((1,0),(-1,0),(0,1),(0,-1))):
        return False
    if any(need[ch] > rest[ch] for ch in need): return False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    okr = True
    for yy in range(15):
        xx = 0
        while xx < 15:
            if not grid[yy][xx]: xx += 1; continue
            x2 = xx
            while x2 < 15 and grid[yy][x2]: x2 += 1
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx, x2))): okr = False
            xx = x2
    for xx in range(15):
        yy = 0
        while yy < 15:
            if not grid[yy][xx]: yy += 1; continue
            y2 = yy
            while y2 < 15 and grid[y2][xx]: y2 += 1
            if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy, y2))): okr = False
            yy = y2
    if not okr:
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    rest.subtract(need); moves.append(new)
    return True

def est(word, x, y, h):
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return -1
    s = 0; wm = 1; nnew = 0; cross = 0
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return -1
            s += val[ch]; continue
        lm = int(LM[cy][cx]); s += val[ch]*lm; wm *= int(WM[cy][cx]); nnew += 1
        cs = 0
        for dd in (-1, 1):
            k = 1
            while True:
                ox, oy = cx+dy*dd*k, cy+dx*dd*k
                if 0 <= ox < 15 and 0 <= oy < 15 and grid[oy][ox]:
                    cs += val[chr(96+grid[oy][ox])]; k += 1
                else: break
        if cs: cross += (cs + val[ch]*lm) * int(WM[cy][cx])
    if nnew == 0 or nnew > 7: return -1
    return s*wm + cross + (50 if nnew == 7 else 0)

words = [w for w in r.words_str if 2 <= len(w) <= 8]
added = 0
while True:
    cands = []
    anchors = [(x, y) for y in range(15) for x in range(15) if grid[y][x]]
    for w in words:
        wc = Counter(w)
        # snelle filter: minstens de niet-hookbare letters moeten in rest passen (grof: alle in rest+1)
        if sum(max(0, wc[ch]-rest[ch]-3) for ch in wc): continue
        for (ax, ay) in anchors:
            achr = chr(96+grid[ay][ax])
            if achr not in wc: continue
            for i, ch in enumerate(w):
                if ch != achr: continue
                for (px, py, h) in ((ax-i, ay, 1), (ax, ay-i, 0)):
                    e = est(w, px, py, h)
                    if e > 0:
                        # exacte rest-check
                        dx, dy = (1, 0) if h else (0, 1)
                        need = Counter(w[j] for j in range(len(w)) if not grid[py+j*dy][px+j*dx])
                        if all(need[c] <= rest[c] for c in need) \
                           and sum(rest.values()) - sum(need.values()) >= 1:
                            cands.append((e, w, px, py, h))   # reserve: >=1 tegel blijft over
    if not cands: break
    cands.sort(key=lambda t: -t[0])
    done = False
    for (e, w, px, py, h) in cands[:600]:
        if play(w, px, py, h):
            print(f"  + {w} ({px},{py}){'h' if h else 'v'} est~{e}")
            added += 1; done = True; break
    if not done: break
print(f"{added} extra zetten; rest nu: {dict(sorted((k,v) for k,v in rest.items() if v>0))}")
tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, bl)
print(f"VERLENGD: score={int(tot)} ok={ok} ({msg})")
if ok:
    out = dict(d); out['grid'] = grid; out['moves'] = [[list(c) for c in mv] for mv in moves]
    out['total'] = int(tot)
    o = sys.argv[1].replace('.json', '_ext.json')
    json.dump(out, open(o, 'w')); print("->", o)
