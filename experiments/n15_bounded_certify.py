"""N=15 bounded-band xfill certification for the 4 analytic-OPEN threat words.

For a word the analytic UB (n15_analytic_certify) exceeds 1952, so we must actually search.  We
enumerate, per legal mask, the HMAX-8-CAPPED band -- length-vectors with each newly-column length in
1..HMAX=8 whose optimistic per-column-best-gross UB exceeds the per-mask vertical floor vfloor =
LB - main_const(word,mask) -- and run `xfill --batchvec` over exactly those vectors.  Vectors with
any length > HMAX are infeasible (a board run > HMAX is illegal) and are correctly excluded; this is
the realizable band, vastly smaller than 35_certify's full-H superset (geschenkcheques 132k vs 32M).

A natural `LE` on every band vector of every mask => the word's verticals never reach vfloor =>
true max <= LB: CERTIFIED.  A `MAX m` with main_const+m > LB => a board beats the floor (NEW-LB,
re-witness).  A `TO` => OPEN (xfill could not close that slice in the wall).

Base file carries reserve=1 (the true bag); we pass --maxscore vfloor per vector.  Pass A short
wall resolves the cheap majority; survivors escalate to a long wall (pass C).

Single sequential process; xfill batchvec is itself single-threaded per chunk (we run one chunk).
"""
import sys, os, json, time, subprocess, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from scrabble import construct_rules, get_word_score
import xtest
import witness_check as wc
from n15_greedy_lb import candidate_masks
import n15_xfill_push as P

ROOT = '/home/bob/programming/scrabble4'
XFILL = f'{ROOT}/experiments/xfill_rs/target/release/xfill_lev3'
B = '15'; W = H = 15; HMAX = 8
r = construct_rules('dutch', B)
CDIR = f'{ROOT}/experiments/results/certs'


def best_at_capped(w, mask):
    """best_at[c][L] = max legal vertical gross at newly col c, length L in 1..HMAX (l=1 => 0).
    Independent recompute (stub a dict word; column multipliers via get_word_score placed=[i==0...])."""
    mt = r.alphabet.to_tup(w); lk = r.words_lookup
    best_at = {}
    for c in mask:
        code = mt[c]; d = {1: 0}
        for ww in r.words:
            if not ww or ww[0] != code or len(ww) < 2 or len(ww) > HMAX:
                continue
            if ww[1:] not in lk:
                continue
            g = int(get_word_score(r, ww, c, 0, 0, [i == 0 for i in range(len(ww))])[0])
            if g > d.get(len(ww), -1):
                d[len(ww)] = g
        best_at[c] = d
    return best_at


def enum_capped_band(best_at, mask, vfloor):
    """All length-vectors (per mask col, length in keys of best_at[c]) whose optimistic UB
    (sum of per-col best gross) > vfloor, under the weak bag budget sum(l-1) <= bag_total - W.
    No center forcing (sound superset).  Recursive with suffix-max pruning."""
    total = sum(r.counts.values()) + r.blank_count
    stub_budget = total - W
    cols = list(mask)
    opts = [[(L, best_at[c][L]) for L in sorted(best_at[c])] for c in cols]
    sufmax = [0] * (len(opts) + 1)
    for i in range(len(opts) - 1, -1, -1):
        sufmax[i] = sufmax[i + 1] + max(g for _, g in opts[i])
    out = []; vec = [0] * len(opts)

    def rec(i, used, gross):
        if gross + sufmax[i] <= vfloor:
            return
        if i == len(opts):
            out.append(tuple(vec)); return
        for L, g in opts[i]:
            if used + (L - 1) > stub_budget:
                continue
            vec[i] = L; rec(i + 1, used + (L - 1), gross + g)
        vec[i] = 0
    rec(0, 0, 0)
    return out


def run_batchvec(base_path, keys_floor, wall, chunk=4000):
    """keys_floor: list of (key, lvec_tuple, vfloor).  Returns dict key -> RES line.
    Chunked so no single subprocess timeout is astronomically large; per-instance wall = `wall`
    (almost all vectors are root-pruned in ms; only the rare hard slice hits `wall`)."""
    out = {}
    for ci in range(0, len(keys_floor), chunk):
        part = keys_floor[ci:ci + chunk]
        lf = base_path + '.list'
        with open(lf, 'w') as f:
            for key, lvec, vfloor in part:
                f.write(f"{key} {' '.join(map(str, lvec))} {vfloor}\n")
        env = dict(os.environ); env.pop('MAXNODES', None); env['BATCHWALL'] = str(wall)
        sub_to = min(86400, int((wall + 2) * len(part) + 120))   # <= 24h/chunk ceiling
        p = subprocess.run([XFILL, '--batchvec', base_path, lf], capture_output=True, text=True,
                           env=env, cwd=ROOT, timeout=sub_to)
        for line in (p.stdout or '').splitlines():
            t = line.split(None, 2)
            if len(t) == 3 and t[0] == 'RES':
                out[t[1]] = t[2]
    return out


def certify_word(w, lb, wall_a, wall_c):
    masks = candidate_masks(w, limit=200)
    print(f"## {w}: {len(masks)} legal masks, LB={lb}", flush=True)
    wdir = f'{CDIR}/n15bound_{w}'; os.makedirs(wdir, exist_ok=True)
    # one base file per (word, mask-turn) -- the base depends only on the scoring columns (mask).
    word_status = 'CERTIFIED'
    refute = None
    for mi, mask in enumerate(masks):
        mc = P.main_const(w, mask); vfloor = lb - mc
        ba = best_at_capped(w, mask)
        band = enum_capped_band(ba, mask, vfloor)
        if not band:
            print(f"  mask {mask}: capped band EMPTY (UB<=vfloor {vfloor}) -> certified", flush=True)
            continue
        turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(w))
        base = xtest.build_base(B, w, turn, scale=False, reserve=1)
        bpath = f'{wdir}/base_{"_".join(map(str, mask))}.txt'
        xtest.dump_base(base, bpath)
        kf = [('-'.join(map(str, v)), v, vfloor) for v in band]
        t0 = time.time()
        res = run_batchvec(bpath, kf, wall_a)
        tos = []
        for key, lvec, vf in kf:
            line = res.get(key, '')
            tk = line.split()
            if tk and tk[0] == 'LE' and tk[1].isdigit() and int(tk[1]) <= vf:
                pass
            elif tk and tk[0] == 'MAX':
                mx = int(tk[1]); tot = mc + mx
                if tot > lb:
                    refute = (mask, lvec, tot)
                    print(f"  !!! MAX {mx} on {key} mask={mask} -> total {tot} > LB {lb}", flush=True)
                    break
            elif line == 'NOCAND':
                pass
            else:
                tos.append((key, lvec, vf))
        if refute:
            word_status = 'NEW-LB'; break
        # escalate TOs to long wall
        if tos:
            res2 = run_batchvec(bpath, tos, wall_c)
            for key, lvec, vf in tos:
                line = res2.get(key, ''); tk = line.split()
                if tk and tk[0] == 'LE' and tk[1].isdigit() and int(tk[1]) <= vf:
                    continue
                if tk and tk[0] == 'MAX':
                    mx = int(tk[1]); tot = mc + mx
                    if tot > lb:
                        refute = (mask, lvec, tot); word_status = 'NEW-LB'
                        print(f"  !!! (passC) MAX {mx} {key} -> {tot} > {lb}", flush=True); break
                    continue
                if line == 'NOCAND':
                    continue
                word_status = 'OPEN'
                print(f"  mask {mask} key {key}: {line or 'TO'} (vfloor {vf}) -> OPEN", flush=True)
        if refute:
            break
        print(f"  mask {mask}: band={len(band)} closed (LE/NOCAND), {time.time()-t0:.0f}s "
              f"[status so far {word_status}]", flush=True)
    print(f"## {w}: WORD VERDICT = {word_status}"
          f"{'  refute='+str(refute) if refute else ''}", flush=True)
    return word_status, refute


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=1952)
    ap.add_argument('--wall-a', type=float, default=3.0)
    ap.add_argument('--wall-c', type=float, default=300.0)
    ap.add_argument('--words', type=str,
                    default='jacquardmachine,chequeformulier,flauwekulexcuus,geschenkcheques')
    a = ap.parse_args()
    summary = {}
    for w in a.words.split(','):
        st, ref = certify_word(w, a.lb, a.wall_a, a.wall_c)
        summary[w] = st
    print("=== SUMMARY ===", flush=True)
    for w, st in summary.items():
        print(f"  {w}: {st}", flush=True)
