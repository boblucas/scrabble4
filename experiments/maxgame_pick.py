"""Kies de beste KETEN-EXISTENTE triple: rank2-constraints + echte span1/span13/span8-woorden."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
def isw(s): return tuple(cba[ch] for ch in s) in lk
words = r.words_str
w15 = [w for w in words if len(w) == 15]
ALPH = 'abcdefghijklmnopqrstuvwxyz'
AF = {c: {x for x in ALPH if isw(c+x)} for c in ALPH}
BF = {c: {x for x in ALPH if isw(x+c)} for c in ALPH}
C8 = {}
for w in words:
    if len(w) == 8: C8.setdefault((w[0], w[7]), []).append(w)
byl = {L: [w for w in words if len(w) == L] for L in (2, 3, 4, 5, 6)}
def rowscore(w, wm): return wm*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50

def span_exists(rw, updown, bcol, bletters):
    """bestaat span (1..bcol) met eind-letter in bletters en AF/BF-eisen van rw?"""
    S = AF if updown == 'up' else BF
    for w in byl[bcol]:
        if w[bcol-1] in bletters and all(w[c-1] in S[rw[c]] for c in range(1, bcol)):
            return True
    return False

def row_ok(rw, updown, c7):
    if not (isw(rw[1:3]) and isw(rw[4:7]) and isw(rw[8:11])): return False
    bcols = []
    for c in (4, 5, 6):
        key = (rw[c], c7[c-4]) if updown == 'up' else (c7[c-4], rw[c])
        if C8.get(key):
            bl = {w[1] if updown == 'up' else w[6] for w in C8[key]}
            if span_exists(rw, updown, c, bl): bcols.append(c)
    if not bcols: return False
    if not any(C8.get((rw[c], c7[c-4]) if updown == 'up' else (c7[c-4], rw[c])) for c in (8, 9, 10)):
        return False
    return True

def sp8_exists(r7):
    c7 = r7[4:11]
    # variant A (pre=12): span (9..12 of 10..12,8) + j2; variant B (pre=13): span (10..13,8)+2w
    for L, x0 in ((3, 10), (4, 9)):
        base = {0: AF[c7[6]]} if x0 == 10 else {0: AF[c7[5]], 1: AF[c7[6]]}
        off = 11-x0
        for w in byl[L]:
            if all(w[i] in base.get(i, ALPH) for i in base) and w[off] in AF[r7[11]] \
               and w[off+1] in AF[r7[12]] and isw(r7[12]+w[off+1]):
                return 'A'
    for w in byl[4]:
        if w[0] in AF[c7[6]] and w[1] in AF[r7[11]] and w[2] in AF[r7[12]] \
           and w[3] in AF[r7[13]] and isw(r7[13]+w[3]) and isw(r7[12]+w[2]):
            return 'B'
    return None

SIG = {}
def sp8_cached(w):
    k = (w[4+5], w[4+6], w[11], w[12], w[13])
    if k not in SIG: SIG[k] = sp8_exists(w)
    return SIG[k]

c7ok = sorted(((rowscore(w, 9), w) for w in w15 if isw(w[4:11])), reverse=True)
print(f"center7-legaal: {len(c7ok)}")
r7c = []
for s7, w in c7ok:
    v = sp8_cached(w)
    if v:
        r7c.append((s7, w, v))
        if len(r7c) >= 25: break
print(f"R7-existent (top-25 lazy): top-5:", r7c[:5])

upok = sorted(((rowscore(w, 27), w) for w in w15
               if isw(w[1:3]) and isw(w[4:7]) and isw(w[8:11])), reverse=True)
SPMEMO = {}
def span_ok(rw, updown, bcol, blfz):
    k = (rw[1], rw[2], rw[3], rw[4], rw[5], updown, bcol, blfz)
    if k not in SPMEMO:
        S = AF if updown == 'up' else BF
        SPMEMO[k] = any(w[bcol-1] in blfz and all(w[c-1] in S[rw[c]] for c in range(1, bcol))
                        for w in byl[bcol])
    return SPMEMO[k]
def row_ok2(rw, updown, c7):
    got = False
    for c in (4, 5, 6):
        key = (rw[c], c7[c-4]) if updown == 'up' else (c7[c-4], rw[c])
        lst = C8.get(key)
        if lst:
            bl = frozenset(w[1] if updown == 'up' else w[6] for w in lst)
            if span_ok(rw, updown, c, bl): got = True; break
    if not got: return False
    return any(C8.get((rw[c], c7[c-4]) if updown == 'up' else (c7[c-4], rw[c])) for c in (8, 9, 10))

bag = Counter({chr(96+c): r.counts[c] for c in r.counts}); BL = r.blank_count
mask014 = (0, 3, 7, 11, 12, 13, 14)
best = None
for s7, w7, v7 in r7c:
    c7 = w7[4:11]
    r0c = [(s, w) for s, w in upok[:400] if row_ok2(w, 'up', c7)][:40]
    r14c = [(s, w) for s, w in upok[:400] if row_ok2(w, 'dn', c7)][:40]
    for s0, w0 in r0c:
        for s14, w14 in r14c:
            if w14 == w0: continue
            tot = Counter(w0)+Counter(w7)+Counter(w14)
            ov = {ch: tot[ch]-bag.get(ch, 0) for ch in tot if tot[ch] > bag.get(ch, 0)}
            if sum(ov.values()) > BL: continue
            m7 = (0,1,2,3,11,13,14) if v7 == 'A' else (0,1,2,3,11,12,14)
            mk = Counter([w0[c] for c in mask014]+[w14[c] for c in mask014]+[w7[c] for c in m7])
            if any(mk[ch] < n for ch, n in ov.items()): continue
            sc = s0+s7+s14
            if best is None or sc > best[0]:
                best = (sc, w0, w7, w14, v7)
print("BESTE TRIPLE:", best)
if best:
    open('experiments/results/maxgame_triple.txt', 'w').write(
        f"{best[1]} {best[2]} {best[3]} {best[4]} {best[0]}\n")
