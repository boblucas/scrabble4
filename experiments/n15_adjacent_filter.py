"""N=15 ADJACENT-LEGALITY FILTERED enumeration + per-mask oracle runner for the geschenkcheques
{3,11} masks.

THE PROBLEM
-----------
enumerate_above_fast (n15_twolevel.py) chooses each scoring column's vertical INDEPENDENTLY, so for
the {3,11} masks it generates 10^5..10^7 combos with total vertical gross > vfloor (= LB - main_const).
The exact CP-SAT connectivity oracle decides each in ~5-1000s -- intractable for 3 of the 4 masks.

THE FILTER (SOUND)
------------------
In these masks the scoring columns contain ADJACENT pairs (e.g. (7,8),(11,12),(13,14)).  When two
adjacent columns c, c+1 BOTH carry verticals, at every row r>=1 where both have a tile the two tail
letters (tail_c[r], tail_{c+1}[r]) sit horizontally side by side.  On ANY legal final board the
maximal horizontal run through those two cells is a legal dictionary word of length <= HMAX, and it
CONTAINS the ordered bigram (tail_c[r], tail_{c+1}[r]) as a contiguous substring.  Hence:

    NECESSARY CONDITION (connector-independent):  for every adjacent scoring pair (c,c+1) and every
    shared row r, the ordered pair (tail_c[r], tail_{c+1}[r]) must occur consecutively in SOME legal
    word of length <= HMAX  (i.e. be a "legal bigram").

If a combo violates this for any pair/row, NO legal board can place those two verticals together
(regardless of any connector tiles at c-1 / c+2, which can only EXTEND the run, never make an absent
bigram appear).  Therefore the combo admits NO legal board and can be dropped WITHOUT testing the
oracle.  This is exactly the bigram-membership condition documented + used in n15_adjacent_ub.py; we
deliberately do NOT require the 2-letter run itself to be a word (that would be unsound -- a longer
legal run whose length-2 substring is not a word could exist).

SOUNDNESS OF CERTIFICATION
--------------------------
The filtered enumeration is COMPLETE over {combos with total gross > vfloor that satisfy the bigram
condition}.  Every combo it DROPS is provably board-infeasible (above).  Every combo it KEEPS is then
decided by the EXACT oracle (proven SAT / UNSAT; UNKNOWN keeps the mask OPEN).  So:
  * all kept combos UNSAT or SAT-witness<=LB  =>  mask CERTIFIED <= LB
    (because every combo above vfloor is either dropped-as-infeasible or oracle-decided-infeasible/<=LB);
  * a kept combo SAT with FIXED witness_check ok=True and total > LB  =>  NEW LB.
The drop set NEVER contains a feasible combo, so it cannot hide a board > LB.

CROSS-CHECKS (run by --selftest):
  * the known 2007 board's combo (mask (0,3,7,8,11,12,14)) must SURVIVE the filter;
  * every oracle-SAT combo in results/oracle_parallel/*.jsonl must SURVIVE the filter.
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import Counter
import multiprocessing as mp

import n15_twolevel as T
import n15_adjacent_ub as A

ROOT = '/home/bob/programming/scrabble4'
LEDGER_DIR = f'{ROOT}/experiments/results/adjacent_filter'
os.makedirs(LEDGER_DIR, exist_ok=True)
r = T.r
HMAX = T.HMAX


def _bigrams():
    return A.legal_bigrams()


def adjacent_pairs(mask):
    s = set(mask)
    return [(c, c + 1) for c in mask if (c + 1) in s]


def pair_ok(tail_i, tail_j, bigrams):
    """tail_i/tail_j = tuple of tail letter codes (rows 1..L-1) for adjacent cols c, c+1.
    Returns True if at every shared row the ordered bigram is legal (necessary condition)."""
    ov = min(len(tail_i), len(tail_j))
    for k in range(ov):
        if (tail_i[k], tail_j[k]) not in bigrams:
            return False
    return True


def enumerate_filtered(word, mask, avail, vfloor, bigrams, collect=True,
                       node_budget=None, time_budget=None):
    """COMPLETE, bag-constrained enumeration of combos (one tail-legal vertical or 'none' per scoring
    col) with total vertical gross > vfloor AND satisfying the adjacent-pair bigram condition.

    Identical suffix-gross + bag pruning as enumerate_above_fast (so completeness over total>vfloor is
    preserved), PLUS an incremental adjacent-pair bigram prune: when both columns of an adjacent pair
    have been assigned, the chosen tails' shared-row bigrams are checked and the branch is cut on the
    first violation.  Since the check only removes provably-infeasible combos, completeness over the
    SURVIVING set is exact.

    Columns are ordered so that for every adjacent pair both endpoints are processed (the pair is
    checked the moment the second endpoint is assigned).  We keep the descending-gmax order but record,
    per column position, the set of already-assigned partner columns of pairs it closes.

    Returns dict(count, nodes, capped, combos) where combos (if collect) = list of (gross, combo_dict).
    combo_dict maps original col -> chosen vertical WORD (codes incl row-0 tile) or None.
    """
    cols = list(mask)
    coldata = []
    for c in cols:
        cands = T.col_candidates(word, c)
        # option = (gross, tail_ct, word_or_None, tail_codes(rows1..) )
        opts = [(0, Counter(), None, ())]
        for d in cands:
            opts.append((d['gross'], d['tail_ct'], d['word'], tuple(d['word'][1:])))
        opts.sort(key=lambda o: -o[0])
        coldata.append((c, opts))
    coldata.sort(key=lambda cd: -cd[1][0][0])   # descending max gross
    order = [cd[0] for cd in coldata]
    optlists = [cd[1] for cd in coldata]
    n = len(order)
    pos = {c: i for i, c in enumerate(order)}   # column -> dfs depth index

    # for each depth k, list of (partner_depth, left_is_k) pairs to check when k is assigned.
    # an adjacent pair (a, a+1): when the LATER-in-order of {a, a+1} is assigned, check vs the earlier.
    pair_checks = [[] for _ in range(n)]
    for (a, b) in adjacent_pairs(mask):         # a<b, b=a+1, a is LEFT column
        ka, kb = pos[a], pos[b]
        later = max(ka, kb)
        earlier = min(ka, kb)
        # left column (smaller original col index) is `a`; record which depth is the left one
        left_depth = ka                          # a is the left horizontal letter
        pair_checks[later].append((earlier, left_depth))

    sufmax = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        sufmax[k] = sufmax[k + 1] + optlists[k][0][0]
    bud = Counter(avail)
    state = {'count': 0, 'nodes': 0, 'capped': False}
    pick = [None] * n          # pick[k] = (word_or_None, tail_codes) chosen at depth k
    combos = [] if collect else None
    t0 = time.time()

    def dfs(k, cur):
        state['nodes'] += 1
        if node_budget and state['nodes'] >= node_budget:
            state['capped'] = True; return
        if time_budget and (state['nodes'] & 0x3FFFF) == 0 and time.time() - t0 > time_budget:
            state['capped'] = True; return
        if cur + sufmax[k] <= vfloor:
            return
        if k == n:
            state['count'] += 1
            if collect:
                combo = {order[i]: pick[i][0] for i in range(n)}
                combos.append((cur, combo))
            return
        for (g, tc, ww, tcodes) in optlists[k]:
            if cur + g + sufmax[k + 1] <= vfloor:
                break
            ok = True
            for code, q in tc.items():
                if bud[code] < q:
                    ok = False; break
            if not ok:
                continue
            # adjacent-pair bigram check: this depth k may close pairs with earlier depths
            bad = False
            for (earlier_depth, left_depth) in pair_checks[k]:
                etail = pick[earlier_depth][1]
                if not tcodes or not etail:
                    continue                     # one side 'none' -> no horizontal pair forced
                if left_depth == k:
                    li, lj = tcodes, etail       # k is the LEFT column
                else:
                    li, lj = etail, tcodes       # earlier is the LEFT column
                if not pair_ok(li, lj, bigrams):
                    bad = True; break
            if bad:
                continue
            for code, q in tc.items():
                bud[code] -= q
            pick[k] = (ww, tcodes)
            dfs(k + 1, cur + g)
            for code, q in tc.items():
                bud[code] += q
            if state['capped']:
                return

    sys.setrecursionlimit(100000)
    dfs(0, 0)
    if collect:
        combos.sort(key=lambda x: -x[0])
    return {'count': state['count'], 'nodes': state['nodes'], 'capped': state['capped'],
            'combos': combos, 'order': order}


# ---------------------------------------------------------------------------
# Parallel oracle over the surviving (filtered) combos.
# ---------------------------------------------------------------------------
def _worker_init(word, mask, cap):
    global _W, _MASK, _CAP
    _W, _MASK, _CAP = word, mask, cap
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')


def _decide(arg):
    cid, gross, combo = arg
    t0 = time.time()
    try:
        st, grid = T.oracle_feasible(_W, _MASK, combo, cap=_CAP)
    except Exception as e:
        return (cid, gross, 'ERROR', None, time.time() - t0, repr(e))
    return (cid, gross, st, grid if st == 'SAT' else None, time.time() - t0, None)


def load_ledger(path):
    done = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    done[d['id']] = d['verdict']
                except Exception:
                    pass
    return done


def run_mask(word, mask, lb, cap, workers, reserve=1, save=True, recheck=False,
             time_budget=None):
    mc = T.main_const(word, mask)
    vfloor = lb - mc
    avail, _ = T.build_avail(word, mask, reserve)
    bigrams = _bigrams()
    tag = ''.join(str(c) for c in mask)
    ledger_path = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}.jsonl'
    done = load_ledger(ledger_path)

    print(f"# mask {mask} main_const={mc} vfloor={vfloor} (LB={lb}) reserve={reserve}", flush=True)
    print(f"# pairs={adjacent_pairs(mask)}  legal_bigrams={len(bigrams)}", flush=True)
    print(f"# enumerating (filtered) combos total gross > {vfloor} ...", flush=True)
    t0 = time.time()
    res = enumerate_filtered(word, mask, avail, vfloor, bigrams, collect=True,
                             time_budget=time_budget)
    combos = res['combos']
    capped = res['capped']
    print(f"# SURVIVING combos>vfloor (adjacent-legal) = {res['count']} "
          f"(capped={capped}); enum {time.time()-t0:.0f}s, {res['nodes']} nodes; "
          f"{len(done)} in ledger", flush=True)
    if capped:
        print("!! enumeration CAPPED (incomplete) -- cannot certify", flush=True)

    work = []
    n_unsat = n_sat = n_unknown = n_err = 0
    for cid, (gross, combo) in enumerate(combos):
        v = done.get(cid)
        if v == 'UNSAT':
            n_unsat += 1; continue
        if v == 'SAT':
            n_sat += 1; continue
        if v in ('UNKNOWN', 'ERROR') and not recheck:
            if v == 'UNKNOWN':
                n_unknown += 1
            else:
                n_err += 1
            continue
        work.append((cid, gross, combo))
    print(f"# ledger: {n_unsat} UNSAT, {n_sat} SAT, {n_unknown} UNKNOWN, {n_err} ERROR; "
          f"{len(work)} to test", flush=True)

    if not work and (n_unknown or n_err) and not recheck:
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'undecided combos remain',
                'undecided': n_unknown + n_err, 'count': res['count'], 'capped': capped}

    undecided = n_unknown + n_err
    new_lb = None; new_grid = None
    pidfile = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}.pids'
    if not work:
        if capped:
            return {'mask': mask, 'verdict': 'OPEN', 'reason': 'enum capped', 'count': res['count']}
        return {'mask': mask, 'verdict': 'CERTIFIED', 'tested': 0, 'count': res['count'],
                'survivors': res['count']}

    t1 = time.time()
    ctx = mp.get_context('spawn')
    pool = ctx.Pool(processes=workers, initializer=_worker_init, initargs=(word, mask, cap))
    try:
        pids = [p.pid for p in pool._pool]
        with open(pidfile, 'w') as pf:
            pf.write('\n'.join(str(p) for p in pids) + '\n')
    except Exception:
        pass

    tested = 0
    lf = open(ledger_path, 'a', buffering=1)
    try:
        for (cid, gross, verdict, grid, secs, err) in pool.imap_unordered(_decide, work, chunksize=1):
            tested += 1
            rec = {'id': cid, 'gross': gross, 'verdict': verdict, 'secs': round(secs, 1)}
            if err:
                rec['err'] = err
            lf.write(json.dumps(rec) + '\n')
            if verdict in ('UNKNOWN', 'ERROR'):
                undecided += 1
                if verdict == 'ERROR':
                    print(f"  [ERROR] cid={cid} gross={gross}: {err}", flush=True)
            elif verdict == 'SAT':
                total = mc + gross
                ok, vt, rep = T.verify_board(word, mask, grid)
                if ok and vt > lb:
                    print(f"  *** NEW-LB *** cid={cid} gross={gross} witness={vt} > LB {lb}",
                          flush=True)
                    new_lb = vt; new_grid = grid
                    if save:
                        turn = ''.join(ch.upper() if i in set(mask) else ch.lower()
                                       for i, ch in enumerate(word))
                        blob = {'board': T.B, 'main_word': word, 'turn_str': turn,
                                'require_center': True, 'claimed_total': vt, 'grid': grid}
                        path = f'{ROOT}/experiments/results/turns/N15_best_{vt}.json'
                        json.dump(blob, open(path, 'w'))
                        print(f"      saved {path}", flush=True)
                    break
                else:
                    fail = ('witness total ' + str(vt)) if ok else rep.get('fail')
                    print(f"  cid={cid} gross={gross} SAT but {fail} (<=LB) -> continue", flush=True)
            if tested % 50 == 0:
                rate = tested / (time.time() - t1)
                rem = len(work) - tested
                print(f"  ... {tested}/{len(work)} ({rate:.2f}/s, ~{rem/max(rate,1e-9)/3600:.2f}h); "
                      f"undecided={undecided}", flush=True)
    finally:
        pool.terminate()
        pool.join()
        lf.close()
        try:
            os.remove(pidfile)
        except OSError:
            pass

    if new_lb is not None:
        return {'mask': mask, 'verdict': 'NEW-LB', 'total': new_lb, 'tested': tested,
                'count': res['count']}
    if undecided:
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'undecided combos', 'undecided': undecided,
                'tested': tested, 'count': res['count']}
    if capped:
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'enum capped', 'tested': tested}
    return {'mask': mask, 'verdict': 'CERTIFIED', 'tested': tested, 'count': res['count'],
            'survivors': res['count']}


# ---------------------------------------------------------------------------
# Self-test: filter must NOT reject the 2007 board nor any oracle-SAT combo.
# ---------------------------------------------------------------------------
def combo_survives(word, mask, combo, bigrams):
    """combo: dict col->word(codes) or None. Return True iff all adjacent pairs satisfy bigram cond."""
    for (a, b) in adjacent_pairs(mask):
        wa = combo.get(a); wb = combo.get(b)
        if wa is None or wb is None:
            continue
        ta = tuple(wa[1:]); tb = tuple(wb[1:])
        if not pair_ok(ta, tb, bigrams):
            return False
    return True


def selftest():
    bigrams = _bigrams()
    ok_all = True
    # 1) 2007 board combo
    g = json.load(open(f'{ROOT}/experiments/results/turns/N15_best_2007.json'))['grid']
    mask = (0, 3, 7, 8, 11, 12, 14)
    combo = {}
    for c in mask:
        col = [g[y][c] for y in range(15)]
        L = 0
        for y in range(15):
            if col[y] == 0:
                break
            L = y + 1
        combo[c] = tuple(col[:L]) if L >= 2 else None
    surv = combo_survives('geschenkcheques', mask, combo, bigrams)
    print(f"[selftest] 2007 board combo survives filter: {surv}", flush=True)
    ok_all &= surv

    # 2) every oracle-SAT combo from the running oracle's ledger must survive.
    op_dir = f'{ROOT}/experiments/results/oracle_parallel'
    for fn in os.listdir(op_dir):
        if not fn.endswith('.jsonl'):
            continue
        # reconstruct that mask's combo enumeration to map id->combo
        parts = fn[:-6].split('_')          # word_tag_lbXXXX
        word = parts[0]
        tag = parts[1]
        mask_o = tuple(int(ch) for ch in _split_tag(tag))
        lb_o = int(parts[2][2:])
        sat_ids = []
        with open(f'{op_dir}/{fn}') as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('verdict') == 'SAT':
                    sat_ids.append(d['id'])
        if not sat_ids:
            continue
        # rebuild the UNFILTERED enumeration (same order/ids the oracle used)
        mc = T.main_const(word, mask_o); vfloor = lb_o - mc
        avail, _ = T.build_avail(word, mask_o, 1)
        ufres = T.enumerate_above_fast(word, mask_o, avail, vfloor, collect_top=50_000_000)
        idmap = {i: combo for i, (gr, combo) in enumerate(ufres['top'])}
        nbad = 0
        for sid in sat_ids:
            combo = idmap.get(sid)
            if combo is None:
                print(f"[selftest] WARNING id {sid} not in enumeration for {fn}", flush=True)
                continue
            if not combo_survives(word, mask_o, combo, bigrams):
                nbad += 1
                print(f"[selftest] !!! oracle-SAT id {sid} ({fn}) REJECTED by filter -- UNSOUND",
                      flush=True)
        print(f"[selftest] {fn}: {len(sat_ids)} SAT combos, {nbad} wrongly rejected", flush=True)
        ok_all &= (nbad == 0)
    print(f"[selftest] {'PASS' if ok_all else 'FAIL'}", flush=True)
    return ok_all


def _split_tag(tag):
    """Map a concatenated column tag like '0378111214' back to the columns of a known {3,11} mask."""
    from n15_greedy_lb import candidate_masks
    ms = candidate_masks('geschenkcheques', limit=500)
    both = [m for m in ms if 3 in m and 11 in m]
    for m in both:
        if ''.join(str(c) for c in m) == tag:
            return [str(c) for c in m]
    # fallback: greedy single/double digit parse won't be needed for our tags
    raise ValueError(f'unknown tag {tag}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', default='geschenkcheques')
    ap.add_argument('--mask', default='all')
    ap.add_argument('--lb', type=int, default=2007)
    ap.add_argument('--reserve', type=int, default=1)
    ap.add_argument('--cap', type=float, default=120.0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--mode', default='count', choices=['count', 'selftest', 'oracle'])
    ap.add_argument('--recheck', action='store_true')
    ap.add_argument('--tbudget', type=float, default=0.0)
    a = ap.parse_args()
    os.environ['RESERVE'] = str(a.reserve)
    os.environ['LB'] = str(a.lb)
    tb = a.tbudget or None

    if a.mode == 'selftest':
        selftest()
        sys.exit(0)

    if a.mask == 'all':
        from n15_greedy_lb import candidate_masks
        ms = candidate_masks(a.word, limit=500)
        masks = [m for m in ms if 3 in m and 11 in m]
    else:
        masks = [tuple(int(x) for x in a.mask.split(','))]

    bigrams = _bigrams()
    print(f"# word={a.word} masks={masks} LB={a.lb} reserve={a.reserve} mode={a.mode}", flush=True)
    summary = []
    lb = a.lb
    for m in masks:
        mc = T.main_const(a.word, m); vfloor = lb - mc
        avail, _ = T.build_avail(a.word, m, a.reserve)
        if a.mode == 'count':
            t0 = time.time()
            res = enumerate_filtered(a.word, m, avail, vfloor, bigrams, collect=False, time_budget=tb)
            # also the unfiltered count for comparison (cap by node/time budget if huge)
            print(f"mask {m} pairs={adjacent_pairs(m)} vfloor={vfloor}: "
                  f"SURVIVING={res['count']} (capped={res['capped']}, {res['nodes']} nodes, "
                  f"{time.time()-t0:.0f}s)", flush=True)
            summary.append((m, res['count'], res['capped']))
        elif a.mode == 'oracle':
            res = run_mask(a.word, m, lb, a.cap, a.workers, reserve=a.reserve, recheck=a.recheck,
                           time_budget=tb)
            print(f"=== mask {m}: {res['verdict']} {res}", flush=True)
            summary.append((m, res))
            if isinstance(res, dict) and res.get('verdict') == 'NEW-LB':
                lb = res['total']
                print(f"### LB RAISED to {lb}", flush=True)
    print("=== SUMMARY ===", flush=True)
    for row in summary:
        print(f"  {row}", flush=True)
