"""LANE B: decide the TURN-BLANK-relevant slice of a fat mask (combos with nominal - penaltyLB
> LB + 27 - mc) with the TB-complete oracle (oracle_beats_lb_tb).  Together with the lane-A
stream certification (standard oracle = all non-TB boards over the full band), this closes the
mask under FULL rules: any board, blanks anywhere.

Ledger: content-keyed JSONL (laneB_<tag>_lb<lb>.jsonl); resumable.  SAT -> witness -> new LB.
Usage: N15_LANG=dutch2026 N15_HMAX=15 python n15_laneB_tb.py --mask 0,3,7,9,11,13,14 --lb 2100
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import multiprocessing as mp

ROOT = '/home/bob/programming/scrabble4'
LEDGER_DIR = f'{ROOT}/experiments/results/oracle_parallel'
WORD = os.environ.get('N15_WORD', 'geschenkcheques')


def _init(word, mask, vfloor, cap):
    global _T, _W, _MASK, _VF, _CAP
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')
    import n15_twolevel as T
    _T, _W, _MASK, _VF, _CAP = T, word, mask, vfloor, cap
    T._oracle_template_tb(word, mask)


def _decide(arg):
    key, gross, combo = arg
    t0 = time.time()
    try:
        st, grid = _T.oracle_beats_lb_tb(_W, _MASK, combo, _VF, cap=_CAP)
    except Exception as e:
        return key, gross, 'ERROR', None, time.time() - t0, repr(e)
    return key, gross, st, grid if st == 'SAT' else None, time.time() - t0, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mask', required=True)
    ap.add_argument('--lb', type=int, required=True)
    ap.add_argument('--workers', type=int, default=20)
    ap.add_argument('--cap', type=float, default=1200.0)
    a = ap.parse_args()
    mask = tuple(int(x) for x in a.mask.split(','))
    os.environ.setdefault('RESERVE', '1')
    import n15_twolevel as T
    mc = T.main_const(WORD, mask)
    vfloor = a.lb - mc                       # lane-A floor; TB lane uses +27
    tag = ''.join(str(c) for c in mask)
    ledger_path = f'{LEDGER_DIR}/laneB_{tag}_lb{a.lb}.jsonl'
    done = {}
    if os.path.exists(ledger_path):
        for line in open(ledger_path):
            try:
                d = json.loads(line)
                done[d['key']] = d['verdict']
            except Exception:
                pass
    print(f"# laneB mask={mask} lb={a.lb} TB-floor nominal-pen > {vfloor + 27}; "
          f"{len(done)} in ledger", flush=True)
    avail, _ = T.build_avail(WORD, mask, 1)
    res = T.enumerate_above_blanks(WORD, mask, avail, vfloor + 27, collect_top=5_000_000)
    assert not res['capped'] and res['count'] == len(res['top'])
    work = []
    for gross, combo in res['top']:
        key = T.combo_key(combo)
        if done.get(key) != 'UNSAT':
            work.append((key, gross, combo))
    print(f"# band {res['count']}; {len(work)} to decide", flush=True)
    und = 0
    new_lb = None
    lf = open(ledger_path, 'a', buffering=1)
    ctx = mp.get_context('spawn')
    t0 = time.time()
    with ctx.Pool(processes=a.workers, initializer=_init,
                  initargs=(WORD, mask, vfloor, a.cap)) as pool:
        n = 0
        for key, gross, st, grid, secs, err in pool.imap_unordered(_decide, work, chunksize=1):
            n += 1
            rec = {'key': key, 'gross': gross, 'verdict': st, 'secs': round(secs, 2), 'eng': 'tb'}
            if err:
                rec['err'] = err
            lf.write(json.dumps(rec) + '\n')
            if st == 'SAT':
                ok, vt, rep = T.verify_board(WORD, mask, grid)
                print(f"  TB-SAT key={key} witness ok={ok} vt={vt}", flush=True)
                if ok and vt > a.lb:
                    blob = {'board': T.B, 'main_word': WORD,
                            'turn_str': ''.join(ch.upper() if i in set(mask) else ch.lower()
                                                for i, ch in enumerate(WORD)),
                            'require_center': True, 'claimed_total': vt, 'grid': grid}
                    json.dump(blob, open(f'{ROOT}/experiments/results/turns/N15_best_{vt}.json', 'w'))
                    print(f"  *** NEW LB {vt} ***", flush=True)
                    new_lb = vt
                    break
                und += 1                      # witness-rejected SAT: investigate, stay OPEN
            elif st != 'UNSAT':
                und += 1
            if n % 500 == 0:
                r = n / (time.time() - t0)
                print(f"  {n}/{len(work)} ({r:.1f}/s, ~{(len(work)-n)/max(r,1e-9)/3600:.1f}h) "
                      f"und={und}", flush=True)
    if new_lb:
        print(f"VERDICT: NEW_LB {new_lb}", flush=True)
    elif und:
        print(f"VERDICT: OPEN ({und} undecided)", flush=True)
    else:
        print(f"VERDICT: laneB mask {mask} CERTIFIED <= {a.lb} ({res['count']} TB-slice combos)",
              flush=True)


if __name__ == '__main__':
    main()
