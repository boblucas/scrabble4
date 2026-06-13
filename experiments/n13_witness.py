"""N=13 center-connected witness driver (WITNESS-FIRST phase helper, read-only on shared tooling).

For a chosen main word + placement mask (turn_str) + length-vector, build the per-vector instance
via xtest.build_instance, run the FAST Rust inner `xfill --maxscore <floor> --emit` (which handles
connectivity / bridges / legality and emits a guaranteed-legal best board with vertical score >
floor), then assemble a witness JSON in the canonical `grid` form, run it through the INDEPENDENT
witness_check.py, and (if OK) save it.

The center constraint is captured exactly as 35_certify's --center mode does it: the center column
(W//2) must be a scoring column whose vertical length reaches the center row (>= H//2 + 1).  This
driver ENFORCES that precondition (errors otherwise) so every emitted board is center-occupying;
witness_check independently re-verifies center occupancy.

Usage:
  python experiments/n13_witness.py --main <13-letter word> --turn <TURN_STR> \
        --lvec l0,l1,...  --floor <F>  [--wall 120] [--out path.json] [--name tag]
  (lvec is given over the SCORING columns in left-to-right order.)

Exit 0 + 'WITNESS OK ...' with the recomputed total on success.
"""
import sys, os, json, subprocess, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
import xtest
import witness_check as wc
from scrabble import construct_rules

XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_lev3')
if not os.path.exists(XFILL):
    XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_frozen')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', required=True)
    ap.add_argument('--turn', required=True)
    ap.add_argument('--lvec', required=True, help='comma-separated lengths over scoring cols L-to-R')
    ap.add_argument('--floor', type=int, required=True, help='emit best board with vert score > floor')
    ap.add_argument('--wall', type=float, default=120.0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--name', default=None)
    ap.add_argument('--board', default='13')
    ap.add_argument('--reserve', type=int, default=1,
                    help='tiles reserved for the opponent (>=1): total setup tiles <= sum(counts)+blanks-reserve')
    ap.add_argument('--no-center-check', action='store_true')
    a = ap.parse_args()

    rules = construct_rules('dutch', a.board)
    W, H = rules.W, rules.H
    assert len(a.main) == W and len(a.turn) == W, f'main/turn must be length {W}'
    scoring = [x for x in range(W) if a.turn[x].isupper()]
    lvals = [int(t) for t in a.lvec.split(',')]
    assert len(lvals) == len(scoring), f'lvec has {len(lvals)} entries, {len(scoring)} scoring cols'
    Lvec = {c: l for c, l in zip(scoring, lvals)}
    cc, cr = W // 2, H // 2
    if not a.no_center_check:
        if cc not in scoring:
            sys.exit(f'CENTER PRECONDITION FAIL: center col {cc} is not a scoring column in turn_str')
        if Lvec[cc] < cr + 1:
            sys.exit(f'CENTER PRECONDITION FAIL: center col {cc} length {Lvec[cc]} < {cr+1} '
                     f'(must reach center row {cr})')

    xtest.write_dict(a.board)
    inst, meta = xtest.build_instance(a.board, a.main, a.turn, Lvec, scale=True, reserve=a.reserve)
    if inst is None:
        sys.exit('INFEASIBLE length-vector: a scoring column has NO candidate vertical of its length')
    # ground-truth (for the score recompute) lives in build_instance; dump for the Rust inner
    tmp = os.path.join(ROOT, 'experiments/xtests', f'n13_wit_{a.name or "tmp"}.txt')
    xtest.dump_simple(inst, None, tmp)

    env = dict(os.environ); env.pop('MAXNODES', None); env['WALL'] = str(a.wall)
    print(f'running inner: {os.path.basename(XFILL)} --maxscore {a.floor} --emit  (wall {a.wall}s)',
          flush=True)
    r = subprocess.run([XFILL, tmp, '--maxscore', str(a.floor), '--emit'],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    lines = (r.stdout or '').splitlines()
    res_line = next((l for l in lines if l.startswith(('MAX', 'LE', 'TO', 'UNSAT'))), '')
    board_line = next((l for l in lines if l.startswith('BOARD')), '')
    print('inner result:', res_line, flush=True)
    # xfill emits a BOARD whenever best > floor -- INCLUDING on a TO abort (main.rs line ~1514:
    # `board = if best > floor { Some(best_grid) }`).  A TO only means "not proven optimal", which is
    # irrelevant for a WITNESS / lower bound: any emitted board is re-verified independently by
    # witness_check below, which is the sole authority.  So accept any emitted BOARD (MAX/TO/LE-incumbent);
    # only bail when no board cleared the floor.
    if not board_line:
        sys.exit(f'inner emitted no BOARD above floor {a.floor} (result: {res_line or "(none)"}; '
                 f'stderr tail: {(r.stderr or "")[-300:]})')
    try:
        if res_line.startswith(('MAX', 'LE')):
            vert_max = int(res_line.split()[1])
        else:  # TO ... best=NNN
            vert_max = int(next(t.split('=')[1] for t in res_line.split() if t.startswith('best=')))
    except Exception:
        vert_max = -1
    codes = [int(t) for t in board_line.split()[1:]]
    assert len(codes) == W * H, f'BOARD has {len(codes)} cells, expected {W*H}'
    grid = [[int(codes[y * W + x]) for x in range(W)] for y in range(H)]
    # force row 0 = the main word (the inner leaves scoring-col row-0 cells empty; the main word
    # IS placed there in the real turn).
    mt = rules.alphabet.to_tup(a.main)
    for x in range(W):
        grid[0][x] = int(mt[x])

    spec = {'board': a.board, 'main_word': a.main, 'turn_str': a.turn,
            'scale': True, 'blanks': True, 'require_center': not a.no_center_check,
            'grid': grid}
    # recompute via witness_check (derives optimal blanks, validates everything)
    rules2 = construct_rules('dutch', a.board)
    f = (W * W) / (15 * 15); mc = Counter(mt)
    rules2.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules2.counts.items()})
    rules2.blank_count = round(rules2.blank_count * f)
    mask = [a.turn[x].isupper() for x in range(W)]
    blank, info = wc.derive_blanks(rules2, grid, mask, W, H)
    if blank is None:
        sys.exit(f'no valid blank assignment: {info}')
    ok, rep = wc.check_witness(rules2, W, H, grid, blank, mask,
                               claimed_total=None, require_center=not a.no_center_check)
    if not ok:
        print(json.dumps(rep, indent=1, default=str))
        sys.exit(f'WITNESS REJECTED: {rep.get("fail")}')
    total = int(rep['total'])
    spec['claimed_total'] = total
    out = a.out or os.path.join(ROOT, 'experiments/results/turns',
                                f'N13_witness_{a.name or total}.json')
    json.dump(spec, open(out, 'w'), indent=1)
    print(json.dumps(rep, indent=1, default=str))
    print(f'WITNESS OK  total={total} (main {rep["main_score"]} + vert {rep["vertical_score"]}); '
          f'inner vert_max={vert_max}; blanks={info}; saved {out}', flush=True)


if __name__ == '__main__':
    main()
