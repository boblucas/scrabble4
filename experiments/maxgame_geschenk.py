"""Directe skelet-constructor voor geschenkcheques/bouwcuratrixjes/babyzwemmertjes (hoge-kern-triple
die de flauwekulexcuus-builder niet aankon: mask 'che' faalt de triple-filter). Bouwt opening +
bruggen + prep-subwoorden + spans zoals nodig, valideert continu, en draait daarna de fill.
Elke play() checkt run-legaliteit; MG.score_game is de arbiter."""
import sys, os, json, random, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
lk = MG.lk
def isw(s): return tuple(cba[c] for c in s) in lk
random.seed(int(os.environ.get('SEED', '1')))
words = r.words_str
byl = {L: [w for w in words if len(w) == L] for L in range(2, 9)}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})

R0 = 'geschenkcheques'; R14 = 'bouwcuratrixjes'; R7 = 'babyzwemmertjes'
C7 = R7[4:11]  # zwemmer, cols 4-10
# maskers (vers-cols) — pre-runs zijn woorden:
M0 = (0, 3, 7, 8, 11, 12, 14)   # geschenkcheques: pre es(1,2)/hen(4,5,6)/he(9,10)/e(13)
M14 = (0, 1, 3, 5, 7, 11, 14)   # bouwcuratrixjes: pre u(2)/c(4)/r(6)/tri(8,9,10)/je(12,13)
M7 = (0, 1, 2, 3, 11, 12, 14)   # babyzwemmertjes: pre y(?)... check hieronder; center 7 + 4-10 = opening
# verify pre-runs
def preruns(w, mask):
    pre = [c for c in range(15) if c not in mask]; out = []; i = 0
    while i < len(pre):
        j = i
        while j+1 < len(pre) and pre[j+1] == pre[j]+1: j += 1
        out.append((pre[i], w[pre[i]:pre[j]+1])); i = j+1
    return out
for lab, w, m in (('R0', R0, M0), ('R14', R14, M14)):
    prs = preruns(w, m)
    print(f"{lab} {w} mask{m}: pre-runs {[(c, s) for c, s in prs]}  legaal={all(len(s) == 1 or isw(s) for c, s in prs)}", flush=True)

grid = [[0]*15 for _ in range(15)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = {(c, 0) for c in M0} | {(c, 7) for c in M7} | {(c, 14) for c in M14}
over = {ch: max(0, (Counter(R0)+Counter(R7)+Counter(R14))[ch]-bag0[ch]) for ch in (Counter(R0)+Counter(R7)+Counter(R14))}
over = {ch: n for ch, n in over.items() if n > 0}
print(f"blanco-overflow ankers: {over} (limiet {r.blank_count})", flush=True)

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

# ---- SKELET ----
log = []
# 1) opening zwemmer (cols 4-10, rij 7) door center
log.append(('open zwemmer', play(C7, 4, 7, 1)))
# 2) up-bruggen op 2 pre-placed R0-cols (6,9,10 mogelijk; kies 6 en 9), dn-bruggen op 2 R14-cols (8,9 of 6,8)
#    brug up c: 8-woord [0]=R0[c], [7]=C7[c-4]; verticaal rijen 0-7
def bridge_up(c):
    for w in byl[8]:
        if w[0] == R0[c] and w[7] == C7[c-4] and play(w, c, 0, 0): return w
    return None
def bridge_dn(c):
    for w in byl[8]:
        if w[0] == C7[c-4] and w[7] == R14[c] and play(w, c, 7, 0): return w
    return None
log.append(('up6', bridge_up(6)))
log.append(('up9', bridge_up(9)))
log.append(('dn8', bridge_dn(8)))
log.append(('dn6', bridge_dn(6)))
# 3) R0 pre-runs: es(1,2), hen(4,5,6), he(9,10), e(13). up6 legde (6,0)? nee up-brug legt (c,0..7);
#    (6,0)=R0[6]='n' ligt door up6. hen(4,5,6): (6,0) ligt, leg (4,0),(5,0)=he -> maar run 4-6='hen'.
#    play 'hen' at (4,0)h: (4,0),(5,0) nieuw, (6,0) bestaand 'n' -> forms hen. OK
log.append(('R0-hen', play('hen', 4, 0, 1)))
log.append(('R0-es', play('es', 1, 0, 1)))       # (1,0),(2,0) - moeten aanhaken; es op rij0 naast? niet verbonden tenzij kruis
log.append(('R0-he', play('he', 9, 0, 1)))       # (9,0) ligt door up9? up9 legt (9,0)='c'(R0[9]=h? ) check
log.append(('R0-e', None))                        # (13,0)='e' enkel -> via verticaal 2-woord
# 4) R14 pre-runs: u(2),c(4),r(6),tri(8,9,10),je(12,13)
log.append(('R14-tri', play('tri', 8, 14, 1)))
log.append(('R14-je', play('je', 12, 14, 1)))
# 5) slotzetten
s7 = play(R7, 0, 7, 1, final=True)
s0 = play(R0, 0, 0, 1, final=True)
s14 = play(R14, 0, 14, 1, final=True)
log.append(('SLOT', (s7, s0, s14)))
for name, res in log: print(f"  {name}: {res}", flush=True)
nt = sum(1 for yy in range(15) for xx in range(15) if grid[yy][xx])
tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"\nSKELET: zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} ({msg}) slot=({s7},{s0},{s14})", flush=True)
if ok and s7 and s0 and s14:
    out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
           'blanks': [list(b) for b in blankcells], 'total': int(tot), 'triple': [R0, R7, R14]}
    json.dump(out, open('experiments/results/maxgame_geschenk.json', 'w'))
    print("skelet OK -> maxgame_geschenk.json (fill apart via extender)", flush=True)
else:
    print("SKELET FAALT — spans/connectiviteit nodig voor corner-subwoorden (es@1,2 / e@13 / he@9,10)", flush=True)
