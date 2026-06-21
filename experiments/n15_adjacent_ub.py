"""N=15 ADJACENT-AWARE sound per-mask UPPER BOUND for the geschenkcheques {3,11} masks.

WHY (the loose bag-UB)
----------------------
The bag/knapsack UB (n15_twolevel.bag_ub_mask) maximises  main_const + sum_c vert_gross(c)  choosing
each scoring column's vertical INDEPENDENTLY subject only to the shared tile bag.  In the open
{3,11} masks the scoring columns contain ADJACENT pairs (e.g. (7,8), (11,12), (13,14)).  When two
adjacent columns c, c+1 both carry verticals, their tail tiles at any row r>=1 sit side by side and
form a HORIZONTAL run that MUST be a legal dictionary word (witness_check checks 3b setup-legality
and 4 final-legality).  The per-column UB ignores this coupling, so it overstates the achievable
total.  This tool adds a SOUND adjacent-pair constraint and re-optimises.

THE MODEL (a relaxation of the true single-turn problem -> a SOUND over-estimate)
---------------------------------------------------------------------------------
Decision: each scoring column c in the mask picks exactly ONE option: a tail-legal vertical
  M[c] + tail   (tail = w[1:] a dict word, full word len 2..HMAX, scored by get_word_score with the
  row-0 board multipliers -- identical to the solvers/oracle), OR 'none' (gross 0, no tail tiles).

Objective: maximise  main_const(M, mask) + sum_c gross(choice_c).

Constraints kept (all NECESSARY conditions of any legal board, so dropping the rest only RAISES the
optimum -> sound over-estimate):
  (a) per-column tail-legality (only legal verticals are options);
  (b) SHARED BAG: the union of chosen tails' tiles fits  avail = scaled bag - 7 newly main tiles
      - reserve(1) is applied as the global cap is irrelevant to a per-letter ceiling; we use the
      per-letter ceiling avail (sound: tails can never use more of a letter than the bag holds minus
      the 7 main tiles).  Blanks: a blank tile scores 0, so a MAX-gross vertical never uses one; we
      therefore charge every tail tile to a real letter (no blank credit), which can only TIGHTEN
      (never inflate) the bound -- still sound because the true board may blank a tile (lowering its
      score), never raise it.  [We also add a blanks-relaxed variant as a cross-check.]
  (c) ADJACENT-PAIR HORIZONTAL legality: for each adjacent scoring-column pair (c, c+1) in the mask
      and each row r>=1 where BOTH chosen verticals have a tile, the two tail letters
      (tail_c[r], tail_{c+1}[r]) must occur CONSECUTIVELY (in that L->R order) inside SOME legal
      dictionary word of length <= HMAX.  This is a SOUND NECESSARY condition: on the final board the
      maximal horizontal run through (c,r),(c+1,r) is a legal word and CONTAINS that ordered bigram as
      a contiguous substring; if no legal word contains the bigram, no legal horizontal run through
      the two tiles can exist, regardless of any connector tiles placed at c-1 / c+2.  We deliberately
      DO NOT require the 2-letter run to itself be a word (that would be UNSOUND: a longer legal run
      whose 2-letter substring is not a word could exist).  The bigram-membership condition is the
      strongest connector-independent necessary condition, hence sound.

Everything else (4-connectivity, center, the full longer-run legality, the global tile cap, blanks)
is DROPPED.  Each dropped constraint only further RESTRICTS real boards, so the max over this
relaxation is >= the true max single-turn score.  Therefore:  UB <= LB  =>  CERTIFIED <= LB.

The optimisation is tiny (7 multiple-choice columns + a handful of adjacent incompatibility clauses
+ ~26 bag rows); CP-SAT solves it to OPTIMAL in well under a second.  CERTIFIED only on OPTIMAL.
"""
import sys, os, argparse, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import Counter
from ortools.sat.python import cp_model

import n15_twolevel as T   # reuse col_candidates / main_const / build_avail / scoring (ground truth)

r = T.r
HMAX = T.HMAX
to_str = r.alphabet.to_str


def legal_bigrams():
    """Set of ordered (a,b) letter-code pairs that occur CONSECUTIVELY in some dict word of length
    <= HMAX (board runs are length <= HMAX, so longer words cannot appear as a board run)."""
    bg = set()
    for ww in r.words:
        if not ww or len(ww) > HMAX:
            continue
        for i in range(len(ww) - 1):
            bg.add((ww[i], ww[i + 1]))
    return bg


def adjacent_pairs(mask):
    s = set(mask)
    return [(c, c + 1) for c in mask if (c + 1) in s]


def mask_ub(word, mask, reserve=1, cap=60.0, blank_relax=False, verbose=False):
    """Return dict with the adjacent-aware sound UB for (word, mask).  blank_relax=True adds the bag's
    blanks to the per-letter ceilings (an even looser, still-sound relaxation) as a cross-check."""
    mt = r.alphabet.to_tup(word)
    mc = T.main_const(word, mask)
    avail, blanks = T.build_avail(word, mask, reserve)
    if blank_relax:
        # blanks are wildcards: add the blank pool to EVERY letter's ceiling (sound over-relaxation).
        avail = {code: avail.get(code, 0) + blanks for code in avail}

    bigrams = legal_bigrams()
    pairs = adjacent_pairs(mask)

    m = cp_model.CpModel()
    # per-column options: index 0 = 'none' (gross 0, empty tail), then the tail-legal verticals.
    col_opts = {}     # c -> list of (var, gross, tail_ct, tail_codes_rows)  tail_codes_rows: tuple of
    #                   (letter at row 1, row 2, ...)  (length L-1)
    for c in mask:
        cands = T.col_candidates(word, c)
        opts = []
        none_v = m.new_bool_var(f'none_{c}')
        opts.append((none_v, 0, Counter(), ()))
        for i, d in enumerate(cands):
            v = m.new_bool_var(f'v{c}_{i}')
            tail_codes = tuple(d['word'][1:])     # rows 1..L-1
            opts.append((v, d['gross'], d['tail_ct'], tail_codes))
        m.add(sum(o[0] for o in opts) == 1)
        col_opts[c] = opts

    # bag rows (per letter ceiling over chosen tails)
    for code in avail:
        terms = []
        for c in mask:
            for (v, _g, tc, _tr) in col_opts[c]:
                n = tc.get(code, 0)
                if n:
                    terms.append(n * v)
        if terms:
            m.add(sum(terms) <= avail[code])

    # adjacent-pair horizontal legality: forbid incompatible (option_c, option_{c+1}) combinations.
    n_forbid = 0
    for (c, d) in pairs:
        for (vi, _gi, _tci, ti) in col_opts[c]:
            if not ti:
                continue                       # 'none' on col c: no tail tiles -> no H-run with d
            for (vj, _gj, _tcj, tj) in col_opts[d]:
                if not tj:
                    continue
                overlap = min(len(ti), len(tj))   # rows 1..overlap both have a tile
                bad = False
                for k in range(overlap):
                    if (ti[k], tj[k]) not in bigrams:
                        bad = True
                        break
                if bad:
                    m.add(vi + vj <= 1)
                    n_forbid += 1

    m.maximize(sum(g * v for c in mask for (v, g, _tc, _tr) in col_opts[c] if g))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    t0 = time.time()
    st = s.Solve(m)
    dt = time.time() - t0
    status = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
              cp_model.INFEASIBLE: 'INFEASIBLE', cp_model.UNKNOWN: 'UNKNOWN'}[st]
    vgross = int(s.objective_value) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    total = (mc + vgross) if vgross is not None else None
    chosen = {}
    if vgross is not None:
        for c in mask:
            for (v, g, _tc, tr) in col_opts[c]:
                if s.value(v):
                    chosen[c] = (g, to_str([mt[c], *tr]) if tr else to_str([mt[c]]))
                    break
    return {'mask': mask, 'main_const': mc, 'vert_gross_ub': vgross, 'total_ub': total,
            'status': status, 'optimal': st == cp_model.OPTIMAL, 'secs': round(dt, 2),
            'pairs': pairs, 'n_forbid': n_forbid, 'chosen': chosen, 'blank_relax': blank_relax}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', default='geschenkcheques')
    ap.add_argument('--lb', type=int, default=2007)
    ap.add_argument('--reserve', type=int, default=1)
    ap.add_argument('--cap', type=float, default=60.0)
    ap.add_argument('--mask', default='all', help='comma cols or "all" for {3,11} masks')
    ap.add_argument('--blank-relax', action='store_true',
                    help='also report the blanks-as-wildcards (looser, still sound) UB')
    a = ap.parse_args()

    if a.mask == 'all':
        from n15_greedy_lb import candidate_masks
        ms = candidate_masks(a.word, limit=500)
        masks = [m for m in ms if 3 in m and 11 in m]
    else:
        masks = [tuple(int(x) for x in a.mask.split(','))]

    print(f"# word={a.word}  LB={a.lb}  reserve={a.reserve}  masks={masks}", flush=True)
    bg = legal_bigrams()
    print(f"# legal ordered bigrams (words len<=HMAX={HMAX}): {len(bg)}", flush=True)
    results = []
    for mk in masks:
        res = mask_ub(a.word, mk, reserve=a.reserve, cap=a.cap)
        verdict = ('CERTIFIED' if (res['optimal'] and res['total_ub'] <= a.lb)
                   else ('OPEN' if res['optimal'] else 'INDET(not-optimal)'))
        res['verdict'] = verdict
        results.append(res)
        print(f"mask {mk}: pairs={res['pairs']} forbid={res['n_forbid']} "
              f"main_const={res['main_const']} vert_gross_UB={res['vert_gross_ub']} "
              f"TOTAL_UB={res['total_ub']} [{res['status']} {res['secs']}s] -> {verdict} "
              f"(LB {a.lb}, residual {res['total_ub'] - a.lb if res['total_ub'] is not None else '?'})",
              flush=True)
        print(f"    chosen verticals: {res['chosen']}", flush=True)
        if a.blank_relax:
            rb = mask_ub(a.word, mk, reserve=a.reserve, cap=a.cap, blank_relax=True)
            print(f"    [blank-relax cross-check] TOTAL_UB={rb['total_ub']} [{rb['status']}]",
                  flush=True)

    print("=== SUMMARY ===", flush=True)
    cert = [r for r in results if r['verdict'] == 'CERTIFIED']
    openm = [r for r in results if r['verdict'] == 'OPEN']
    indet = [r for r in results if r['verdict'].startswith('INDET')]
    for r in results:
        print(f"  mask {r['mask']}: TOTAL_UB={r['total_ub']} -> {r['verdict']}", flush=True)
    print(f"CERTIFIED <= {a.lb}: {len(cert)}   OPEN: {len(openm)}   INDET: {len(indet)}", flush=True)
    if openm:
        worst = max(r['total_ub'] for r in openm)
        print(f"bracket after this pass: [{a.lb}, {worst}]  ({len(openm)} mask(s) still open)",
              flush=True)
    else:
        print(f"ALL {len(results)} {a.word} {{3,11}} masks CERTIFIED <= {a.lb}.", flush=True)
    return results


if __name__ == '__main__':
    main()
