"""N=15 ANALYTIC sound certification on the BIGGER Dutch lexicon (data/words/dutch_bigger_le15).

Same sound argument as experiments/n15_analytic_certify.py, threaded through the bigger word list:

For a 15-letter main word M placed on row 0 with a legal size-7 newly mask m (contains {0,7,14}),
    total(M, m, board) = main_const(M, m) + sum_{c in m} vert_gross(c, board)
and for any LEGAL board   vert_gross(c) <= G(c, M[c]) := max legal vertical "M[c]+tail" gross over
run-lengths 1..HMAX (l=1 = bare tile = 0).  So
    UB(M, m) = main_const(M, m) + sum_{c in m} G(c, M[c])  >=  any achievable total with main M, mask m.
If max over legal masks of UB(M, m) <= LB, M is CERTIFIED <= LB (no search).  The UB ignores tile
contention, blanks, connectivity, reserve and the center constraint (all only LOWER the score), so
it is a SOUND over-estimate.

EFFICIENCY: G(c, letter) depends only on the column c (its word/letter multipliers) and the row-0
letter, NOT on the word.  We precompute G[c][code] for all 15 columns x 26 letters ONCE (scanning
the <=HMAX dictionary slice), then UB for every 15-letter word is a cheap per-mask sum.  This makes
the sweep over all ~605k bigger 15-letter words fast.

Legal masks: size-7, contain {0,7,14}, and every maximal pre-placed (lowercase) row-0 run >=2 spells
a dict word (necessary board-legality condition).
"""
import sys, os, argparse, time
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from itertools import combinations
from scrabble import construct_rules, get_word_score

ROOT = '/home/bob/programming/scrabble4'
B = '15'; W = H = 15; HMAX = 8
WORD_FILE = os.environ.get('N15_WORD_FILE', 'data/words/dutch_bigger_le15')

print(f"# loading rules (word_file={WORD_FILE}) ...", flush=True)
_t0 = time.time()
r = construct_rules('dutch', B, word_file=WORD_FILE)
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
print(f"# loaded {len(r.words)} words in {time.time()-_t0:.1f}s", flush=True)


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


# ---- precompute G[c][code] = max legal vertical gross at col c for row-0 letter `code` ----
# A vertical at col c is a dict word ww with ww[0]==code, 2<=len(ww)<=HMAX, ww[1:] a dict word.
# Gross = get_word_score with placed=[i==0...] at col c (only the row-0 tile gets board multipliers).
def build_G():
    cba = r.alphabet.cba
    lk = r.words_lookup
    # raw per-letter best: max over words of (val(top)+sum(tail)) is mult-dependent, so compute the
    # actual gross at each scoring col directly (15 cols).  But the score at a col c for a vertical
    # ww is wm[c]*(lm[c]*val(top) + sum(tail)).  So per top-letter we need:
    #   tailmax[top] = max over legal ww (len 2..HMAX, ww[1:] a word) of sum(tail values)
    # and l=1 contributes 0.  Then G(c, top) = wm[c]*(lm[c]*val(top) + tailmax[top]) if a >=2 vert
    # exists for top, else 0 (but a bare tile is l=1 -> 0, and wm[c]*lm[c]*val(top) alone is NOT a
    # legal play: a single placed tile below row 0 is just the tile, no cross-word, score 0).
    # IMPORTANT: the row-0 tile's contribution is only scored when a vertical of len>=2 exists.
    tailmax = {}
    has_vert = {}
    for ww in r.words:
        if len(ww) < 2 or len(ww) > HMAX:
            continue
        if ww[1:] not in lk:
            continue
        top = ww[0]
        tv = sum(int(r.scores[c]) for c in ww[1:])
        if tv > tailmax.get(top, -1):
            tailmax[top] = tv
        has_vert[top] = True
    G = [[0] * 27 for _ in range(W)]
    for c in range(W):
        for code in range(1, 27):
            if code in tailmax:
                topval = int(r.scores[code])
                G[c][code] = wm[c] * (lm[c] * topval + tailmax[code])
    return G, tailmax


print("# building per-column vertical-gross table G[c][letter] ...", flush=True)
_t1 = time.time()
G, TAILMAX = build_G()
print(f"# built G in {time.time()-_t1:.1f}s; letters with a legal >=2 vertical: {len(TAILMAX)}", flush=True)


def _pre_runs_legal(w, mask):
    wl = r.words_lookup; cba = r.alphabet.cba
    preset = set(range(W)) - set(mask)
    x = 0
    while x < W:
        if x not in preset:
            x += 1; continue
        x2 = x
        while x2 < W and x2 in preset:
            x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in wl:
            return False
        x = x2
    return True


_FREE = [c for c in range(W) if c not in (0, 7, 14)]
_EXTRAS = list(combinations(_FREE, 4))   # all C(12,4)=495 ways to pick the 4 extra newly cols
_BASE_WORDMULT = 27                      # word mult on the 3 fixed TWS cols 0/7/14


def unconstrained_ub(w):
    """Fast SOUND upper bound on max_mask UB(w, mask) IGNORING mask legality (legality can only
    remove masks, never raise UB).  Base = the always-in cols {0,7,14}; then add the 4 free cols
    with the highest marginal value (vertical G plus the x2-letter main bonus at cols 3/11).  This
    over-estimates the true legal max, so unconstrained_ub <= LB  =>  word CERTIFIED without any
    mask-legality enumeration."""
    wcodes = r.alphabet.to_tup(w)
    # base main_const for mask exactly {0,7,14}: WM=27, only cols 0/7/14 are 'newly' (lm at 3/11 not
    # captured since 3,11 not in this base) -> all letters x1, three TWS letters get the x27 word mult.
    base = _BASE_WORDMULT * sum(val[w[x]] for x in range(W)) + 50
    base += G[0][wcodes[0]] + G[7][wcodes[7]] + G[14][wcodes[14]]
    margins = []
    for c in _FREE:
        m = G[c][wcodes[c]]
        if c in (3, 11):
            m += _BASE_WORDMULT * val[w[c]]      # x2-letter bonus: adds 27*val once when newly
        margins.append(m)
    margins.sort(reverse=True)
    return base + sum(margins[:4])


def word_ub(w):
    """Max over LEGAL size-7 masks of UB(w, mask).  Returns (max_ub, argmax_mask) or (None, None)
    if no legal mask exists.  Enumerates all 495 masks (only called for words whose unconstrained UB
    already exceeds LB)."""
    wcodes = r.alphabet.to_tup(w)
    best_ub = -1; best_m = None; any_legal = False
    for extra in _EXTRAS:
        mask = tuple(sorted((0, 7, 14) + extra))
        if not _pre_runs_legal(w, mask):
            continue
        any_legal = True
        ub = main_const(w, mask)
        for c in mask:
            ub += G[c][wcodes[c]]
        if ub > best_ub:
            best_ub = ub; best_m = mask
    if not any_legal:
        return None, None
    return best_ub, best_m


def sweep(lb, words):
    openw = []
    cert = 0; unplay = 0; n = 0; fast_cert = 0
    t0 = time.time()
    for w in words:
        n += 1
        # FAST PREFILTER: unconstrained UB (ignores mask legality) is a sound over-estimate; if it
        # is <= LB the word is CERTIFIED with no per-mask enumeration.  Only the rare words above the
        # bound pay for the legal-mask enumeration.
        if unconstrained_ub(w) <= lb:
            cert += 1; fast_cert += 1
            if n % 100000 == 0:
                print(f"  ... {n} words, open={len(openw)} cert={cert} ({time.time()-t0:.0f}s)", flush=True)
            continue
        ub, m = word_ub(w)
        if ub is None:
            unplay += 1
            continue
        if ub > lb:
            openw.append((w, ub, m))
        else:
            cert += 1
        if n % 100000 == 0:
            print(f"  ... {n} words, open={len(openw)} cert={cert} unplay={unplay} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    print(f"  (fast-prefilter certified {fast_cert} of {cert} without mask enumeration)", flush=True)
    openw.sort(key=lambda t: -t[1])
    print(f"=== ANALYTIC SWEEP @ LB={lb} ===", flush=True)
    print(f"total 15-letter words scanned: {n}", flush=True)
    print(f"CERTIFIED (UB<=LB): {cert}", flush=True)
    print(f"UNPLAYABLE (no legal x27 mask): {unplay}", flush=True)
    print(f"OPEN (UB>LB): {len(openw)}", flush=True)
    for w, ub, m in openw:
        print(f"  OPEN {w}: UB={ub} mask={list(m)} (slack {ub-lb})", flush=True)
    return openw


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=2050)
    ap.add_argument('--words', type=str, default='', help='comma list; default = ALL 15-letter words')
    ap.add_argument('--out', type=str, default=f'{ROOT}/experiments/results/n15_bigger_open.txt')
    a = ap.parse_args()
    if a.words:
        ws = a.words.split(',')
    else:
        ws = [w for w in r.words_str if len(w) == 15]
        print(f"# sweeping ALL {len(ws)} 15-letter words", flush=True)
    openw = sweep(a.lb, ws)
    with open(a.out, 'w') as fp:
        fp.write(f"# analytic OPEN set @ LB={a.lb} (word_file={WORD_FILE})\n")
        for w, ub, m in openw:
            fp.write(f"{w}\t{ub}\t{','.join(map(str,m))}\n")
    print(f"# wrote open set -> {a.out}", flush=True)
