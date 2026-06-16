#!/usr/bin/env python3
"""N=15 VARMAX certification driver.

For the OPEN set (15-letter threat words whose SOUND analytic UB > current LB), runs the
variable-length xfill engine (`xfill_varmax --varmax BASE --maxscore VFLOOR`) ONCE per legal
(word, mask) -- one varmax search == the full fixed length-vector sweep (proof in
experiments/results/XFILL_VARLEN.md).  Goal: either RAISE the verified LB (a board beats it) or
PROVE the LB optimal (every open mask certifies natural LE <= its vfloor).

Per (word, mask):
  - build the base via xtest.build_base(B, word, turn, scale=False, reserve=1) + dump_base;
  - vfloor = LB - main_const(word, mask)  (verticals must EXCEED this to beat the LB);
  - run xfill_varmax --varmax base --maxscore vfloor --emit  (env WALL = wall cap, MAXVERB=1);
  - interpret (trust ONLY natural, non-WALL completion):
      natural "LE m"  (m == vfloor)        -> CERTIFIED <= LB for this mask (verticals can't reach).
      "MAX m" with main_const + m > LB     -> a board BEATS the LB: reconstruct full board from the
                                              emitted BOARD, witness_check (require_center, reserve=1);
                                              if ok save N15_best_<total>.json, RAISE LB, re-derive
                                              the open set, continue.
      "TO ..." (WALL/deadline/nodecap)     -> OPEN (proves nothing).

SOUNDNESS: a TO proves nothing -> OPEN.  A total is a verified LB ONLY if witness_check ok=True.
The LB is PROVEN optimal ONLY if EVERY open word has natural LE on EVERY legal mask.

PARALLELISM: up to PROCS concurrent workers; each worker is a tracked Popen; on wall expiry we kill
ONLY that worker's specific PID (never a process group / negative PID).
"""
import sys, os, time, json, subprocess, argparse, signal
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')

import xtest
from scrabble import construct_rules, get_word_score
import numpy as np
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B = '15'; W = H = 15; HMAX = 8
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_varmax')

r = construct_rules('dutch', B)
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]

from n15_greedy_lb import candidate_masks


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


def turn_str(word, mask):
    ms = set(mask)
    return ''.join(c.upper() if i in ms else c.lower() for i, c in enumerate(word))


def analytic_open_set(lb):
    """Re-derive the OPEN set at `lb` by shelling the sound analytic certifier (single source of
    truth).  Returns the ordered list of words with analytic UB > lb."""
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'experiments/n15_analytic_certify.py'),
                          '--lb', str(lb)], capture_output=True, text=True, cwd=ROOT)
    words = []
    for line in out.stdout.splitlines():
        if line.startswith('OPEN (UB >'):
            # e.g.  OPEN (UB > 1955): 4  ['geschenkcheques', ...]
            lb_bracket = line.split('[', 1)
            if len(lb_bracket) == 2:
                inner = lb_bracket[1].rstrip().rstrip(']')
                for tok in inner.split(','):
                    t = tok.strip().strip("'\"")
                    if t:
                        words.append(t)
    return words, out.stdout


def build_unit_base(word, mask, outdir):
    turn = turn_str(word, mask)
    base = xtest.build_base(B, word, turn, scale=False, reserve=1)
    tag = '_'.join(str(c) for c in mask)
    p = os.path.join(outdir, f'base_{tag}.txt')
    xtest.dump_base(base, p)
    return p, tag, turn


def reconstruct_board(word, board_codes):
    """Full final board: row 0 = the main word (all 15 letters); rows 1..H-1 from the emitted
    BOARD (row-major W*H letter codes, 0=empty).  We TRUST only row>=1 of the emit (the verticals);
    row 0 is the known main word.  witness_check is the independent arbiter."""
    mt = r.alphabet.to_tup(word)
    grid = [[0] * W for _ in range(H)]
    for x in range(W):
        grid[0][x] = mt[x]
    if board_codes is not None and len(board_codes) == W * H:
        for y in range(1, H):
            for x in range(W):
                grid[y][x] = int(board_codes[y * W + x])
    return grid


def run_witness(word, mask, grid, claimed_total):
    turn = turn_str(word, mask)
    spec = {'board': B, 'main_word': word, 'turn_str': turn, 'require_center': True,
            'scale': False, 'reserve': 1, 'claimed_total': claimed_total, 'grid': grid}
    rules = construct_rules('dutch', B)
    rules.reserve = 1
    Wr, Hr = rules.W, rules.H
    mask_b = [turn[x].isupper() for x in range(Wr)]
    blank, info = wc.derive_blanks(rules, grid, mask_b, Wr, Hr)
    if blank is None:
        return False, {'fail': 'no blank assignment', 'info': info}, spec
    ok, rep = wc.check_witness(rules, Wr, Hr, grid, blank, mask_b,
                               claimed_total=claimed_total, require_center=True)
    return ok, rep, spec


class Unit:
    __slots__ = ('word', 'mask', 'tag', 'vfloor', 'mainc', 'base', 'turn',
                 'proc', 'start', 'logf', 'verb_path')

    def __init__(self, word, mask, outdir):
        self.word = word; self.mask = mask
        self.mainc = main_const(word, mask)
        self.base, self.tag, self.turn = build_unit_base(word, mask, outdir)
        self.vfloor = None  # set per LB at launch
        self.proc = None; self.start = None
        self.verb_path = os.path.join(outdir, f'{word}_{self.tag}.maxverb')


def fmt_eta(secs):
    if secs < 0 or secs != secs:
        return '?'
    secs = int(secs)
    h, rem = divmod(secs, 3600); m, s = divmod(rem, 60)
    if h:
        return f'{h}h{m:02d}m'
    if m:
        return f'{m}m{s:02d}s'
    return f'{s}s'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=1955)
    ap.add_argument('--procs', type=int, default=24)
    ap.add_argument('--wall', type=int, default=int(os.environ.get('WALL', '1800')))
    ap.add_argument('--outdir', type=str,
                    default=os.path.join(ROOT, 'experiments/results/certs/n15varmax'))
    ap.add_argument('--logfile', type=str,
                    default=os.path.join(ROOT, 'experiments/results/n15_varmax_certify.log'))
    ap.add_argument('--words', type=str, default='',
                    help='comma list to override the analytic open set (debug)')
    ap.add_argument('--max-masks', type=int, default=0,
                    help='cap masks per word (debug; 0=all)')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    logfp = open(args.logfile, 'a', buffering=1)

    def log(msg):
        line = f'[{time.strftime("%H:%M:%S")}] {msg}'
        print(line, flush=True)
        logfp.write(line + '\n')

    LB = args.lb
    procs = max(1, min(24, args.procs))

    log(f'=== N15 VARMAX CERTIFY start  LB={LB}  procs={procs}  wall={args.wall}s '
        f'bin={BIN} ===')

    # ---- open set (sound analytic) ----
    if args.words:
        open_words = [w.strip() for w in args.words.split(',') if w.strip()]
        log(f'open set OVERRIDDEN by --words: {open_words}')
    else:
        open_words, raw = analytic_open_set(LB)
        log(f'analytic open set @ LB={LB}: {open_words}')

    # ---- build all units ----
    units = []
    for w in open_words:
        masks = candidate_masks(w, limit=10000)
        if args.max_masks:
            masks = masks[:args.max_masks]
        for m in masks:
            units.append(Unit(w, m, args.outdir))
    total = len(units)
    per_word_counts = {}
    for u in units:
        per_word_counts[u.word] = per_word_counts.get(u.word, 0) + 1
    log(f'WORK UNITS = {total} masks over {len(open_words)} words: '
        + ', '.join(f'{w}:{per_word_counts.get(w,0)}' for w in open_words))
    vfs = sorted(LB - u.mainc for u in units)
    if vfs:
        log(f'vfloor (LB-main_const) range [{vfs[0]}..{vfs[-1]}] median {vfs[len(vfs)//2]}')

    # ---- result accumulators ----
    pending = list(units)            # not yet launched
    inflight = []                    # launched, running (Unit)
    done = 0
    wall_times = []                  # completed-unit wall secs (for ETA)
    verdicts = {}                    # (word, tagmask) -> dict
    new_lb_events = []
    results_path = os.path.join(args.outdir, 'verdicts.jsonl')
    resfp = open(results_path, 'a', buffering=1)

    def launch(u):
        u.vfloor = LB - u.mainc
        env = dict(os.environ)
        env['WALL'] = str(args.wall)
        env['MAXVERB'] = '1'
        vf = open(u.verb_path, 'w')
        u.logf = vf
        u.proc = subprocess.Popen(
            [BIN, '--varmax', u.base, '--maxscore', str(u.vfloor), '--emit'],
            stdout=subprocess.PIPE, stderr=vf, text=True, env=env)
        u.start = time.time()
        inflight.append(u)

    def latest_nodes(u):
        # last "nodes=" seen in the maxverb file (intra-search progress)
        try:
            with open(u.verb_path) as f:
                data = f.read()
            idx = data.rfind('nodes=')
            if idx < 0:
                return None
            seg = data[idx + 6:idx + 6 + 20].split()[0]
            return int(''.join(ch for ch in seg if ch.isdigit()))
        except Exception:
            return None

    def handle_completion(u, rc):
        nonlocal done, LB, open_words
        elapsed = time.time() - u.start
        try:
            u.logf.flush(); u.logf.close()
        except Exception:
            pass
        out, _ = u.proc.communicate()
        line = ''
        board_codes = None
        for ln in (out or '').splitlines():
            ls = ln.strip()
            if ls.startswith(('LE ', 'MAX ', 'TO ', 'UNSAT', 'NOCAND')):
                line = ls
            elif ls.startswith('BOARD'):
                board_codes = [int(x) for x in ls.split()[1:]]
        nodes = None
        if 'nodes=' in line:
            try:
                nodes = int(line.split('nodes=')[1].split()[0])
            except Exception:
                nodes = None
        verdict = 'UNKNOWN'; value = None; note = ''
        if line.startswith('LE '):
            value = int(line.split()[1]); verdict = 'CERT'
            assert value == u.vfloor, f'LE value {value} != vfloor {u.vfloor}'
        elif line.startswith('NOCAND'):
            verdict = 'CERT'; note = 'nocand'
        elif line.startswith('UNSAT'):
            verdict = 'CERT'; note = 'unsat'
        elif line.startswith('MAX '):
            value = int(line.split()[1])
            total_score = u.mainc + value
            if total_score > LB:
                # candidate NEW LB -- must witness_check before trusting
                grid = reconstruct_board(u.word, board_codes)
                ok, rep, spec = run_witness(u.word, u.mask, grid, total_score)
                if ok:
                    verdict = 'NEW_LB'; note = f'total={total_score} WITNESS_OK'
                    fn = os.path.join(ROOT, f'experiments/results/turns/N15_best_{total_score}.json')
                    with open(fn, 'w') as wf:
                        json.dump(spec, wf)
                    new_lb_events.append((u.word, u.mask, total_score, fn))
                    LB = total_score
                    log(f'*** NEW VERIFIED LB = {LB}  word={u.word} mask={u.mask} '
                        f'main_const={u.mainc} vert={value}  saved {fn} ***')
                    # re-derive open set at new LB; drop pending units whose word certified out,
                    # and recompute vfloors at next launch.
                    open_words, _ = analytic_open_set(LB)
                    log(f're-derived open set @ LB={LB}: {open_words}')
                else:
                    verdict = 'WITNESS_REJECT'
                    note = f'total={total_score} REJECTED: {rep.get("fail", rep)}'
                    log(f'!!! MAX {value} (total {total_score}) but WITNESS REJECTED for '
                        f'{u.word} {u.mask}: {note}')
            else:
                # MAX <= vfloor band cannot happen (MAX>floor by construction); treat as CERT
                verdict = 'CERT'; note = f'max {value} <= vfloor {u.vfloor}'
        elif line.startswith('TO '):
            verdict = 'OPEN'; note = 'wall/deadline -> proves nothing'
        else:
            verdict = 'OPEN'; note = f'unparsed line: {line!r} rc={rc}'

        done += 1
        wall_times.append(elapsed)
        rec = {'word': u.word, 'mask': list(u.mask), 'verdict': verdict, 'line': line,
               'vfloor': u.vfloor, 'main_const': u.mainc, 'nodes': nodes,
               'wall_s': round(elapsed, 2), 'note': note, 'lb_at': LB}
        verdicts[(u.word, u.tag)] = rec
        resfp.write(json.dumps(rec) + '\n')
        # ETA
        remaining = len(pending) + len(inflight)  # inflight excludes this one already removed
        avg = sum(wall_times) / len(wall_times)
        eta = avg * remaining / procs
        log(f'DONE {u.word} mask={u.mask} -> {verdict} {line.split("nodes=")[0].strip()} '
            f'nodes={nodes} wall={elapsed:.1f}s  [{done}/{total}] LB={LB} '
            f'ETA~{fmt_eta(eta)} (avg {avg:.0f}s/unit, {remaining} left @ {procs}w)')

    last_hb = time.time()
    HB = 45

    # ---- main loop ----
    while pending or inflight:
        # fill the pool, skipping pending units whose word is no longer open (certified out by a
        # raised LB)
        while pending and len(inflight) < procs:
            u = pending.pop(0)
            if u.word not in open_words:
                # certified out by a raised LB -> skip (sound: analytic UB <= LB)
                rec = {'word': u.word, 'mask': list(u.mask), 'verdict': 'SKIP_CERTOUT',
                       'note': f'word analytic-certified <= LB {LB}', 'lb_at': LB}
                verdicts[(u.word, u.tag)] = rec
                resfp.write(json.dumps(rec) + '\n')
                continue
            launch(u)

        # poll inflight
        time.sleep(1.0)
        now = time.time()
        finished = []
        for u in inflight:
            rc = u.proc.poll()
            if rc is not None:
                finished.append((u, rc))
            elif now - u.start > args.wall + 120:
                # safety net: the binary's own WALL should fire first; if it overran by 2min,
                # kill ONLY this specific PID (never a group / negative PID).
                try:
                    u.proc.send_signal(signal.SIGTERM)
                    time.sleep(2)
                    if u.proc.poll() is None:
                        u.proc.kill()
                except Exception:
                    pass
                log(f'WATCHDOG killed PID {u.proc.pid} ({u.word} {u.mask}) overran wall')
                finished.append((u, -99))
        for u, rc in finished:
            inflight.remove(u)
            handle_completion(u, rc)

        # heartbeat
        if now - last_hb >= HB:
            last_hb = now
            infl_desc = []
            for u in inflight:
                el = now - u.start
                nd = latest_nodes(u)
                infl_desc.append(f'{u.word[:6]}:{u.tag}({el:.0f}s,n={nd})')
            remaining = len(pending) + len(inflight)
            if wall_times:
                avg = sum(wall_times) / len(wall_times)
                eta = avg * remaining / procs
            else:
                eta = float('nan')
            log(f'HB [{done}/{total}] LB={LB} inflight={len(inflight)} pending={len(pending)} '
                f'ETA~{fmt_eta(eta)} :: ' + ' '.join(infl_desc[:procs]))

    # ---- final summary ----
    log('=== FINAL SUMMARY ===')
    # group by word
    byword = {}
    for (w, tag), rec in verdicts.items():
        byword.setdefault(w, []).append(rec)
    all_cert = True
    open_residual = []
    for w in sorted(byword):
        recs = byword[w]
        cert = [x for x in recs if x['verdict'] in ('CERT', 'SKIP_CERTOUT')]
        openm = [x for x in recs if x['verdict'] == 'OPEN']
        rej = [x for x in recs if x['verdict'] == 'WITNESS_REJECT']
        new = [x for x in recs if x['verdict'] == 'NEW_LB']
        status = 'CERTIFIED <= LB' if not openm and not new and not rej else (
            'NEW_LB' if new else 'OPEN')
        if openm or rej:
            all_cert = False
        for x in openm:
            open_residual.append((w, tuple(x['mask']), x.get('nodes')))
        log(f'  {w}: {status}  ({len(cert)} cert, {len(openm)} open, {len(new)} new-lb, '
            f'{len(rej)} reject) of {len(recs)}')
        for x in openm:
            log(f'      OPEN mask={x["mask"]} nodes={x.get("nodes")} vfloor={x.get("vfloor")}')

    log(f'final LB = {LB}')
    if new_lb_events:
        for w, m, t, fn in new_lb_events:
            log(f'  NEW LB witness: {w} {m} total={t} -> {fn}')
    if all_cert and not open_residual:
        log(f'VERDICT: N15 OPTIMUM PROVEN at LB={LB} (every open word certifies natural LE on '
            f'every legal mask).')
    elif open_residual:
        log(f'VERDICT: NOT PROVEN. OPEN residual = {len(open_residual)} masks: '
            + '; '.join(f'{w}{list(m)}(n={n})' for w, m, n in open_residual))
    logfp.close(); resfp.close()


if __name__ == '__main__':
    main()
