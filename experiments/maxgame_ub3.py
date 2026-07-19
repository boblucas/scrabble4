"""Maxgame UB V3: analytisch per-lijn frontier (gegroepeerde WM-stage + geneste-ketensom) +
zakwaarde-koppeling (<=230/richting) + TWS-case-analyse (Stelling 1+2).  Zie MAXGAME_PROOF.md."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
ch = json.load(open('experiments/results/maxgame_chains.json'))
mwsd = {}
for w in r.words_str:
    L = len(w); s = sum(val[c] for c in w)
    if s > mwsd.get(L, 0): mwsd[L] = s
CS = {int(k): v for k, v in ch['chainsum'].items()}
CH = {int(k): v for k, v in ch['chain'].items()}
BAGV = sum(val[chr(96+c)]*r.counts[c] for c in r.counts)

def line_scores(lms, wms, wbig_override=None):
    """frontier: (L, v) -> score.  Wbig = product WM>1 (of override); LME = som (lm-1)*10.
    score = Wbig*(min(v,mws[L])+LME) + greedy keten-rest (som bases <= CS[L]-v, b_j <= min(mws,v))."""
    out = {}
    prem = 1
    for c in range(15):
        if wms[c] > 1: prem *= wms[c]
    if wbig_override is not None: prem = wbig_override
    LME = sum((lms[c]-1)*10 for c in range(15) if lms[c] > 1)
    for L in range(2, 16):
        mw = mwsd.get(L, 0)
        for v in range(2, mw+1, 4):
            big = prem*(v + min(LME, 2*v))
            rest_budget = max(0, CS.get(L, 0) - v)
            kmax = CH.get(L, 1)
            restv = 0; got = 0
            out[(L, v, 1)] = big
            for j in range(2, kmax+1):
                b = min(mwsd.get(L-j+1, 0), v, rest_budget-got)
                if b <= 0: break
                restv += b; got += b
                out[(L, v, j)] = big + restv
    return out

def knap(fronts, cellbud=101, valbud=BAGV, stagebud=202):
    # DP over (cellen, waarde, stages) -> max score; retourneert beste per stage-gebruik
    import numpy as np
    NEG = -1
    VB = valbud//5 + 1
    dp = np.full((cellbud+1, VB+1, stagebud+1), NEG, dtype=np.int32)
    dp[0][0][0] = 0
    for f in fronts:
        nd = dp.copy()
        for (L, v, k), sc in sorted(f.items(), key=lambda t: -t[1]):
            vb = v//5   # verbruik naar beneden afgerond -> relaxatie, sound
            src = dp[:cellbud+1-L, :VB+1-vb, :stagebud+1-k]
            tgt = nd[L:, vb:, k:]
            cand = src + sc
            mask = (src >= 0) & (cand > tgt)
            tgt[mask] = cand[mask]
        dp = nd
    # beste score per totaal-stages (voor gezamenlijke stage-verdeling)
    flat = dp.reshape(-1, stagebud+1).max(axis=0)
    return flat

rowsLW = [([int(LM[y][x]) for x in range(15)], [int(WM[y][x]) for x in range(15)]) for y in range(15)]
colsLW = [([int(LM[y][x]) for y in range(15)], [int(WM[y][x]) for y in range(15)]) for x in range(15)]
# CASE R: rijen houden TWS (rij0/14 Wbig incl 27; rij7: center-DWS verbruikt -> Wbig=9);
#         kolommen 0/7/14 verliezen alle TWS -> Wbig = 1 (geen DWS op die lijnen)
def fronts_case(primary):
    fr = []
    for i, (lms, wms) in enumerate(rowsLW):
        ov = None
        if primary == 'C' and i in (0, 7, 14): ov = 1
        if primary == 'R' and i == 7: ov = 9   # center-DWS al verbruikt (Stelling 2)
        fr.append(line_scores(lms, wms, ov))
    fc = []
    for i, (lms, wms) in enumerate(colsLW):
        ov = None
        if primary == 'R' and i in (0, 7, 14): ov = 1
        if primary == 'C' and i == 7: ov = 9
        fc.append(line_scores(lms, wms, ov))
    return fr, fc

import numpy as np
best = 0
for case in ('R', 'C'):
    fr, fc = fronts_case(case)
    A = knap(fr); B = knap(fc)
    # gezamenlijk stagebudget 202: max over splitsingen
    Acm = np.maximum.accumulate(A); Bcm = np.maximum.accumulate(B)
    U = max(int(Acm[s1] + Bcm[202-s1]) for s1 in range(0, 203)
            if Acm[s1] >= 0 and Bcm[202-s1] >= 0)
    print(f"case {case}: rijen+kolommen (stages<=202 samen) = {U}")
    best = max(best, U)
U2 = best + 700
print(f"\nU2 = {U2}  -> bracket [3917, {U2}]")
