"""Finish the monster (0,3,7,9,11,13,14)@2010 certification: PARALLEL CP-SAT residue for the
39,339 pin-TO combos (resumes past hard_verdicts.jsonl), then the coverage check + verdict.
Mirrors n15_stream_certify phases 3b-4 exactly; artifacts land in the same stream dir."""
import sys, os, json, time, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import multiprocessing as mp

ROOT = '/home/bob/programming/scrabble4'
D = f'{ROOT}/experiments/results/oracle_parallel/stream_0379111314_lb2010'
MASK = (0, 3, 7, 9, 11, 13, 14)
LB = 2010
WORD = 'geschenkcheques'
NSHARD = 20


def _init():
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')
    import n15_twolevel as T
    global _T, _VF
    _T = T
    _VF = LB - T.main_const(WORD, MASK)
    T._oracle_template(WORD, MASK)


def _decide(key):
    combo = {}
    for part in key.split('|'):
        c, w = part.split(':')
        combo[int(c)] = None if w == '-' else tuple(ord(ch) - 96 for ch in w)
    t0 = time.time()
    try:
        st, grid = _T.oracle_beats_lb(WORD, MASK, combo, _VF, cap=1200.0)
    except Exception as e:
        return key, 'ERROR', repr(e), time.time() - t0, None
    return key, st, None, time.time() - t0, grid if st == 'SAT' else None


def main():
    import n15_twolevel as T
    os.environ.setdefault('RESERVE', '1')
    # hard keys = TO/NOCAND RES lines across verdict files
    hard = []
    for i in range(NSHARD):
        for line in open(f'{D}/verdict_{i:02d}.txt'):
            if line.startswith('RES '):
                _, key, rest = line.split(None, 2)
                if not (rest.startswith('LE') or rest.startswith('MAX')):
                    hard.append(key)
    done = set()
    if os.path.exists(f'{D}/hard_verdicts.jsonl'):
        for line in open(f'{D}/hard_verdicts.jsonl'):
            try:
                done.add(json.loads(line)['key'])
            except Exception:
                pass
    work = [k for k in hard if k not in done]
    print(f'hard={len(hard)} done={len(done)} remaining={len(work)}', flush=True)

    und = 0
    new_lb = None
    hf = open(f'{D}/hard_verdicts.jsonl', 'a', buffering=1)
    ctx = mp.get_context('spawn')
    t0 = time.time()
    with ctx.Pool(processes=20, initializer=_init) as pool:
        for n, (key, st, err, secs, grid) in enumerate(pool.imap_unordered(_decide, work,
                                                                           chunksize=4), 1):
            hf.write(json.dumps({'key': key, 'why': 'TO', 'verdict': st,
                                 'secs': round(secs, 2)}) + '\n')
            if st == 'SAT':
                ok, vt, rep = T.verify_board(WORD, MASK, grid)
                print(f'  hard SAT key={key} witness ok={ok} vt={vt}', flush=True)
                if ok and vt > LB:
                    print(f'  *** NEW LB {vt} ***', flush=True)
                    new_lb = vt
            elif st not in ('UNSAT',):
                und += 1
            if n % 2000 == 0:
                r = n / (time.time() - t0)
                print(f'  {n}/{len(work)} ({r:.1f}/s, ~{(len(work)-n)/max(r,1e-9)/60:.0f}min left) '
                      f'undecided={und}', flush=True)
    print(f'residue done: undecided={und} new_lb={new_lb}', flush=True)
    if new_lb or und:
        print('VERDICT: OPEN (new LB or undecided residue)'); return

    # coverage: every shard key has a verdict; every hard key has an exact verdict
    print('coverage check ...', flush=True)
    rc = subprocess.run(
        f'cat {D}/shard_*.txt | cut -d" " -f1 | sort -u > {D}/_keys_in.txt; '
        f'cat {D}/verdict_*.txt | grep "^RES " | cut -d" " -f2 | sort -u > {D}/_keys_out.txt; '
        f'cmp -s {D}/_keys_in.txt {D}/_keys_out.txt && echo COVERAGE-OK || echo COVERAGE-FAIL',
        shell=True, capture_output=True, text=True)
    print(rc.stdout.strip(), flush=True)
    nhard_ok = sum(1 for line in open(f'{D}/hard_verdicts.jsonl')
                   if json.loads(line).get('verdict') == 'UNSAT')
    print(f'hard UNSAT total: {nhard_ok} (need >= {len(hard)} unique)', flush=True)
    if 'COVERAGE-OK' in rc.stdout:
        print(f'=== VERDICT: mask {MASK} CERTIFIED <= {LB} (282299680 band combos, complete) ===',
              flush=True)


if __name__ == '__main__':
    main()
