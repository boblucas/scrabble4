#!/usr/bin/env python3
"""Hunt a >LB board over the OPEN {3,11} masks (capture BOTH x2-letter columns) of the 4 open
N=15 words, using the FASTER varmax engine (incremental consistent-set rebuild).  One varmax
search per (word, mask) == the full fixed length-vector sweep (see XFILL_VARLEN.md).

Goal: a board with total > LB.  --maxscore (LB - main_const) stops at the FIRST board whose
verticals exceed the floor (-> total > LB); on such a MAX we reconstruct + witness_check
(require_center=True, reserve=1) and save experiments/results/turns/N15_best_<total>.json.

A TO proves nothing (the mask stays OPEN).  Soundness: a total is a verified LB only when
witness_check ok=True.

Parallelism: up to PROCS tracked Popens; on wall expiry we kill ONLY that worker's specific PID.
Does NOT touch the paused n15_bounded_certify run or its dir.
"""
import sys, os, time, json, subprocess, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')

from n15_varmax_certify import (main_const, turn_str, build_unit_base, reconstruct_board,
                                run_witness, B)
from n15_greedy_lb import candidate_masks

ROOT = '/home/bob/programming/scrabble4'
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_varmax')
WORDS = ['geschenkcheques', 'flauwekulexcuus', 'jacquardmachine', 'chequeformulier']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=1955)
    ap.add_argument('--procs', type=int, default=23)
    ap.add_argument('--wall', type=int, default=3600)
    ap.add_argument('--outdir', type=str,
                    default=os.path.join(ROOT, 'experiments/results/certs/n15hunt_3_11'))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'experiments/results/turns'), exist_ok=True)
    LB = args.lb
    procs = max(1, min(24, args.procs))
    logfp = open(os.path.join(args.outdir, 'hunt.log'), 'a', buffering=1)
    resfp = open(os.path.join(args.outdir, 'verdicts.jsonl'), 'a', buffering=1)

    def log(m):
        line = f'[{time.strftime("%H:%M:%S")}] {m}'
        print(line, flush=True); logfp.write(line + '\n')

    # build the {3,11} unit list
    units = []
    for w in WORDS:
        for m in candidate_masks(w, limit=10000):
            if 3 in m and 11 in m:
                mainc = main_const(w, m)
                base, tag, turn = build_unit_base(w, m, args.outdir)
                units.append({'word': w, 'mask': m, 'mainc': mainc, 'base': base, 'tag': tag,
                              'vfloor': LB - mainc})
    log(f'=== HUNT {{3,11}} start LB={LB} units={len(units)} procs={procs} wall={args.wall}s bin={BIN} ===')
    for u in units:
        log(f'  unit {u["word"]} {u["mask"]} mainc={u["mainc"]} vfloor={u["vfloor"]}')

    pending = list(units)
    inflight = []
    done = 0
    found = None

    def launch(u):
        env = dict(os.environ); env['WALL'] = str(args.wall); env['MAXVERB'] = '1'
        vf = open(os.path.join(args.outdir, f'{u["word"]}_{u["tag"]}.maxverb'), 'w')
        u['logf'] = vf
        u['proc'] = subprocess.Popen(
            [BIN, '--varmax', u['base'], '--maxscore', str(u['vfloor']), '--emit'],
            stdout=subprocess.PIPE, stderr=vf, text=True, env=env)
        u['start'] = time.time()
        inflight.append(u)

    def finish(u, rc):
        nonlocal done, LB, found
        elapsed = time.time() - u['start']
        try: u['logf'].flush(); u['logf'].close()
        except Exception: pass
        out, _ = u['proc'].communicate()
        line = ''; board_codes = None
        for ln in (out or '').splitlines():
            ls = ln.strip()
            if ls.startswith(('LE ', 'MAX ', 'TO ', 'UNSAT', 'NOCAND')): line = ls
            elif ls.startswith('BOARD'): board_codes = [int(x) for x in ls.split()[1:]]
        nodes = None
        if 'nodes=' in line:
            try: nodes = int(line.split('nodes=')[1].split()[0])
            except Exception: pass
        verdict = 'OPEN'; note = ''; value = None
        if line.startswith('LE '):
            value = int(line.split()[1]); verdict = 'CERT'
            assert value == u['vfloor']
        elif line.startswith(('UNSAT', 'NOCAND')):
            verdict = 'CERT'; note = line.split()[0].lower()
        elif line.startswith('MAX '):
            value = int(line.split()[1]); total = u['mainc'] + value
            if total > LB:
                grid = reconstruct_board(u['word'], board_codes)
                ok, rep, spec = run_witness(u['word'], u['mask'], grid, total)
                if ok:
                    verdict = 'NEW_LB'; note = f'total={total} WITNESS_OK'
                    fn = os.path.join(ROOT, f'experiments/results/turns/N15_best_{total}.json')
                    with open(fn, 'w') as wf: json.dump(spec, wf)
                    found = (u['word'], u['mask'], total, fn)
                    LB = total
                    log(f'*** NEW VERIFIED LB = {LB} word={u["word"]} mask={u["mask"]} '
                        f'mainc={u["mainc"]} vert={value} saved {fn} ***')
                else:
                    verdict = 'WITNESS_REJECT'; note = f'total={total} REJECTED: {rep.get("fail", rep)}'
                    log(f'!!! MAX {value} (total {total}) WITNESS REJECTED {u["word"]} {u["mask"]}: {note}')
            else:
                verdict = 'CERT'; note = f'max {value} <= vfloor'
        elif line.startswith('TO '):
            verdict = 'OPEN'; note = 'wall -> proves nothing'
        else:
            verdict = 'OPEN'; note = f'unparsed {line!r} rc={rc}'
        done += 1
        rec = {'word': u['word'], 'mask': list(u['mask']), 'verdict': verdict, 'line': line,
               'vfloor': u['vfloor'], 'main_const': u['mainc'], 'nodes': nodes,
               'wall_s': round(elapsed, 1), 'note': note, 'lb_at': LB}
        resfp.write(json.dumps(rec) + '\n')
        log(f'DONE {u["word"]} {u["mask"]} -> {verdict} {line.split("nodes=")[0].strip()} '
            f'nodes={nodes} wall={elapsed:.0f}s [{done}/{len(units)}]')

    last_hb = time.time()
    while pending or inflight:
        while pending and len(inflight) < procs:
            launch(pending.pop(0))
        time.sleep(2)
        for u in inflight[:]:
            rc = u['proc'].poll()
            if rc is not None:
                inflight.remove(u); finish(u, rc)
        if time.time() - last_hb > 60:
            last_hb = time.time()
            prog = []
            for u in inflight:
                el = int(time.time() - u['start'])
                prog.append(f'{u["word"][:4]}{u["mask"][-3:]}:{el}s')
            log(f'HB inflight={len(inflight)} pending={len(pending)} done={done} :: ' + ' '.join(prog))
    log(f'=== HUNT DONE done={done} LB={LB} found={found} ===')


if __name__ == '__main__':
    main()
