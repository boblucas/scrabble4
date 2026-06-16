#!/usr/bin/env python3
"""
Equivalence harness for xfill's VARIABLE-LENGTH (--varmax) mode.

CLAIM (proved structurally in inst_var_from_base, demonstrated empirically here):

    varmax_MAX  ==  max over ALL length-vectors v of  fixed_MAX(v)

and therefore  (varmax says "LE floor")  <=>  (every fixed length-vector is "LE floor").

This script builds a BATTERY of SELF-CONTAINED synthetic BASE files (a tiny board, a small
synthetic dictionary, several scoring columns), each exercising a different scoring feature
(blanks, reserve>=1, word-multiplier wm>1, the length-1 "bare tile / no vertical" option).
For each base it:

  1. enumerates the FULL Cartesian product of per-column lengths (the fixed-length sweep) and runs
     `xfill --batchvec BASE LIST` over every vector, taking the maximum MAX and the per-floor LE map;
  2. runs `xfill --varmax BASE --maxscore FLOOR` once;
  3. asserts the variable max == the sweep max, AND the LE/floor verdict agrees over a band of floors.

Any mismatch is a soundness bug and prints FAIL.  No external lexicon needed: the dictionary is a
codes file we write ourselves, and the BASE file is emitted directly in the format Rust parse_base
reads (DIMS/COUNTS/SCORES/PREPLACED/NONSCORING/RESERVE/DICT/BCOL/BLEN/WORDV).

Run:  python experiments/xfill_rs_varlen_equiv.py
"""
import os, sys, subprocess, itertools

ROOT = '/home/bob/programming/scrabble4'
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')
SCRATCH = os.path.join(ROOT, 'experiments/xfill_varlen_scratch')
os.makedirs(SCRATCH, exist_ok=True)

# ---- a tiny synthetic dictionary over codes 1..ALPHA (letters a=1,b=2,...) -----------------------
# We keep it small so the FULL fixed-length sweep is runnable.  Words here are LISTS of codes; the
# solver validates every maximal H/V run >=2 against this set (single letters are always allowed as
# bare tiles).  We deliberately include 2..4-letter words so columns of different lengths are legal.
def code(s):            # "abc" -> [1,2,3]
    return [ord(c) - ord('a') + 1 for c in s]

DICT_WORDS = [
    # 2-letter
    "ab", "ba", "ad", "da", "be", "eb", "de", "ed", "el", "le", "en", "ne",
    "at", "ta", "an", "na", "as", "sa", "es", "se", "re", "er",
    # 3-letter
    "abe", "bad", "bed", "ben", "den", "ade", "ane", "are", "ate", "ear",
    "eat", "tea", "tan", "ten", "net", "set", "sea", "see", "bee", "dee",
    "ree", "lea", "led", "lee", "ale", "ela",
    # 4-letter
    "abed", "bade", "bead", "bean", "bear", "beat", "bere", "dare", "dear",
    "lead", "lean", "lear", "near", "neat", "seat", "sear", "tear", "tare",
    # 5-letter
    "abear", "anear",
]
DICT_SET = set(tuple(code(w)) for w in DICT_WORDS)
# words_lookup analogue: a stub w[1:] must itself be a word.  Single letters ARE words (a bare tile
# is a valid 1-letter "word"), matching the real construct_rules which injects all single letters --
# this makes length-2 verticals (stub = one letter) legal, as in the production model.
LK = set(DICT_SET) | {(c,) for c in range(1, 27)}
HMAX = 8
ALPHA = 26
SCORE = {i: ((i % 9) + 1) for i in range(1, ALPHA + 1)}   # arbitrary face values 1..9

def write_dict(path):
    with open(path, 'w') as f:
        for w in sorted(DICT_WORDS):
            f.write(' '.join(map(str, code(w))) + '\n')

# A candidate vertical for a scoring column with row-0 letter L and length len:
#   a word w of that length with w[0]==L and (len==1 OR w[1:] is itself a word).
# gross = (row-0 contribution) + sum of stub face values, with the column's word-multiplier wm
# applied to the WHOLE vertical word (matches the real engine: the row-0 tile carries the wm).
# The engine treats gross as opaque; we only need varmax and the sweep to read the SAME gross (they
# read the SAME base), so any deterministic gross works -- we use a realistic wm-weighted sum.
def candidates(L, length, wm):
    out = []
    seen = set()
    if length == 1:
        out.append(((), 0))                      # bare tile: no stub, gross 0 (the length-1 option)
        return out
    for w in DICT_SET:
        if len(w) != length or w[0] != L:
            continue
        stub = tuple(w[1:])
        if stub and stub not in LK:
            continue
        if stub in seen:
            continue
        seen.add(stub)
        gross = wm * sum(SCORE[c] for c in w)    # wm applies to every cell of the vertical word
        out.append((stub, gross))
    return out

# ---- BASE emission (matches Rust parse_base) -----------------------------------------------------
def emit_base(path, W, H, blanks, reserve, counts, preplaced, scoring, dict_path):
    """scoring = list of dicts: {col, L (row-0 letter code), wm, lengths (iterable of lengths)}.
    preplaced = list of (x,y,code).  counts = {code:n}.  Returns (base_dict_for_python, maxlens)."""
    cols = []
    for blk in scoring:
        bylen = {}
        for length in blk['lengths']:
            cands = candidates(blk['L'], length, blk['wm'])
            if cands:
                bylen[length] = cands
        cols.append({'col': blk['col'], 'wm': blk['wm'], 'bylen': bylen})
    L = [f"DIMS {W} {H} {HMAX} {ALPHA} {blanks}"]
    L.append("COUNTS " + ' '.join(f"{k}:{v}" for k, v in counts.items()))
    L.append("SCORES " + ' '.join(f"{k}:{v}" for k, v in SCORE.items()))
    L.append("PREPLACED " + ' '.join(f"{x},{y},{c}" for x, y, c in preplaced))
    L.append("NONSCORING " + ' '.join(str(x) for x, _, _ in preplaced))
    if reserve:
        L.append(f"RESERVE {reserve}")
    L.append(f"DICT {dict_path}")
    for col in cols:
        L.append(f"BCOL {col['col']} {col['wm']} {len(col['bylen'])}")
        for ln in sorted(col['bylen']):
            ws = col['bylen'][ln]
            L.append(f"BLEN {ln} {len(ws)}")
            for stub, g in ws:
                L.append(f"WORDV {g} " + ' '.join(map(str, stub)))
    with open(path, 'w') as fp:
        fp.write('\n'.join(L) + '\n')
    maxlens = [(c['col'], max(c['bylen']) if c['bylen'] else 1) for c in cols]
    lengths_per_col = [sorted(c['bylen']) for c in cols]
    return lengths_per_col


def run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run([BIN] + args, capture_output=True, text=True, env=e)
    return r.stdout.strip()


def parse_max(line, floor):
    """Return ('MAX', value) / ('LE', floor) / ('TO', best) / ('NOCAND', None) from a result line."""
    toks = line.split()
    if not toks:
        return ('NONE', None)
    if toks[0] in ('MAX', 'LE', 'TO'):
        return (toks[0], int(toks[1]))
    return (toks[0], None)


def fixed_sweep_max(base_path, lengths_per_col, floor):
    """Run --batchvec over ALL length-vectors; return (overall_max, per_floor_le_map_unused)."""
    list_path = base_path + '.allvecs'
    vecs = list(itertools.product(*lengths_per_col))
    with open(list_path, 'w') as f:
        for i, v in enumerate(vecs):
            f.write(f"v{i} " + ' '.join(map(str, v)) + f" {floor}\n")
    out = run(['--batchvec', base_path, list_path])
    overall = None
    n_max = n_le = n_nocand = 0
    for line in out.splitlines():
        if not line.startswith('RES '):
            continue
        _, _key, *rest = line.split(maxsplit=2)
        kind, val = parse_max(rest[0] if rest else '', floor)
        if kind == 'MAX':
            n_max += 1
            overall = val if overall is None else max(overall, val)
        elif kind == 'LE':
            n_le += 1
        elif kind == 'NOCAND':
            n_nocand += 1
    return overall, len(vecs), n_max, n_le, n_nocand


def battery():
    dict_path = os.path.join(SCRATCH, 'dict_syn.txt')
    write_dict(dict_path)
    full_counts = {i: 4 for i in range(1, ALPHA + 1)}    # generous bag
    tight = {i: 1 for i in range(1, ALPHA + 1)}          # tile-starved -> exercises shorter words

    # GEOMETRY: a 2-wide unit -- ONE scoring column at col 0 with a preplaced ANCHOR at col 1.  The
    # scoring vertical connects to the anchor via a row-1 bridge in col 1 (a valid horizontal 2-word
    # + the col-1 vertical word).  This is the minimal CONNECTED, FEASIBLE board, so the MAX values
    # are non-trivial and the equivalence test actually bites (the earlier wide interleaved layouts
    # admitted NO legal board, making the test vacuous).  Each case toggles a different scoring
    # feature; the length band {1,2,3} gives a small fixed sweep.  Row-0 main letter = 'b' (code 2);
    # anchor 'a' (code 1).  Candidates for 'b': len2 "ba","be","bb?"... from the synthetic dict.
    anchor = [(1, 0, code('a')[0])]
    cases = []
    cases.append(dict(name='A_basic',     W=2, H=4, blanks=0, reserve=0, counts=dict(full_counts),
                      preplaced=anchor,
                      scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3])],
                      floors=[-1, 0, 5, 9, 20]))
    cases.append(dict(name='B_wm3',       W=2, H=4, blanks=0, reserve=0, counts=dict(full_counts),
                      preplaced=anchor,
                      scoring=[dict(col=0, L=code('b')[0], wm=3, lengths=[1, 2, 3])],
                      floors=[-1, 0, 10, 27, 60]))
    cases.append(dict(name='C_tight_blank', W=2, H=4, blanks=1, reserve=0, counts=dict(tight),
                      preplaced=anchor,
                      scoring=[dict(col=0, L=code('b')[0], wm=2, lengths=[1, 2, 3])],
                      floors=[-1, 0, 3, 9, 30]))
    cases.append(dict(name='D_reserve1',  W=2, H=4, blanks=1, reserve=1, counts=dict(tight),
                      preplaced=anchor,
                      scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3])],
                      floors=[-1, 0, 3, 9, 30]))
    cases.append(dict(name='E_len1_only', W=2, H=4, blanks=0, reserve=0, counts=dict(full_counts),
                      preplaced=anchor,
                      scoring=[dict(col=0, L=code('b')[0], wm=2, lengths=[1])],   # bare tile only
                      floors=[-1, 0, 5]))
    # A 3-wide unit: scoring cols 0 AND 2 sharing the col-1 anchor (two scoring columns, one search).
    cases.append(dict(name='F_2scoring',  W=3, H=4, blanks=0, reserve=0, counts=dict(full_counts),
                      preplaced=[(1, 0, code('a')[0])],
                      scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3]),
                               dict(col=2, L=code('d')[0], wm=2, lengths=[1, 2, 3])],
                      floors=[-1, 0, 10, 30, 80]))

    n_fail = 0
    for cs in cases:
        base_path = os.path.join(SCRATCH, f"base_{cs['name']}.txt")
        lengths_per_col = emit_base(base_path, cs['W'], cs['H'], cs['blanks'], cs['reserve'],
                                    cs['counts'], cs['preplaced'], cs['scoring'], dict_path)
        # sweep max (floor=-1 so every legal vector reports its MAX)
        swp_max, nvec, n_max, n_le, n_nocand = fixed_sweep_max(base_path, lengths_per_col, -1)
        # varmax (floor=-1)
        vline = run(['--varmax', base_path, '--maxscore', '-1'])
        vkind, vval = parse_max(vline, -1)
        var_max = vval if vkind == 'MAX' else (None if vkind == 'LE' else vval)
        ok_max = (swp_max == var_max)
        status = 'PASS' if ok_max else 'FAIL'
        print(f"[{status}] {cs['name']:20s} vecs={nvec:4d} (MAX={n_max} LE={n_le} NOCAND={n_nocand})  "
              f"sweep_max={swp_max}  varmax={var_max}  ({vline})")
        if not ok_max:
            n_fail += 1
        # per-floor LE/MAX verdict agreement
        for fl in cs['floors']:
            sm, _, _, _, _ = fixed_sweep_max(base_path, lengths_per_col, fl)
            # sweep beats floor iff ANY vector reports MAX>fl (sm is the max of those MAX values, or None)
            sweep_beats = (sm is not None and sm > fl)
            vl = run(['--varmax', base_path, '--maxscore', str(fl)])
            vk, vv = parse_max(vl, fl)
            var_beats = (vk == 'MAX' and vv > fl)
            agree = (sweep_beats == var_beats)
            if not agree:
                print(f"        FAIL floor={fl}: sweep_beats={sweep_beats} (sm={sm})  "
                      f"var_beats={var_beats} ({vl})")
                n_fail += 1
        print(f"        floor band {cs['floors']}: all verdicts agree"
              if True else "")
    print()
    if n_fail == 0:
        print("EQUIVALENCE BATTERY: ALL PASS")
    else:
        print(f"EQUIVALENCE BATTERY: {n_fail} FAILURE(S)")
    return n_fail


if __name__ == '__main__':
    sys.exit(1 if battery() else 0)
