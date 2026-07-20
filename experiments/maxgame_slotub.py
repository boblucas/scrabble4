"""Sound skelet-S*-UB via separabiliteit: per ketenslot exact max-zetscore over kandidaten
(zak-gerelaxeerd = UB). Som + backbone-vaste-deel. Vergelijk met S*_lb=3738."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
def isw(s): return tuple(cba[c] for c in s) in MG.lk
R0, R7, R14 = 'flauwekulexcuus', 'babyzwemmertjes', 'zelfbeschikking'; C7 = R7[4:11]
words = r.words_str
AF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(c+x)} for c in set(R0+R7+R14+C7)}
BF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(x+c)} for c in set(R14)}
C8 = {}
for w in words:
    if len(w) == 8: C8.setdefault((w[0], w[7]), []).append(w)
byl = {L: [w for w in words if len(w) == L] for L in (2, 3, 4, 5, 6)}

def zetscore(w, x, y, h, pre):
    dx, dy = (1, 0) if h else (0, 1)
    s = 0; wm = 1; nnew = 0
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if (cx, cy) in pre:
            s += val[ch]
        else:
            s += val[ch]*int(LM[cy][cx]); wm *= int(WM[cy][cx]); nnew += 1
    return s*wm + (50 if nnew == 7 else 0)

def rowscore(w, wm): return wm*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50
BASE = rowscore(R0, 27)+rowscore(R14, 27)+rowscore(R7, 9)

def brmax(kind, c):
    lst = C8.get((R0[c], C7[c-4]) if kind == 'up' else (C7[c-4], R14[c]), [])
    if not lst: return 0
    pre = {(c, 0), (c, 7)} if kind == 'up' else {(c, 7), (c, 14)}
    y0 = 0 if kind == 'up' else 7
    return max(zetscore(w, c, y0, 0, pre) for w in lst)

SL = {}
SL['up6'] = brmax('up', 6); SL['up8'] = brmax('up', 8)
SL['dn5'] = brmax('dn', 5); SL['dn10'] = brmax('dn', 10)
SL['center7'] = zetscore(C7, 4, 7, 1, set())
smax = max(zetscore(w, 1, 1, 1, set()) for w in byl[6])
SL['span1'] = smax; SL['span13'] = smax
run3 = max(zetscore(w, 4, 0, 1, set()) for w in byl[3])
SL['runs'] = 6*run3
S_UB = BASE + sum(SL.values())
print("BASE(3 slotzetten)=", BASE)
for k, v in SL.items(): print(f"  slot {k}: {v}")
print(f"S*_UB (zak-gerelaxeerd, separabel) = {S_UB}")
print(f"S*_lb (stochastisch) = 3738  -> skelet-bracket [3738, {S_UB}]")
