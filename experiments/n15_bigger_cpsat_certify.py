#!/usr/bin/env python3
"""N=15 BIGGER-lexicon CP-SAT certification driver (sound, connectivity-respecting).

The frozen xfill binary UNDERFLOWS (panics) on letter-starved bigger instances (recyclingcyclus,
recyclagecyclus) and its WALL deadline is unreliable on others.  CP-SAT decides the EXACT full-turn
model (the same model the incumbent maximizes, with full center-connectivity, bag, reserve=1, blanks)
and -- crucially -- proves the connector-INFEASIBLE words in <1s, which is precisely the family xfill
crashes on.

Per (word, mask) with per-mask analytic UB > LB (others are analytically certified):
  build the v2 full-turn model, add  obj >= (LB - main_const) + 1  (i.e. total > LB), ask for ANY
  feasible board:
    INFEASIBLE (natural, not TO)  -> CERTIFIED <= LB for this mask (sound: no legal board beats LB).
    OPTIMAL/FEASIBLE              -> a board BEATS LB: reconstruct, witness_check (require_center,
                                     reserve=1); if ok RAISE LB, save N15_bigger_best_<total>.json.
    UNKNOWN (time limit)          -> OPEN (proves nothing).

A TO proves nothing; a board is a verified LB ONLY if witness_check ok=True.  The LB is PROVEN
optimal ONLY if every UB>LB mask certifies natural INFEASIBLE (or a higher board is found and the
process repeats to closure).

Single sequential process (the CP-SAT solver itself uses CPSAT_WORKERS threads).  Process-kill safe.
"""
import sys, os, json, time, argparse
from collections import Counter
from itertools import combinations
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from ortools.sat.python import cp_model

import n15_bigger_v2 as V          # bigger-lexicon full-turn model + helpers
import n15_bigger_incumbent as I   # build_model / verify (word_file-threaded)

ROOT = '/home/bob/programming/scrabble4'
B = '15'; W = H = 15; HMAX = 8
WORD_FILE = V.WORD_FILE
r = V.r
val = V.val
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


# G table for the per-mask UB prune (same sound bound as the analytic certifier)
def _build_G():
    lk = r.words_lookup; tailmax = {}
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
_G = _build_G()


def mask_ub(word, mask):
    wc_ = r.alphabet.to_tup(word)
    return main_const(word, mask) + sum(_G[c][wc_[c]] for c in mask)


def _pre_runs_legal(w, mask):
    wl = r.words_lookup; cba = r.alphabet.cba
    preset = set(range(W)) - set(mask); x = 0
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
_FREE = [c for c in range(W) if c not in (0, 7, 14)]
def legal_masks(w):
    return [tuple(sorted((0, 7, 14) + e)) for e in combinations(_FREE, 4)
            if _pre_runs_legal(w, tuple(sorted((0, 7, 14) + e)))]


def load_open_words(lb, openfile):
    out = []
    for line in open(openfile):
        if line.startswith('#') or not line.strip():
            continue
        p = line.split('\t')
        if int(p[1]) > lb:
            out.append(p[0].strip())
    return out


def certify_mask(word, mask, lb, cap, workers):
    """Returns (verdict, info).  verdict in {CERT, NEW_LB, OPEN}."""
    mc = main_const(word, mask); need = (lb - mc) + 1     # obj >= need <=> total > lb
    M = I.build_model(word, mask, rows=9)
    M['m'].add(M['obj'] >= int(need))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = workers
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(M['m'])
    if st == cp_model.INFEASIBLE:
        return 'CERT', {'note': 'cpsat INFEASIBLE -> no board > LB for this mask'}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = I._grid_from_solver(s, M['cells'], M['mt'])
        obj = int(s.value(M['obj'])); total = mc + obj
        ok, vtotal, rep = I.verify(word, mask, grid)
        if ok and vtotal > lb:
            return 'NEW_LB', {'total': vtotal, 'grid': grid, 'obj': obj, 'rep': rep}
        return 'OPEN', {'note': f'feasible obj={obj} total={total} but witness ok={ok} vtotal={vtotal}'}
    return 'OPEN', {'note': 'cpsat UNKNOWN/TO -> proves nothing'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=2053)
    ap.add_argument('--cap', type=float, default=float(os.environ.get('CAP', '120')))
    ap.add_argument('--workers', type=int, default=int(os.environ.get('CPSAT_WORKERS', '8')))
    ap.add_argument('--openfile', default=os.path.join(ROOT, 'experiments/results/n15_bigger_open.txt'))
    ap.add_argument('--logfile', default=os.path.join(ROOT, 'experiments/results/n15_bigger_cpsat_certify.log'))
    ap.add_argument('--words', default='', help='comma override')
    ap.add_argument('--max-masks', type=int, default=0, help='cap UB>LB masks per word (0=all)')
    a = ap.parse_args()
    logfp = open(a.logfile, 'a', buffering=1)
    def log(m):
        line = f'[{time.strftime("%H:%M:%S")}] {m}'; print(line, flush=True); logfp.write(line + '\n')

    LB = a.lb
    open_words = [w.strip() for w in a.words.split(',') if w.strip()] if a.words \
        else load_open_words(LB, a.openfile)
    log(f'=== N15 BIGGER CP-SAT CERTIFY LB={LB} cap={a.cap}s workers={a.workers} ===')
    log(f'open words @ LB={LB}: {len(open_words)}: {open_words}')

    resfp = open(os.path.join(ROOT, 'experiments/results/certs/n15_bigger/cpsat_verdicts.jsonl'), 'a', buffering=1)
    os.makedirs(os.path.join(ROOT, 'experiments/results/certs/n15_bigger'), exist_ok=True)

    word_status = {}
    for w in open_words:
        masks = [m for m in legal_masks(w) if mask_ub(w, m) > LB]
        masks.sort(key=lambda m: -mask_ub(w, m))
        if a.max_masks:
            masks = masks[:a.max_masks]
        log(f'--- {w}: {len(masks)} masks UB>LB ---')
        w_open = []; w_cert = 0
        for m in masks:
            if mask_ub(w, m) <= LB:       # may have been raised mid-run
                w_cert += 1; continue
            t0 = time.time()
            verdict, info = certify_mask(w, m, LB, a.cap, a.workers)
            dt = time.time() - t0
            rec = {'word': w, 'mask': list(m), 'verdict': verdict, 'ub': mask_ub(w, m),
                   'main_const': main_const(w, m), 'wall_s': round(dt, 1),
                   'note': info.get('note', ''), 'lb_at': LB}
            resfp.write(json.dumps(rec) + '\n')
            if verdict == 'CERT':
                w_cert += 1
                log(f'  {w} mask={list(m)} -> CERT (INFEASIBLE) {dt:.1f}s')
            elif verdict == 'NEW_LB':
                total = info['total']
                fn = os.path.join(ROOT, f'experiments/results/turns/N15_bigger_best_{total}.json')
                turn = ''.join(c.upper() if i in set(m) else c.lower() for i, c in enumerate(w))
                spec = {'board': B, 'main_word': w, 'turn_str': turn,
                        'require_center': True, 'lexicon': WORD_FILE, 'claimed_total': total,
                        'grid': info['grid']}
                json.dump(spec, open(fn, 'w'))
                log(f'  *** NEW VERIFIED LB = {total} word={w} mask={list(m)} saved {fn} ***')
                LB = total
                open_words = load_open_words(LB, a.openfile)
            else:
                w_open.append(list(m))
                log(f'  {w} mask={list(m)} -> OPEN ({info.get("note","")}) {dt:.1f}s')
        word_status[w] = ('CERTIFIED' if not w_open else 'OPEN', w_cert, w_open)

    log('=== FINAL SUMMARY ===')
    all_cert = True
    for w in open_words if False else word_status:
        st, nc, wo = word_status[w]
        if wo:
            all_cert = False
        log(f'  {w}: {st} ({nc} masks CERT, {len(wo)} masks OPEN)')
    log(f'final LB = {LB}')
    if all_cert:
        log(f'VERDICT: every UB>LB mask of every open word certified INFEASIBLE -> N15 dutch_bigger '
            f'OPTIMUM PROVEN at LB={LB}.')
    else:
        openw = [w for w, (st, _, wo) in word_status.items() if wo]
        log(f'VERDICT: NOT PROVEN. words with OPEN masks: {openw}')
    logfp.close(); resfp.close()


if __name__ == '__main__':
    main()
