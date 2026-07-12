"""FINALE 2102-residu: beslis alle pipe-TO-keys (key<TAB>floor) met CP-SAT op vfloor=378
(= beats-2102).  Keys gegroepeerd per masker (kolommen uit de key); per masker een pool met
gedeelde template.  Witness-eerst; SAT>2102 -> NIEUWE LB (stop).  Ledger: final_residue.jsonl."""
import sys, os, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import multiprocessing as mp

ROOT = '/home/bob/programming/scrabble4'
KEYS = f'{ROOT}/experiments/results/oracle_parallel/pipe_to_keys.txt'
LEDGER = f'{ROOT}/experiments/results/oracle_parallel/final_residue_2102.jsonl'
WORD = 'geschenkcheques'
VFLOOR = 2102 - 1724   # 378


def _init(mask):
    os.environ['CPSAT_WORKERS'] = '1'
    os.environ.setdefault('RESERVE', '1')
    import n15_twolevel as T
    global _T, _MASK
    _T, _MASK = T, mask
    T._oracle_template(WORD, mask)


def _decide(arg):
    key = arg
    combo = {}
    for part in key.split('|'):
        c, w = part.split(':')
        combo[int(c)] = None if w == '-' else tuple(ord(ch) - 96 for ch in w)
    t0 = time.time()
    try:
        st, grid = _T.oracle_beats_lb(WORD, _MASK, combo, VFLOOR, cap=1200.0)
    except Exception as e:
        return key, 'ERROR', repr(e), time.time() - t0, None
    return key, st, None, time.time() - t0, grid if st == 'SAT' else None


def main():
    done = {}
    if os.path.exists(LEDGER):
        for line in open(LEDGER):
            try:
                d = json.loads(line)
                done[d['key']] = d['verdict']
            except Exception:
                pass
    bymask = {}
    seen = set()
    for line in open(KEYS):
        key = line.split('\t')[0].strip()
        if not key or key in seen:
            continue
        seen.add(key)
        if done.get(key) == 'UNSAT':
            continue
        mask = tuple(int(p.split(':')[0]) for p in key.split('|'))
        bymask.setdefault(mask, []).append(key)
    print(f"# {sum(len(v) for v in bymask.values())} unieke onbesliste keys over "
          f"{len(bymask)} maskers ({len(done)} in ledger)", flush=True)
    import n15_twolevel as T
    lf = open(LEDGER, 'a', buffering=1)
    ctx = mp.get_context('spawn')
    for mask, keys in sorted(bymask.items(), key=lambda kv: len(kv[1])):
        print(f"# masker {mask}: {len(keys)} keys", flush=True)
        und = 0
        t0 = time.time()
        with ctx.Pool(processes=int(os.environ.get('RES_WORKERS', '12')),
                      initializer=_init, initargs=(mask,)) as pool:
            n = 0
            for key, st, err, secs, grid in pool.imap_unordered(_decide, keys, chunksize=1):
                n += 1
                if st == 'SAT':
                    ok, vt, rep = T.verify_board(WORD, mask, grid)
                    fail = None if ok else (rep.get('fail') if isinstance(rep, dict) else str(rep))
                    print(f"SAT {key} witness ok={ok} vt={vt} fail={fail}", flush=True)
                    lf.write(json.dumps({'key': key, 'verdict': 'SAT' if ok and vt > 2102 else 'MISMATCH',
                                         'vt': vt, 'secs': round(secs, 1)}) + '\n')
                    if ok and vt > 2102:
                        blob = {'board': T.B, 'main_word': WORD,
                                'turn_str': ''.join(ch.upper() if i in set(mask) else ch.lower()
                                                    for i, ch in enumerate(WORD)),
                                'require_center': True, 'claimed_total': vt, 'grid': grid}
                        json.dump(blob, open(f'{ROOT}/experiments/results/turns/N15_best_{vt}.json', 'w'))
                        print(f"*** NIEUWE LB {vt} *** -- stop", flush=True)
                        return
                else:
                    lf.write(json.dumps({'key': key, 'verdict': st, 'secs': round(secs, 1)}) + '\n')
                    if st != 'UNSAT':
                        und += 1
                if n % 1000 == 0:
                    rate = n / (time.time() - t0)
                    print(f"  {n}/{len(keys)} ({rate:.1f}/s, ~{(len(keys)-n)/max(rate,1e-9)/3600:.1f}h) "
                          f"und={und}", flush=True)
        print(f"# masker {mask} KLAAR: undecided={und}", flush=True)
    print("FINALE-RESIDU KLAAR", flush=True)


if __name__ == '__main__':
    main()
