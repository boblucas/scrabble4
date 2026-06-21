"""PARALLEL per-combo oracle driver for the N=15 geschenkcheques {3,11} masks.

Reuses the EXACT, sound machinery in n15_twolevel.py:
  - enumerate_above_fast(...collect_top=BIG): COMPLETE, bag-constrained enumeration of every combo
    whose total vertical gross > vfloor (= LB - main_const).  The suffix-gross UB never discards a
    feasible higher-gross combo, so the generated set is exhaustive (soundness req (a)).
  - oracle_feasible(word, mask, combo, cap): EXACT CP-SAT feasibility (full row+col <=HMAX legality,
    flow-to-center, bag/blank/reserve, verticals FIXED, connectors allowed below).  Returns
    'SAT' / 'UNSAT' (proven INFEASIBLE) / 'UNKNOWN' (wall timeout).  A combo counts as infeasible
    ONLY on proven UNSAT; UNKNOWN keeps the mask OPEN (soundness req (b)).
  - verify_board(...): the FIXED witness_check (require_center=True, reserve via scaled bag).  Any
    board claimed as a NEW LB must pass this with ok=True.

PARALLELISM: many small INDEPENDENT solves.  A process pool of WORKERS processes, each running
oracle_feasible with CPSAT_WORKERS=1 (one CP-SAT thread per solve), so WORKERS solves run
concurrently.  Combos are dispatched DESCENDING by gross; the first SAT whose witnessed total > LB
raises the LB (saved board), which shrinks every mask's band.

RESUMABLE: each combo has a stable integer id (its rank in the descending-gross enumeration).  A
JSONL ledger records {id, gross, verdict} per decided combo; a restart skips decided ids.

KILL SAFETY: only the pool's own child PIDs are ever terminated (recorded in a pidfile); no group
kills, no pgrep/xargs -P.
"""
import sys, os, json, time, argparse, signal
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import multiprocessing as mp
from collections import Counter

import n15_twolevel as T

ROOT = '/home/bob/programming/scrabble4'
LEDGER_DIR = f'{ROOT}/experiments/results/oracle_parallel'
os.makedirs(LEDGER_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Worker: decide a single combo.  Runs in a child process; CPSAT_WORKERS=1.
# ---------------------------------------------------------------------------
def _worker_init(word, mask, cap):
    global _W, _MASK, _CAP
    _W, _MASK, _CAP = word, mask, cap
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')


def _decide(arg):
    """arg = (cid, gross, combo_dict).  Returns (cid, gross, verdict, grid_or_None, secs)."""
    cid, gross, combo = arg
    t0 = time.time()
    try:
        st, grid = T.oracle_feasible(_W, _MASK, combo, cap=_CAP)
    except Exception as e:                       # never let a worker crash kill the pool
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


def run_mask(word, mask, lb, cap, workers, save=True, recheck_unknown=False):
    mc = T.main_const(word, mask)
    vfloor = lb - mc
    avail, _ = T.build_avail(word, mask, int(os.environ.get('RESERVE', '1')))

    tag = ''.join(str(c) for c in mask)
    ledger_path = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}.jsonl'
    done = load_ledger(ledger_path)

    print(f"# mask {mask} main_const={mc} vfloor={vfloor} (LB={lb})", flush=True)
    print(f"# enumerating combos (total gross > {vfloor}) ...", flush=True)
    t0 = time.time()
    # collect_top huge -> collect ALL above-vfloor combos (complete).  count first reported.
    res = T.enumerate_above_fast(word, mask, avail, vfloor, collect_top=50_000_000)
    if res['capped']:
        print(f"!! enumeration CAPPED (incomplete) -- cannot certify this mask", flush=True)
    combos = res['top']                      # sorted desc by gross, list of (gross, combo_dict)
    print(f"# {res['count']} combos>vfloor (capped={res['capped']}), collected {len(combos)}; "
          f"enum {time.time()-t0:.0f}s; {len(done)} already in ledger", flush=True)
    if res['count'] != len(combos):
        print(f"!! WARNING: count {res['count']} != collected {len(combos)} -- collect_top too small",
              flush=True)

    # build work list: skip ids already UNSAT/SAT-decided (resume).  If recheck_unknown, redo UNKNOWN/ERROR.
    work = []
    n_unsat = n_sat = n_unknown = n_err = 0
    for cid, (gross, combo) in enumerate(combos):
        v = done.get(cid)
        if v == 'UNSAT':
            n_unsat += 1; continue
        if v == 'SAT':
            n_sat += 1
            # a previously-found SAT below LB: keep skipping (already handled); above-LB would have stopped run
            continue
        if v in ('UNKNOWN', 'ERROR') and not recheck_unknown:
            (n_unknown if v == 'UNKNOWN' else n_err)
            if v == 'UNKNOWN': n_unknown += 1
            else: n_err += 1
            continue
        work.append((cid, gross, combo))
    print(f"# ledger: {n_unsat} UNSAT, {n_sat} SAT, {n_unknown} UNKNOWN, {n_err} ERROR already; "
          f"{len(work)} to test", flush=True)

    if not work and (n_unknown or n_err) and not recheck_unknown:
        print(f"!! mask has {n_unknown+n_err} undecided (UNKNOWN/ERROR) combos -> OPEN. "
              f"re-run with --recheck to retry them at higher cap.", flush=True)
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'undecided combos remain',
                'undecided': n_unknown + n_err, 'count': res['count']}

    pidfile = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}.pids'
    new_lb = None; new_grid = None
    undecided = n_unknown + n_err
    t1 = time.time()
    ctx = mp.get_context('spawn')
    pool = ctx.Pool(processes=workers, initializer=_worker_init, initargs=(word, mask, cap))
    # record child pids for safe targeted cleanup
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
            if verdict == 'UNKNOWN':
                undecided += 1
            elif verdict == 'ERROR':
                undecided += 1
                print(f"  [ERROR] cid={cid} gross={gross}: {err}", flush=True)
            elif verdict == 'SAT':
                total = mc + gross
                ok, vt, rep = T.verify_board(word, mask, grid)
                if ok and vt > lb:
                    print(f"  *** NEW-LB *** cid={cid} gross={gross} total(model)={total} "
                          f"witness={vt} > LB {lb}", flush=True)
                    new_lb = vt; new_grid = grid
                    if save:
                        turn = ''.join(ch.upper() if i in set(mask) else ch.lower()
                                       for i, ch in enumerate(word))
                        blob = {'board': T.B, 'main_word': word, 'turn_str': turn,
                                'require_center': True, 'claimed_total': vt, 'grid': grid}
                        path = f'{ROOT}/experiments/results/turns/N15_best_{vt}.json'
                        json.dump(blob, open(path, 'w'))
                        print(f"      saved {path}", flush=True)
                    break                    # stop the band: LB rises, re-enumerate needed
                else:
                    fail = ('witness total ' + str(vt)) if ok else rep.get('fail')
                    print(f"  cid={cid} gross={gross} SAT but {fail} (not > LB) -> continue",
                          flush=True)
            if tested % 200 == 0:
                rate = tested / (time.time() - t1)
                rem = len(work) - tested
                print(f"  ... {tested}/{len(work)} tested ({rate:.2f}/s, ~{rem/max(rate,1e-9)/3600:.1f}h "
                      f"left); undecided={undecided}", flush=True)
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
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'undecided (UNKNOWN/ERROR) combos',
                'undecided': undecided, 'tested': tested, 'count': res['count']}
    if res['capped']:
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'enumeration capped', 'tested': tested}
    return {'mask': mask, 'verdict': 'CERTIFIED', 'tested': tested, 'count': res['count'],
            'bag_ub_total': mc + (combos[0][0] if combos else 0)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', default='geschenkcheques')
    ap.add_argument('--mask', default='0,3,7,8,11,12,14',
                    help='comma-separated newly columns, or "all" for all {3,11} masks')
    ap.add_argument('--lb', type=int, default=2007)
    ap.add_argument('--reserve', type=int, default=1)
    ap.add_argument('--cap', type=float, default=120.0, help='CP-SAT wall per oracle solve (s)')
    ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--recheck', action='store_true', help='retry UNKNOWN/ERROR combos in ledger')
    ap.add_argument('--nosave', action='store_true')
    a = ap.parse_args()
    os.environ['RESERVE'] = str(a.reserve)
    os.environ['LB'] = str(a.lb)

    if a.mask == 'all':
        from n15_greedy_lb import candidate_masks
        ms = candidate_masks(a.word, limit=500)
        masks = [m for m in ms if 3 in m and 11 in m]
    else:
        masks = [tuple(int(x) for x in a.mask.split(','))]

    print(f"# word={a.word} masks={masks} LB={a.lb} reserve={a.reserve} cap={a.cap} "
          f"workers={a.workers}", flush=True)
    summary = []
    lb = a.lb
    for m in masks:
        res = run_mask(a.word, m, lb, a.cap, a.workers, save=not a.nosave, recheck_unknown=a.recheck)
        print(f"=== mask {m}: {res['verdict']} {res}", flush=True)
        summary.append((m, res))
        if res['verdict'] == 'NEW-LB':
            lb = res['total']
            print(f"### LB RAISED to {lb}; remaining masks will use the higher floor (re-enumerated)",
                  flush=True)
    print("=== SUMMARY ===", flush=True)
    for m, res in summary:
        print(f"  mask {m}: {res['verdict']} {res}", flush=True)
    print(f"=== final LB = {lb}", flush=True)
