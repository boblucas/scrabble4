"""Maxgame UB V0: per-lijn stage-DP + knapsack-koppeling (zie MAXGAME_PROOF.md)."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
tiles = sorted((val[chr(96+c)] for c in r.counts for _ in range(r.counts[c])), reverse=True)

def line_frontier(lms, wms):
    """F[(stages, cellen)] = max som stage-scores voor deze lijn (letters: beste toewijzing).
    Toewijzing (UB): hoogste tegelwaarden op hoogste LM-cellen van het gebruikte interval."""
    n = 15
    # beste letterwaarde per cel als functie van gekozen interval is interval-afhankelijk;
    # UB-vereenvoudiging: v_c = tiles[rang van lm_c binnen de lijn] (hoogste waarde op hoogste lm)
    order = sorted(range(n), key=lambda c: -lms[c])
    v = [0]*n
    for rank, c in enumerate(order): v[c] = tiles[rank]
    best = {}
    # DP over intervallen; stages = ketenlengte
    from functools import lru_cache
    import itertools
    INT = [(a, b) for a in range(n) for b in range(a, n)]
    # topologisch op grootte
    INT.sort(key=lambda ab: ab[1]-ab[0])
    dp = {}   # (a,b) -> dict stages -> max score
    for (a, b) in INT:
        base_new = sum(v[c]*lms[c] for c in range(a, b+1))
        wm_new = 1
        for c in range(a, b+1): wm_new *= wms[c]
        cur = {1: base_new * wm_new}
        for (a2, b2) in INT:
            if b2-a2 >= b-a: break
            if a2 < a or b2 > b or (a2 == a and b2 == b): continue
            if (a2, b2) not in dp: continue
            delta = [c for c in range(a, b+1) if c < a2 or c > b2]
            if not delta: continue
            ds = sum(v[c]*lms[c] for c in delta) + sum(v[c] for c in range(a2, b2+1))
            dwm = 1
            for c in delta: dwm *= wms[c]
            sc = ds * dwm
            for st, tot in dp[(a2, b2)].items():
                cur[st+1] = max(cur.get(st+1, 0), tot + sc)
        dp[(a, b)] = cur
        cells = b-a+1
        for st, tot in cur.items():
            k = (st, cells)
            best[k] = max(best.get(k, 0), tot)
    return best

fronts = []
for y in range(15):
    fronts.append(line_frontier([int(LM[y][x]) for x in range(15)], [int(WM[y][x]) for x in range(15)]))
for x in range(15):
    fronts.append(line_frontier([int(LM[y][x]) for y in range(15)], [int(WM[y][x]) for y in range(15)]))
# knapsack: kies per lijn 1 frontier-punt (of niets); Σ cellen<=202, Σ stages<=202
CB, SB = 202, 202
NEG = 0
dp = {(0, 0): 0}
for f in fronts:
    nd = dict(dp)
    for (cu, su), tot in dp.items():
        for (st, ce), v2 in f.items():
            c2, s2 = cu+ce, su+st
            if c2 > CB or s2 > SB: continue
            k = (c2, s2)
            if nd.get(k, -1) < tot + v2: nd[k] = tot + v2
    # prune: houd pareto-beste per (cellen-bucket)
    pruned = {}
    for (c2, s2), tot in nd.items():
        k = (c2, s2)
        if pruned.get(k, -1) < tot: pruned[k] = tot
    dp = pruned
U_rest = max(dp.values())
print(f"rest-UB V0 (per-lijn DP + budgetkoppeling): {U_rest}")
print(f"bingo-budget: +700")
print(f"U0 totaal = {U_rest + 700}  (NB: mains van het frame zitten IN de lijn-DP's van rijen 0/7/14)")
print(f"bracket: [3917, {U_rest + 700}]")
