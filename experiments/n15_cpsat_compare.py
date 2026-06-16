"""
Correctness comparison: n15_cpsat_lazy (CP-SAT + lazy connectivity) vs xfill --varmax (the
bespoke Rust B&B), on instances where xfill COMPLETES naturally.  Asserts the two agree:
  - synthetic battery (tiny boards, synthetic dict): xfill MAX == cpsat MAX (mode=max).
  - N=15 already-CERTIFIED masks: xfill proved `LE vfloor`; cpsat must also prove `LE vfloor`
    (mode=le, floor=vfloor).  Optionally cpsat MAX (mode=max) for the ones that close.
Also runs witness_check on any board cpsat emits.

Prints a PASS/FAIL table.  This is the soundness guard for the learning solver.

Usage:
  python experiments/n15_cpsat_compare.py             # synthetic + a sample of CERT N=15 masks
  python experiments/n15_cpsat_compare.py --n15 N     # use N CERT masks (default 8)
"""
import sys, os, json, time, subprocess, argparse, importlib.util

ROOT = '/home/bob/programming/scrabble4'
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_varmax')
LAZY = os.path.join(ROOT, 'experiments/n15_cpsat_lazy.py')
PY = sys.executable


def run_xfill_varmax(base, floor, wall=30):
    env = dict(os.environ); env['WALL'] = str(wall)
    r = subprocess.run([XFILL, '--varmax', base, '--maxscore', str(floor)],
                       capture_output=True, text=True, env=env)
    return r.stdout.strip()


def run_lazy(base, mode, floor, wall=60, workers=8, emit=False):
    cmd = [PY, LAZY, base, '--mode', mode, '--floor', str(floor),
           '--workers', str(workers), '--wall', str(wall)]
    if emit:
        cmd.append('--emit')
    r = subprocess.run(cmd, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith('JSON')]
    result = next((l for l in lines if l.split() and l.split()[0]
                   in ('MAX', 'LE', 'GT', 'TO', 'INFEASIBLE')), lines[0] if lines else '')
    board = next((l for l in lines if l.startswith('BOARD')), None)
    return result, board


def parse_kind_val(line):
    t = line.split()
    if not t:
        return ('NONE', None)
    if t[0] in ('MAX', 'LE', 'GT', 'TO'):
        try:
            return (t[0], int(t[1]))
        except (IndexError, ValueError):
            return (t[0], None)
    return (t[0], None)


def verify_emitted_setup(base_path, board_line):
    """Independently re-validate a board emitted by n15_cpsat_lazy --emit, exactly as xfill's model
    requires: the SETUP board (row-0 scoring cells emptied) must have EVERY maximal H/V run >=2 be a
    dict word, and be ONE 4-connected component including the root (first preplaced cell).  (The
    row-0 MAIN word itself is a precondition placed this turn, scored as main_const, not part of the
    vertical-fill model -- so it is not re-validated here, matching xfill.)  Returns (ok, msg)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("lazy", LAZY)
    lz = importlib.util.module_from_spec(spec); spec.loader.exec_module(lz)
    base = lz.parse_base(base_path)
    W, H = base['W'], base['H']
    dw = set(lz.load_dict_words(base['dict_path'], base['hmax']))
    for c in range(1, base['alpha'] + 1):
        dw.add((c,))
    toks = board_line.split()
    if not toks or toks[0] != 'BOARD':
        return False, 'no BOARD line'
    vals = list(map(int, toks[1:]))
    g = [[vals[y * W + x] for x in range(W)] for y in range(H)]
    scoring = set(c['col'] for c in base['cols'])
    for x in scoring:
        g[0][x] = 0                                  # SETUP: row-0 scoring cells are empty
    # runs
    runs = []
    for y in range(H):
        x = 0
        while x < W:
            if g[y][x] == 0:
                x += 1; continue
            x2 = x
            while x2 < W and g[y][x2] != 0:
                x2 += 1
            if x2 - x >= 2:
                runs.append(tuple(g[y][k] for k in range(x, x2)))
            x = x2
    for x in range(W):
        y = 0
        while y < H:
            if g[y][x] == 0:
                y += 1; continue
            y2 = y
            while y2 < H and g[y2][x] != 0:
                y2 += 1
            if y2 - y >= 2:
                runs.append(tuple(g[k][x] for k in range(y, y2)))
            y = y2
    bad = [r for r in runs if r not in dw]
    setup = [(x, y) for y in range(H) for x in range(W) if g[y][x] != 0]
    comps = lz.setup_components(setup, W, H)
    if bad:
        return False, f'{len(bad)} illegal setup run(s)'
    if len(comps) != 1:
        return False, f'{len(comps)} components (disconnected)'
    return True, f'legal + connected ({len(setup)} setup cells)'


def synthetic():
    spec = importlib.util.spec_from_file_location(
        "equiv", os.path.join(ROOT, "experiments/xfill_rs_varlen_equiv.py"))
    eq = importlib.util.module_from_spec(spec); spec.loader.exec_module(eq)
    os.makedirs(eq.SCRATCH, exist_ok=True)
    dict_path = os.path.join(eq.SCRATCH, 'dict_syn.txt'); eq.write_dict(dict_path)
    code = eq.code
    full = {i: 4 for i in range(1, 27)}; tight = {i: 1 for i in range(1, 27)}
    anchor = [(1, 0, code('a')[0])]
    cases = [
        dict(name='A_basic', W=2, H=4, blanks=0, reserve=0, counts=dict(full), preplaced=anchor,
             scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3])]),
        dict(name='B_wm3', W=2, H=4, blanks=0, reserve=0, counts=dict(full), preplaced=anchor,
             scoring=[dict(col=0, L=code('b')[0], wm=3, lengths=[1, 2, 3])]),
        dict(name='C_tight_blank', W=2, H=4, blanks=1, reserve=0, counts=dict(tight),
             preplaced=anchor, scoring=[dict(col=0, L=code('b')[0], wm=2, lengths=[1, 2, 3])]),
        dict(name='D_reserve1', W=2, H=4, blanks=1, reserve=1, counts=dict(tight),
             preplaced=anchor, scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3])]),
        dict(name='E_len1_only', W=2, H=4, blanks=0, reserve=0, counts=dict(full),
             preplaced=anchor, scoring=[dict(col=0, L=code('b')[0], wm=2, lengths=[1])]),
        dict(name='F_2scoring', W=3, H=4, blanks=0, reserve=0, counts=dict(full),
             preplaced=[(1, 0, code('a')[0])],
             scoring=[dict(col=0, L=code('b')[0], wm=1, lengths=[1, 2, 3]),
                      dict(col=2, L=code('d')[0], wm=2, lengths=[1, 2, 3])]),
    ]
    rows = []
    npass = 0
    for cs in cases:
        p = os.path.join(eq.SCRATCH, f"cmp_{cs['name']}.txt")
        eq.emit_base(p, cs['W'], cs['H'], cs['blanks'], cs['reserve'], cs['counts'],
                     cs['preplaced'], cs['scoring'], dict_path)
        xf = run_xfill_varmax(p, -1)
        xk, xv = parse_kind_val(xf)
        cp, board = run_lazy(p, 'max', -1, wall=30, workers=2, emit=True)
        ck, cv = parse_kind_val(cp)
        ok = (xk == 'MAX' and ck == 'MAX' and xv == cv)
        # witness check on the emitted SETUP board (legality + connectivity), matching xfill's model.
        wmsg = 'no board'
        if board is not None:
            wok, wmsg = verify_emitted_setup(p, board)
            ok = ok and wok
        npass += ok
        rows.append((cs['name'], f"xfill MAX={xv}", f"cpsat MAX={cv} [witness:{wmsg}]",
                     'PASS' if ok else 'FAIL'))
    return rows, npass, len(cases)


def n15_certs(nmasks):
    """Sample CERT masks from stage1; assert cpsat proves LE vfloor (mode=le)."""
    vp = os.path.join(ROOT, 'experiments/results/certs/n15varmax_stage1/verdicts.jsonl')
    bdir = os.path.join(ROOT, 'experiments/results/certs/n15varmax_stage1')
    masks = []
    for ln in open(vp):
        d = json.loads(ln)
        if d['verdict'] != 'CERT':
            continue
        base = os.path.join(bdir, 'base_' + '_'.join(map(str, d['mask'])) + '.txt')
        if os.path.exists(base):
            masks.append((d['mask'], base, d['vfloor']))
    # sample a spread (some LE 501, some LE 636)
    seen_floor = {}
    chosen = []
    for m in masks:
        f = m[2]
        if seen_floor.get(f, 0) < (nmasks // 2 + 1):
            chosen.append(m); seen_floor[f] = seen_floor.get(f, 0) + 1
        if len(chosen) >= nmasks:
            break
    rows = []
    npass = 0
    for (mask, base, vfloor) in chosen:
        t = time.time()
        cp, _ = run_lazy(base, 'le', vfloor, wall=120, workers=8)
        dt = time.time() - t
        ck, cv = parse_kind_val(cp)
        # CERT means xfill proved LE vfloor; cpsat must also prove LE vfloor.
        ok = (ck == 'LE' and cv == vfloor)
        npass += ok
        rows.append(('_'.join(map(str, mask)), f"xfill LE {vfloor}",
                     f"cpsat {cp} ({dt:.1f}s)", 'PASS' if ok else 'FAIL'))
    return rows, npass, len(chosen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n15', type=int, default=8)
    ap.add_argument('--skip-synth', action='store_true')
    ap.add_argument('--skip-n15', action='store_true')
    a = ap.parse_args()
    total_pass = total = 0
    if not a.skip_synth:
        print("=== SYNTHETIC BATTERY (xfill MAX vs cpsat MAX) ===")
        rows, p, n = synthetic()
        for r in rows:
            print(f"  [{r[3]}] {r[0]:16s} {r[1]:18s} {r[2]:18s}")
        print(f"  synthetic: {p}/{n} PASS\n")
        total_pass += p; total += n
    if not a.skip_n15:
        print(f"=== N=15 CERT MASKS (xfill LE vfloor vs cpsat LE vfloor), {a.n15} masks ===")
        rows, p, n = n15_certs(a.n15)
        for r in rows:
            print(f"  [{r[3]}] {r[0]:22s} {r[1]:14s} {r[2]}")
        print(f"  n15 certs: {p}/{n} PASS\n")
        total_pass += p; total += n
    print(f"TOTAL: {total_pass}/{total} PASS" + (" -- ALL MATCH" if total_pass == total else " -- MISMATCH"))
    sys.exit(0 if total_pass == total else 1)


if __name__ == '__main__':
    main()
