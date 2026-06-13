"""N=13 center-connected witness SWEEP (witness-first, ratcheting).

For a fixed main word + placement mask, try a list of length-vectors over the scoring columns,
from gentle to aggressive. For each, run n13_witness.py with --floor = (best verified vertical so
far), so xfill only needs to EMIT a board beating the current best. Any emitted board is already
re-verified by witness_check inside n13_witness; on success we ratchet best_vert up and keep the
witness JSON. Configs that TO (don't emit within the wall) are skipped, logged, and we move on.

This is pure compute (no LLM). Run detached + niced; it logs the best verified TOTAL as it climbs.

Usage:
  python experiments/n13_sweep.py --main <w> --turn <TURN> --center-col 6 \
      --start-vert <V0> --wall <s> --out-prefix experiments/results/n13/sweep_<tag>
"""
import sys, os, json, subprocess, argparse, itertools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NW = os.path.join(ROOT, 'experiments', 'n13_witness.py')
PY = sys.executable


def lvec_candidates(ncols, center_idx, clen):
    """Yield length-vectors (over scoring cols), center col fixed >= clen, gentle -> aggressive."""
    seen = set()
    # single non-center column lengthened
    for L in (3, 4, 5, 6, 7, 8):
        for j in range(ncols):
            if j == center_idx:
                continue
            v = [2] * ncols
            v[center_idx] = clen
            v[j] = L
            t = tuple(v)
            if t not in seen:
                seen.add(t); yield v
    # two non-center columns lengthened (moderate)
    for L in (4, 5, 6):
        others = [j for j in range(ncols) if j != center_idx]
        for a, b in itertools.combinations(others, 2):
            v = [2] * ncols
            v[center_idx] = clen
            v[a] = L; v[b] = L
            t = tuple(v)
            if t not in seen:
                seen.add(t); yield v


def run_one(main, turn, lvec, floor, wall, out):
    cmd = [PY, NW, '--main', main, '--turn', turn, '--lvec', ','.join(map(str, lvec)),
           '--floor', str(floor), '--wall', str(wall), '--out', out, '--name', 'sweep']
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=wall + 60)
    out_txt = p.stdout + p.stderr
    if 'WITNESS OK' in out_txt:
        # n13_witness prints "WITNESS OK ... total <N>"; recover total from the saved file
        try:
            d = json.load(open(out))
            return int(d.get('claimed_total', 0)), out_txt
        except Exception:
            pass
    return None, out_txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', required=True)
    ap.add_argument('--turn', required=True)
    ap.add_argument('--center-col', type=int, default=6, help='index of center scoring col in lvec')
    ap.add_argument('--clen', type=int, default=7, help='center column length (>=7 to reach row 6)')
    ap.add_argument('--main-score', type=int, required=True, help='fixed main-word score (total - vertical)')
    ap.add_argument('--start-vert', type=int, default=86, help='starting best vertical floor')
    ap.add_argument('--wall', type=float, default=30.0)
    ap.add_argument('--out-prefix', required=True)
    a = ap.parse_args()

    ncols = sum(1 for c in a.turn if c.isupper())
    best_vert = a.start_vert
    best_file = None
    log = a.out_prefix + '.log'
    os.makedirs(os.path.dirname(log), exist_ok=True)

    def emit(msg):
        with open(log, 'a') as f:
            f.write(msg + '\n')
        print(msg, flush=True)

    emit(f"# N=13 sweep main={a.main} turn={a.turn} ncols={ncols} center_col={a.center_col} "
         f"clen={a.clen} start_vert={best_vert} wall={a.wall}")

    for lvec in lvec_candidates(ncols, a.center_col, a.clen):
        cand = a.out_prefix + f"_cand.json"
        total, _ = run_one(a.main, a.turn, lvec, best_vert, a.wall, cand)
        if total is not None and (total - 0) > 0:
            vert = total  # n13_witness total includes main; recompute vert vs main below
            # keep the witness as the new best (rename)
            keep = a.out_prefix + f"_best.json"
            try:
                d = json.load(open(cand))
                json.dump(d, open(keep, 'w'), indent=1)
                best_file = keep
                best_vert = total - a.main_score   # vertical floor for the next run ratchets up
                emit(f"NEWBEST lvec={lvec} TOTAL={total} vert={best_vert}  saved {keep}")
            except Exception as e:
                emit(f"  (save failed: {e})")
        else:
            emit(f"  skip lvec={lvec} (no emit at floor {best_vert})")

    emit(f"# DONE best_total_file={best_file} best_vert_floor={best_vert}")


if __name__ == '__main__':
    main()
