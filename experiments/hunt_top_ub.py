"""Floor-raise hunt: run the HIGHEST-UB band vectors through xfill --batchvec hoping for a MAX.

The certification cost is driven by the floor<->UB gap: any witnessed board above the current
floor both RAISES the proven lower bound and SHRINKS the remaining band (UB>floor).  The
certifier processes vectors in enumeration order; this tool instead sorts the band by optimistic
UB descending and probes the top-K with a generous wall -- the vectors most likely to hold a
better board (and the ones that make the certification slow while unresolved).

Usage: python experiments/hunt_top_ub.py --board 11 --main bouwfysicus --turn BOUWfYsiCuS \
           --floor 221 [--center] [--top 2000] [--wall 900] [--name n11_fixed_221]
Reuses the cert dir's base.txt (or builds it).  Prints any MAX loudly; exit 0 = no improvement
found (floor stands), exit 3 = IMPROVED (re-witness + restart certification at the new floor).
"""
import sys, os, json, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
sys.argv_backup = sys.argv
import importlib
m35 = importlib.import_module('35_certify')
import xtest

XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_lev3')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True); ap.add_argument('--main', required=True)
    ap.add_argument('--turn', required=True); ap.add_argument('--floor', type=int, required=True)
    ap.add_argument('--center', action='store_true')
    ap.add_argument('--top', type=int, default=2000); ap.add_argument('--wall', type=int, default=900)
    ap.add_argument('--name', required=True)
    a = ap.parse_args()
    rules = m35.make_rules(a.board, a.main, True, True)
    scoring, best_at, mt = m35.derive_columns(rules, a.main, a.turn)
    band = m35.enumerate_band(rules, scoring, best_at, a.floor, a.center)
    band.sort(key=lambda lv: -sum(best_at[c][l] for c, l in zip(scoring, lv)))
    top = band[:a.top]
    print(f'band={len(band)}; probing top {len(top)} by UB '
          f'(max UB={sum(best_at[c][l] for c, l in zip(scoring, top[0]))})', flush=True)
    cdir = os.path.join(ROOT, 'experiments/results/certs', a.name)
    os.makedirs(cdir, exist_ok=True)
    bpath = os.path.join(cdir, 'base.txt')
    if not os.path.exists(bpath):
        xtest.write_dict(a.board)
        xtest.dump_base(xtest.build_base(a.board, a.main, a.turn, scale=True), bpath)
    lf = os.path.join(cdir, 'hunt_top.list')
    with open(lf, 'w') as f:
        for lv in top:
            k = '-'.join(map(str, lv))
            f.write(f"{k} {' '.join(map(str, lv))} {a.floor}\n")
    env = dict(os.environ); env.pop('MAXNODES', None); env['BATCHWALL'] = str(a.wall)
    p = subprocess.Popen([XFILL, '--batchvec', bpath, lf], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, env=env, cwd=ROOT)
    best = a.floor; best_key = None
    n = 0
    for line in p.stdout:
        t = line.split()
        if len(t) >= 3 and t[0] == 'RES':
            n += 1
            if t[2] == 'MAX':
                v = int(t[3])
                if v > best:
                    best, best_key = v, t[1]
                    print(f'  !!! IMPROVED: {t[1]} -> MAX {v}', flush=True)
            if n % 100 == 0:
                print(f'  [{n}/{len(top)}] best={best}', flush=True)
    p.wait()
    if best > a.floor:
        print(f'FLOOR RAISED: {a.floor} -> {best} at {best_key}.')
        print(f'Next: emit+verify the board (xfill --maxscore {best-1} --emit on that vector), '
              f'then restart certification at floor {best}.')
        sys.exit(3)
    print(f'no improvement over {a.floor} in the top {len(top)} UB vectors (floor stands)')
    sys.exit(0)


if __name__ == '__main__':
    main()
