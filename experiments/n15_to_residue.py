"""Parallel CP-SAT afwikkeling van ladder-TO-residu.  SAT -> witness -> bord opslaan.
Usage: N15_LANG=... N15_HMAX=15 python n15_to_residue.py <word> <mask_csv> <ladder_dir> <floor...>
Ledger: <ladder_dir>/to_residue.jsonl (content-keyed, resumable)."""
import sys, os, json, glob, gzip, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import multiprocessing as mp

WORD = sys.argv[1]
MASK = tuple(int(x) for x in sys.argv[2].split(','))
D = sys.argv[3]
FLOORS = [int(x) for x in sys.argv[4:]]
WORKERS = int(os.environ.get('RES_WORKERS', '12'))


def _init():
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')
    import n15_twolevel as T
    global _T
    _T = T
    T._oracle_template(WORD, MASK)


def _decide(arg):
    key, floor = arg
    combo = {}
    for part in key.split('|'):
        c, w = part.split(':')
        combo[int(c)] = None if w == '-' else tuple(ord(ch) - 96 for ch in w)
    t0 = time.time()
    try:
        st, grid = _T.oracle_beats_lb(WORD, MASK, combo, floor, cap=float(os.environ.get("RES_CAP", "1200")))
    except Exception as e:
        return key, floor, 'ERROR', repr(e), time.time() - t0, None
    return key, floor, st, None, time.time() - t0, grid if st == 'SAT' else None


def main():
    done = {}
    lp = f'{D}/to_residue.jsonl'
    if os.path.exists(lp):
        for line in open(lp):
            try:
                d = json.loads(line)
                done[d['key']] = d['verdict']
            except Exception:
                pass
    work = []
    for fl in FLOORS:
        for vf in glob.glob(f'{D}/f{fl}/verdict_*.txt') + glob.glob(f'{D}/f{fl}/verdict_*.txt.gz'):
            op = gzip.open if vf.endswith('.gz') else open
            for line in op(vf, 'rt'):
                if line.startswith('RES ') and ' TO ' in line:
                    k = line.split()[1]
                    if done.get(k) not in ('UNSAT', 'SAT'):
                        work.append((k, fl))
    print(f"# {len(work)} TO-combos te beslissen ({len(done)} in ledger)", flush=True)
    import n15_twolevel as T
    lf = open(lp, 'a', buffering=1)
    und = 0
    best = None
    ctx = mp.get_context('spawn')
    t0 = time.time()
    with ctx.Pool(processes=WORKERS, initializer=_init) as pool:
        n = 0
        for key, fl, st, err, secs, grid in pool.imap_unordered(_decide, work, chunksize=1):
            n += 1
            if st == 'SAT':
                # witness EERST; een verworpen SAT is een MODEL-MISMATCH (retrybaar, nooit
                # stilletjes 'beslist' -- de 2026-07-08 qattenden/uw-mismatch les)
                ok, vt, rep = T.verify_board(WORD, MASK, grid)
                fail = None if ok else (rep.get('fail') if isinstance(rep, dict) else str(rep))
                print(f"SAT {key} witness ok={ok} vt={vt} fail={fail}", flush=True)
                lf.write(json.dumps({'key': key, 'floor': fl,
                                     'verdict': 'SAT' if ok and vt > 2000 else 'MISMATCH',
                                     'vt': vt, 'fail': fail, 'secs': round(secs, 1)}) + '\n')
            else:
                lf.write(json.dumps({'key': key, 'floor': fl, 'verdict': st,
                                     'secs': round(secs, 1)}) + '\n')
            if st == 'SAT':
                if ok and (best is None or vt > best):
                    blob = {'board': T.B, 'main_word': WORD,
                            'turn_str': ''.join(ch.upper() if i in set(MASK) else ch.lower()
                                                for i, ch in enumerate(WORD)),
                            'require_center': True, 'claimed_total': vt, 'grid': grid}
                    p = (f'/home/bob/programming/scrabble4/experiments/results/turns/'
                         f'N15_{WORD[:3]}_best_{vt}.json')
                    json.dump(blob, open(p, 'w'))
                    print(f"*** BORD {vt} -> {p} ***", flush=True)
                    best = vt
            elif st not in ('UNSAT',):
                und += 1
            if n % 1000 == 0:
                r = n / (time.time() - t0)
                print(f"  {n}/{len(work)} ({r:.1f}/s, ~{(len(work)-n)/max(r,1e-9)/3600:.1f}h) "
                      f"und={und}", flush=True)
    print(f"RESIDU KLAAR: undecided={und} best={best}", flush=True)


if __name__ == '__main__':
    main()
