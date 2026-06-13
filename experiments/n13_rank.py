"""N=13 center-constrained witness CANDIDATE RANKER (analytic, no search).

total = main_score + sum_c(vertical scores). The per-column verticals are nearly independent, and
in this model premiums sit on row 0: a vertical in column x scores (sum of its letter values) * wm_x
where wm_x = word_multiplier[0,x].  So we can RANK every 13-letter main word by an optimistic total
with NO search, then hand only the top candidates to xfill --emit for a verified witness.

Structure assumed = the proven-tractable LEFT-EDGE block: scoring cols {0,1,2,3,4,5,6} (=> 7 newly
placed => bingo), center col 6 long (len 7-8, reaches center row 6 and is a x3 word col), others
short.  Premiums on row 0 for N=13: x3 word at cols 0,6,12; x2 letter at cols 3,9.

Optimistic per-column vertical bound:
  maxsum[L][lo..hi] = max over dict words starting with letter L, length in [lo,hi], of sum-of-values.
  col x (x in {0..5}):  wv_x = wm_x * maxsum[w[x]][2..8]        (wm_0=3, wm_1..5=1)
  col 6 (center):       wv_6 = wm_6 * maxsum[w[6]][7..8]        (wm_6=3)   -- REQUIRED > 0 (feasibility)
Main proxy (bingo, x3 at masked cols 0 & 6 => WM=9; x2 letter at masked col 3):
  WM=9; main = WM*( sum_{x in 0..6} v_x*lm_x  +  sum_{x in 7..12} v_x ) + 50

Usage:  python experiments/n13_rank.py [--top 400] [--out experiments/results/n13/rank.txt]
"""
import sys, os, argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from scrabble import construct_rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=400)
    ap.add_argument('--out', default='experiments/results/n13/rank.txt')
    a = ap.parse_args()

    r = construct_rules('dutch', '13')
    W = r.W
    val = {chr(ord('a') + i - 1): r.scores[i] for i in range(1, 27)}
    wm0 = [int(x) for x in r.word_multiplier[0]]
    lm0 = [int(x) for x in r.letter_multiplier[0]]
    mask = list(range(7))                      # left-edge scoring block {0..6}
    WM = 1
    for x in mask:
        WM *= wm0[x]                            # = 9 (cols 0 and 6 are x3)

    def sv(word):
        return sum(val[c] for c in word)

    # one pass over the lexicon: vertical maxsum buckets (by first letter) + collect 13-letter mains
    maxsum_short = defaultdict(int)   # len 2..8
    maxsum_long = defaultdict(int)    # len 7..8 (center col)
    mains = []
    for w in r.words_str:
        l = len(w)
        if l == 13:
            mains.append(w)
        if 2 <= l <= 8:
            s = sv(w)
            c0 = w[0]
            if s > maxsum_short[c0]:
                maxsum_short[c0] = s
            if 7 <= l <= 8 and s > maxsum_long[c0]:
                maxsum_long[c0] = s
    sys.stderr.write(f"lexicon scanned: {len(mains)} 13-letter mains; "
                     f"{len(maxsum_short)} short-vert letters, {len(maxsum_long)} long-vert letters\n")
    _skip_note = []

    from collections import Counter
    counts = {int(k): int(v) for k, v in r.counts.items()}   # letter-index -> bag count
    nblank = int(r.blank_count)

    def idx(c):
        return ord(c) - ord('a') + 1

    ranked = []
    skipped_bag = 0
    for w in mains:
        # center feasibility: col 6 must admit a length 7-8 vertical
        c6 = w[6]
        if maxsum_long[c6] == 0:
            continue
        # BAG feasibility of the main word: its own letters must come from bag + blanks.
        # (verticals/bridges need MORE tiles, so this is a necessary-not-sufficient prefilter that
        #  still removes the q/x/y/z-heavy words that are LE-0-nodes=1 infeasible.)
        dem = Counter(idx(c) for c in w)
        shortfall = sum(max(0, n - counts.get(li, 0)) for li, n in dem.items())
        if shortfall > nblank:
            skipped_bag += 1
            continue
        # main proxy
        main = WM * (sum(val[w[x]] * lm0[x] for x in range(7)) + sum(val[w[x]] for x in range(7, 13))) + 50
        # BAG-AWARE vertical proxy: the verticals' stub tiles come from the bag REMAINING after the
        # main word draws its letters (blanks cover the main shortfall first). Assign the best
        # remaining tiles to the x3 columns (0 and center-6) first, then the x1 columns -- an
        # optimistic multiple-choice tile-knapsack that correctly penalises words which spend all the
        # rare high-value tiles on the main word (leaving nothing for verticals).
        rem = dict(counts)
        bl = nblank
        for c in w:
            li = idx(c)
            if rem.get(li, 0) > 0:
                rem[li] -= 1
            else:
                bl -= 1                                       # main consumed a blank (shortfall<=nblank)
        tiles = []
        for li, n in rem.items():
            tiles.extend([r.scores[li]] * n)
        tiles.sort(reverse=True)
        # x3 cols 0 & 6: up to 7 stub cells each (len<=8); x1 cols 1..5: up to 7 stubs each.
        v3 = sum(tiles[:14])                                  # best 14 tiles -> the two x3 columns
        v1 = sum(tiles[14:14 + 35])                           # next tiles -> the five x1 columns
        vert = 3 * v3 + 1 * v1
        ranked.append((main + vert, main, vert, w))

    ranked.sort(reverse=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        f.write(f"# N=13 left-block {{0..6}} candidate ranking  (optimistic total = main + vert)\n")
        f.write(f"# WM={WM} wm0={wm0} lm0={lm0}\n")
        f.write(f"# {'opt_total':>9} {'main':>6} {'vert':>6}  word\n")
        for tot, main, vert, w in ranked[:a.top]:
            f.write(f"{tot:>11} {main:>6} {vert:>6}  {w}\n")
    print(f"wrote {a.out}: {len(ranked)} bag+center-feasible candidates "
          f"({skipped_bag} mains skipped: letters exceed bag+{nblank} blanks), top {a.top} saved")
    for tot, main, vert, w in ranked[:25]:
        print(f"  opt={tot:>6} main={main:>5} vert={vert:>5}  {w}")


if __name__ == '__main__':
    main()
