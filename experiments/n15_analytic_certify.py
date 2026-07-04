"""N=15 ANALYTIC sound certification: true single-turn max <= LB for a threat word.

THE ARGUMENT (sound, no search)
-------------------------------
For a 15-letter main word M placed on row 0 with newly-tile column mask m (m contains the three
TWS cols {0,7,14} => x27; a bingo plays exactly 7 newly cols):

    total(M, m, board) = main_const(M, m)  +  sum over c in m of vert_gross(c, board)

where vert_gross(c, .) is the vertical cross-word score at newly col c.  A vertical at col c is a
dictionary word  M[c] + tail  whose RUN LENGTH L satisfies 2 <= L <= HMAX (=8): a board run longer
than HMAX is ILLEGAL (no >HMAX word is in the legal dictionary), so L > 8 verticals cannot occur.
For each (c, L<=8) let best_gross(c, L) be the MAX score of any legal vertical  M[c]+tail  of length
L (stub = tail a dict word; row-0 tile gets the col's word multiplier).  Then for ANY legal board,

    vert_gross(c) <= max over 1<=L<=8 of best_gross(c, L)  =: G(c)        (l=1 => bare tile, 0)

so   total(M, m, .) <= main_const(M, m) + sum_{c in m} G(c)  =: UB(M, m).

This UB IGNORES tile contention, blanks, connectivity, the reserve and the center constraint
(all of which only LOWER the achievable score), so it is a SOUND over-estimate.  If
    max over all LEGAL masks m of UB(M, m) <= LB
then no legal turn with main word M scores above LB: M is CERTIFIED <= LB.

This is exactly 35_certify.enumerate_band's optimistic per-column-best UB, with vertical lengths
correctly capped at HMAX (the full-H band that 35_certify enumerates is a superset that also lists
infeasible L>8 vectors; capping at HMAX is the realizable set).  An empty HMAX-capped band == this
UB <= LB.

We re-derive best_gross INDEPENDENTLY from rules.words (not from any solver state) and recompute
main_const from the multiplier rows, so the certificate stands on its own.  Legal masks are the
size-7 masks containing {0,7,14} whose pre-placed row-0 runs (>=2) all spell dict words
(necessary board-legality condition; n15_greedy_lb._pre_runs_legal).

SCOPE / honesty: this certifies the BINGO masks (size-7, the +50 case), which carry the maximum
main score and the threat UB; non-bingo masks (>7 newly) lose the +50 from main_const while adding
the same per-column verticals, so their UB is strictly lower and is covered.  A word whose UB
EXCEEDS LB is reported OPEN (this analytic bound does not rule it out; e.g. geschenkcheques, which
actually achieves 1952).
"""
import sys, os, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from scrabble import construct_rules, get_word_score
from n15_greedy_lb import candidate_masks

ROOT = '/home/bob/programming/scrabble4'
B = '15'; W = H = 15; HMAX = int(os.environ.get("N15_HMAX", "15"))
r = construct_rules(os.environ.get('N15_LANG', 'dutch'), B)
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
CENTER_LEN = H // 2 + 1   # 8: the center column (col 7) must reach center row (7,7)


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


def best_gross_by_len(letter_code):
    """G_by_len[L] = max legal vertical score for a vertical starting with `letter_code` at a col of
    word-multiplier 1 (we apply the column wm separately).  Independent recompute from rules.words:
    stub = w[1:] must be a dict word (setup legality); length 1..HMAX; l=1 = bare tile, 0.
    We return the per-length max of (LM-free) inner score = LM[c]*val(top)+sum(tail) WITHOUT wm/LM,
    then the caller scales by the column's wm and adds the LM bonus.  Simpler: compute raw
    (val(top)+sum(tail)) per length; caller multiplies by wm and adds (LM-1)*val(top)*wm."""
    raise NotImplementedError  # replaced by per-column exact get_word_score below


def col_best_gross(w, c):
    """Exact max vertical gross at newly column c (row-0 letter w[c]), over legal verticals of
    length 1..HMAX, using the SAME scoring as the solvers (get_word_score with placed=[i==0...],
    which applies the column's board multipliers to the row-0 tile only).  l=1 => 0."""
    L = r.alphabet.cba[w[c]] if False else None
    code = r.alphabet.to_tup(w)[c]
    lk = r.words_lookup
    best = 0
    for ww in r.words:
        if not ww or ww[0] != code or len(ww) < 2 or len(ww) > HMAX:
            continue
        if ww[1:] not in lk:
            continue
        g = int(get_word_score(r, ww, c, 0, 0, [i == 0 for i in range(len(ww))])[0])
        if g > best:
            best = g
    return best                       # >=0; bare tile (l=1) contributes 0


def col_best_gross_centerlen(w, c):
    """Same as col_best_gross but the vertical must have length >= CENTER_LEN (=8) -- used only for
    the center column (col 7), whose vertical must reach the center row to satisfy connectivity.
    For col 7 the only legal length is exactly HMAX (8), so this is the max over length-8 verticals."""
    code = r.alphabet.to_tup(w)[c]
    lk = r.words_lookup
    best = 0
    for ww in r.words:
        if not ww or ww[0] != code or len(ww) < CENTER_LEN or len(ww) > HMAX:
            continue
        if ww[1:] not in lk:
            continue
        g = int(get_word_score(r, ww, c, 0, 0, [i == 0 for i in range(len(ww))])[0])
        if g > best:
            best = g
    return best


def word_ub(w):
    """Max over legal masks of UB(w, mask).  Returns (max_ub, argmax_mask, per_mask)."""
    masks = candidate_masks(w, limit=200)
    if not masks:
        return (None, None, [])
    # per-column best gross caches (independent of mask): G(c) and Gcenter(7)
    gcache = {}
    per = []
    best_ub = -1; best_m = None
    for m in masks:
        mc = main_const(w, m)
        ub = mc
        for c in m:
            # SOUND UB: take the unconstrained per-column max over lengths 1..HMAX for EVERY column
            # (including the center col 7).  The center/connectivity constraint can only LOWER the
            # achievable score, so ignoring it here is a sound over-estimate.  (We deliberately do
            # NOT force col-7 length >= 8: that would shrink the bound and risk under-counting.)
            g = gcache.get(c)
            if g is None:
                g = col_best_gross(w, c); gcache[c] = g
            ub += g
        per.append((m, mc, ub))
        if ub > best_ub:
            best_ub = ub; best_m = m
    return (best_ub, best_m, per)


def certify(words, lb):
    out = {}
    for w in words:
        ub, m, per = word_ub(w)
        if ub is None:
            print(f"{w}: NO LEGAL MASK -> unplayable x27 (excluded)", flush=True)
            out[w] = ('UNPLAYABLE', None)
            continue
        status = 'CERTIFIED' if ub <= lb else 'OPEN'
        print(f"{w}: analytic UB = {ub} (mask {m}) vs LB {lb} -> {status} "
              f"(slack {lb - ub})", flush=True)
        out[w] = (status, ub)
    print("=== SUMMARY ===", flush=True)
    cert = [w for w, (s, _) in out.items() if s == 'CERTIFIED']
    openw = [w for w, (s, _) in out.items() if s == 'OPEN']
    print(f"CERTIFIED <= {lb}: {len(cert)}  {cert}", flush=True)
    print(f"OPEN (UB > {lb}): {len(openw)}  {openw}", flush=True)
    return out


THREAT_WORDS = [
    'geschenkcheques', 'flauwekulexcuus', 'chequeformulier', 'cultuurchequeje',
    'jacquardmachine', 'bouwcuratrixjes', 'chemsexpartytje', 'chequebedragjes',
    'craqueleachtigs', 'quichebuffetjes', 'babyglimlachjes', 'cliquetsystemen',
    'wetenschapsquiz', 'schuurschijfjes', 'dyscalculischen', 'craqueleachtige',
    'textielcyclusje', 'aliquotvleugels', 'jacquardweefsel', 'yoghurtcultures',
    'upcyclestertjes', 'vluchtreflexjes', 'playboyachtigst', 'perscommuniques',
    'chiquelingetjes', 'quicheachtigers',
]

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=1952)
    ap.add_argument('--words', type=str, default='')
    a = ap.parse_args()
    ws = a.words.split(',') if a.words else THREAT_WORDS
    certify(ws, a.lb)
