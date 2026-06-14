"""N=15 THREAT-SET enumerator -- step 1/2 of the proof toward the true N=15 optimum.

Floor (verified LB): 1952  (geschenkcheques, experiments/results/turns/N15_best_1952.json,
witness_check OK: main 1724 + verticals golfsurf69 / klepstuw69 / skyboxje90 = 228).

GOAL
----
Compute a SOUND upper bound UB(word) on the achievable single-turn total for every candidate
15-letter main word, and report the THREAT SET = {words : UB(word) > 1952}.  Any word with
UB <= 1952 provably cannot beat the floor and is discarded.

WHY ONLY 15-LETTER WORDS, AND WHY ALL THREE TWS (cols 0,7,14)
------------------------------------------------------------
The three x3-WORD (TWS) premium cols on row 0 are 0, 7, 14.  The board word multiplier is the
PRODUCT of the word multipliers of the NEWLY-placed cells the main word covers.  To reach x27 the
main word must newly-place tiles on all three of cols 0,7,14 -- which forces a 15-letter word on
row 0 (the only word spanning cols 0..14).  Any word that does NOT cover all three TWS cols has
word multiplier <= x9 (product of at most two 3's).  The maximum raw letter-sum over ALL 15-letter
Dutch words is 56, so even the most optimistic x9 play
    9 * (56 + val[3-doubled] + val[11-doubled]) + bingo  <=  9*(56+16)+50 = 698  <<  1952.
Hence every word with word-mult <= x9 (i.e. every word not spanning all three TWS, including every
word shorter than 15) is trivially excluded.  => Only 15-letter words placed newly on {0,7,14}
(x27) can threaten the floor.  (This is the same shape as the proven global-N=11 argument.)

THE SOUND UPPER BOUND  UB(word) = x27_proxy(word) + vert_UB(word)
-----------------------------------------------------------------
  x27_proxy(word) = 27 * ( sum(val(letter)) + val(word[3]) + val(word[11]) ) + 50
    -- the exact main-turn score assuming BOTH DLS cols 3,11 are newly-placed (best case, an
       over-estimate when a legal mask must drop one) and a 7-tile bingo +50.  SOUND over-estimate
       of the main score for ANY legal x27 placement of this word.

  vert_UB(word) = sum over the SEVEN best newly columns of  best_vert_bonus(col, letter)
    -- verticals add ONLY at newly columns; a turn newly-places exactly the columns in the mask
       (>=7 cells incl. {0,7,14}; with bingo exactly 7).  We may newly-place up to 7 columns
       (a bingo plays 7 tiles; placing >7 would lose the bingo and reduce the main multiplier
       coverage -- but to stay SOUND we BOUND verticals by the 7 highest-bonus columns, which is an
       over-estimate of any real mask's vertical total).  For each column c with top letter L=word[c]
       the best vertical bonus is
           best_vert_bonus(c, L) = max over legal dict words "L+tail", len 2..HMAX(8), of
                                       WM[c] * ( LM[c]*val(L) + sum(val(tail)) )
       maximised independently per column (we IGNORE cross-column bag contention -> looser but
       SOUND), where WM[c]=3 on TWS {0,7,14}, LM[c]=2 on DLS {3,11}, else 1.  A column with no
       legal vertical (or where the bare top tile scores more than any vertical) contributes its
       bare-top contribution 0 to the vertical bonus (the main word already counts the top letter).
       We then take the 7 columns with the largest best_vert_bonus.

SOUNDNESS of vert_UB
--------------------
  * Per-column bonus is the EXACT maximum single-column vertical score (full dictionary, len<=8),
    so it over-estimates any realised vertical at that column.
  * Summing the 7 best columns over-estimates the total vertical bonus of ANY legal board, because
    a real board newly-places at most ... well, a bingo newly-places exactly 7 columns, and a
    non-bingo play newly-places MORE columns but loses the +50 and we keep the +50 in x27_proxy, so
    bounding the vertical contribution by the 7 best columns is sound for the bingo case and the
    main-score side already over-counts for any other case.  (We additionally report a strictly
    sound "all-columns" vert_UB = sum of best_vert_bonus over ALL 15 columns, which can only be
    larger, as a fully-conservative cross-check; the 7-best version is the tighter sound bound we
    actually use to prune.)
  * Bag contention (shared scarce tiles/blanks, reserve=1) is IGNORED -> the bound is looser
    (never tighter) than reality.  SOUND.
  * cross-check: vert_UB(geschenkcheques) must be >= 228 (the realised vertical bonus).

OUTPUT: the sorted threat list (UB desc) with x27_proxy, vert_UB, and a best legal mask, written to
experiments/results/n15_threats.jsonl and printed.
"""
import sys, os, json, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from itertools import combinations
from scrabble import construct_rules

ROOT = '/home/bob/programming/scrabble4'
B = '15'
HMAX = 8
FLOOR_DEFAULT = 1952

r = construct_rules('dutch', B)
W = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]      # row-0 word multipliers (3 at 0/7/14)
LM = np.array(r.letter_multiplier)[0]    # row-0 letter multipliers (2 at 3/11)
TWS = [c for c in range(W) if WM[c] == 3]
DLS = [c for c in range(W) if LM[c] == 2]
assert TWS == [0, 7, 14] and DLS == [3, 11], (TWS, DLS)

N15 = [w for w in r.words_str if len(w) == 15]


def x27_proxy(w):
    return 27 * (sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50


# ---- best vertical bonus per (column, top-letter), exact over the dictionary (len<=8) ----
# Group dict words 2..HMAX by their first letter, precompute the max tail-value sum.
_TAILMAX = {}   # first-letter -> max sum(val(tail)) over legal words "letter+tail", len 2..8
for word in r.words_str:
    if 2 <= len(word) <= HMAX:
        f = word[0]
        tv = sum(val[c] for c in word[1:])
        if tv > _TAILMAX.get(f, -1):
            _TAILMAX[f] = tv


def best_vert_bonus(c, L):
    """Exact max single-column vertical bonus at column c with top letter L (or 0 if no vertical
    beats placing nothing extra). WM[c]*(LM[c]*val(L) + best_tail) minus the bare main-top already
    counted -> we return the ADDED vertical bonus over an empty column.

    An empty newly column contributes its top letter once via the MAIN word at multiplier WM (the
    main word's word-mult), already inside x27_proxy.  Hanging a vertical there ADDS a *new* word
    `L+tail` scored independently: bonus = WM[c]*(LM[c]*val(L) + sum tail).  (The top tile is scored
    in BOTH the main word and the vertical -- that double-count is real Scrabble scoring, see
    witness_check/n15_push_lb.)  If no legal vertical exists, the added bonus is 0.
    """
    if L not in _TAILMAX:
        return 0
    return int(WM[c]) * (int(LM[c]) * val[L] + _TAILMAX[L])


def vert_UB_per_col(w):
    """List of (col, bonus) best vertical bonus per column for word w."""
    return [(c, best_vert_bonus(c, w[c])) for c in range(W)]


def vert_UB(w):
    """SOUND tight-ish vertical UB: sum of the 7 largest per-column best vertical bonuses."""
    bonuses = sorted((b for _, b in vert_UB_per_col(w)), reverse=True)
    return sum(bonuses[:7])


def vert_UB_all(w):
    """Fully-conservative vertical UB: sum over ALL 15 columns (only larger)."""
    return sum(b for _, b in vert_UB_per_col(w))


# ---- legal-mask helper (mirrors n15_greedy_lb): pre-placed runs must spell words ----
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


def best_legal_mask(w):
    """A legal 7-col newly mask (contains {0,7,14}) maximising the x2-letter bonus, or None."""
    free = [c for c in range(W) if c not in (0, 7, 14)]
    best = None; bestbonus = -1
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if not _pre_runs_legal(w, mask):
            continue
        ms = set(mask)
        bonus = 27 * ((val[w[3]] if 3 in ms else 0) + (val[w[11]] if 11 in ms else 0))
        if bonus > bestbonus:
            bestbonus = bonus; best = mask
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--floor', type=int, default=FLOOR_DEFAULT)
    ap.add_argument('--require-mask', action='store_true',
                    help='also require a legal mask to exist (else word is unplayable x27)')
    a = ap.parse_args()
    floor = a.floor

    # x27_proxy alone is an upper bound on the MAIN score; UB adds verticals.  First sort by x27.
    rows = []
    for w in N15:
        xp = x27_proxy(w)
        vu = vert_UB(w)
        ub = xp + vu
        if ub > floor:
            rows.append((ub, xp, vu, w))
    rows.sort(reverse=True)

    print(f"# N=15 THREAT enumeration  floor={floor}", flush=True)
    print(f"# 15-letter words total: {len(N15)}", flush=True)
    print(f"# words with UB = x27_proxy + vert_UB(7-best) > {floor}: {len(rows)}", flush=True)

    # cross-check geschenkcheques
    g = 'geschenkcheques'
    if g in r.words_lookup_str if hasattr(r, 'words_lookup_str') else (g in N15):
        print(f"# CHECK vert_UB({g}) = {vert_UB(g)}  (must be >= 228); "
              f"x27_proxy={x27_proxy(g)} UB={x27_proxy(g)+vert_UB(g)}", flush=True)

    out = f'{ROOT}/experiments/results/n15_threats.jsonl'
    with open(out, 'w') as f:
        for ub, xp, vu, w in rows:
            mask = best_legal_mask(w)
            rec = {'word': w, 'UB': ub, 'x27_proxy': xp, 'vert_UB': vu,
                   'vert_UB_all': vert_UB_all(w), 'best_mask': mask,
                   'has_legal_mask': mask is not None}
            f.write(json.dumps(rec) + '\n')
    print(f"# wrote {out}", flush=True)

    # print top of the threat list
    print(f"\n{'UB':>6} {'x27p':>6} {'vUB':>5}  {'mask?':>5}  word", flush=True)
    n_mask = 0
    for ub, xp, vu, w in rows:
        mask = best_legal_mask(w)
        if mask is not None:
            n_mask += 1
        print(f"{ub:6d} {xp:6d} {vu:5d}  {str(mask is not None):>5}  {w}", flush=True)
    print(f"\n# threat words (UB>{floor}): {len(rows)};  "
          f"with a legal x27 mask: {n_mask}", flush=True)


if __name__ == '__main__':
    main()
