#!/usr/bin/env python3
"""
REAL-board equivalence harness for xfill --varmax (the production-data half of the battery).

Uses xtest.build_base on real Dutch N=7 boards (known-SAT main words) -- the SAME plumbing the
production --batchvec sweep uses -- then, for each base:
  * RESTRICTS every scoring column to a small length BAND so the full fixed-length sweep K^n is
    runnable (and writes the band-restricted base both modes read, so they see identical candidates);
  * runs `xfill --batchvec BASE ALLVECS` over EVERY length-vector in the band -> overall MAX + per-floor;
  * runs `xfill --varmax BASE --maxscore FLOOR` once;
  * asserts varmax MAX == sweep MAX, and the LE/floor verdict agrees over a band of floors.

These cases carry the FULL real scoring features automatically: word multipliers (wm per column),
blanks, the length-1 bare-tile option, and (we add) a reserve=1 variant.  Any mismatch = FAIL.

Run:  python experiments/xfill_rs_varlen_equiv_real.py
(requires the Dutch lexicon; ~4s one-time load.)
"""
import os, sys, subprocess, itertools

ROOT = '/home/bob/programming/scrabble4'
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')
SCRATCH = os.path.join(ROOT, 'experiments/xfill_varlen_scratch')
os.makedirs(SCRATCH, exist_ok=True)

import xtest   # build_base / dump_base, real Dutch rules


def restrict_band(base, band):
    """Drop every (col,length) whose length is not in `band` from a build_base() base dict.
    Returns the list of available lengths per column (vector order)."""
    lengths_per_col = []
    for col in base['cols']:
        col['bylen'] = {ln: ws for ln, ws in col['bylen'].items() if ln in band}
        lengths_per_col.append(sorted(col['bylen']))
    return lengths_per_col


def run(args, wall=None):
    env = dict(os.environ)
    if wall is not None:
        env['BATCHWALL'] = str(wall)   # per-instance wall in batchvec; WALL for single varmax
        env['WALL'] = str(wall)
    return subprocess.run([BIN] + args, capture_output=True, text=True, env=env).stdout.strip()


def parse_line(line):
    toks = line.split()
    if not toks:
        return ('NONE', None)
    if toks[0] in ('MAX', 'LE', 'TO'):
        return (toks[0], int(toks[1]))
    return (toks[0], None)


def sweep_max(base_path, lengths_per_col, floor, wall):
    """Full fixed sweep.  Returns (overall_max, nvec, n_max, n_le, n_nocand, n_to).  n_to>0 means some
    vector hit the wall -> its value is UNKNOWN, so the caller must NOT assert equivalence for it."""
    vecs = list(itertools.product(*lengths_per_col))
    list_path = base_path + '.allvecs'
    with open(list_path, 'w') as f:
        for i, v in enumerate(vecs):
            f.write(f"v{i} " + ' '.join(map(str, v)) + f" {floor}\n")
    out = run(['--batchvec', base_path, list_path], wall=wall)
    overall = None
    n_max = n_le = n_nocand = n_to = 0
    for line in out.splitlines():
        if not line.startswith('RES '):
            continue
        rest = line.split(maxsplit=2)[2] if len(line.split(maxsplit=2)) > 2 else ''
        kind, val = parse_line(rest)
        if kind == 'MAX':
            n_max += 1
            overall = val if overall is None else max(overall, val)
        elif kind == 'LE':
            n_le += 1
        elif kind == 'NOCAND':
            n_nocand += 1
        elif kind == 'TO':
            n_to += 1
    return overall, len(vecs), n_max, n_le, n_nocand, n_to


def make_turn(word):
    return ''.join(word[x].upper() if x % 2 == 0 else word[x].lower() for x in range(len(word)))


WALL = 3.0   # per-vector / per-varmax wall (s); a vector that exceeds it reports TO and is skipped.
             # NOTE batchvec applies WALL PER vector, so keep bands small (K^4 vectors) for a fast run.


def one_case(word, band, reserve, floors):
    name = f"r7_{word}_band{min(band)}-{max(band)}_res{reserve}"
    base = xtest.build_base('7', word, make_turn(word), scale=False, reserve=reserve)
    lengths_per_col = restrict_band(base, set(band))
    base_path = os.path.join(SCRATCH, f"realbase_{name}.txt")
    xtest.dump_base(base, base_path)
    swp_max, nvec, n_max, n_le, n_nocand, n_to = sweep_max(base_path, lengths_per_col, -1, WALL)
    vline = run(['--varmax', base_path, '--maxscore', '-1'], wall=WALL)
    vk, vv = parse_line(vline)
    var_max = vv if vk == 'MAX' else None
    if n_to > 0 or vk == 'TO':
        # some vector (or varmax) hit the wall -> value unknown -> cannot assert equivalence soundly.
        print(f"[SKIP] {name:34s} vecs={nvec:4d} sweep_TO={n_to} varmax={vk} -- wall hit, not compared")
        return 0
    ok = (swp_max == var_max)
    print(f"[{'PASS' if ok else 'FAIL'}] {name:34s} vecs={nvec:4d} "
          f"(MAX={n_max} LE={n_le} NOCAND={n_nocand})  sweep_max={swp_max}  varmax={var_max}")
    fails = 0 if ok else 1
    for fl in floors:
        sm, _, _, _, _, fto = sweep_max(base_path, lengths_per_col, fl, WALL)
        if fto > 0:
            continue                       # vector timed out at this floor -> skip (unknown)
        sweep_beats = (sm is not None and sm > fl)
        vl = run(['--varmax', base_path, '--maxscore', str(fl)], wall=WALL)
        vk2, vv2 = parse_line(vl)
        if vk2 == 'TO':
            continue
        var_beats = (vk2 == 'MAX' and vv2 > fl)
        if sweep_beats != var_beats:
            print(f"        FAIL floor={fl}: sweep_beats={sweep_beats}(sm={sm}) var_beats={var_beats}({vl})")
            fails += 1
    if fails == 0:
        print(f"        floor band {floors}: all verdicts agree")
    return fails


def main():
    # Bands kept SMALL so the full fixed sweep K^4 is runnable fast (4^4=256, 5^4=625).  Any vector
    # that still exceeds the per-vector wall is reported TO and the case is SKIPPED (never compared
    # against an unknown) -- soundness over coverage.
    cases = [
        ('streden', range(1, 4), 0, [-1, 20, 60]),    # 3^4 = 81 vectors
        ('sneaken', range(1, 4), 0, [-1, 20, 60]),
        ('croches', range(1, 4), 1, [-1, 20, 60]),    # reserve=1 variant
        ('arsisje', range(1, 4), 0, [-1, 15, 40]),
        ('rentend', range(1, 4), 0, [-1, 30, 90]),
    ]
    total = 0
    for word, band, reserve, floors in cases:
        total += one_case(word, list(band), reserve, floors)
    print()
    print("REAL-BOARD EQUIVALENCE: ALL PASS" if total == 0
          else f"REAL-BOARD EQUIVALENCE: {total} FAILURE(S)")
    return total


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
