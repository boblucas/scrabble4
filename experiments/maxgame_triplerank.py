"""Triplet-ranker onder bob's aannames (2026-07-20).
Per triplet (R0 x27, R14 x27, R7 x9): 'optimaal uitvoerbaar'-score =
  A = R0-completie: 27*(Sigma val + DLS-bonus cols 3,11 indien vers) + 50  (bingo)
  B = R14-completie: idem
  C = R7-completie: 9*(...) + 50, masker sluit center-col 7 uit (pre-placed door opening)
  D = opening op rij 7: beste 7-venster incl col 7, x2 (center-DWS), +50  (bingo)
Eis: prepareerbaar = elk ankerwoord heeft een legaal 7-masker (incl TWS-cols) met legale pre-runs
     (subwoordjes); bingo-eis op de prep-zetten NIET vereist.
Blancos: bag-overflow van de 45 ankertegels; penalty = blanks op laagste val*wordmult-cel (greedy).
Bingo's: 3 completies + 1 opening = 4 gegarandeerd (+ >=1 extra per aanname 5 = 5).
Output: top-100 op (A+B+C+D - blankpenalty)."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
from itertools import combinations
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
lk = r.words_lookup
w15 = sorted({w for w in r.words_str if len(w) == 15})
print(f"# {len(w15)} 15-letter woorden", flush=True)
bag = Counter({chr(96+c): r.counts[c] for c in r.counts}); BL = r.blank_count
DLS = (3, 11)  # dubbele-letter op rijen 0/7/14

def pre_runs_legal(w, mask):
    pre = set(range(15)) - set(mask); x = 0
    while x < 15:
        if x not in pre: x += 1; continue
        x2 = x
        while x2 < 15 and x2 in pre: x2 += 1
        if x2-x >= 2 and tuple(cba[c] for c in w[x:x2]) not in lk: return False
        x = x2
    return True

def best_completion(w, mustcols, wmv, forbid=()):
    """beste legale 7-masker-completie: wmv*(letters + DLS-bonus vers) + 50."""
    free = [c for c in range(15) if c not in mustcols and c not in forbid]
    base = sum(val[w[c]] for c in range(15))
    best = -1
    for extra in combinations(free, 7-len(mustcols)):
        mask = set(mustcols) | set(extra)
        if not pre_runs_legal(w, mask): continue
        dls = sum(val[w[c]] for c in DLS if c in mask)
        sc = wmv*(base+dls)+50
        if sc > best: best = sc
    return best

def best_opening(w):
    """beste 7-venster incl col 7 (center): x2 * (7 letters + DLS-bonus in venster) + 50."""
    best = -1
    for x0 in range(1, 8):  # venster [x0, x0+6], moet col 7 bevatten -> x0 in 1..7
        x1 = x0+6
        if not (x0 <= 7 <= x1): continue
        s = sum(val[w[c]] for c in range(x0, x1+1))
        dls = sum(val[w[c]] for c in DLS if x0 <= c <= x1)
        sc = 2*(s+dls)+50
        if sc > best: best = sc
    return best

# pre-filter met cheap bound (alle letters x27 / x9), exact op top-K
def cheap27(w): return 27*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50
def cheap9(w): return 9*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50
K = 1500
c27 = sorted(((cheap27(w), w) for w in w15), reverse=True)[:K]
c9 = sorted(((cheap9(w), w) for w in w15), reverse=True)[:K]
print(f"# exact op top-{K} per rol", flush=True)
S27 = {}; S9 = {}; OPEN = {}
for _, w in c27:
    s = best_completion(w, (0, 7, 14), 27)
    if s > 0: S27[w] = s
for _, w in c9:
    s = best_completion(w, (0, 14), 9, forbid=(7,))
    if s > 0: S9[w] = s; OPEN[w] = best_opening(w)
r27 = sorted(S27.items(), key=lambda t: -t[1])
r9 = sorted(((w, S9[w]+OPEN[w]) for w in S9), key=lambda t: -t[1])
print(f"# R0/R14-kandidaten: {len(r27)}, R7-kandidaten: {len(r9)}", flush=True)

codes = {w: Counter(w) for w in set(list(S27)+list(S9))}

def blanks_and_penalty(wa, wb, wc):
    """blancos nodig (overflow) + min penalty. Elke cel-occurrence heeft blank-cost = val*wm:
    R0/R14 cellen wm=27, R7-completie wm=9, R7-midden ook +2 (opening). Greedy: goedkoopste eerst."""
    tot = codes[wa] + codes[wb] + codes[wc]
    over = {c: tot[c]-bag.get(c, 0) for c in tot if tot[c] > bag.get(c, 0)}
    nbl = sum(over.values())
    if nbl > BL: return None, None
    # bouw per-letter lijst van occurrence-kosten (kies goedkoopste occurrences om te blanken)
    costs = {}  # letter -> sorted list of blank-costs (oplopend)
    for (w, wm) in ((wa, 27), (wb, 27), (wc, 9)):
        for i, ch in enumerate(w):
            costs.setdefault(ch, []).append(val[ch]*wm)
    pen = 0
    for ch, k in over.items():
        cs = sorted(costs.get(ch, []))
        pen += sum(cs[:k])  # blank de k goedkoopste occurrences van deze letter
    return nbl, pen

results = []
seen = set()
for wc, s9o in r9[:400]:
    for i in range(min(400, len(r27))):
        wa, sa = r27[i]
        if wa == wc: continue
        for j in range(i, min(400, len(r27))):
            wb, sb = r27[j]
            if wb == wc: continue
            key = frozenset([wa, wb, wc])
            if key in seen: continue
            nbl, pen = blanks_and_penalty(wa, wb, wc)
            if nbl is None: continue
            seen.add(key)
            score = sa + sb + s9o - pen
            results.append((score, wa, wb, wc, sa, sb, S9[wc], OPEN[wc], nbl, pen))
    if wc == r9[0][0] or len(results) % 5000 < 2:
        print(f"  .. {len(results)} triplets", flush=True)
results.sort(reverse=True)
print(f"\n# {len(results)} bag-haalbare prepareerbare triplets\n")
print(f"{'#':>3} {'score':>6} {'R0':<16}{'R14':<16}{'R7':<16} {'A':>5}{'B':>5}{'C':>5}{'D':>4} {'bl':>2} {'pen':>4} bingo")
for k, (sc, wa, wb, wc, sa, sb, c, dO, nbl, pen) in enumerate(results[:100]):
    print(f"{k+1:>3} {sc:>6} {wa:<16}{wb:<16}{wc:<16} {sa:>5}{sb:>5}{c:>5}{dO:>4} {nbl:>2} {pen:>4}  4+")
json.dump([{'rank': k+1, 'score': sc, 'triple': [wa, wb, wc], 'A': sa, 'B': sb, 'C_compl': c,
            'D_open': dO, 'blanks': nbl, 'penalty': pen}
           for k, (sc, wa, wb, wc, sa, sb, c, dO, nbl, pen) in enumerate(results[:200])],
          open('experiments/results/maxgame_triplerank.json', 'w'))
print(f"\nrecord-triplet-check: onze 3963 = flauwekulexcuus/babyzwemmertjes/zelfbeschikking")
for k, (sc, wa, wb, wc, *_ ) in enumerate(results):
    if {wa, wb, wc} == {'flauwekulexcuus', 'babyzwemmertjes', 'zelfbeschikking'}:
        print(f"  staat op rank {k+1}, kern-score {sc}"); break
