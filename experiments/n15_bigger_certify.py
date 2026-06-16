#!/usr/bin/env python3
"""N=15 VARMAX certification driver on the BIGGER Dutch lexicon (data/words/dutch_bigger_le15).

Self-contained twin of experiments/n15_varmax_certify.py threaded through the bigger word list.
For the analytic OPEN set (15-letter words whose SOUND analytic UB > current LB), runs the validated
PARALLEL B&B binary `xfill --varmax BASE --maxscore VFLOOR --emit` (env XFILL_THREADS) ONCE per legal
(word, mask).  Goal: RAISE the verified LB (a board beats it) or PROVE the LB optimal (every open
mask certifies natural LE <= its vfloor).

Per (word, mask):
  - build the base (candidate verticals per scoring col x length, bag/scores/preplaced, reserve=1),
    DICT pointing at the bigger <=HMAX dict file;
  - vfloor = LB - main_const(word, mask)  (verticals must EXCEED this to beat the LB);
  - run xfill --varmax base --maxscore vfloor --emit  (env WALL = wall cap);
  - interpret (trust ONLY natural, non-WALL completion):
      natural "LE m" (m==vfloor) / NOCAND / UNSAT  -> CERTIFIED <= LB for this mask.
      "MAX m" with main_const + m > LB             -> a board BEATS the LB: reconstruct, witness_check
                                                      (require_center, reserve=1); if ok RAISE LB.
      "TO ..." (WALL/deadline/nodecap)             -> OPEN (proves nothing).

SOUNDNESS: a TO proves nothing -> OPEN.  A total is a verified LB ONLY if witness_check ok=True.
The LB is PROVEN optimal ONLY if EVERY open word certifies natural LE on EVERY legal mask.

Process-kill safety: each worker is a tracked Popen; watchdog kills ONLY that worker's specific PID.
"""
import sys, os, time, json, subprocess, argparse, signal
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')

from scrabble import construct_rules, get_word_score
import numpy as np
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B = '15'; W = H = 15; HMAX = 8
WORD_FILE = os.environ.get('N15_WORD_FILE', 'data/words/dutch_bigger_le15')
# validated PARALLEL B&B binary (frozen a546 worktree)
BIN = os.environ.get('XFILL_BIN',
    os.path.join(ROOT, '.claude/worktrees/agent-a546290f42c7617aa/experiments/xfill_rs/target/release/xfill'))
DICT_PATH = 'experiments/xtests/dict_15_bigger.txt'   # bigger <=HMAX dict (relative to ROOT, cwd=ROOT)

print(f"# loading rules (word_file={WORD_FILE}) ...", flush=True)
_t0 = time.time()
r = construct_rules('dutch', B, word_file=WORD_FILE)
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
print(f"# loaded {len(r.words)} words in {time.time()-_t0:.1f}s", flush=True)


def ensure_dict():
    """Write the bigger <=HMAX dict file (space-separated letter codes, one word/line) used by the
    Rust cross-word automaton.  Only words 1..HMAX are needed (longer verticals are illegal)."""
    p = os.path.join(ROOT, DICT_PATH)
    if os.path.exists(p):
        return p
    t0 = time.time()
    with open(p, 'w') as fp:
        for w in r.words:
            if 1 <= len(w) <= HMAX:
                fp.write(' '.join(map(str, w)) + '\n')
    print(f"# wrote bigger <=HMAX dict -> {p} ({time.time()-t0:.1f}s)", flush=True)
    return p


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


def turn_str(word, mask):
    ms = set(mask)
    return ''.join(c.upper() if i in ms else c.lower() for i, c in enumerate(word))


# ---- candidate bucket (first-letter,length) -> valid vertical words, built ONCE ----
_BUCKET = None
def cand_bucket():
    global _BUCKET
    if _BUCKET is None:
        b = {}
        lk = r.words_lookup
        for w in r.words:
            if w and (len(w) == 1 or w[1:] in lk):
                b.setdefault((w[0], len(w)), []).append(w)
        _BUCKET = b
    return _BUCKET


def build_base(word, turn, reserve=1):
    """BASE for xfill --varmax (no scaling: full 15x15 bag).  Candidate stub words per scoring col x
    every length; gross = vertical score (only row-0 tile gets board multipliers).  Mirrors
    xtest.build_base with scale=False, threaded through the bigger rules."""
    mt = r.alphabet.to_tup(word)
    counts = Counter(r.counts); blanks = r.blank_count
    scoring = [x for x in range(W) if turn[x].isupper()]
    pre = [x for x in range(W) if not turn[x].isupper()]
    bucket = cand_bucket()
    cols = []
    for c in scoring:
        L = mt[c]; bylen = {}; seen = set()
        for length in range(1, H + 1):
            for w in bucket.get((L, length), ()):
                stub = tuple(w[1:])
                if (len(w), stub) in seen:
                    continue
                seen.add((len(w), stub))
                sc = 0 if len(w) == 1 else int(get_word_score(r, w, c, 0, 0,
                                                              [i == 0 for i in range(len(w))])[0])
                bylen.setdefault(len(w), []).append((stub, sc))
        for ln in bylen:
            bylen[ln].sort()
        cols.append({'col': c, 'wm': int(r.word_multiplier[0][c]), 'bylen': bylen})
    mc_scoring = Counter(mt[c] for c in scoring)
    return {
        'W': W, 'H': H, 'hmax': HMAX, 'alphabet_size': len(r.abc), 'blanks': blanks,
        'counts': {str(code): counts[code] - mc_scoring[code] for code in counts},
        'scores': {str(code): r.scores[code] for code in r.scores},
        'preplaced': [[x, 0, mt[x]] for x in pre],
        'nonscoring_cols': pre,
        'reserve': reserve,
        'dict_path': DICT_PATH,
        'cols': cols,
    }


def dump_base(base, path):
    L = [f"DIMS {base['W']} {base['H']} {base['hmax']} {base['alphabet_size']} {base['blanks']}"]
    L.append("COUNTS " + ' '.join(f"{k}:{v}" for k, v in base['counts'].items()))
    L.append("SCORES " + ' '.join(f"{k}:{v}" for k, v in base['scores'].items()))
    L.append("PREPLACED " + ' '.join(f"{x},{y},{c}" for x, y, c in base['preplaced']))
    L.append("NONSCORING " + ' '.join(map(str, base['nonscoring_cols'])))
    if base.get('reserve', 0):
        L.append(f"RESERVE {base['reserve']}")
    L.append(f"DICT {base['dict_path']}")
    for col in base['cols']:
        L.append(f"BCOL {col['col']} {col['wm']} {len(col['bylen'])}")
        for ln in sorted(col['bylen']):
            ws = col['bylen'][ln]
            L.append(f"BLEN {ln} {len(ws)}")
            for stub, g in ws:
                L.append(f"WORDV {g} " + ' '.join(map(str, stub)))
    with open(path, 'w') as fp:
        fp.write('\n'.join(L) + '\n')


def _pre_runs_legal(w, mask):
    wl = r.words_lookup; cba = r.alphabet.cba
    preset = set(range(W)) - set(mask)
    x = 0
    while x < W:
        if x not in preset:
            x += 1; continue
        x2 = x
        while x2 < W and x2 in preset:
            x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in wl:
            return False
        x = x2
    return True


from itertools import combinations
_FREE = [c for c in range(W) if c not in (0, 7, 14)]
def legal_masks(w):
    out = []
    for extra in combinations(_FREE, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if _pre_runs_legal(w, mask):
            out.append(mask)
    return out


# per-column vertical-gross table G[c][code] (same sound bound as n15_bigger_analytic) used to SKIP
# masks whose per-mask analytic UB <= LB (those are already CERTIFIED by the analytic argument; no
# xfill needed -- sound: vert_gross(c) <= G(c, w[c]) for every legal board).
def _build_G():
    lk = r.words_lookup
    tailmax = {}
    for ww in r.words:
        if len(ww) < 2 or len(ww) > HMAX or ww[1:] not in lk:
            continue
        tv = sum(int(r.scores[c]) for c in ww[1:])
        if tv > tailmax.get(ww[0], -1):
            tailmax[ww[0]] = tv
    G = [[0] * 27 for _ in range(W)]
    for c in range(W):
        for code in range(1, 27):
            if code in tailmax:
                G[c][code] = wm[c] * (lm[c] * int(r.scores[code]) + tailmax[code])
    return G

_G = None
def mask_ub(word, mask):
    global _G
    if _G is None:
        _G = _build_G()
    wc_ = r.alphabet.to_tup(word)
    return main_const(word, mask) + sum(_G[c][wc_[c]] for c in mask)


def reconstruct_board(word, board_codes):
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
    rules = construct_rules('dutch', B, word_file=WORD_FILE)
    Wr, Hr = rules.W, rules.H
    mask_b = [turn[x].isupper() for x in range(Wr)]
    blank, info = wc.derive_blanks(rules, grid, mask_b, Wr, Hr)
    if blank is None:
        return False, {'fail': 'no blank assignment', 'info': info}, None
    ok, rep = wc.check_witness(rules, Wr, Hr, grid, blank, mask_b,
                               claimed_total=claimed_total, require_center=True)
    # explicit reserve: board <= bag+blanks-1
    occ = sum(1 for y in range(Hr) for x in range(Wr) if grid[y][x] != 0)
    if occ > sum(rules.counts.values()) + rules.blank_count - 1:
        return False, {'fail': f'reserve: {occ} tiles too many'}, None
    spec = {'board': B, 'main_word': word, 'turn_str': turn, 'require_center': True,
            'lexicon': WORD_FILE, 'claimed_total': claimed_total, 'grid': grid}
    return ok, rep, spec


class Unit:
    __slots__ = ('word', 'mask', 'tag', 'vfloor', 'mainc', 'base', 'turn',
                 'proc', 'start', 'logf', 'verb_path')
    def __init__(self, word, mask, outdir):
        self.word = word; self.mask = mask
        self.mainc = main_const(word, mask)
        self.tag = '_'.join(str(c) for c in mask)
        self.turn = turn_str(word, mask)
        self.base = os.path.join(outdir, f'base_{word}_{self.tag}.txt')
        dump_base(build_base(word, self.turn, reserve=1), self.base)
        self.vfloor = None
        self.proc = None; self.start = None; self.logf = None
        self.verb_path = os.path.join(outdir, f'{word}_{self.tag}.verb')


def fmt_eta(secs):
    if secs < 0 or secs != secs:
        return '?'
    secs = int(secs); h, rem = divmod(secs, 3600); m, s = divmod(rem, 60)
    if h: return f'{h}h{m:02d}m'
    if m: return f'{m}m{s:02d}s'
    return f'{s}s'


def load_open_set(lb, openfile):
    """Read the analytic open set file (word\tUB\tmask) and return words with UB > lb."""
    words = []
    with open(openfile) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            w = parts[0].strip(); ub = int(parts[1])
            if ub > lb:
                words.append(w)
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=2050)
    ap.add_argument('--procs', type=int, default=2, help='concurrent xfill workers')
    ap.add_argument('--threads', type=int, default=int(os.environ.get('XFILL_THREADS', '8')),
                    help='threads PER xfill worker (XFILL_THREADS)')
    ap.add_argument('--wall', type=int, default=int(os.environ.get('WALL', '1800')))
    ap.add_argument('--outdir', type=str, default=os.path.join(ROOT, 'experiments/results/certs/n15_bigger'))
    ap.add_argument('--logfile', type=str, default=os.path.join(ROOT, 'experiments/results/n15_bigger_certify.log'))
    ap.add_argument('--openfile', type=str, default=os.path.join(ROOT, 'experiments/results/n15_bigger_open.txt'))
    ap.add_argument('--words', type=str, default='', help='comma list override (debug)')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    ensure_dict()
    logfp = open(args.logfile, 'a', buffering=1)
    def log(msg):
        line = f'[{time.strftime("%H:%M:%S")}] {msg}'
        print(line, flush=True); logfp.write(line + '\n')

    LB = args.lb
    procs = max(1, args.procs)
    log(f'=== N15 BIGGER VARMAX CERTIFY  LB={LB} procs={procs} threads/worker={args.threads} '
        f'wall={args.wall}s bin={BIN} ===')

    if args.words:
        open_words = [w.strip() for w in args.words.split(',') if w.strip()]
    else:
        open_words = load_open_set(LB, args.openfile)
    log(f'open set @ LB={LB}: {len(open_words)} words: {open_words}')

    resfp = open(os.path.join(args.outdir, 'verdicts.jsonl'), 'a', buffering=1)
    verdicts = {}
    units = []; ub_skipped = 0
    for w in open_words:
        for m in legal_masks(w):
            # SOUND mask-level prune: per-mask analytic UB <= LB => this mask cannot beat the LB
            # (vert_gross(c) <= G(c,w[c]) for every legal board), so it is CERTIFIED with no xfill.
            if mask_ub(w, m) <= LB:
                ub_skipped += 1
                tag = '_'.join(str(c) for c in m)
                rec = {'word': w, 'mask': list(m), 'verdict': 'CERT', 'note': 'mask-UB<=LB',
                       'lb_at': LB}
                verdicts[(w, tag)] = rec; resfp.write(json.dumps(rec) + '\n')
                continue
            units.append(Unit(w, m, args.outdir))
    total = len(units)
    log(f'WORK UNITS = {total} masks (per-mask UB>LB) over {len(open_words)} words; '
        f'{ub_skipped} masks analytically certified (UB<=LB)')

    pending = list(units); inflight = []; done = 0
    wall_times = []; new_lb_events = []

    def launch(u):
        u.vfloor = LB - u.mainc
        env = dict(os.environ)
        env['WALL'] = str(args.wall); env['XFILL_THREADS'] = str(args.threads)
        vf = open(u.verb_path, 'w'); u.logf = vf
        u.proc = subprocess.Popen([BIN, '--varmax', u.base, '--maxscore', str(u.vfloor), '--emit'],
                                  stdout=subprocess.PIPE, stderr=vf, text=True, env=env, cwd=ROOT)
        u.start = time.time(); inflight.append(u)

    def handle_completion(u, rc):
        nonlocal done, LB, open_words
        elapsed = time.time() - u.start
        try: u.logf.flush(); u.logf.close()
        except Exception: pass
        out, _ = u.proc.communicate()
        line = ''; board_codes = None
        for ln in (out or '').splitlines():
            ls = ln.strip()
            if ls.startswith(('LE ', 'MAX ', 'TO ', 'UNSAT', 'NOCAND')):
                line = ls
            elif ls.startswith('BOARD'):
                board_codes = [int(x) for x in ls.split()[1:]]
        nodes = None
        if 'nodes=' in line:
            try: nodes = int(line.split('nodes=')[1].split()[0])
            except Exception: nodes = None
        # detect a binary PANIC (frozen xfill underflows on letter-starved bigger instances): a
        # crash proves NOTHING -> OPEN_CRASH (sound: not treated as a certification).
        panicked = False
        try:
            with open(u.verb_path) as f:
                panicked = 'panicked' in f.read()
        except Exception:
            pass
        verdict = 'UNKNOWN'; value = None; note = ''
        if panicked and not line:
            verdict = 'OPEN_CRASH'; note = f'binary panic (rc={rc}) -> proves nothing'
        elif line.startswith('LE '):
            value = int(line.split()[1]); verdict = 'CERT'
            assert value == u.vfloor, f'LE {value} != vfloor {u.vfloor}'
        elif line.startswith('NOCAND'):
            verdict = 'CERT'; note = 'nocand'
        elif line.startswith('UNSAT'):
            verdict = 'CERT'; note = 'unsat'
        elif line.startswith('MAX '):
            value = int(line.split()[1]); total_score = u.mainc + value
            if total_score > LB:
                grid = reconstruct_board(u.word, board_codes)
                ok, rep, spec = run_witness(u.word, u.mask, grid, total_score)
                if ok:
                    verdict = 'NEW_LB'; note = f'total={total_score} WITNESS_OK'
                    fn = os.path.join(ROOT, f'experiments/results/turns/N15_bigger_best_{total_score}.json')
                    json.dump(spec, open(fn, 'w'))
                    new_lb_events.append((u.word, u.mask, total_score, fn)); LB = total_score
                    log(f'*** NEW VERIFIED LB = {LB} word={u.word} mask={u.mask} '
                        f'main_const={u.mainc} vert={value} saved {fn} ***')
                    open_words = load_open_set(LB, args.openfile)
                    log(f're-derived open set @ LB={LB}: {open_words}')
                else:
                    verdict = 'WITNESS_REJECT'; note = f'total={total_score} REJECTED: {rep.get("fail", rep)}'
                    log(f'!!! MAX {value} (total {total_score}) WITNESS REJECTED {u.word} {u.mask}: {note}')
            else:
                verdict = 'CERT'; note = f'max {value} <= vfloor {u.vfloor}'
        elif line.startswith('TO '):
            verdict = 'OPEN'; note = 'wall/deadline -> proves nothing'
        else:
            verdict = 'OPEN'; note = f'unparsed line: {line!r} rc={rc}'
        done += 1; wall_times.append(elapsed)
        rec = {'word': u.word, 'mask': list(u.mask), 'verdict': verdict, 'line': line,
               'vfloor': u.vfloor, 'main_const': u.mainc, 'nodes': nodes,
               'wall_s': round(elapsed, 2), 'note': note, 'lb_at': LB}
        verdicts[(u.word, u.tag)] = rec; resfp.write(json.dumps(rec) + '\n')
        remaining = len(pending) + len(inflight)
        avg = sum(wall_times) / len(wall_times); eta = avg * remaining / procs
        log(f'DONE {u.word} mask={u.mask} -> {verdict} {line.split("nodes=")[0].strip()} '
            f'nodes={nodes} wall={elapsed:.1f}s [{done}/{total}] LB={LB} ETA~{fmt_eta(eta)}')

    last_hb = time.time(); HB = 60
    while pending or inflight:
        while pending and len(inflight) < procs:
            u = pending.pop(0)
            if u.word not in open_words:
                rec = {'word': u.word, 'mask': list(u.mask), 'verdict': 'SKIP_CERTOUT',
                       'note': f'analytic-certified <= LB {LB}', 'lb_at': LB}
                verdicts[(u.word, u.tag)] = rec; resfp.write(json.dumps(rec) + '\n'); continue
            launch(u)
        time.sleep(1.0); now = time.time(); finished = []
        for u in inflight:
            rc = u.proc.poll()
            if rc is not None:
                finished.append((u, rc))
            elif now - u.start > args.wall + 30:
                # the frozen binary's own WALL deadline is UNRELIABLE on bigger instances (it does
                # not fire during the seed phase), so WE enforce the wall: kill this specific PID
                # (never a group / negative PID).  A killed-by-watchdog unit is OPEN (proves nothing).
                try:
                    u.proc.send_signal(signal.SIGTERM); time.sleep(2)
                    if u.proc.poll() is None: u.proc.kill()
                except Exception: pass
                log(f'WATCHDOG killed PID {u.proc.pid} ({u.word} {u.mask}) overran wall'); finished.append((u, -99))
        for u, rc in finished:
            inflight.remove(u); handle_completion(u, rc)
        if now - last_hb >= HB:
            last_hb = now; remaining = len(pending) + len(inflight)
            eta = (sum(wall_times)/len(wall_times)*remaining/procs) if wall_times else float('nan')
            infl = ' '.join(f'{u.word[:8]}:{u.tag}({now-u.start:.0f}s)' for u in inflight)
            log(f'HB [{done}/{total}] LB={LB} inflight={len(inflight)} pending={len(pending)} '
                f'ETA~{fmt_eta(eta)} :: {infl}')

    log('=== FINAL SUMMARY ===')
    byword = {}
    for (w, tag), rec in verdicts.items():
        byword.setdefault(w, []).append(rec)
    all_cert = True; open_residual = []
    for w in sorted(byword):
        recs = byword[w]
        cert = [x for x in recs if x['verdict'] in ('CERT', 'SKIP_CERTOUT')]
        openm = [x for x in recs if x['verdict'] == 'OPEN']
        rej = [x for x in recs if x['verdict'] == 'WITNESS_REJECT']
        new = [x for x in recs if x['verdict'] == 'NEW_LB']
        status = 'CERTIFIED <= LB' if not openm and not new and not rej else ('NEW_LB' if new else 'OPEN')
        if openm or rej: all_cert = False
        for x in openm: open_residual.append((w, tuple(x['mask']), x.get('nodes')))
        log(f'  {w}: {status} ({len(cert)} cert, {len(openm)} open, {len(new)} new-lb, {len(rej)} reject) of {len(recs)}')
    log(f'final LB = {LB}')
    for w, m, t, fn in new_lb_events:
        log(f'  NEW LB witness: {w} {m} total={t} -> {fn}')
    if all_cert and not open_residual:
        log(f'VERDICT: N15 dutch_bigger OPTIMUM PROVEN at LB={LB}.')
    elif open_residual:
        log(f'VERDICT: NOT PROVEN. OPEN residual = {len(open_residual)} masks: '
            + '; '.join(f'{w}{list(m)}(n={n})' for w, m, n in open_residual))
    logfp.close(); resfp.close()


if __name__ == '__main__':
    main()
