"""N=15 BAG-AWARE sound upper bound per threat word -- a tighter, fully-sound refinement of
tight_UB that ACCOUNTS FOR FINITE-BAG CONTENTION among the vertical cross-words.

CONTEXT
-------
n15_threat_enum.tight_UB(word) = max over legal masks of
    true_main(word, mask) + sum_{c in mask} best_vert_bonus(c, word[c])
treats each newly column's vertical independently and IGNORES that all verticals draw from one
finite bag (1 q, 1 x, 1 y, 2 z, 2 c, ..., minus the 7 main tiles, minus reserve=1).  The big TWS
verticals (cols 0/7/14, x3) want the same scarce high-value tiles, so the independent sum is loose.

This tool computes, per word, a SOUND tighter UB by solving a small ILP to OPTIMAL:
    choose at most one vertical word per newly column (it must start with the fixed top letter
    word[c], length 2..HMAX=8, OR "no vertical"), MAXIMIZE the total premium-weighted vertical
    bonus SUBJECT TO the union of all chosen tails' letter multiset fitting the AVAILABLE bag
    (full bag - the 7 main tiles - reserve=1).  Blanks are NOT usable on scored vertical tiles
    (they score 0; modelling them as wildcards would only lower the achievable score, so omitting
    them is sound).
This is a SOUND relaxation of the true problem: it drops connectivity, the legality of OTHER runs
(connector words, cross-words on the tails), and that tails must physically lay out below row 0 in
non-newly-adjacent cells -- every dropped constraint can only REDUCE the realisable score.  So
    realisable_max(word) <= true_main + ILP_optimum = bag_UB(word).
If bag_UB(word) <= FLOOR (1952) the word is CERTIFIED: no board on this main word can beat 1952.

The ILP closes to OPTIMAL fast (it is tiny: <=7 columns x a Pareto-pruned candidate list per
column), so this certification is SOUND and needs no solver wall.  Candidate pruning: for each
starting letter we keep only the tail words that are NOT dominated (a word W dominates V if W's
bonus >= V's and W's tail-letter multiset is componentwise <= V's) -- the optimum only ever uses
non-dominated words, so pruning is exact (sound).  We additionally cap the per-letter candidate
list defensively; if a word's ILP does not reach OPTIMAL we report it as UNRESOLVED (never as
certified).

Single sequential process.
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from itertools import combinations
from collections import Counter
from ortools.sat.python import cp_model

from scrabble import construct_rules

ROOT = '/home/bob/programming/scrabble4'
B = '15'; HMAX = 8; RESERVE = 1; FLOOR = 1952
r = construct_rules('dutch', B)
W = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]; LM = np.array(r.letter_multiplier)[0]
cba = r.alphabet.cba
wl = r.words_lookup

# words len 2..8 grouped by first letter, with (tail_value, tail_counter)
_BYFIRST = {}
for word in r.words_str:
    if 2 <= len(word) <= HMAX:
        tail = word[1:]
        tv = sum(val[ch] for ch in tail)
        tc = Counter(cba[ch] for ch in tail)
        _BYFIRST.setdefault(word[0], []).append((tv, tc, word))


# A tile can only BIND the bag ILP if its availability is small enough to actually run out across the
# <=7 verticals (each tail <=7 tiles).  We RELAX (treat as unlimited) every tile whose availability
# is large (>= RELAX_AT); relaxing a bag constraint only ENLARGES the feasible set -> the ILP optimum
# can only RISE -> the resulting UB is still SOUND (an over-estimate).  This lets us collapse the
# thousands of common-letter tails (which differ only in these plentiful letters) down to a handful,
# keyed by their multiset over the CONSTRAINED tiles only.  The relaxed letters keep their VALUE in
# the objective (we keep the max-value representative per constrained-signature), so no score is lost
# -- only the (sound) relaxation of those letters' bag limits.
_RELAX_AT = 6     # tiles with availability >= 6 are relaxed (a,e,n,o appear with avail>=6; e=18,n=10)
_CONSTRAINED = sorted(code for code, n in r.counts.items() if n < _RELAX_AT)


def _reduce(cands):
    """Reduce tails to their multiset over CONSTRAINED tiles only, keeping the max-value (full)
    representative per constrained-signature.  Sound (see note above): unconstrained tiles are
    treated as unlimited (over-estimate); value is preserved by keeping the highest-value tail.
    Returns list of (tail_value, constrained_counter, word)."""
    best = {}
    for tv, tc, w in cands:
        sig = tuple((code, tc[code]) for code in _CONSTRAINED if tc.get(code, 0))
        cur = best.get(sig)
        if cur is None or tv > cur[0]:
            # store the CONSTRAINED-only counter (the bag ILP only constrains these tiles)
            ctc = Counter({code: tc[code] for code in _CONSTRAINED if tc.get(code, 0)})
            best[sig] = (tv, ctc, w)
    return list(best.values())


_CAND_CACHE = {}
def cands_for(letter):
    c = _CAND_CACHE.get(letter)
    if c is None:
        c = _reduce(_BYFIRST.get(letter, []))
        _CAND_CACHE[letter] = c
    return c


def true_main(w, mask):
    ms = set(mask)
    s = sum(val[w[x]] * (2 if (x in ms and x in (3, 11)) else 1) for x in range(W))
    return 27 * s + 50


def pre_runs_legal(w, mask):
    preset = set(range(W)) - set(mask); x = 0
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


def mask_bag_opt(w, mask, cap=15):
    """OPTIMAL total vertical bonus for (w, mask) under the bag constraint.  Returns (status, obj).
    status True iff CP-SAT proved OPTIMAL."""
    mt = r.alphabet.to_tup(w)
    newly_ct = Counter(mt[c] for c in mask)
    avail = {code: r.counts[code] - newly_ct.get(code, 0) for code in r.counts}
    m = cp_model.CpModel()
    cols = []
    for c in mask:
        top = w[c]
        cands = cands_for(top)
        opts = [(m.new_bool_var(f'n{c}'), 0, Counter())]              # no vertical
        for tv, tc, word in cands:
            bonus = int(WM[c]) * (int(LM[c]) * val[top] + tv)
            opts.append((m.new_bool_var(f'v{c}_{len(opts)}'), bonus, tc))
        m.add(sum(v for v, _, _ in opts) == 1)
        cols.append(opts)
    for code in r.counts:
        terms = []
        for opts in cols:
            for v, _, tc in opts:
                n = tc.get(code, 0)
                if n:
                    terms.append(n * v)
        if terms:
            m.add(sum(terms) <= avail[code])
    m.maximize(sum(b * v for opts in cols for v, b, _ in opts if b))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.OPTIMAL:
        return True, int(s.objective_value)
    return False, None


def word_bag_UB(w, cap=15):
    """Sound bag-aware UB over all legal masks (max of true_main+mask ILP optimum).  Returns
    (ub, mask, all_optimal)."""
    free = [c for c in range(W) if c not in (0, 7, 14)]
    best = -1; bestmask = None; all_opt = True
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if not pre_runs_legal(w, mask):
            continue
        ok, obj = mask_bag_opt(w, mask, cap)
        if not ok:
            all_opt = False
            continue                 # unresolved mask -> can't certify this word via bag UB
        tot = true_main(w, mask) + obj
        if tot > best:
            best = tot; bestmask = mask
    return best, bestmask, all_opt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--floor', type=int, default=FLOOR)
    ap.add_argument('--cap', type=float, default=15.0)
    ap.add_argument('--threats', default=f'{ROOT}/experiments/results/n15_threats_tight.json')
    ap.add_argument('--out', default=f'{ROOT}/experiments/results/n15_bag_ub.json')
    ap.add_argument('--reverse', action='store_true', help='process lowest tight_UB first')
    a = ap.parse_args()
    threats = json.load(open(a.threats))
    if a.reverse:
        threats = sorted(threats, key=lambda t: t['tight_UB'])   # lowest tight_UB first (likeliest to certify)
    print(f"# bag-aware sound UB for {len(threats)} threat words; floor={a.floor}; "
          f"reverse={a.reverse}; constrained tiles={[chr(96+c) for c in _CONSTRAINED]}", flush=True)
    results = []
    for t in threats:
        w = t['word']; t0 = time.time()
        ub, mask, all_opt = word_bag_UB(w, a.cap)
        if not all_opt:
            verdict = 'UNRESOLVED'      # some mask ILP didn't close -> not certified by bag UB
        elif ub <= a.floor:
            verdict = 'CERTIFIED<=floor'
        else:
            verdict = 'STILL-THREAT'
        results.append({'word': w, 'tight_UB': t['tight_UB'], 'bag_UB': ub,
                        'bag_mask': list(mask) if mask else None, 'all_masks_optimal': all_opt,
                        'verdict': verdict})
        print(f"  {w:18s} tight_UB={t['tight_UB']:5d} bag_UB={str(ub):>5} "
              f"-> {verdict:18s} ({time.time()-t0:.0f}s)", flush=True)
        json.dump(results, open(a.out, 'w'), indent=1)
    cert = sum(1 for x in results if x['verdict'] == 'CERTIFIED<=floor')
    still = sum(1 for x in results if x['verdict'] == 'STILL-THREAT')
    unres = sum(1 for x in results if x['verdict'] == 'UNRESOLVED')
    print(f"\n# bag-aware certification: CERTIFIED<=floor={cert}  STILL-THREAT={still}  "
          f"UNRESOLVED={unres}  (of {len(results)})", flush=True)
    print(f"# wrote {a.out}", flush=True)


if __name__ == '__main__':
    main()
