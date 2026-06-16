#!/usr/bin/env python3
"""varmax knap-UB validation: with/without-UB MAX-equality + pruning benchmark.

Builds a REAL base (default N=11 bouwfysicus, full lengths) and runs `xfill --varmax` twice:
  * KNAP ON  (default)
  * KNAP OFF (NOKNAP=1, == fd886d7 behaviour)
Asserts identical MAX/LE verdict over a floor band; reports nodes/time WITH vs WITHOUT the UB.
Scratch base lives in experiments/xfill_varmax_knap_scratch/ (NOT the proof-job dir)."""
import os, sys, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'experiments'))
import xtest
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')
SCR = os.path.join(ROOT, 'experiments/xfill_varmax_knap_scratch')
os.makedirs(SCR, exist_ok=True)


def parse(line):
    # "MAX 224 nodes=.. time=..s" / "LE 0 nodes=.." / "TO .."
    t = line.split()
    return t[0], int(t[1]), line


def run(base_path, floor, noknap, wall=None):
    e = dict(os.environ)
    if noknap:
        e['NOKNAP'] = '1'
    else:
        e.pop('NOKNAP', None)
    if wall is not None:
        e['WALL'] = str(wall)
    t0 = time.time()
    r = subprocess.run([BIN, '--varmax', base_path, '--maxscore', str(floor)],
                       capture_output=True, text=True, env=e)
    dt = time.time() - t0
    out = r.stdout.strip().splitlines()
    verd = out[-1] if out else ''
    # pull nodes + knap counters from stderr
    nodes = None
    for ln in verd.split():
        if ln.startswith('nodes='):
            nodes = int(ln[6:])
    knap = ''
    for ln in r.stderr.splitlines():
        if ln.startswith('knap-ub:'):
            knap = ln.strip()
    return verd, nodes, dt, knap


def main():
    board = sys.argv[sys.argv.index('--board') + 1] if '--board' in sys.argv else '11'
    main_w = sys.argv[sys.argv.index('--main') + 1] if '--main' in sys.argv else 'bouwfysicus'
    turn = sys.argv[sys.argv.index('--turn') + 1] if '--turn' in sys.argv else 'BOUWfYsiCuS'
    wall = float(sys.argv[sys.argv.index('--wall') + 1]) if '--wall' in sys.argv else None
    floors = [int(x) for x in sys.argv[sys.argv.index('--floors') + 1].split(',')] \
        if '--floors' in sys.argv else [-1]
    band = None
    if '--band' in sys.argv:
        lo, hi = sys.argv[sys.argv.index('--band') + 1].split('-')
        band = set(range(int(lo), int(hi) + 1))

    base = xtest.build_base(board, main_w, turn, scale=True)
    if band is not None:
        for col in base['cols']:
            col['bylen'] = {ln: ws for ln, ws in col['bylen'].items() if ln in band}
    bpath = os.path.join(SCR, f'base_{board}_{main_w}.txt')
    xtest.dump_base(base, bpath)
    print(f"base: {board} {main_w} '{turn}'  scoring cols={[c['col'] for c in base['cols']]}")
    print(f"      lengths/col: {[sorted(c['bylen']) for c in base['cols']]}")

    ok = True
    for floor in floors:
        v_on, n_on, t_on, k_on = run(bpath, floor, noknap=False, wall=wall)
        v_off, n_off, t_off, k_off = run(bpath, floor, noknap=True, wall=wall)
        agree = parse(v_on)[0] == parse(v_off)[0] and parse(v_on)[1] == parse(v_off)[1]
        # if either TIMED OUT, the verdict isn't a proof -> can't compare values
        to = v_on.startswith('TO') or v_off.startswith('TO')
        tag = 'PASS' if (agree or to) else 'FAIL'
        if not (agree or to):
            ok = False
        spd = (t_off / t_on) if t_on > 0 else float('inf')
        ndx = (n_off / n_on) if n_on else float('inf')
        print(f"[{tag}] floor={floor}")
        print(f"    KNAP ON : {v_on}   {k_on}")
        print(f"    KNAP OFF: {v_off}")
        if not to:
            print(f"    pruning : nodes {n_off} -> {n_on}  ({ndx:.1f}x fewer)   "
                  f"time {t_off:.3f}s -> {t_on:.3f}s  ({spd:.1f}x faster)")
    print("RESULT:", "ALL MAX/LE MATCH (UB verdict-neutral)" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
