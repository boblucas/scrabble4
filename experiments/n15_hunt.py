"""N=15 witness hunt (first verified center-connected LB). Sequential, single-process, no parallelism
(process-kill safety: NO xargs / setsid / group-kill).

N=15: x3 word cols 0/7/14, x2 letter cols 3/11, center (7,7), HMAX=8, reserve=1 (opponent tile).
Center (7,7) must be occupied & connected -> col7 (=center) gets a length-8 vertical (reaches row 7).
We try several 7-col scoring masks that INCLUDE col7, ranked: capturing col0 too => x9 main (but
non-contiguous -> may explode xfill); contiguous {1..7} => x3 main (tractable). For each (mask,word)
we run xfill --emit with a short wall and capture the incumbent (incl. TO), verify with witness_check,
and keep the best verified TOTAL.
"""
import sys, os, time, subprocess, json
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import xtest, witness_check as wc
from scrabble import construct_rules
import numpy as np
from collections import Counter

ROOT = '/home/bob/programming/scrabble4'
XFILL = f'{ROOT}/experiments/xfill_rs/target/release/xfill_lev3'
B = '15'; r = construct_rules('dutch', B); W = H = 15
val = {chr(96+i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
bucket = xtest._cand_bucket(r, B)
n15 = [w for w in r.words_str if len(w) == 15]

# masks (all include col7=center). lvec: col0/col7/col14 long (8), others short (2).
MASKS = [
    (1, 2, 3, 4, 5, 6, 7),        # contiguous, x3 (col7 only) -- tractable baseline
    (0, 1, 2, 3, 4, 6, 7),        # x9 (col0+col7), gap at col5  (col7 adjacent col6)
    (0, 1, 2, 3, 4, 5, 7),        # x9, gap at col6
    (7, 8, 9, 10, 11, 12, 13),    # mirror contiguous x3
]
def lvec_for(mask):
    return {c: (8 if c in (0, 7, 14) else 2) for c in mask}

def main_proxy(w, mask):
    ms = set(mask); WM = 1
    for x in mask: WM *= wm[x]
    return WM*(sum(val[w[x]]*(lm[x] if x in ms else 1) if x in ms else val[w[x]] for x in range(W)))+50

def buildable(w, mask, lv):
    return all(bucket.get((ord(w[c])-96, lv[c])) for c in mask)

def witness(word, mask, floor, wall):
    lv = lvec_for(mask)
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(word))
    inst, meta = xtest.build_instance(B, word, turn, lv, scale=False, reserve=1)
    if inst is None: return None
    tmp = f'/home/bob/.claude/jobs/f990c408/tmp/n15_inst.txt'
    xtest.dump_simple(inst, 0, tmp)
    env = dict(os.environ); env['WALL'] = str(wall)
    p = subprocess.run([XFILL, tmp, '--maxscore', str(floor), '--emit'],
                       capture_output=True, text=True, env=env, timeout=wall+30)
    bl = next((l for l in p.stdout.splitlines() if l.startswith('BOARD')), '')
    if not bl: return None
    codes = [int(t) for t in bl.split()[1:]]
    grid = [[codes[y*W+x] for x in range(W)] for y in range(H)]
    mt = r.alphabet.to_tup(word)
    for x in range(W): grid[0][x] = int(mt[x])
    r2 = construct_rules('dutch', B)
    mask_b = [turn[x].isupper() for x in range(W)]
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None: return None
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    if not ok: return None
    return int(rep['total']), turn, lv, grid

def main():
    best = 0; best_info = None
    for mask in MASKS:
        lv = lvec_for(mask)
        cands = sorted((w for w in n15 if buildable(w, mask, lv)), key=lambda w: main_proxy(w, mask), reverse=True)[:8]
        print(f"# mask {mask}: top candidates {[(main_proxy(w,mask),w) for w in cands[:4]]}", flush=True)
        for w in cands:
            floor = max(0, best - main_proxy(w, mask) + main_proxy(w, mask) - best) if False else 0
            try:
                res = witness(w, mask, floor=max(0, best - 1) if best else 0, wall=20)
            except Exception as e:
                print(f"  {w} mask={mask}: ERR {e}", flush=True); continue
            if res:
                tot = res[0]
                tag = "NEWBEST" if tot > best else "ok"
                print(f"  [{tag}] {w} mask={mask} TOTAL={tot}", flush=True)
                if tot > best:
                    best = tot; best_info = res
                    json.dump({'board': B, 'main_word': w, 'turn_str': res[1], 'require_center': True,
                               'claimed_total': tot, 'grid': res[3]},
                              open(f'{ROOT}/experiments/results/turns/N15_best_{tot}.json', 'w'))
            else:
                print(f"  {w} mask={mask}: no witness (explode/infeasible)", flush=True)
    print(f"# DONE best N15 verified LB = {best}", flush=True)

if __name__ == '__main__':
    main()
