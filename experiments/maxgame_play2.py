"""MAXGAME game-builder v2: ANKER-CHOREOGRAFIE.
1 myalgie door center (bingo).  2 bruggen-omhoog (rijen 0-6, 7 nieuw = bingo) in kol 4,9,13:
leggen rij-0-pre h/h/e + rij-7-pre e(13,7).  3 bruggen-omlaag (rijen 8-14) kol 4,6,9,13:
rij-14-pre c/r/r/e.  4 pre-runs hen/he/tri/je + verbindingszoektocht voor es(1,2)+u(2,14).
5 slotzetten rij 7, rij 0, rij 14 (elk x27/x9).  6 greedy rest.  Engine-gescoord."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

r = MG.r; W = H = 15
cba = r.alphabet.cba; lk = MG.lk
val = {chr(96+i): r.scores[i] for i in range(1, 27)}
def isw(s): return tuple(cba[ch] for ch in s) in lk
R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'

grid = [[0]*W for _ in range(H)]
moves = []
bag = Counter({chr(96+c): r.counts[c] for c in r.counts})
blanks_left = r.blank_count
blankcells = set(); used = Counter()

def can_pay(need):
    return sum(max(0, used[ch]+n-bag[ch]) for ch, n in need.items()) <= blanks_left

def runs_ok():
    for yy in range(H):
        xx = 0
        while xx < W:
            if not grid[yy][xx]: xx += 1; continue
            x2 = xx
            while x2 < W and grid[yy][x2]: x2 += 1
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx, x2))): return False
            xx = x2
    for xx in range(W):
        yy = 0
        while yy < H:
            if not grid[yy][xx]: yy += 1; continue
            y2 = yy
            while y2 < H and grid[y2][xx]: y2 += 1
            if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy, y2))): return False
            yy = y2
    return True

MASKCELLS = ({(c,0) for c in (0,3,7,8,11,12,14)} | {(c,7) for c in (0,1,2,3,11,12,14)}
             | {(c,14) for c in (0,1,3,5,7,11,14)})

def play(word, x, y, h, maxnew=7, final=False):
    global blanks_left
    dx, dy = (1,0) if h else (0,1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < W and 0 <= py < H and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < W and 0 <= ey < H and grid[ey][ex]: return False
    new = []; need = Counter(); by = {}
    cross = False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return False
            cross = True
        else:
            if not final and (cx, cy) in MASKCELLS: return False
            new.append((cx, cy)); need[ch] += 1; by.setdefault(ch, []).append((cx, cy))
    if not new or len(new) > maxnew: return False
    if moves:
        if not cross and not any(0<=nx+a<W and 0<=ny+b<H and grid[ny+b][nx+a]
                                 for (nx,ny) in new for a,b in ((1,0),(-1,0),(0,1),(0,-1))):
            return False
    elif (7,7) not in new: return False
    if not can_pay(need): return False
    if not final:
        if sum(max(0, used[ch]+n-bag[ch]) for ch, n in need.items()) > 0:
            return False      # blanks gereserveerd voor slotzetten
        resv = Counter()
        for (rx, ry, word_) in ((0, 0, R0), (0, 7, R7), (0, 14, R14)):
            for cx in range(15):
                if not grid[ry][cx] and (cx, ry) not in new:
                    resv[word_[cx]] += 1
        resv['c'] -= 1; resv['y'] -= 1        # gedekt door de 2 blanks
        for ch in set(list(need) + list(resv)):
            if used[ch] + need.get(ch, 0) + max(0, resv.get(ch, 0)) > bag[ch]:
                return False                   # zou anker-letters opeten
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    if not runs_ok():
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    for ch, n in need.items():
        over = max(0, used[ch]+n-bag[ch]); used[ch] += n
        for k in range(over): blankcells.add(by[ch][k]); blanks_left -= 1
    moves.append(new)
    return True

SEED = int(os.environ.get('SEED', '1'))
random.seed(SEED)
w8 = [w for w in r.words_str if len(w) == 8]
random.shuffle(w8)

def bridge_up(c):
    for w in w8:
        if w[0] == R0[c] and w[7] == R7[c] and play(w, c, 0, 0): return w
    return None

def bridge_dn(c):
    for w in w8:
        if w[0] == R7[c] and w[7] == R14[c] and play(w, c, 7, 0): return w
    return None

log = []
assert play('myalgie', 4, 7, 1); log.append('myalgie')
for c in (4, 9):
    b = bridge_up(c); log.append(f'up{c}:{b}')
for c in (6, 8, 10):
    b = bridge_dn(c); log.append(f'dn{c}:{b}')
# pre-runs rij 0: hen(4-6): h ligt; he(9-10): h ligt; e(13) ligt
play('hen', 4, 0, 1) and log.append('hen')
play('he', 9, 0, 1) and log.append('he')
# rij 14: tri(8-10): r(9,14) ligt; je(12-13): e(13,14) ligt; c(4,14) r(6,14) via bruggen
play('tri', 8, 14, 1) and log.append('tri')
# ===== DETERMINISTISCHE LADDER-KETENS voor de rand-pre-cellen =====
bylen = {}
for w in r.words_str:
    if 2 <= len(w) <= 6: bylen.setdefault(len(w), []).append(w)

def span(y, x0, x1, want=None):
    """Vul rij y kolommen x0..x1 met een woord (play valideert kruisrunnen); want = {pos_abs: ch}
    extra eisen op letters.  Return gelegd woord of None."""
    L = x1 - x0 + 1
    for w in bylen.get(L, []):
        if want and any(w[x-x0] != ch for x, ch in want.items()): continue
        if play(w, x0, y, 1): return w
    return None

def vfill(x, y0, word_pat):
    """Verticaal woord op kolom x vanaf rij y0; word_pat met vaste letters uit grid gematcht door play."""
    for w in bylen.get(len(word_pat), []):
        okp = all(pc in ('?', w[i]) for i, pc in enumerate(word_pat))
        if okp and play(w, x, y0, 0): return w
    return None

def after(ch): return {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(ch + x)}
def before(ch): return {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(x + ch)}
E_AFTER = after('e'); E_BEFORE = before('e')
chain = []
def span_sets(y, x0, x1, constraints):
    L = x1 - x0 + 1
    for w in bylen.get(L, []):
        if any(w[p - x0] not in a for p, a in constraints.items()): continue
        if play(w, x0, y, 1): return w
    return None
# rij-8-span: (11,8) na-'t', (12,8) na-'j', (13,8) na-'e'
chain.append(('span8_10_13', span_sets(8, 10, 13, {11: after('t'), 12: after('j'), 13: E_AFTER})))
for w2 in bylen[2]:
    if w2[0] == 'e' and grid[8][13] and w2[1] == chr(96+grid[8][13]) and play(w2, 13, 7, 0):
        chain.append(('e13_7', w2)); break
b13 = bridge_up(13); chain.append(('up13', b13))
# rij-14-rand: rij-12-span 4..6 met w[0]='s' (vanaf dn6), dan 'sec' verticaal (4,12..14)
chain.append(('span12_4_6', span(12, 4, 6, want={4: 's'})))
if grid[12][4] and play('sec', 4, 12, 0):
    chain.append(('sec', 'sec'))
# (2,14)'u': rij-13-span 2..4? (4,13) ligt via sec='e' -> span 2..4 met w[2]='e'; dan 'nu'
chain.append(('span13_2_4', span(13, 2, 4, want={4: 'e', 2: 'n'})))
if grid[13][2] and play('nu', 2, 13, 0):
    chain.append(('nu', 'nu'))
# (12,14)'j'+(13,14)'e': rij-13-span 10..12 (vanaf dn10 (10,13)), dan (13,14)e via... simpeler:
# verticale 2-run op kol 13: (13,13)+(13,14): span 10..13 rij 13, dan 2-run ?+e
chain.append(('span13_10_13', span_sets(13, 10, 13, {11: before('x'), 12: before('j'), 13: E_BEFORE})))
for w2 in bylen[2]:
    if grid[13][13] and w2[0] == chr(96+grid[13][13]) and w2[1] == 'e' and play(w2, 13, 13, 0):
        chain.append(('e13_14', w2)); break
if grid[14][13] and play('je', 12, 14, 1):
    chain.append(('je', 'je'))
# 'es'(1,2): rij-1-span 1..4 (vanaf up4), verticale 2-runs e+w[0], s+w[1] via play zelf
chain.append(('span1_1_4', span_sets(1, 1, 4, {1: after('e'), 2: after('s'), 3: after('c')})))
if play('es', 1, 0, 1):
    chain.append(('es', 'es'))
print("ketens:", chain, flush=True)
# oud commentaar hieronder blijft
# es(1,2)+u(2,14): verbindingszoektocht -- horizontaal woord dat kol<=2 aan brug-kol 4 hangt
def connect_left(rowrange, targetcell, vertword_ok):
    """Zoek: horizontaal woord op rij y van kol x0<=2 tot een liggende cel; dan verticaal naar target."""
    for y in rowrange:
        for ln in (3, 4, 5):
            for x0 in range(0, 5-ln+2):
                xe = x0+ln-1
                if not grid[y][xe] and not grid[y][x0]:
                    continue
            # simpeler: probeer alle woorden die (4,y) of (x,y) kruisen -- fase B doet dit; skip
        break
    return False
# eenvoudig: laat fase B dit oplossen; forceer daarna de pre-cellen expliciet
# slotzet rij 7 (pre compleet: myalgie + e(13,7))
play(R7, 0, 7, 1, final=True) and log.append('SLOTZET-R7')
print("log:", log, flush=True)

# fase B greedy (ook om es/u aan te leggen)
wlist = [w for w in r.words_str if 2 <= len(w) <= 8]
random.shuffle(wlist); wlist = wlist[:200000]
PRE = ([(c,0) for c in (1,2,4,5,6,9,10,13)] + [(c,14) for c in (2,4,6,8,9,10,12,13)]
       + [(13,7)])
for rnd in range(40):
    missing = [(x, y) for (x, y) in PRE if not grid[y][x]]
    # doelgericht: probeer eerst zetten die een ontbrekende pre-cel leggen
    for (mx, my) in missing:
        want = (R0 if my == 0 else R14 if my == 14 else R7)[mx]
        hit = False
        for w in wlist[:60000]:
            if want not in w: continue
            for i, ch in enumerate(w):
                if ch != want: continue
                if play(w, mx-i, my, 1) or play(w, mx, my-i, 0):
                    hit = True; break
            if hit: break
    anchors = [(x, y) for y in range(H) for x in range(W) if grid[y][x]]
    random.shuffle(anchors)
    prog = False
    for (ax, ay) in anchors[:80]:
        achr = chr(96+grid[ay][ax])
        for w in wlist[:30000]:
            if achr not in w: continue
            done = False
            for i, ch in enumerate(w):
                if ch != achr: continue
                if play(w, ax-i, ay, 1) or play(w, ax, ay-i, 0): done = True; break
            if done: prog = True; break
    # probeer pre-completeringen + slotzetten
    if grid[1][0]==0:
        pass
    if not grid[1-1][1]:
        play('es', 1, 0, 1) and print("  es gelegd", flush=True)
    play('nu', 2, 13, 0)
    if all(grid[0][c] for c in (1,2,4,5,6,9,10,13)) and not grid[0][0]:
        if play(R0, 0, 0, 1, final=True): print("  *** SLOTZET RIJ 0 ***", flush=True)
    if all(grid[14][c] for c in (2,4,6,8,9,10,12,13)) and not grid[14][0]:
        if play(R14, 0, 14, 1, final=True): print("  *** SLOTZET RIJ 14 ***", flush=True)
    if not prog: break
missing = [(x, y) for (x, y) in PRE if not grid[y][x]]
print(f"ontbrekende pre-cellen: {missing}", flush=True)
nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"\nSPEL: zetten={len(moves)} tegels={nt} score={tot} ok={ok} ({msg})", flush=True)
r0done = grid[0][0] != 0; r14done = grid[14][0] != 0
print(f"slotzetten: R7={'JA' if grid[7][0] else 'NEE'}, R0={'JA' if r0done else 'NEE'}, R14={'JA' if r14done else 'NEE'}", flush=True)
json.dump({'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
           'blanks': [list(b) for b in blankcells], 'total': int(tot), 'seed': SEED},
          open(f'experiments/results/maxgame_play2_{SEED}.json', 'w'))
