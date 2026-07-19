"""Maxgame UB V1: V0-DP + woordsom-caps + per-richting budgetten + Lagrange-letterkoppeling.
Elke Lagrange-iteratie levert een GELDIGE bovengrens; we rapporteren de beste."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
LM = r.letter_multiplier; WM = r.word_multiplier
ALPH = [ch for ch in 'abcdefghijklmnopqrstuvwxyz' if r.counts.get(cba[ch], 0)]
cnt = {ch: r.counts[cba[ch]] for ch in ALPH}
# woordsom-cap per lengte (harde dictionary-feiten)
mws = {}
for w in r.words_str:
    L = len(w)
    s = sum(val[c] for c in w)
    if s > mws.get(L, 0): mws[L] = s
print("max woordsom per lengte:", {k: mws[k] for k in sorted(mws) if k <= 15})

def line_frontier(lms, wms, adjtiles):
    """DP; base-waarden = adjtiles[rank] op lm-gesorteerde cellen; stage-score gecapt met
    3*mws[|interval|] (LM<=3).  Returns {(stages,cellen): (score, usage-ranks)}."""
    n = 15
    order = sorted(range(n), key=lambda c: -lms[c])
    v = [0.0]*n; rank_of = [0]*n
    for rank, c in enumerate(order):
        v[c] = max(0.0, adjtiles[rank][0]); rank_of[c] = rank
    INT = [(a, b) for a in range(n) for b in range(a, n)]
    INT.sort(key=lambda ab: ab[1]-ab[0])
    dp = {}
    best = {}
    for (a, b) in INT:
        L = b-a+1
        cap = mws.get(L, 0) + sum((lms[c]-1)*10 for c in range(a, b+1) if lms[c] > 1)
        if L == 1: cap = 0
        base = sum(v[c]*lms[c] for c in range(a, b+1))
        wmp = 1
        for c in range(a, b+1): wmp *= wms[c]
        cur = {1: min(base, cap) * wmp}
        for (a2, b2) in INT:
            if b2-a2 >= L-1: break
            if a2 < a or b2 > b: continue
            if (a2, b2) not in dp: continue
            delta = [c for c in range(a, b+1) if c < a2 or c > b2]
            ds = sum(v[c]*lms[c] for c in delta) + sum(v[c] for c in range(a2, b2+1))
            dwm = 1
            for c in delta: dwm *= wms[c]
            sc = min(ds, cap) * dwm
            for st, tot in dp[(a2, b2)].items():
                if cur.get(st+1, -1) < tot + sc: cur[st+1] = tot + sc
        dp[(a, b)] = cur
        for st, tot in cur.items():
            k = (st, L)
            if best.get(k, (-1,))[0] < tot:
                best[k] = (tot, tuple(sorted(rank_of[c] for c in range(a, b+1))))
    return best

def solve(lam):
    # adjusted gesorteerde tegel-lijst: (waarde - lambda[type], type)
    adj = sorted(((val[ch]-lam.get(ch, 0.0), ch) for ch in ALPH for _ in range(cnt[ch])),
                 key=lambda t: -t[0])
    rows = [line_frontier([int(LM[y][x]) for x in range(15)], [int(WM[y][x]) for x in range(15)], adj)
            for y in range(15)]
    cols = [line_frontier([int(LM[y][x]) for y in range(15)], [int(WM[y][x]) for y in range(15)], adj)
            for x in range(15)]
    def knap(fronts, cellbud):
        dp = {(0, 0): (0.0, [])}
        for fi, f in enumerate(fronts):
            nd = dict(dp)
            for (cu, su), (tot, us) in dp.items():
                for (st, ce), (v2, ranks) in f.items():
                    if st > ce: continue          # stelling: stages <= cellen per lijn
                    c2, s2 = cu+ce, su+st
                    if c2 > cellbud or s2 > cellbud: continue
                    k = (c2, s2)
                    if nd.get(k, (-1,))[0] < tot + v2:
                        nd[k] = (tot + v2, us + [(fi, ranks)])
            dp = nd
        bk = max(dp.values(), key=lambda t: t[0])
        return bk
    rv, rus = knap(rows, 101)
    cv, cus = knap(cols, 101)
    # duale term + usage per lettertype (voor subgradient)
    use = Counter()
    adjtypes = [t for _, t in sorted(((val[ch]-lam.get(ch, 0.0), ch) for ch in ALPH
                                      for _ in range(cnt[ch])), key=lambda t: -t[0])]
    for us in (rus, cus):
        for fi, ranks in us:
            for rk in ranks:
                if rk < len(adjtypes): use[adjtypes[rk]] += 1
    U = rv + cv + sum(lam.get(ch, 0.0)*2*cnt[ch] for ch in ALPH) + 700
    return U, use

lam = {ch: 0.0 for ch in ALPH}
bestU = None
for it in range(26):
    U, use = solve(lam)
    if bestU is None or U < bestU: bestU = U
    print(f"iter {it}: U = {U:.0f} (beste {bestU:.0f})", flush=True)
    step = max(0.3, 2.0/(1+it))
    for ch in ALPH:
        g = use[ch] - 2*cnt[ch]
        lam[ch] = max(0.0, lam[ch] + step*(0.15 if g > 0 else -0.1)*max(1, abs(g))**0.5 * (1 if g > 0 else 1))
        if g < 0: lam[ch] = max(0.0, lam[ch]*0.7)
print(f"\nU1 = {bestU:.0f}  -> bracket [3917, {bestU:.0f}]")
