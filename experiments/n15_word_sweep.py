"""SOUND global threat sweep over ALL 15-letter words (lang/HMAX from env; LB via --lb).

For every 15-letter main word w, a cheap SOUND upper bound on any turn using it:

    UB(w) = max over 7-col masks m ⊇ {0,7,14} of  [ WM(m)·mainsum(w,m) + 50 + Σ_{c∈m} colbest(w[c], c) ]

with colbest(L, c) = wm[c] · (maxtailsum(L) + val(L)·(lm[c]−1)) where maxtailsum(L) is the max
letter-sum over TAIL-LEGAL dictionary verticals starting with L (computed in ONE dict pass —
closed form because tails carry no multipliers: only the newly row-0 tile triggers premiums).
Mask legality (pre-run words) and bag limits only REDUCE the score, so ignoring them is sound.
Every word with UB(w) <= LB is CERTIFIED; survivors go to the exact per-mask assessor.
Writes survivors to --out.
"""
import sys, os, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from itertools import combinations
import n15_twolevel as T

r = T.r
val = {i: r.scores[i] for i in range(1, 27)}
wmv = T.wm
lmv = T.lm
lk = T.lk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, required=True)
    ap.add_argument('--out', default='experiments/results/n15_2026_sweep_open.txt')
    a = ap.parse_args()
    LB = a.lb
    print(f"# lang={os.environ.get('N15_LANG', 'dutch')} HMAX={T.HMAX} LB={LB}", flush=True)

    # one pass: max tail-legal vertical letter-sum per starting letter
    t0 = time.time()
    maxtail = [0] * 27                       # maxtail[L] = max sum(val) over legal verticals w/ w[0]=L
    for ww in r.words:
        if len(ww) < 2 or len(ww) > T.HMAX:
            continue
        if ww[1:] not in lk:
            continue
        s = sum(val[c] for c in ww)
        L = ww[0]
        if s > maxtail[L]:
            maxtail[L] = s
    print(f"# maxtail pass: {time.time()-t0:.0f}s  (e.g. maxtail[s]={maxtail[19]})", flush=True)

    def colbest(L, c):
        if maxtail[L] == 0:
            return 0                        # no legal vertical; bare tile scores 0
        return wmv[c] * (maxtail[L] + val[L] * (lmv[c] - 1))

    extra_cols = [c for c in range(1, 14) if c not in (7,)]
    extra_cols = [c for c in extra_cols if c not in (0, 7, 14)]
    words15 = sorted({w for w in r.words_str if len(w) == 15})
    print(f"# {len(words15)} 15-letter words", flush=True)
    survivors = []
    t0 = time.time()
    for n, w in enumerate(words15):
        codes = [T.cba[ch] for ch in w]
        base_sum = sum(val[c] for c in codes)
        fixed_cb = sum(colbest(codes[c], c) for c in (0, 7, 14))
        best = 0
        for extra in combinations(extra_cols, 4):
            mainsum = base_sum + sum(val[codes[c]] * (lmv[c] - 1) for c in extra)
            tot = 27 * mainsum + 50 + fixed_cb + sum(colbest(codes[c], c) for c in extra)
            if tot > best:
                best = tot
        if best > LB:
            survivors.append((best, w))
        if (n + 1) % 20000 == 0:
            print(f"  {n+1}/{len(words15)} ({(n+1)/(time.time()-t0):.0f}/s) "
                  f"survivors={len(survivors)}", flush=True)
    survivors.sort(reverse=True)
    with open(a.out, 'w') as f:
        for ub, w in survivors:
            f.write(f"{w}\t{ub}\n")
    print(f"# SWEEP DONE: {len(survivors)} survivors (cheap UB > {LB}) -> {a.out}", flush=True)
    for ub, w in survivors[:15]:
        print(f"    {w}  cheapUB={ub}", flush=True)


if __name__ == '__main__':
    main()
