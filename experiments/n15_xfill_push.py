"""N=15 LB push + per-(word,mask,Lvec) certification driver using the xfill engine.

PART A (push): for each threat word, enumerate legal masks (n15_greedy_lb._pre_runs_legal /
candidate_masks), pick a per-column-greedy length-vector (each newly col independently takes the
length 1..8 maximising its best candidate gross from xtest._cand_bucket), build the instance, run
    xfill --maxscore (TARGET - main_const) --emit   (TARGET defaults to current floor)
A natural MAX gives the exact slice max (total = main_const + MAX); a TO-incumbent BOARD that beats
the floor is reconstructed, witness_check'd (require_center=True, reserve=1), and kept if ok.  Any
verified total > floor RAISES the LB and is saved to results/turns/N15_best_<total>.json.

SOUNDNESS: a total is reported VERIFIED only when witness_check returns ok=True.  MAX/LE verdicts
are trusted only from natural (non-WALL) completion (xfill prints MA/LE for those; a WALL abort
prints TO and proves nothing -- we only use its BOARD incumbent as a candidate to re-verify).

Single sequential process (process-kill safety: NO parallelism / group kills / setsid).
"""
import sys, os, json, time, subprocess, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from scrabble import construct_rules, get_word_score
import xtest
import witness_check as wc
from n15_greedy_lb import candidate_masks, _pre_runs_legal, x27_proxy

ROOT = '/home/bob/programming/scrabble4'
XFILL = f'{ROOT}/experiments/xfill_rs/target/release/xfill_lev3'
TMP = '/home/bob/.claude/jobs/f990c408/tmp'
os.makedirs(TMP, exist_ok=True)
B = '15'; W = H = 15
r = construct_rules('dutch', B)
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
bucket = xtest._cand_bucket(r, B)


def main_const(w, mask):
    """Exact main-word turn score for this mask (x27 on 0/7/14, x2 letter on newly 3/11, +50 bingo).
    Identical to n15_greedy_lb.true_proxy but recomputed locally from the multiplier rows."""
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


def best_gross_at(c, L, length):
    """Max candidate gross for column c (row-0 letter code L) at vertical length `length`."""
    bg = 0
    for ww in bucket.get((L, length), ()):
        g = 0 if len(ww) == 1 else int(get_word_score(r, ww, c, 0, 0,
                                                       [i == 0 for i in range(len(ww))])[0])
        if g > bg:
            bg = g
    return bg


def greedy_lvec(w, mask, maxlen=8):
    """Per-column-greedy length-vector: each newly col independently takes the length maximising its
    best candidate gross.  Returns (lvec dict over mask, ub = main_const + sum of per-col best gross)."""
    mt = r.alphabet.to_tup(w)
    lv = {}; ub_v = 0
    for c in mask:
        L = mt[c]; best = (1, 0)
        for length in range(1, maxlen + 1):
            bg = best_gross_at(c, L, length)
            if bg > best[1]:
                best = (length, bg)
        lv[c] = best[0]; ub_v += best[1]
    return lv, main_const(w, mask) + ub_v


def run_xfill(w, mask, lv, floor, wall, emit=True):
    """Run xfill --maxscore floor on (w, mask, lv).  Returns (verdict, value, board_codes_or_None).
    verdict in {MAX, LE, TO, UN, NONE}; value is the int after MAX/LE (None otherwise)."""
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(w))
    inst, meta = xtest.build_instance(B, w, turn, lv, scale=False, reserve=1)
    if inst is None:
        return ('NOCAND', None, None)
    tmp = f'{TMP}/push_inst.txt'
    xtest.dump_simple(inst, 'UNKNOWN', tmp)
    env = dict(os.environ); env['WALL'] = str(wall); env.pop('MAXNODES', None)
    cmd = [XFILL, tmp, '--maxscore', str(floor)] + (['--emit'] if emit else [])
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=wall + 60, cwd=ROOT)
    verdict, value, board = 'NONE', None, None
    for line in p.stdout.splitlines():
        t = line.split()
        if not t:
            continue
        if t[0] in ('MA', 'MAX'):
            verdict, value = 'MAX', int(t[1])
        elif t[0] == 'LE':
            verdict, value = 'LE', int(t[1])
        elif t[0] in ('TO',):
            if verdict == 'NONE':
                verdict = 'TO'
        elif t[0] in ('UN', 'UNSAT'):
            if verdict == 'NONE':
                verdict = 'UN'
        elif t[0] == 'BOARD':
            board = [int(x) for x in t[1:]]
    return (verdict, value, board)


def verify_board(w, mask, board):
    """Reconstruct grid (row 0 = full main word) and witness_check it.  Returns (ok, total, rep)."""
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(w))
    grid = [[board[y * W + x] for x in range(W)] for y in range(H)]
    mt = r.alphabet.to_tup(w)
    for x in range(W):
        grid[0][x] = int(mt[x])
    r2 = construct_rules('dutch', B)
    mask_b = [turn[x].isupper() for x in range(W)]
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None,
                               require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def save_witness(w, mask, total, board):
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(w))
    grid = [[board[y * W + x] for x in range(W)] for y in range(H)]
    mt = r.alphabet.to_tup(w)
    for x in range(W):
        grid[0][x] = int(mt[x])
    path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
    json.dump({'board': B, 'main_word': w, 'turn_str': turn, 'require_center': True,
               'claimed_total': total, 'grid': grid}, open(path, 'w'))
    return path


def push(words, floor, wall, masks_per_word, alt_lvecs=False):
    """For each word try its top masks' greedy length-vectors; keep the best verified total."""
    best = floor; best_blob = None
    for w in words:
        masks = candidate_masks(w, limit=masks_per_word)
        if not masks:
            print(f"# {w}: NO LEGAL MASK", flush=True)
            continue
        for mask in masks:
            lv, ub = greedy_lvec(w, mask)
            if ub <= best:
                print(f"  {w} mask={mask}: greedy UB {ub} <= best {best}, skip", flush=True)
                continue
            mc = main_const(w, mask)
            target_floor = best - mc          # certify total <= best  <=>  xfill <= best - mc
            t0 = time.time()
            try:
                verdict, value, board = run_xfill(w, mask, lv, target_floor, wall)
            except subprocess.TimeoutExpired:
                print(f"  {w} mask={mask}: subprocess TIMEOUT (>{wall+60}s)", flush=True)
                continue
            dt = time.time() - t0
            total_max = (mc + value) if (verdict == 'MAX') else None
            print(f"  {w} mask={mask} lv={[lv[c] for c in mask]} mc={mc} greedyUB={ub} "
                  f"-> {verdict} {value} (slice_max_total={total_max}) {dt:.0f}s", flush=True)
            # verify any incumbent board that could beat best
            if board is not None:
                ok, total, rep = verify_board(w, mask, board)
                if ok and total > best:
                    p = save_witness(w, mask, total, board)
                    print(f"    [NEWBEST] VERIFIED total={total} (was {best}) saved {p}", flush=True)
                    best = total; best_blob = {'word': w, 'mask': mask, 'lv': [lv[c] for c in mask],
                                               'total': total, 'path': p}
                elif ok:
                    print(f"    verified total={total} (<= best {best})", flush=True)
                else:
                    print(f"    board REJECTED by witness_check: {rep.get('fail')}", flush=True)
    print(f"# DONE push: best verified LB = {best}"
          f"{' (' + best_blob['word'] + ')' if best_blob else ''}", flush=True)
    return best, best_blob


THREAT_WORDS = [  # descending tight_UB (N15_THREAT_REPORT.md)
    'geschenkcheques', 'flauwekulexcuus', 'chequeformulier', 'cultuurchequeje',
    'jacquardmachine', 'bouwcuratrixjes', 'chemsexpartytje', 'chequebedragjes',
    'craqueleachtigs', 'quichebuffetjes', 'babyglimlachjes', 'cliquetsystemen',
    'wetenschapsquiz', 'schuurschijfjes', 'dyscalculischen', 'craqueleachtige',
    'textielcyclusje', 'aliquotvleugels', 'jacquardweefsel', 'yoghurtcultures',
    'upcyclestertjes', 'vluchtreflexjes', 'playboyachtigst', 'perscommuniques',
    'chiquelingetjes', 'quicheachtigers',
]

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--floor', type=int, default=1952)
    ap.add_argument('--wall', type=int, default=180)
    ap.add_argument('--masks', type=int, default=6)
    ap.add_argument('--words', type=str, default='', help='comma-separated; default = all threats')
    a = ap.parse_args()
    ws = a.words.split(',') if a.words else THREAT_WORDS
    push(ws, a.floor, a.wall, a.masks)
