"""PARALLEL per-combo oracle driver for the N=15 geschenkcheques {3,11} masks.   (v2, 2026-07-02)

v2 SOUNDNESS OVERHAUL (three holes found+fixed 2026-07-02; v1 ledgers are QUARANTINED):
  1. CONTENT-KEYED ledger.  The old positional combo id was PYTHONHASHSEED-NONDETERMINISTIC
     across processes (proven: same 81872-combo band, different id->combo mapping under different
     hash seeds), so v1's id-keyed resume had coverage holes -- the mask (8,12) "all 33716 UNSAT"
     sweep is WITHDRAWN (real SAT combos with nominal 2010 exist and were missed by the holes).
     v2 keys every ledger record by combo_key (the combo's content), process-independent.
  2. BLANK-AWARE band: enumerate_above_blanks includes combos whose tails exceed the per-letter
     bag only if <=2 blanks cover the deficit (band criterion nominal - n_deficit > vfloor,
     a sound superset).  v1's enumeration missed blank-assisted combos entirely.
  3. SCORE-AWARE decision: oracle_beats_lb asks "does ANY grid with these verticals REALIZE a
     total > LB" (blanks on scored tails cost val*wm[c] realized points, constrained <= slack).
     v1 witnessed the ONE returned grid and continued if <= LB -- unsound, a different grid for
     the same combo could score higher.  In v2, SAT means "beats LB" by construction: the witness
     must confirm > LB, and a witness disagreement is a loud ERROR, never a silent continue.
     Turn-tile blanks are excluded by the 27-point argument (blanking a newly row-0 tile costs
     >= 27 > analytic_mask_UB - LB); run_mask asserts lb >= UB_TURNBLANK_FLOOR.

  Speed: oracle_beats_lb reuses a cached template model (proto CopyFrom + domain-fix pins),
  ~10x over rebuilding the model per combo (92% of v1's per-combo cost was Python model build).

PARALLELISM: many small INDEPENDENT solves.  A process pool of WORKERS processes, each running
the oracle with CPSAT_WORKERS=1.  Combos are dispatched DESCENDING by nominal gross; the first
SAT (witnessed > LB) raises the LB, which shrinks every mask's band.

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

# turn-blank exclusion floor: analytic per-mask UB is 2030 (N15_ADJACENT_UB.md); a turn-blank
# board scores <= UB - 27, so for lb >= 2004 no turn-blank board can beat lb.
UB_ANALYTIC = 2030
UB_TURNBLANK_FLOOR = UB_ANALYTIC - 26


# ---------------------------------------------------------------------------
# Worker: decide a single combo.  Runs in a child process; CPSAT_WORKERS=1.
# ---------------------------------------------------------------------------
def _worker_init(word, mask, vfloor, cap, basefile=None, bcols=None):
    global _W, _MASK, _VF, _CAP, _PIN, _BCOLS, _NLE
    _W, _MASK, _VF, _CAP = word, mask, vfloor, cap
    _PIN, _BCOLS, _NLE = None, bcols, 0
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')
    if basefile and os.environ.get('ORACLE_ENGINE', 'pin') != 'cpsat':
        _PIN = _spawn_pin(basefile)
    else:
        T._oracle_template(word, mask)   # CP-SAT-only worker: build the template up front


XFILL_BIN = os.environ.get('XFILL_BIN',
                           f'{ROOT}/experiments/xfill_rs/target/release/xfill')


def _spawn_pin(basefile):
    import subprocess
    return subprocess.Popen([XFILL_BIN, '--pinbatch', basefile, '--emit'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)


def _pin_decide(key, combo):
    """One combo through the Rust engine.  Returns (verdict, grid) with verdict in
    SAT/UNSAT/TO/ERROR; grid only on SAT (reconstructed full board, row 0 = main word)."""
    toks = []
    for c in _BCOLS:
        ww = combo.get(c)
        toks.append('-' if not ww or len(ww) <= 1 else ','.join(str(x) for x in ww[1:]))
    _PIN.stdin.write(f"{key} {_VF} {' '.join(toks)}\n"); _PIN.stdin.flush()
    res = None
    board = None
    while True:
        line = _PIN.stdout.readline()
        if not line:
            return 'ERROR', None                      # engine died
        if line.startswith('RES '):
            res = line.split(None, 2)[2].strip()
            if res.startswith('MAX'):
                nxt = _PIN.stdout.readline()
                if nxt.startswith('BOARD'):
                    board = [int(x) for x in nxt.split()[2:]]
            break
    if res.startswith('LE'):
        return 'UNSAT', None
    if res.startswith('MAX'):
        mt = T.r.alphabet.to_tup(_W)
        H = W = T.W
        grid = [[0] * W for _ in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        if board and len(board) == W * H:
            for y in range(1, H):
                for x in range(W):
                    grid[y][x] = int(board[y * W + x])
        return 'SAT', grid
    if res.startswith('TO'):
        return 'TO', None
    return 'ERROR', None                              # NOCAND/BADLINE = miscoordination, loud


def _decide(arg):
    """arg = (key, gross, combo_dict).  Returns (key, gross, verdict, grid_or_None, secs, err, eng).

    Engine: Rust --pinbatch first (~ms refutations; gated by _pin_gate.py: 4000/4000 UNSAT
    agreement vs CP-SAT, TO/never-LE on the known-SAT canaries).  TO/engine-death falls back to
    the CP-SAT oracle (cap=_CAP).  Every ORACLE_AUDIT-th pin-UNSAT is double-solved by CP-SAT as
    a continuous cross-engine audit; a disagreement is a LOUD ERROR (never silently recorded)."""
    key, gross, combo = arg
    t0 = time.time()
    audit_n = int(os.environ.get('ORACLE_AUDIT', '1000'))
    global _NLE
    try:
        if _PIN is not None:
            st, grid = _pin_decide(key, combo)
            if st == 'UNSAT':
                _NLE += 1
                if audit_n and _NLE % audit_n == 0:
                    st2, _ = T.oracle_beats_lb(_W, _MASK, combo, _VF, cap=_CAP)
                    if st2 == 'SAT':
                        return (key, gross, 'ERROR', None, time.time() - t0,
                                f'AUDIT MISMATCH: pin=UNSAT cpsat=SAT key={key}', 'audit')
                return (key, gross, 'UNSAT', None, time.time() - t0, None, 'pin')
            if st == 'SAT':
                return (key, gross, 'SAT', grid, time.time() - t0, None, 'pin')
            # TO or engine trouble -> exact CP-SAT fallback
            st, grid = T.oracle_beats_lb(_W, _MASK, combo, _VF, cap=_CAP)
            return (key, gross, st, grid if st == 'SAT' else None, time.time() - t0, None,
                    'cpsat-fb')
        st, grid = T.oracle_beats_lb(_W, _MASK, combo, _VF, cap=_CAP)
        return (key, gross, st, grid if st == 'SAT' else None, time.time() - t0, None, 'cpsat')
    except Exception as e:                       # never let a worker crash kill the pool
        return (key, gross, 'ERROR', None, time.time() - t0, repr(e), '?')


def load_ledger(path):
    """Returns {combo_key: verdict}.  v2 records carry a 'key' field; any keyless (v1) record is
    IGNORED (v1 ids are not trustworthy across processes)."""
    done = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if 'key' in d:
                    done[d['key']] = d['verdict']
    return done


def run_mask(word, mask, lb, cap, workers, save=True, recheck_unknown=False,
             collect_top=50_000_000):
    mc = T.main_const(word, mask)
    vfloor = lb - mc
    ubm = int(os.environ.get('UB_MASK', UB_ANALYTIC))    # per-mask analytic UB (caller-supplied)
    assert lb >= ubm - 26, \
        f"lb {lb} < UB_mask {ubm} - 26: turn-blank exclusion fails -- use the TB-extended oracle"
    assert all(c in mask for c in (0, 7, 14)), "27-pt turn-blank argument needs the x27 main"
    avail, _ = T.build_avail(word, mask, int(os.environ.get('RESERVE', '1')))

    tag = ''.join(str(c) for c in mask)
    ledger_path = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}_v2.jsonl'
    done = load_ledger(ledger_path)

    print(f"# [v2] mask {mask} main_const={mc} vfloor={vfloor} (LB={lb})", flush=True)
    print(f"# enumerating BLANK-AWARE band (nominal - deficit > {vfloor}) ...", flush=True)
    t0 = time.time()
    res = T.enumerate_above_blanks(word, mask, avail, vfloor, blank_budget=2,
                                   collect_top=collect_top)
    if res['capped']:
        print(f"!! enumeration CAPPED (incomplete) -- cannot certify this mask", flush=True)
    combos = res['top']                      # canonical order: (-gross, combo_key)
    print(f"# {res['count']} combos in band (capped={res['capped']}), collected {len(combos)}; "
          f"enum {time.time()-t0:.0f}s; {len(done)} already in ledger", flush=True)
    if res['count'] != len(combos):
        print(f"!! count {res['count']} != collected {len(combos)} -- collect_top too small; "
              f"deciding the collected TOP slice only, verdict will be OPEN (partial coverage "
              f"is NEVER a certificate; use the streaming shard path for over-cap bands)",
              flush=True)

    # work list: skip content-keys already decided (UNSAT).  SAT would have ended the run.
    work = []
    n_unsat = n_sat = n_unknown = n_err = 0
    for gross, combo in combos:
        key = T.combo_key(combo)
        v = done.get(key)
        if v == 'UNSAT':
            n_unsat += 1; continue
        if v == 'SAT':
            n_sat += 1; continue
        if v in ('UNKNOWN', 'ERROR') and not recheck_unknown:
            if v == 'UNKNOWN': n_unknown += 1
            else: n_err += 1
            continue
        work.append((key, gross, combo))
    print(f"# ledger: {n_unsat} UNSAT, {n_sat} SAT, {n_unknown} UNKNOWN, {n_err} ERROR already; "
          f"{len(work)} to test", flush=True)

    if not work and (n_unknown or n_err) and not recheck_unknown:
        print(f"!! mask has {n_unknown+n_err} undecided (UNKNOWN/ERROR) combos -> OPEN. "
              f"re-run with --recheck to retry them at higher cap.", flush=True)
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'undecided combos remain',
                'undecided': n_unknown + n_err, 'count': res['count']}

    pidfile = f'{LEDGER_DIR}/{word}_{tag}_lb{lb}_v2.pids'
    new_lb = None; new_grid = None
    undecided = n_unknown + n_err
    t1 = time.time()
    # Rust pinbatch engine (default): build the base file once; each worker owns one child.
    basefile = bcols = None
    if os.environ.get('ORACLE_ENGINE', 'pin') != 'cpsat':
        from n15_varmax_certify import build_unit_base
        bdir = os.path.join(LEDGER_DIR, f'bases_{os.environ.get("N15_LANG", "dutch")}', word)
        os.makedirs(bdir, exist_ok=True)
        basefile, _, _ = build_unit_base(word, mask, bdir)
        bcols = [int(l.split()[1]) for l in open(basefile) if l.startswith('BCOL')]
        print(f"# engine=pinbatch base={basefile} PINWALL={os.environ.get('PINWALL', '5')}s "
              f"audit=1/{os.environ.get('ORACLE_AUDIT', '1000')}", flush=True)
    ctx = mp.get_context('spawn')
    pool = ctx.Pool(processes=workers, initializer=_worker_init,
                    initargs=(word, mask, vfloor, cap, basefile, bcols))
    try:
        pids = [p.pid for p in pool._pool]
        with open(pidfile, 'w') as pf:
            pf.write('\n'.join(str(p) for p in pids) + '\n')
    except Exception:
        pass

    tested = 0
    lf = open(ledger_path, 'a', buffering=1)
    try:
        # chunksize: ~ms pin decisions make per-item IPC the bottleneck; 32 amortizes it.  On a
        # NEW-LB break the in-flight chunks' results are lost (stay undecided) -- the follow-up
        # run at the higher LB re-decides them (known, sound; see memory note).
        chunk = 32 if basefile else 1
        for (key, gross, verdict, grid, secs, err, eng) in pool.imap_unordered(_decide, work,
                                                                              chunksize=chunk):
            tested += 1
            if verdict == 'SAT':
                # witness FIRST, then record: a witness-rejected SAT is a MODEL BUG and must land
                # in the ledger as retryable MISMATCH, never as a skip-forever SAT.
                total = mc + gross
                ok, vt, rep = T.verify_board(word, mask, grid)
                if ok and vt > lb:
                    lf.write(json.dumps({'key': key, 'gross': gross, 'verdict': 'SAT',
                                         'secs': round(secs, 1), 'witness': vt}) + '\n')
                    print(f"  *** NEW-LB *** key={key} gross(nominal)={gross} "
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
                    undecided += 1
                    fail = ('witness total ' + str(vt)) if ok else rep.get('fail')
                    lf.write(json.dumps({'key': key, 'gross': gross, 'verdict': 'MISMATCH',
                                         'secs': round(secs, 1), 'note': str(fail)}) + '\n')
                    print(f"  [MODEL-WITNESS MISMATCH] key={key} SAT but {fail} -- "
                          f"INVESTIGATE (mask stays OPEN)", flush=True)
                continue
            rec = {'key': key, 'gross': gross, 'verdict': verdict, 'secs': round(secs, 3),
                   'eng': eng}
            if err:
                rec['err'] = err
            lf.write(json.dumps(rec) + '\n')
            if verdict == 'UNKNOWN':
                undecided += 1
            elif verdict == 'ERROR':
                undecided += 1
                print(f"  [ERROR] key={key} gross={gross}: {err}", flush=True)
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

    if new_lb:
        return {'mask': mask, 'verdict': 'NEW_LB', 'new_lb': new_lb, 'count': res['count']}
    if undecided:
        print(f"!! {undecided} undecided -> mask OPEN", flush=True)
        return {'mask': mask, 'verdict': 'OPEN', 'undecided': undecided, 'count': res['count']}
    if res['count'] != len(combos):
        print(f"!! band TRUNCATED ({len(combos)} of {res['count']} tested) -> PROBE ONLY, "
              f"mask stays OPEN (re-run with --collect >= {res['count']})", flush=True)
        return {'mask': mask, 'verdict': 'OPEN', 'reason': 'band truncated (collect_top)',
                'count': res['count'], 'tested_band': len(combos)}
    print(f"mask {mask} at LB={lb}: {res['count']} band combos ALL SAFE (no grid beats {lb})",
          flush=True)
    print(f"VERDICT: CERTIFIED <= {lb}", flush=True)
    return {'mask': mask, 'verdict': 'CERTIFIED', 'lb': lb, 'count': res['count']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', default='geschenkcheques')
    ap.add_argument('--mask', required=True, help='comma cols, e.g. 0,3,7,8,11,12,14')
    ap.add_argument('--lb', type=int, required=True)
    ap.add_argument('--cap', type=float, default=1200.0)
    ap.add_argument('--workers', type=int, default=20)
    ap.add_argument('--recheck', action='store_true')
    ap.add_argument('--nosave', action='store_true')
    ap.add_argument('--collect', type=int, default=50_000_000,
                    help='collect_top for the band enum; must be >= band count to certify')
    a = ap.parse_args()
    mask = tuple(int(x) for x in a.mask.split(','))
    os.environ.setdefault('RESERVE', '1')
    print(f"# [v2] word={a.word} mask={mask} LB={a.lb} reserve={os.environ['RESERVE']} "
          f"cap={a.cap} workers={a.workers}", flush=True)
    out = run_mask(a.word, mask, a.lb, a.cap, a.workers, save=not a.nosave,
                   recheck_unknown=a.recheck, collect_top=a.collect)
    print(json.dumps({**out, 'mask': list(out['mask'])}), flush=True)


if __name__ == '__main__':
    main()
