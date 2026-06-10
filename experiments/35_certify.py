"""Certification ledger for max-turn vertical-optimum claims (the machine-checkable proof artifact).

A CLAIM: for main word M on board N (scaled bag, blanks), with floor F:
    "no legal connected setup board (center-constrained or not) has vertical score > F,
     and the embedded witness achieves exactly F"  =>  vertical optimum == F.

The ledger makes the claim independently re-checkable.  It re-derives, WITHOUT exp32/exp33:
  * per-column candidate lengths and the best gross per (col,length)  [same problem definition:
    stub w[1:] must be a dict word (setup legality); length-1 = no vertical, gross 0];
  * the BAND: every length-vector whose optimistic UB (sum of per-col best gross) exceeds F,
    under the weak tile budget sum(l-1) <= bag_total - W  (a SUPERSET of any sound enumeration --
    kills the truncation-bug class);
and requires a sound verdict for every band vector:
  * GEOM   -- pure-Python Steiner lower bound (connectivity.min_bridge_cells) > bridge budget;
  * LE     -- receipt of a NATURALLY-COMPLETED, UNCAPPED `xfill --maxscore F` run printing
              "LE F": stdout line + sha256 of the instance file + sha256 of the binary;
  * MAX    -- the run found a better board: the claim is REFUTED (recorded loudly).
The witness is embedded and re-verified via witness_check (independent full-rules recompute,
center occupancy included).

Usage:
  build:  python experiments/35_certify.py build --board 11 --main bouwfysicus \
              --turn BOUWfYsiCuS --floor 224 [--center] [--no-scale] [--no-blanks] \
              [--witness witness.json] --name n11_unconstrained [--procs 8]
  check:  python experiments/35_certify.py check experiments/results/certs/<name>/ledger.json \
              [--rerun-sample 5]
Build is RESUMABLE (re-run the same command; existing verdicts are kept).
"""
import sys, os, json, time, hashlib, subprocess, random, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
from scrabble import construct_rules, get_word_score
from connectivity import min_bridge_cells, setup_fixed_cells
import xtest
import witness_check as wc

XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_lev3')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def make_rules(board, main, scale, blanks):
    rules = construct_rules('dutch', board)
    if scale:
        f = (rules.W * rules.W) / (15 * 15)
        mt = rules.alphabet.to_tup(main)
        mc = Counter(mt)
        rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
        rules.blank_count = round(rules.blank_count * f)
    if not blanks:
        rules.blank_count = 0
    return rules


def derive_columns(rules, main, turn):
    """Independently re-derive per-column available lengths + best gross per (col,length).
    Problem definition shared with the solvers: candidate vertical = dict word w, w[0] = the main
    tile, len <= H, stub w[1:] a dict word when len>=2 (setup legality); len==1 = no vertical,
    gross 0 (the bare tile already scores in the main word -- see the l=1 phantom fix)."""
    W, H = rules.W, rules.H
    mt = rules.alphabet.to_tup(main)
    scoring = [x for x in range(W) if turn[x].isupper()]
    best_at = {c: {} for c in scoring}
    for c in scoring:
        L = mt[c]
        for w in rules.words:
            if not w or w[0] != L or len(w) > H:
                continue
            if len(w) > 1 and w[1:] not in rules.words_lookup:
                continue
            g = 0 if len(w) == 1 else int(get_word_score(rules, w, c, 0, 0,
                                                         [i == 0 for i in range(len(w))])[0])
            if g > best_at[c].get(len(w), -1):
                best_at[c][len(w)] = g
    return scoring, best_at, mt


def enumerate_band(rules, scoring, best_at, floor, center):
    """All length-vectors with optimistic UB > floor under the weak budget sum(l-1) <= bag - W.
    Center: the center column's length must reach the center row (>= H//2 + 1).  Recursive with
    suffix-max pruning; returns list of tuples (lvec ordered by `scoring`)."""
    W, H = rules.W, rules.H
    total = sum(rules.counts.values()) + rules.blank_count
    stub_budget = total - W                              # weak: ignores bridge reserve (superset)
    cc, cr = W // 2, H // 2
    opts = []
    for c in scoring:
        ls = sorted(best_at[c])
        if center and c == cc:
            ls = [l for l in ls if l >= cr + 1]
        opts.append([(l, best_at[c][l]) for l in ls])
    sufmax = [0] * (len(opts) + 1)
    for i in range(len(opts) - 1, -1, -1):
        sufmax[i] = sufmax[i + 1] + max(g for _, g in opts[i])
    out = []
    vec = [0] * len(opts)

    def rec(i, used, gross):
        if gross + sufmax[i] <= floor:
            return
        if i == len(opts):
            out.append(tuple(vec))
            return
        for l, g in opts[i]:
            if used + (l - 1) > stub_budget:
                continue
            vec[i] = l
            rec(i + 1, used + (l - 1), gross + g)
        vec[i] = 0
    rec(0, 0, 0)
    return out


def geom_verdict(rules, mt, turn, scoring, lvec):
    """Sound geometric infeasibility: pure-Python Steiner lower bound > bridge budget."""
    W, H = rules.W, rules.H
    Lvec = {c: lvec[i] for i, c in enumerate(scoring)}
    fx = setup_fixed_cells(W, H, turn, mt, {c: tuple([0] * Lvec[c]) for c in scoring})
    total = sum(rules.counts.values()) + rules.blank_count
    budget = total - W - sum(l - 1 for l in Lvec.values())
    if budget < 0:
        return {'verdict': 'GEOM', 'min_bridge_lb': 'inf', 'budget': budget}
    lb, exact = min_bridge_cells(fx, W, H)
    if lb > budget:
        return {'verdict': 'GEOM', 'min_bridge_lb': lb, 'exact': exact, 'budget': budget}
    return None


def xfill_verdict(board, main, turn, scoring, lvec, floor, scale, inst_dir, wall=3600):
    """Run xfill --maxscore floor on the vector's instance.  Returns a receipt dict.
    NO MAXNODES (it would fake LE); LE must come from natural completion within `wall`."""
    Lvec = {c: lvec[i] for i, c in enumerate(scoring)}
    inst, meta = xtest.build_instance(board, main, turn, Lvec, scale=scale)
    if inst is None:
        return {'verdict': 'NOCAND'}
    name = '-'.join(map(str, lvec))
    path = os.path.join(inst_dir, f'{name}.txt')
    xtest.dump_simple(inst, 'UNKNOWN', path)
    env = dict(os.environ); env.pop('MAXNODES', None)
    try:
        r = subprocess.run([XFILL, path, '--maxscore', str(floor)], capture_output=True,
                           text=True, timeout=wall, env=env, cwd=ROOT)
    except subprocess.TimeoutExpired:
        return {'verdict': 'TO', 'wall': wall}
    line = (r.stdout or '').strip().splitlines()
    line = line[0] if line else ''
    rec = {'stdout': line, 'instance_sha256': sha(path), 'returncode': r.returncode}
    if line.startswith(f'LE {floor} '):
        rec['verdict'] = 'LE'
    elif line.startswith('MAX '):
        rec['verdict'] = 'MAX'
        rec['max_value'] = int(line.split()[1])          # REFUTES the claim -- must be surfaced
    else:
        rec['verdict'] = 'TO' if not line else 'ODD'
        rec['stderr_tail'] = (r.stderr or '')[-400:]
    return rec


def cmd_build(a):
    rules = make_rules(a.board, a.main, not a.no_scale, not a.no_blanks)
    scoring, best_at, mt = derive_columns(rules, a.main, a.turn)
    band = enumerate_band(rules, scoring, best_at, a.floor, a.center)
    cdir = os.path.join(ROOT, 'experiments/results/certs', a.name)
    inst_dir = os.path.join(cdir, 'inst'); os.makedirs(inst_dir, exist_ok=True)
    lpath = os.path.join(cdir, 'ledger.json')
    led = json.load(open(lpath)) if os.path.exists(lpath) else {
        'claim': {'board': a.board, 'main': a.main, 'turn': a.turn, 'floor': a.floor,
                  'center': a.center, 'scale': not a.no_scale, 'blanks': not a.no_blanks},
        'binary': {'path': XFILL, 'sha256': sha(XFILL)},
        'band_size': len(band), 'verdicts': {}, 'witness': None}
    led['band_size'] = len(band)
    V = led['verdicts']
    print(f'band: {len(band)} vectors with UB > {a.floor}'
          f'{" (center)" if a.center else ""}; {len(V)} verdicts cached')
    t0 = time.time(); done = 0
    for lvec in band:
        key = '-'.join(map(str, lvec))
        if key in V and V[key].get('verdict') in ('GEOM', 'LE', 'NOCAND'):
            continue
        g = geom_verdict(rules, mt, a.turn, scoring, lvec)
        V[key] = g if g else xfill_verdict(a.board, a.main, a.turn, scoring, lvec,
                                           a.floor, not a.no_scale, inst_dir, a.wall)
        done += 1
        if V[key]['verdict'] == 'MAX':
            print(f'  !!! REFUTED: {key} -> {V[key]["stdout"]}')
        if done % 10 == 0 or V[key]['verdict'] not in ('GEOM', 'LE'):
            json.dump(led, open(lpath, 'w'), indent=1)
            print(f'  [{done}] {key}: {V[key]["verdict"]} ({time.time()-t0:.0f}s)', flush=True)
    if a.witness:
        led['witness'] = json.load(open(a.witness))
    json.dump(led, open(lpath, 'w'), indent=1)
    tally = Counter(v['verdict'] for v in V.values())
    print(f'ledger -> {lpath}\n  tally: {dict(tally)}')
    holes = [k for k in ('-'.join(map(str, b)) for b in band)
             if V.get(k, {}).get('verdict') not in ('GEOM', 'LE', 'NOCAND')]
    print(f'  holes (band vectors without a sound verdict): {len(holes)}'
          + (f'  e.g. {holes[:5]}' if holes else '  => COMPLETE'))


def cmd_check(a):
    led = json.load(open(a.ledger))
    cl = led['claim']
    rules = make_rules(cl['board'], cl['main'], cl['scale'], cl['blanks'])
    scoring, best_at, mt = derive_columns(rules, cl['main'], cl['turn'])
    band = enumerate_band(rules, scoring, best_at, cl['floor'], cl['center'])
    V = led['verdicts']
    inst_dir = os.path.join(os.path.dirname(a.ledger), 'inst')
    fails = []
    # 1) coverage: every re-derived band vector has a sound verdict
    for lvec in band:
        key = '-'.join(map(str, lvec))
        v = V.get(key)
        if not v or v.get('verdict') not in ('GEOM', 'LE', 'NOCAND'):
            fails.append(f'hole: {key} -> {v and v.get("verdict")}')
    # 2) GEOM verdicts: recompute the pure-Python bound
    for lvec in band:
        key = '-'.join(map(str, lvec))
        v = V.get(key)
        if v and v.get('verdict') == 'GEOM':
            g = geom_verdict(rules, mt, cl['turn'], scoring, lvec)
            if not g:
                fails.append(f'GEOM not reproducible: {key}')
    # 3) LE receipts: instance sha must match a fresh re-dump; stdout must be a natural LE line
    recheck = []
    for lvec in band:
        key = '-'.join(map(str, lvec))
        v = V.get(key)
        if v and v.get('verdict') == 'LE':
            Lvec = {c: lvec[i] for i, c in enumerate(scoring)}
            inst, _ = xtest.build_instance(cl['board'], cl['main'], cl['turn'], Lvec,
                                           scale=cl['scale'])
            tmp = os.path.join(inst_dir, f'_chk_{key}.txt')
            xtest.dump_simple(inst, 'UNKNOWN', tmp)
            if sha(tmp) != v.get('instance_sha256'):
                fails.append(f'instance sha mismatch: {key}')
            if not v.get('stdout', '').startswith(f"LE {cl['floor']} "):
                fails.append(f'bad LE line: {key}: {v.get("stdout")}')
            recheck.append((key, tmp))
    # 4) optional re-run sample of LE receipts through the binary
    for key, tmp in random.sample(recheck, min(a.rerun_sample, len(recheck))):
        r = subprocess.run([XFILL, tmp, '--maxscore', str(cl['floor'])], capture_output=True,
                           text=True, timeout=3600, cwd=ROOT)
        line = (r.stdout or '').strip().splitlines()
        line = line[0] if line else ''
        if not line.startswith(f"LE {cl['floor']} "):
            fails.append(f're-run mismatch: {key}: {line}')
        else:
            print(f'  re-run ok: {key}: {line}')
    # 5) witness: independent full-rules recompute (center per claim)
    wrep = None
    if led.get('witness'):
        spec = led['witness']
        wr = make_rules(spec['board'], spec['main_word'], spec.get('scale', True),
                        spec.get('blanks', True))
        Wd, Hd = wr.W, wr.H
        mask = [spec['turn_str'][x].isupper() for x in range(Wd)]
        grid = spec['grid']
        blank = spec.get('blank')
        if not blank:
            blank, info = wc.derive_blanks(wr, grid, mask, Wd, Hd)
            if blank is None:
                fails.append(f'witness: no blank assignment: {info}')
        if blank is not None:
            ok, wrep = wc.check_witness(wr, Wd, Hd, grid, blank, mask,
                                        claimed_total=spec.get('claimed_total'),
                                        require_center=cl['center'])
            if not ok:
                fails.append(f'witness rejected: {wrep.get("fail")}')
    else:
        fails.append('no witness embedded (claim is upper-bound-only)')
    print(f'band={len(band)}  verdicts={len(V)}  fails={len(fails)}')
    for f in fails[:20]:
        print(f'  FAIL: {f}')
    if wrep:
        print(f'  witness: {json.dumps(wrep, default=str)[:300]}')
    print('CERTIFIED' if not fails else 'NOT CERTIFIED')
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--board', required=True); b.add_argument('--main', required=True)
    b.add_argument('--turn', required=True); b.add_argument('--floor', type=int, required=True)
    b.add_argument('--center', action='store_true'); b.add_argument('--no-scale', action='store_true')
    b.add_argument('--no-blanks', action='store_true'); b.add_argument('--witness')
    b.add_argument('--name', required=True); b.add_argument('--wall', type=int, default=3600)
    b.add_argument('--procs', type=int, default=1)       # reserved; v1 is sequential+resumable
    c = sub.add_parser('check')
    c.add_argument('ledger'); c.add_argument('--rerun-sample', type=int, default=3)
    a = p.parse_args()
    (cmd_build if a.cmd == 'build' else cmd_check)(a)
