"""Gegeneraliseerde skelet-constructor (R7-eerst + brug-per-pre-run + span voor onbrugbare cellen).
Target: vluchtreflexjes(R0)/chequeformulier(R14)/babyzwemmertjes(R7). Elke stap score_game-gevalideerd.
R7-choreografie = record-babyzwemmertjes (opening zwemmer + teee-span + je); R0/R14 = verticale bruggen."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[c] for c in s) in lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
random.seed(int(os.environ.get('SEED', '1')))
words = r.words_str
byl = {L: [w for w in words if len(w) == L] for L in range(2, 9)}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})

R0 = 'vluchtreflexjes'; R14 = 'chequeformulier'; R7 = 'babyzwemmertjes'
C7 = R7[4:11]
M0 = (0, 6, 7, 8, 9, 11, 14)     # pre lucht(1-5),e(10),je(12-13)
M14 = (0, 3, 5, 7, 8, 11, 14)    # pre he(1-2),u(4),f(6),mu(9-10),ie(12-13)
M7 = (0, 1, 2, 3, 11, 13, 14)    # babyzwemmertjes ×9 (variant A)
anch = Counter(R0)+Counter(R7)+Counter(R14)
over = {ch: max(0, anch[ch]-bag0[ch]) for ch in anch if anch[ch] > bag0[ch]}
print(f"blanco-overflow ankers: {over}", flush=True)

grid = [[0]*15 for _ in range(15)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = {(c, 0) for c in M0} | {(c, 7) for c in M7} | {(c, 14) for c in M14}

def play(word, x, y, h, final=False):
    global blanks_left
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < 15 and 0 <= py < 15 and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < 15 and 0 <= ey < 15 and grid[ey][ex]: return False
    new = []; need = Counter(); byc = {}; cross = False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return False
            cross = True
        else:
            if not final and (cx, cy) in MASKC: return False
            new.append((cx, cy)); need[ch] += 1; byc.setdefault(ch, []).append((cx, cy))
    if not new or len(new) > 7: return False
    if moves:
        if not cross and not any(0 <= nx+a < 15 and 0 <= ny+b < 15 and grid[ny+b][nx+a]
                                 for (nx, ny) in new for a, b in ((1,0),(-1,0),(0,1),(0,-1))): return False
    elif (7, 7) not in new: return False
    ov = sum(max(0, used[ch]+n-bag0[ch]) for ch, n in need.items())
    if ov > (blanks_left if final else 0): return False
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
    for ch, n in need.items():
        o2 = max(0, used[ch]+n-bag0[ch]); used[ch] += n
        for k in range(o2): blankcells.add(byc[ch][k]); blanks_left -= 1
    moves.append(new)
    return True

log = []
def L(name, res): log.append((name, res)); return res

# ---- R7 eerst: opening + teee-span + je + completie (record-babyzwemmertjes-choreografie) ----
L('open zwemmer', play(C7, 4, 7, 1))                       # cols 4-10
# span8 'teee' op rij 8 (kol 9-12): (9,8)=e? nvm; record legde teee@(9,8). (10,8)=onder up-oost.
L('teee@9,8', play('teee', 9, 8, 1))                       # verbindt (9,8) onder zwemmer[5]='e'
# je verticaal op (12,7): (12,8)='e' van teee ligt -> 'je' = (12,7)j+(12,8)e
L('je@12,7', play('je', 12, 7, 0))
# R7-completie (final): legt de 7 masker-cellen (0,1,2,3,11,13,14)
s7 = L('R7 SLOT', play(R7, 0, 7, 1, final=True))

# ---- R0-bruggen (up, rijen 0-7, kruisen R7 op rij 7) ----
def bridge_up(c):
    for w in byl[8]:
        if w[0] == R0[c] and w[7] == R7[c] and play(w, c, 0, 0): return w
    return None
def bridge_dn(c):
    for w in byl[8]:
        if w[0] == R7[c] and w[7] == R14[c] and play(w, c, 7, 0): return w
    return None
L('up5 (lucht)', bridge_up(5))     # (5,0)=t
L('up10 (e)', bridge_up(10))       # (10,0)=e
L('up13 (je)', None if grid[0][13] else (lambda: [w for w in byl[8] if w[0]==R0[13] and w[7]==R7[13] and play(w,13,0,0)][0:1])())
# lucht: (5,0) ligt via up5 -> leg lucht cols 1-4
L('R0 lucht', play('lucht', 1, 0, 1))
# je: (13,0) via up13 -> leg (12,0)='j': 'je' at (12,0)h needs (12,0),(13,0); (13,0) ligt -> ok
L('R0 je', play('je', 12, 0, 1))

# ---- R14-bruggen (dn, rijen 7-14) ----
L('dn6 (f)', bridge_dn(6))
L('dn9 (mu)', bridge_dn(9))
L('dn2 (he)', bridge_dn(2))        # (2,14)=e connects he
L('dn13 (ie)', bridge_dn(13))      # (13,14)=e connects ie
# he: (2,14) via dn2 -> leg (1,14)='h': 'he' at (1,14)h
L('R14 he', play('he', 1, 14, 1))
# mu: (9,14) via dn9 -> leg (10,14)='u': mu at (9,14) is (9,14)m+(10,14)u; (9,14) ligt -> leg u? play 'mu'?
L('R14 mu', play('mu', 9, 14, 1))
# ie: (13,14) via dn13 -> leg (12,14)='i': 'ie' at (12,14)h
L('R14 ie', play('ie', 12, 14, 1))
# u@4: geen brug -> span op rij 13 van kol 4 naar dn6-brug (kol 6). (6,13)=dn6[6]. woord cols 4-6 rij13
#   eindletter=(6,13); (4,13)+(4,14)u vormt verticaal ?+u (before-ok). probeer 'nu'-achtig via span.
def span_u():
    if not grid[13][6]: return None
    tgt = chr(96+grid[13][6])
    for w in byl[3]:
        if w[2] == tgt and isw(w[0]+'u'):   # (4,13)=w[0], onder =u -> w[0]+u woord
            if play(w, 4, 13, 1): return w
    return None
L('u-span', span_u())
L('R14 u', play('u', 4, 14, 1) if not grid[14][4] else 'al-gelegd')
# f: (6,14) via dn6
# ---- completes R0, R14 ----
s0 = L('R0 SLOT', play(R0, 0, 0, 1, final=True))
s14 = L('R14 SLOT', play(R14, 0, 14, 1, final=True))

for name, res in log: print(f"  {name}: {res}", flush=True)
nt = sum(1 for yy in range(15) for xx in range(15) if grid[yy][xx])
tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"\nSKELET: zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} ({msg}) slot=({s7},{s0},{s14})", flush=True)
if ok and s7 and s0 and s14:
    out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
           'blanks': [list(b) for b in blankcells], 'total': int(tot), 'triple': [R0, R7, R14]}
    json.dump(out, open('experiments/results/maxgame_gen.json', 'w'))
    print("*** SKELET SLUIT -> maxgame_gen.json (fill via extender)", flush=True)
else:
    print("skelet nog niet dicht — zie fails hierboven", flush=True)
