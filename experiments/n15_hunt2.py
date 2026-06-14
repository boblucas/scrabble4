"""N=15 LB hunt -- CORRECT model. The optimal play is a high-value main word scored x27 (newly-placed
on the three x3 cols 0/7/14) with productive x2 letters on cols 3/11, the newly-placed columns EMPTY
(no verticals => no cross-word constraint, trivially legal), and ONLY col7 carrying a vertical to
reach the center (7,7).  No forced verticals on the other columns (that was the earlier mistake).

Rank legal 15-letter words by x27 main, then witness the top: scoring mask = {0,3,7,11,14}+2 (bingo),
Lvec=1 (bare tile, no vertical) for all except col7 (len 8 -> reaches center row 7). xfill --emit +
witness_check (full-rules score incl. x27 multipliers, center occupancy, bag, reserve=1).
Single sequential process (no parallelism / group-kill).
"""
import sys, os, time, subprocess, json
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import xtest, witness_check as wc
from scrabble import construct_rules
import numpy as np

ROOT = '/home/bob/programming/scrabble4'
XFILL = f'{ROOT}/experiments/xfill_rs/target/release/xfill_lev3'
B = '15'; r = construct_rules('dutch', B); W = H = 15
val = {chr(96+i): r.scores[i] for i in range(1, 27)}

def x27main(w):
    return 27*(sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50

def scoring_mask(w):
    base = {0, 3, 7, 11, 14}
    extra = sorted((p for p in range(15) if p not in base), key=lambda p: val[w[p]], reverse=True)[:2]
    return sorted(base | set(extra))

def witness(word, floor, wall):
    mask = scoring_mask(word)
    lv = {c: (8 if c == 7 else 1) for c in mask}
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(word))
    res = xtest.build_instance(B, word, turn, lv, scale=False, reserve=1)
    if res[0] is None:
        return ('build_None', None)
    inst, meta = res
    tmp = f'/home/bob/.claude/jobs/f990c408/tmp/n15h2_inst.txt'
    xtest.dump_simple(inst, 0, tmp)
    env = dict(os.environ); env['WALL'] = str(wall)
    p = subprocess.run([XFILL, tmp, '--maxscore', str(floor), '--emit'],
                       capture_output=True, text=True, env=env, timeout=wall+30)
    resline = next((l for l in p.stdout.splitlines() if l[:2] in ('MA','LE','TO','UN')), '')
    bl = next((l for l in p.stdout.splitlines() if l.startswith('BOARD')), '')
    if not bl:
        return (f'no-board[{resline}]', None)
    codes = [int(t) for t in bl.split()[1:]]
    grid = [[codes[y*W+x] for x in range(W)] for y in range(H)]
    mt = r.alphabet.to_tup(word)
    for x in range(W): grid[0][x] = int(mt[x])
    r2 = construct_rules('dutch', B)
    mb = [turn[x].isupper() for x in range(W)]
    blank, info = wc.derive_blanks(r2, grid, mb, W, H)
    if blank is None: return (f'blank_fail[{info}]', None)
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mb, claimed_total=None, require_center=True)
    if not ok: return (f'REJECT[{rep.get("fail")}]', None)
    return ('OK', (int(rep['total']), turn, mask, grid, rep))

def main():
    words = [w for w in r.words_str if len(w) == 15]
    top = sorted(words, key=x27main, reverse=True)[:40]
    best = 0; best_word = None
    for w in top:
        try:
            tag, res = witness(w, floor=max(0, best-1), wall=40)
        except Exception as e:
            print(f"  {w} (x27main={x27main(w)}): ERR {e}", flush=True); continue
        if res:
            tot = res[0]
            mark = "NEWBEST" if tot > best else "ok"
            print(f"  [{mark}] {w} x27main={x27main(w)} -> verified TOTAL={tot} mask={res[2]}", flush=True)
            if tot > best:
                best = tot; best_word = w
                json.dump({'board': B, 'main_word': w, 'turn_str': res[1], 'require_center': True,
                           'claimed_total': tot, 'grid': res[3]},
                          open(f'{ROOT}/experiments/results/turns/N15_best_{tot}.json', 'w'))
        else:
            print(f"  {w} (x27main={x27main(w)}): {tag}", flush=True)
    print(f"# DONE best verified N=15 LB = {best} ({best_word})", flush=True)

if __name__ == '__main__':
    main()
