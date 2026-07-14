"""MAXGAME anker-herranking onder KETENBAARHEIDS-maskers (2026-07-14).
Rij 0/14: masker geforceerd (0,3,7,11,12,13,14) -> pre-runs w[1:3], w[4:7], w[8:11] moeten woorden
zijn; rij-1/13-span vereist after/before(w[c])!=nul voor c=1..3; brug-existentie per run.
R7: w[4:11] (center-7) moet woord zijn; masker {0,1,2,3,11,12,14} of {..13..}; pre-cel 12/13
bereikbaar via rij-8-span (after-eisen). Bruggen: 8-woorden begin/eind-letterparen."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
def isw(s): return tuple(cba[ch] for ch in s) in lk
words = r.words_str
w15 = [w for w in words if len(w) == 15]
AF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(c+x)} for c in 'abcdefghijklmnopqrstuvwxyz'}
BF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(x+c)} for c in 'abcdefghijklmnopqrstuvwxyz'}
C8b = Counter((w[0], w[7]) for w in words if len(w) == 8)  # (begin,eind) -> count

def rowscore(w, wm):
    return wm * (sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50

# R7-kandidaten
r7c = []
for w in w15:
    if not isw(w[4:11]): continue
    # pre 12 ('j'-slot) of 13; span8 10..12/13: (11,8) in AF[w[11]], (12,8) in AF[w[12]]
    ok12 = AF[w[11]] and AF[w[12]]                       # pre=12: 2-woord w12+x
    ok13 = AF[w[11]] and AF[w[12]] and AF[w[13]]         # pre=13: span door 12 heen
    if not (ok12 or ok13): continue
    r7c.append((rowscore(w, 9), w, 12 if ok12 else 13))
r7c.sort(reverse=True)
print("top-10 R7 (x9, center-7 legaal, oost-pre bereikbaar):")
for s, w, p in r7c[:10]:
    print(f"  {s:5d} {w}  center7={w[4:11]} pre-oost={p}")

# rij 0/14-kandidaten (zelfde constraint-vorm, richting verschilt)
def rowcands(updown):
    out = []
    for w in w15:
        if not (isw(w[1:3]) and isw(w[4:7]) and isw(w[8:11])): continue
        S = AF if updown == 'up' else BF
        if not (S[w[1]] and S[w[2]] and S[w[3]]): continue
        out.append((rowscore(w, 27), w))
    out.sort(reverse=True)
    return out
r0c = rowcands('up'); r14c = rowcands('dn')
print(f"\nrij-0-kandidaten: {len(r0c)}, rij-14: {len(r14c)}")
print("top-10 rij 0:");  [print(f"  {s:5d} {w}  [{w[1:3]}|{w[4:7]}|{w[8:11]}]") for s, w in r0c[:10]]
print("top-10 rij 14:"); [print(f"  {s:5d} {w}  [{w[1:3]}|{w[4:7]}|{w[8:11]}]") for s, w in r14c[:10]]

# triples: R7 uit top-30, R0/R14 uit top-60, zak-feasible, brug-existentie
bag = Counter({chr(96+c): r.counts[c] for c in r.counts}); BL = r.blank_count
best = []
for s7, w7, p7 in r7c[:30]:
    c7 = w7[4:11]
    for s0, w0 in r0c[:60]:
        # up-bruggen: run {4,5,6} en {8,9,10} elk >=1 kolom met 8-woord R0[c]->c7[c-4]
        if not any(C8b[(w0[c], c7[c-4])] for c in (4,5,6)): continue
        if not any(C8b[(w0[c], c7[c-4])] for c in (8,9,10)): continue
        for s14, w14 in r14c[:60]:
            if w14 == w0: continue
            if not any(C8b[(c7[c-4], w14[c])] for c in (4,5,6)): continue
            if not any(C8b[(c7[c-4], w14[c])] for c in (8,9,10)): continue
            tot = Counter(w0) + Counter(w7) + Counter(w14)
            over = sum(max(0, tot[c] - bag.get(c, 0)) for c in tot)
            if over > BL: continue
            best.append((s0+s7+s14, over, w0, w7, w14))
best.sort(reverse=True)
print(f"\n{len(best)} ketenbare zak-feasible triples; top-10:")
for s, o, w0, w7, w14 in best[:10]:
    print(f"  {s:5d} (blanks {o})  r0={w0} r7={w7} r14={w14}")
