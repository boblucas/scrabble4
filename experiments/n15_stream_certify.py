"""STREAMING shard certifier for over-cap bands (mask (0,3,7,9,11,13,14): 282,299,680 combos --
collect_top materialization is impossible, and the in-driver pool's per-combo IPC would bottleneck).

Pipeline (no Python in the hot loop):
  1. ENUM  : enumerate_above_blanks(stream=...) writes every in-band combo as a pinbatch line
             `<key> <floor> <toks>` round-robin into NSHARD shard files.  Complete by construction
             (same DFS the count uses; the count is re-verified against lines written).
  2. SOLVE : NSHARD parallel `xfill --pinbatch BASE --emit < shard_i > verdict_i` (PINWALL env).
  3. COLLECT: scan verdicts.  LE -> safe.  MAX -> reconstruct + witness_check (a witnessed
             total > LB is a NEW LB -> stop everything, cascade).  TO/NOCAND -> re-decided
             exactly by the CP-SAT oracle (oracle_beats_lb, cap 1200; UNKNOWN kept undecided).
  4. CHECK : coverage = every shard key has a verdict (sort -u on keys, disk-based), plus
             count == lines written.  Only then: CERTIFIED.

Artifacts (the machine-checkable certificate): shard files + verdict files + FINISH log.
Usage: python n15_stream_certify.py --mask 0,3,7,9,11,13,14 --lb 2010 [--shards 20] [--dir DIR]
"""
import sys, os, json, time, argparse, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')

import n15_twolevel as T
from n15_varmax_certify import build_unit_base, reconstruct_board

ROOT = '/home/bob/programming/scrabble4'
BIN = os.environ.get('XFILL_BIN', f'{ROOT}/experiments/xfill_rs/target/release/xfill')
WORD = 'geschenkcheques'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mask', required=True)
    ap.add_argument('--lb', type=int, required=True)
    ap.add_argument('--shards', type=int, default=20)
    ap.add_argument('--dir', default=None)
    ap.add_argument('--skip-enum', action='store_true', help='shards already written')
    a = ap.parse_args()
    mask = tuple(int(x) for x in a.mask.split(','))
    tag = ''.join(str(c) for c in mask)
    d = a.dir or f'{ROOT}/experiments/results/oracle_parallel/stream_{tag}_lb{a.lb}'
    os.makedirs(d, exist_ok=True)
    os.environ.setdefault('RESERVE', '1')

    mc = T.main_const(WORD, mask)
    vfloor = a.lb - mc
    assert a.lb >= 2004 and all(c in mask for c in (0, 7, 14))   # 27-pt turn-blank argument
    base_path, _, _ = build_unit_base(WORD, mask, d)
    bcols = [int(l.split()[1]) for l in open(base_path) if l.startswith('BCOL')]

    log = open(f'{d}/driver.log', 'a', buffering=1)
    def say(m):
        line = f'[{time.strftime("%H:%M:%S")}] {m}'
        print(line, flush=True); log.write(line + '\n')

    say(f'=== STREAM CERTIFY mask={mask} lb={a.lb} vfloor={vfloor} shards={a.shards} dir={d}')

    # ---- 1. ENUM -> shards -------------------------------------------------------------------
    nwritten = 0
    if not a.skip_enum:
        avail, _ = T.build_avail(WORD, mask, 1)
        fhs = [open(f'{d}/shard_{i:02d}.txt', 'w', buffering=1 << 20) for i in range(a.shards)]
        stat = {'n': 0, 't': time.time()}

        def emit(gross, combo):
            toks = []
            parts = []
            for c in bcols:
                ww = combo.get(c)
                toks.append('-' if not ww or len(ww) <= 1 else ','.join(str(x) for x in ww[1:]))
            key = T.combo_key(combo)
            fhs[stat['n'] % a.shards].write(f'{key} {vfloor} {" ".join(toks)}\n')
            stat['n'] += 1
            if stat['n'] % 20_000_000 == 0:
                say(f'  enum: {stat["n"]/1e6:.0f}M streamed ({stat["n"]/(time.time()-stat["t"]):.0f}/s)')

        res = T.enumerate_above_blanks(WORD, mask, avail, vfloor, blank_budget=2, stream=emit)
        for fh in fhs:
            fh.close()
        nwritten = stat['n']
        say(f'enum DONE: count={res["count"]} streamed={nwritten} capped={res["capped"]}')
        assert res['count'] == nwritten and not res['capped'], 'enum/stream mismatch'
    else:
        nwritten = sum(int(subprocess.run(['wc', '-l', f'{d}/shard_{i:02d}.txt'],
                       capture_output=True, text=True).stdout.split()[0]) for i in range(a.shards))
        say(f'skip-enum: {nwritten} lines in existing shards')

    # ---- 2. SOLVE: parallel pinbatch over shards ----------------------------------------------
    procs = []
    for i in range(a.shards):
        sf = open(f'{d}/shard_{i:02d}.txt')
        vf = open(f'{d}/verdict_{i:02d}.txt', 'w')
        p = subprocess.Popen([BIN, '--pinbatch', base_path, '--emit'],
                             stdin=sf, stdout=vf, stderr=subprocess.DEVNULL, text=True)
        procs.append((p, sf, vf))
    say(f'launched {len(procs)} pinbatch shard workers (PINWALL={os.environ.get("PINWALL", "5")}s)')
    t0 = time.time()
    while any(p.poll() is None for p, _, _ in procs):
        time.sleep(60)
        done = sum(int(subprocess.run(['grep', '-c', '^RES', f'{d}/verdict_{i:02d}.txt'],
                   capture_output=True, text=True).stdout.strip() or 0) for i in range(a.shards))
        rate = done / max(time.time() - t0, 1)
        say(f'  solve: {done}/{nwritten} ({rate:.0f}/s, ~{(nwritten-done)/max(rate,1e-9)/3600:.1f}h left)')
    for p, sf, vf in procs:
        sf.close(); vf.close()
    say('all shard workers done')

    # ---- 3. COLLECT --------------------------------------------------------------------------
    n_le = n_max = n_to = n_bad = 0
    hard = []                                   # (key, toks) needing CP-SAT
    new_lb = None
    for i in range(a.shards):
        pend_board = {}
        for line in open(f'{d}/verdict_{i:02d}.txt'):
            if line.startswith('BOARD '):
                toks = line.split()
                pend_board[toks[1]] = [int(x) for x in toks[2:]]
                continue
            if not line.startswith('RES '):
                continue
            _, key, rest = line.split(None, 2)
            if rest.startswith('LE'):
                n_le += 1
            elif rest.startswith('MAX'):
                n_max += 1
                hard.append((key, 'MAX'))
            elif rest.startswith('TO'):
                n_to += 1
                hard.append((key, 'TO'))
            else:
                n_bad += 1
                hard.append((key, rest.strip()))
        # witness any boards immediately
        for key, board in pend_board.items():
            grid = reconstruct_board(WORD, board)
            ok, vt, rep = T.verify_board(WORD, mask, grid)
            say(f'  MAX board key={key}: witness ok={ok} total={vt}')
            if ok and vt > a.lb:
                blob = {'board': T.B, 'main_word': WORD,
                        'turn_str': ''.join(ch.upper() if j in set(mask) else ch.lower()
                                            for j, ch in enumerate(WORD)),
                        'require_center': True, 'claimed_total': vt, 'grid': grid}
                path = f'{ROOT}/experiments/results/turns/N15_best_{vt}.json'
                json.dump(blob, open(path, 'w'))
                say(f'  *** NEW LB {vt} *** saved {path}')
                new_lb = max(new_lb or 0, vt)
    say(f'collect: LE={n_le} MAX={n_max} TO={n_to} odd={n_bad}; hard={len(hard)}')
    if new_lb:
        say(f'NEW LB {new_lb} -> stop; re-floor everything'); return

    # hard residue -> exact CP-SAT
    if hard:
        say(f're-deciding {len(hard)} hard combos via CP-SAT (cap 1200) ...')
        keymap = {}
        for i in range(a.shards):
            for line in open(f'{d}/shard_{i:02d}.txt'):
                k = line.split(None, 1)[0]
                keymap[k] = line
        und = 0
        hf = open(f'{d}/hard_verdicts.jsonl', 'a', buffering=1)
        for key, why in hard:
            combo = {}
            for part in key.split('|'):
                c, w = part.split(':')
                combo[int(c)] = None if w == '-' else tuple(ord(ch) - 96 for ch in w)
            st, grid = T.oracle_beats_lb(WORD, mask, combo, vfloor, cap=1200.0)
            hf.write(json.dumps({'key': key, 'why': why, 'verdict': st}) + '\n')
            if st == 'SAT':
                ok, vt, rep = T.verify_board(WORD, mask, grid)
                say(f'  hard SAT key={key} witness ok={ok} vt={vt}')
                if ok and vt > a.lb:
                    say(f'  *** NEW LB {vt} (hard residue) ***'); new_lb = vt
            elif st != 'UNSAT':
                und += 1
        say(f'hard residue done: undecided={und}')
        if new_lb or und:
            say('NOT certified (new LB or undecided residue)'); return

    # ---- 4. COVERAGE CHECK --------------------------------------------------------------------
    say('coverage check (disk sort of shard keys vs verdict keys) ...')
    rc = subprocess.run(
        f'cat {d}/shard_*.txt | cut -d" " -f1 | sort -u > {d}/_keys_in.txt; '
        f'cat {d}/verdict_*.txt | grep "^RES " | cut -d" " -f2 | sort -u > {d}/_keys_out.txt; '
        f'cmp -s {d}/_keys_in.txt {d}/_keys_out.txt && echo COVERAGE-OK || echo COVERAGE-FAIL',
        shell=True, capture_output=True, text=True)
    say(rc.stdout.strip())
    if 'COVERAGE-OK' in rc.stdout and nwritten == n_le + n_max + n_to + n_bad:
        say(f'=== VERDICT: mask {mask} CERTIFIED <= {a.lb} ({nwritten} band combos, complete) ===')
    else:
        say('=== VERDICT: OPEN (coverage mismatch) ===')


if __name__ == '__main__':
    main()
