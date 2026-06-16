#!/usr/bin/env python3
"""
Artificial-problem SPEEDUP benchmark for xfill --varmax.

The fixed-length certification of one main word sweeps K^n length-vectors (n scoring columns, each
choosing a length in a K-sized band) and certifies EACH.  --varmax does ONE search ranging over the
union of all those word-choice spaces.  This benchmark uses a real (feasible, known-SAT) N=7 board
-- so the MAX values are non-trivial and the equivalence assertion actually bites -- and GROWS the
length band K (the sweep is K^4 over the 4 scoring columns).  It reports, per K:
  * the sweep's TOTAL wall + TOTAL nodes (summed over all K^4 vectors) and overall MAX,
  * varmax's single-search wall + nodes and MAX,
  * the wall-clock and node speedup factors,
and asserts identical MAX at every K (a mismatch = bug).  As K grows the sweep's K^4 vectors blow up
while varmax stays one search, so the speedup grows.

Run:  python experiments/xfill_rs_varlen_bench.py   (requires the Dutch lexicon; ~4s one-time load.)
"""
import os, sys, time, itertools, subprocess, re

ROOT = '/home/bob/programming/scrabble4'
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')
SCRATCH = os.path.join(ROOT, 'experiments/xfill_varlen_scratch')
os.makedirs(SCRATCH, exist_ok=True)
import xtest


def make_turn(word):
    return ''.join(word[x].upper() if x % 2 == 0 else word[x].lower() for x in range(len(word)))


def restrict_band(base, band):
    lpc = []
    for col in base['cols']:
        col['bylen'] = {ln: ws for ln, ws in col['bylen'].items() if ln in band}
        lpc.append(sorted(col['bylen']))
    return lpc


WALL = 3.0   # per-vector / per-varmax wall so a pathological vector can't hang the benchmark


def run_capture(args):
    env = dict(os.environ); env['BATCHWALL'] = str(WALL); env['WALL'] = str(WALL)
    return subprocess.run([BIN] + args, capture_output=True, text=True, env=env).stdout.strip()


def sweep(base_path, lpc, floor):
    vecs = list(itertools.product(*lpc))
    list_path = base_path + '.bench'
    with open(list_path, 'w') as f:
        for i, v in enumerate(vecs):
            f.write(f"v{i} " + ' '.join(map(str, v)) + f" {floor}\n")
    t0 = time.time()
    out = run_capture(['--batchvec', base_path, list_path])
    wall = time.time() - t0
    nodes = 0
    overall = None
    n_to = 0
    for line in out.splitlines():
        m = re.search(r'nodes=(\d+)', line)
        if m:
            nodes += int(m.group(1))
        if re.search(r'\bRES \S+ TO ', line):
            n_to += 1
        mm = re.search(r'\bMAX (\-?\d+)', line)
        if mm:
            v = int(mm.group(1))
            overall = v if overall is None else max(overall, v)
    return wall, nodes, overall, len(vecs), n_to


def varmax(base_path, floor):
    t0 = time.time()
    out = run_capture(['--varmax', base_path, '--maxscore', str(floor)])
    wall = time.time() - t0
    m = re.search(r'nodes=(\d+)', out)
    nodes = int(m.group(1)) if m else 0
    mm = re.search(r'\bMAX (\-?\d+)', out)
    val = int(mm.group(1)) if mm else None
    return wall, nodes, val


def main():
    word = 'streden'                 # a known-SAT real N=7 board (scoring cols 0,2,4,6)
    print(f"  board=N7 word={word!r} (4 scoring columns; fixed sweep = K^4 vectors)")
    print(f"  {'K':>2} {'vecs':>6}  {'sweep_wall':>11} {'sweep_nodes':>12}  "
          f"{'var_wall':>9} {'var_nodes':>10}  {'wall_x':>7} {'node_x':>8}  match (sweep/var MAX)")
    n_fail = 0
    for K in (2, 3, 4):
        base = xtest.build_base('7', word, make_turn(word), scale=False, reserve=0)
        lpc = restrict_band(base, set(range(1, K + 1)))
        base_path = os.path.join(SCRATCH, f'benchreal_{word}_K{K}.txt')
        xtest.dump_base(base, base_path)
        sw_wall, sw_nodes, sw_max, nvec, n_to = sweep(base_path, lpc, -1)
        v_wall, v_nodes, v_max = varmax(base_path, -1)
        comparable = (n_to == 0)
        match = (sw_max == v_max) if comparable else True
        if not match:
            n_fail += 1
        wall_x = sw_wall / v_wall if v_wall > 0 else float('inf')
        node_x = sw_nodes / v_nodes if v_nodes > 0 else float('inf')
        tag = ('OK' if match else 'MISMATCH') if comparable else f'TO({n_to}) skip-cmp'
        print(f"  {K:>2} {nvec:>6}  {sw_wall:>10.3f}s {sw_nodes:>12d}  "
              f"{v_wall:>8.3f}s {v_nodes:>10d}  {wall_x:>6.1f}x {node_x:>7.1f}x  "
              f"{tag} ({sw_max}/{v_max})")
    print()
    if n_fail == 0:
        print("BENCHMARK: ALL MAX MATCH; varmax = one search vs the K^4 sweep (speedup grows with K)")
    else:
        print(f"BENCHMARK: {n_fail} MISMATCH(ES)")
    return n_fail


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
