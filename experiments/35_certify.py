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


def derive_knap_lists(rules, main, turn):
    """Per-(col,len) Pareto-pruned candidate lists [(gross, stub-letter-usage dict)] for the
    tile-aware knapsack bound, + AVAIL (bag minus newly-placed main tiles).  Same candidate
    semantics as derive_columns; dominance pruning keeps lists small (a word is dominated if
    another scores >= with component-wise <= letter usage) -- ported from exp32/exp33."""
    W, H = rules.W, rules.H
    mt = rules.alphabet.to_tup(main)
    scoring = [x for x in range(W) if turn[x].isupper()]
    lists = {c: {} for c in scoring}
    for c in scoring:
        L = mt[c]
        byl = {}
        for w in rules.words:
            if not w or w[0] != L or len(w) > H:
                continue
            if len(w) > 1 and w[1:] not in rules.words_lookup:
                continue
            g = 0 if len(w) == 1 else int(get_word_score(rules, w, c, 0, 0,
                                                         [i == 0 for i in range(len(w))])[0])
            byl.setdefault(len(w), []).append((g, Counter(w[1:])))
        for l, items in byl.items():
            items.sort(key=lambda t: (-t[0], sum(t[1].values())))
            kept = []
            for g, rq in items:
                if not any(g2 >= g and all(rq2[k] <= rq.get(k, 0) for k in rq2)
                           for g2, rq2 in kept):
                    kept.append((g, rq))
            lists[c][l] = kept
    newly = Counter(mt[c] for c in scoring)
    avail = {code: rules.counts[code] - newly[code] for code in rules.counts}
    return lists, avail


def knap_verdict(rules, lists, avail, scoring, lvec, floor, cap=30.0):
    """Tile-aware CP-SAT knapsack UPPER bound for the vector (sound: counts only stub letters;
    blank overflow penalized at face value <= true value*wm; connectivity/legality only lower
    the score).  Returns a KNAP receipt when bound <= floor, else None.  Ported from exp32
    _knap_ub_cached (validated there: 0 violations vs CP-SAT true maxima)."""
    from ortools.sat.python import cp_model
    import math
    items = {c: lists[c].get(l, []) for c, l in zip(scoring, lvec)}
    if any(not items[c] for c in scoring):
        return {'verdict': 'NOCAND'}
    m = cp_model.CpModel()
    xv = {}
    for c in scoring:
        vs = [m.new_bool_var(f'x{c}_{i}') for i in range(len(items[c]))]
        for i, v in enumerate(vs):
            xv[(c, i)] = v
        m.add(sum(vs) == 1)
    over = {code: m.new_int_var(0, rules.blank_count, f'o{code}') for code in rules.counts} \
        if rules.blank_count else {}
    if over:
        m.add(sum(over.values()) <= rules.blank_count)
    pen = 0
    for code in rules.counts:
        usage = [xv[(c, i)] * rq[code]
                 for c in scoring for i, (g, rq) in enumerate(items[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= avail[code])
        if code in over:
            pen = pen + over[code] * rules.scores[code]
    m.maximize(sum(xv[(c, i)] * g for c in scoring
                   for i, (g, rq) in enumerate(items[c])) - pen)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 1
    s.parameters.max_time_in_seconds = cap
    s.Solve(m)
    bound = int(math.floor(s.best_objective_bound + 1e-6))   # sound even on cap-hit
    if bound <= floor:
        return {'verdict': 'KNAP', 'bound': bound, 'floor': floor}
    return None


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


# ---- stage-1 GEOM worker (multiprocessing: one RustOracle per worker process) ------------------
_G = {}


def _geom_init(board, main, turn, scale, blanks):
    from connectivity import RustOracle
    rules = make_rules(board, main, scale, blanks)
    _G['rules'] = rules
    _G['mt'] = rules.alphabet.to_tup(main)
    _G['turn'] = turn
    _G['oracle'] = RustOracle(rules.W, rules.H)
    _G['scoring'] = [x for x in range(rules.W) if turn[x].isupper()]
    _G['total'] = sum(rules.counts.values()) + rules.blank_count


def _geom_chunk(chunk):
    """Returns [(key, verdict_dict_or_None), ...] -- GEOM verdicts via the persistent Rust oracle
    (sound: prunes only when the oracle's LOWER bound on bridge cells exceeds the budget)."""
    rules = _G['rules']; mt = _G['mt']; turn = _G['turn']; oracle = _G['oracle']
    scoring = _G['scoring']; total = _G['total']
    W, H = rules.W, rules.H
    out = []
    for lvec in chunk:
        key = '-'.join(map(str, lvec))
        Lvec = {c: lvec[i] for i, c in enumerate(scoring)}
        budget = total - W - sum(l - 1 for l in Lvec.values())
        if budget < 0:
            out.append((key, {'verdict': 'GEOM', 'min_bridge_lb': 'inf', 'budget': budget}))
            continue
        fx = setup_fixed_cells(W, H, turn, mt, {c: tuple([0] * Lvec[c]) for c in scoring})
        lb, _ub = oracle.bounds(fx)
        if lb > budget:
            out.append((key, {'verdict': 'GEOM', 'oracle_lb': lb, 'budget': budget}))
        else:
            out.append((key, None))
    return out


def cmd_build(a):
    rules = make_rules(a.board, a.main, not a.no_scale, not a.no_blanks)
    scoring, best_at, mt = derive_columns(rules, a.main, a.turn)
    band = enumerate_band(rules, scoring, best_at, a.floor, a.center)
    cdir = os.path.join(ROOT, 'experiments/results/certs', a.name)
    os.makedirs(cdir, exist_ok=True)
    lpath = os.path.join(cdir, 'ledger.json')
    vpath = os.path.join(cdir, 'verdicts.jsonl')       # APPEND-ONLY: O(1) saves at millions scale
    # base file (per-main-word candidate domains) + dict for the Rust batch engine
    xtest.write_dict(a.board)
    bpath = os.path.join(cdir, 'base.txt')
    if not os.path.exists(bpath):
        xtest.dump_base(xtest.build_base(a.board, a.main, a.turn, scale=not a.no_scale), bpath)
    base_sha = sha(bpath)
    led = {'claim': {'board': a.board, 'main': a.main, 'turn': a.turn, 'floor': a.floor,
                     'center': a.center, 'scale': not a.no_scale, 'blanks': not a.no_blanks},
           'binary': {'path': XFILL, 'sha256': sha(XFILL)},
           'base_sha256': base_sha, 'band_size': len(band), 'witness': None}
    if a.witness:
        led['witness'] = json.load(open(a.witness))
    json.dump(led, open(lpath, 'w'), indent=1)
    # resume: keys already decided; keys recorded TO in an earlier pass have ALREADY survived the
    # geometric stage (geom verdicts are persisted, TO means it reached xfill) -> skip stage 1 for
    # them and send them straight back to stage 2.
    have = set(); geom_ok = set()
    if os.path.exists(vpath):
        for line in open(vpath):
            try:
                r = json.loads(line)
                vd = r.get('v', {}).get('verdict')
                if vd in ('GEOM', 'LE', 'NOCAND', 'KNAP'):
                    have.add(r['k']); geom_ok.discard(r['k'])
                elif vd == 'TO':
                    geom_ok.add(r['k'])
            except Exception:
                pass
    geom_ok -= have
    todo = [lv for lv in band if '-'.join(map(str, lv)) not in have]
    print(f'band={len(band)} (UB>{a.floor}{", center" if a.center else ""})  '
          f'cached={len(have)}  todo={len(todo)}  geom-already-passed={len(geom_ok)}', flush=True)
    t0 = time.time()
    vf = open(vpath, 'a')
    refuted = []

    def record(key, v):
        vf.write(json.dumps({'k': key, 'v': v}) + '\n')
        if v.get('verdict') == 'MAX':
            refuted.append((key, v))
            print(f'  !!! REFUTED: {key} -> {v.get("stdout")}', flush=True)

    # ---- stage 1: GEOM via parallel Rust-oracle workers (sound lb > budget prune) ----
    # Keys that already passed geom in an earlier pass (recorded TO) skip straight to stage 2.
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
    stage1_in = [lv for lv in todo if '-'.join(map(str, lv)) not in geom_ok]
    survivors = [k for k in ('-'.join(map(str, lv)) for lv in todo) if k in geom_ok]
    CH = 5000
    chunks = [stage1_in[i:i + CH] for i in range(0, len(stage1_in), CH)]
    geom_cut = 0
    if chunks:
        with ProcessPoolExecutor(max_workers=max(1, a.procs),
                                 initializer=_geom_init,
                                 initargs=(a.board, a.main, a.turn, not a.no_scale,
                                           not a.no_blanks)) as ex:
            for res in ex.map(_geom_chunk, chunks):
                for key, v in res:
                    if v:
                        record(key, v); geom_cut += 1
                    else:
                        survivors.append(key)
                vf.flush()
                print(f'  [geom] cut={geom_cut} survivors={len(survivors)} '
                      f'({time.time()-t0:.0f}s)', flush=True)
    # ---- stage 2: THREE-PASS pipeline over survivors --------------------------------------------
    # Order by optimistic UB DESCENDING (any refutation surfaces in the first minutes -> at most
    # one cheap restart) with deterministic shuffle within equal-UB groups (load balance; the
    # measured straggler fix).  Then:
    #   pass A: batchvec with a SHORT wall (--wall-a, default 2s) -- resolves the measured ~94%
    #           cheap majority at ~ms each;
    #   pass B: the TO survivors get the tile-aware CP-SAT knapsack bound (tighter than xfill's
    #           internal greedy bound; receipts record the bound);
    #   pass C: the residue runs at the LONG wall (--wall) as before.
    bdir = os.path.join(cdir, 'batches'); os.makedirs(bdir, exist_ok=True)
    rnd = random.Random(0)
    ubk = {}
    for k in survivors:
        ubk[k] = sum(best_at[c][int(l)] for c, l in zip(scoring, k.split('-')))
    survivors.sort(key=lambda k: (-ubk[k], rnd.random()))
    BCH = 500
    pass_state = {'done': 0, 'total': 0, 'label': ''}

    def run_chunk_keys(keys, ci, wall):
        lf = os.path.join(bdir, f'chunk_{pass_state["label"]}_{ci}.list')
        with open(lf, 'w') as f:
            for k in keys:
                f.write(f"{k} {' '.join(k.split('-'))} {a.floor}\n")
        env = dict(os.environ); env.pop('MAXNODES', None)
        env['BATCHWALL'] = str(wall)
        r = subprocess.run([XFILL, '--batchvec', bpath, lf], capture_output=True, text=True,
                           env=env, cwd=ROOT, timeout=(wall + 60) * max(1, len(keys)))
        out = {}
        for line in (r.stdout or '').splitlines():
            t = line.split(None, 2)
            if len(t) == 3 and t[0] == 'RES':
                out[t[1]] = t[2]
        return out

    def batch_pass(keys, wall, label):
        """Run keys through batchvec at `wall`; record LE/MAX/NOCAND; return the TO keys."""
        pass_state.update(done=0, total=len(keys), label=label)
        bchunks = [keys[i:i + BCH] for i in range(0, len(keys), BCH)]
        tos = []
        with ThreadPoolExecutor(max_workers=max(1, a.procs)) as ex:
            futs = {ex.submit(run_chunk_keys, bchunks[ci], ci, wall): ci
                    for ci in range(len(bchunks))}
            for fut in as_completed(futs):
                ci = futs[fut]; out = fut.result()
                for k in bchunks[ci]:
                    line = out.get(k, '')
                    if line.startswith('LE ') and line.split()[1].isdigit() \
                            and int(line.split()[1]) <= a.floor:
                        record(k, {'verdict': 'LE', 'stdout': line, 'base_sha256': base_sha})
                    elif line.startswith('MAX '):
                        record(k, {'verdict': 'MAX', 'stdout': line, 'base_sha256': base_sha,
                                   'max_value': int(line.split()[1])})
                    elif line == 'NOCAND':
                        record(k, {'verdict': 'NOCAND'})
                    else:
                        tos.append(k)
                pass_state['done'] += len(bchunks[ci])
                vf.flush()
                print(f'  [{label}] {pass_state["done"]}/{pass_state["total"]} '
                      f'tos={len(tos)} ({time.time()-t0:.0f}s)', flush=True)
        return tos

    wall_a = getattr(a, 'wall_a', 2.0)
    if wall_a and wall_a < a.wall and len(survivors) > 5000:
        tos_a = batch_pass(survivors, wall_a, 'passA')
        # pass B: tile-aware knapsack receipts on the short-wall survivors
        print(f'  [passB] knapsack bound on {len(tos_a)} survivors', flush=True)
        klists, avail = derive_knap_lists(rules, a.main, a.turn)
        residue = []
        kcut = 0
        with ThreadPoolExecutor(max_workers=max(1, a.procs)) as ex:
            futs = {ex.submit(knap_verdict, rules, klists, avail, scoring,
                              tuple(int(x) for x in k.split('-')), a.floor): k
                    for k in tos_a}
            for fut in as_completed(futs):
                k = futs[fut]; v = fut.result()
                if v:
                    record(k, v); kcut += 1
                    if kcut % 200 == 0:
                        vf.flush()
                        print(f'  [passB] knap-cut={kcut} ({time.time()-t0:.0f}s)', flush=True)
                else:
                    residue.append(k)
        vf.flush()
        print(f'  [passB] knap-cut={kcut}, residue={len(residue)} ({time.time()-t0:.0f}s)',
              flush=True)
        final_tos = batch_pass(residue, a.wall, 'passC') if residue else []
    else:
        final_tos = batch_pass(survivors, a.wall, 'passC')
    for k in final_tos:
        record(k, {'verdict': 'TO', 'stdout': ''})
    vf.close()
    print(f'DONE in {time.time()-t0:.0f}s.  refuted={len(refuted)}')
    if refuted:
        best = max(int(v['max_value']) for _, v in refuted)
        print(f'  !!! THE FLOOR {a.floor} IS REFUTED: best witnessed {best} -- '
              f're-witness and re-run with the higher floor.')
    print(f'ledger: {lpath}\nverdicts: {vpath}\nNow run:  check {lpath}')


def cmd_check(a):
    led = json.load(open(a.ledger))
    cl = led['claim']
    cdir = os.path.dirname(a.ledger)
    rules = make_rules(cl['board'], cl['main'], cl['scale'], cl['blanks'])
    scoring, best_at, mt = derive_columns(rules, cl['main'], cl['turn'])
    band = enumerate_band(rules, scoring, best_at, cl['floor'], cl['center'])
    fails = []
    # 0) base file integrity: re-derive and compare CANONICALLY (parsed + sorted).  A byte-wise
    #    sha comparison is wrong here: rules.words iterates a Python SET, so WORDV line order
    #    varies per process (hash randomization) while the content is identical.  The receipts
    #    bind to the literal base.txt sha (proving the engine saw THAT file); this step proves
    #    THAT file is semantically equal to an independent re-derivation.
    def canon_base(path):
        head, cols, cur_col, cur_len = [], {}, None, None
        for line in open(path):
            t = line.split()
            if not t:
                continue
            if t[0] in ('DIMS', 'DICT'):
                head.append(tuple(t))
            elif t[0] in ('COUNTS', 'SCORES', 'PREPLACED', 'NONSCORING'):
                head.append((t[0],) + tuple(sorted(t[1:])))
            elif t[0] == 'BCOL':
                cur_col = (t[1], t[2]); cols[cur_col] = {}
            elif t[0] == 'BLEN':
                cur_len = t[1]; cols[cur_col][cur_len] = []
            elif t[0] == 'WORDV':
                cols[cur_col][cur_len].append(tuple(t[1:]))
        for c in cols:
            for l in cols[c]:
                cols[c][l] = sorted(cols[c][l])
        return (sorted(head), sorted((c, sorted(ls.items())) for c, ls in cols.items()))
    bpath = os.path.join(cdir, 'base.txt')
    tmpb = os.path.join(cdir, '_chk_base.txt')
    xtest.dump_base(xtest.build_base(cl['board'], cl['main'], cl['turn'], scale=cl['scale']), tmpb)
    base_ok = os.path.exists(bpath) and canon_base(bpath) == canon_base(tmpb)
    if not base_ok:
        fails.append('base CANONICAL mismatch vs re-derived base (candidate semantics changed?)')
    if led.get('base_sha256') and (not os.path.exists(bpath) or led['base_sha256'] != sha(bpath)):
        fails.append('ledger base_sha256 does not match the base.txt the receipts bind to')
    print(f'base re-derivation (canonical): {"OK" if base_ok else "MISMATCH/absent"}')
    # 1) stream verdicts.jsonl (last verdict per key wins), then coverage over the re-derived band
    V = {}
    vpath = os.path.join(cdir, 'verdicts.jsonl')
    if os.path.exists(vpath):
        for line in open(vpath):
            try:
                r = json.loads(line); V[r['k']] = r['v']
            except Exception:
                pass
    holes = 0
    geom_keys, le_keys, knap_keys = [], [], []
    for lvec in band:
        key = '-'.join(map(str, lvec))
        v = V.get(key)
        vd = v.get('verdict') if v else None
        if vd == 'GEOM':
            geom_keys.append((key, lvec, v))
        elif vd == 'LE':
            le_keys.append((key, v))
        elif vd == 'MAX' and v.get('max_value', 10**9) <= cl['floor']:
            pass        # exhaustively proven vector max <= the claim floor: decided, sound
        elif vd == 'KNAP' and v.get('bound', 10**9) <= cl['floor']:
            knap_keys.append((key, lvec, v))    # sound tile-knapsack bound receipt
        elif vd != 'NOCAND':
            holes += 1
            if holes <= 5:
                fails.append(f'hole: {key} -> {vd}')
    if holes:
        fails.append(f'TOTAL holes: {holes} band vectors without a sound verdict')
    # 2) GEOM verdicts: re-verify a random sample with the PURE-PYTHON Steiner bound
    for key, lvec, v in random.sample(geom_keys, min(a.rerun_sample * 10, len(geom_keys))):
        g = geom_verdict(rules, mt, cl['turn'], scoring, lvec)
        if not g:
            fails.append(f'GEOM not reproducible (python Steiner): {key} {v}')
    # 2b) KNAP receipts: re-solve a random sample of the tile-knapsack bounds
    if knap_keys:
        klists, avail = derive_knap_lists(rules, cl['main'], cl['turn'])
        for key, lvec, v in random.sample(knap_keys, min(a.rerun_sample * 2, len(knap_keys))):
            rv = knap_verdict(rules, klists, avail, scoring, lvec, cl['floor'], cap=120.0)
            if not rv or rv.get('verdict') != 'KNAP':
                fails.append(f'KNAP not reproducible: {key} (receipt bound {v.get("bound")})')
            else:
                print(f'  knap re-solve ok: {key}: bound {rv["bound"]} <= {cl["floor"]}')
    # 3) LE receipts: must carry the base sha + a natural "LE f" line with f <= the claim floor
    #    (an LE-f proof for smaller f is STRONGER: max <= f <= floor).
    for key, v in le_keys:
        if v.get('base_sha256') != led.get('base_sha256'):
            fails.append(f'LE receipt base-sha mismatch: {key}')
            break
        toks = v.get('stdout', '').split()
        if len(toks) < 2 or toks[0] != 'LE' or not toks[1].isdigit() \
                or int(toks[1]) > cl['floor']:
            fails.append(f'bad LE line: {key}: {v.get("stdout")}')
            break
    # 4) re-run a sample of LE receipts through the binary (batchvec, fresh)
    if le_keys:
        samp = random.sample(le_keys, min(a.rerun_sample, len(le_keys)))
        lf = os.path.join(cdir, '_chk_rerun.list')
        with open(lf, 'w') as f:
            for key, _ in samp:
                f.write(f"{key} {' '.join(key.split('-'))} {cl['floor']}\n")
        env = dict(os.environ); env.pop('MAXNODES', None); env['BATCHWALL'] = '3600'
        r = subprocess.run([XFILL, '--batchvec', tmpb, lf], capture_output=True, text=True,
                           timeout=3700 * len(samp), cwd=ROOT)
        got = {}
        for line in (r.stdout or '').splitlines():
            t = line.split(None, 2)
            if len(t) == 3 and t[0] == 'RES':
                got[t[1]] = t[2]
        for key, _ in samp:
            line = got.get(key, '')
            if not line.startswith(f"LE {cl['floor']} "):
                fails.append(f're-run mismatch: {key}: {line}')
            else:
                print(f'  re-run ok: {key}: {line}')
    # 5) witness: independent full-rules recompute (center per claim)
    #    A witness is the LOWER side of an EQUALITY claim ("vertical optimum == F, here is a board
    #    achieving F").  A witness-free ledger is an UPPER-BOUND-ONLY claim ("no legal board's verticals
    #    exceed F"), which is fully established by band coverage alone (every band vector has a sound
    #    LE/GEOM/KNAP/MAX<=F verdict, no holes) -- this is exactly the per-word rule-out used by the global
    #    N=11 proof (verticals <= floor => turn <= seeded global lower).  So a missing witness is NOT a
    #    failure; it only means we are not ALSO asserting achievability of F.  Reported as upper-bound-only.
    wrep = None
    upper_only = not led.get('witness')
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
    if upper_only:
        print('  (no witness embedded -- UPPER-BOUND-ONLY claim: '
              f'verticals <= floor {cl["floor"]}, established by band coverage)')
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
    b.add_argument('--wall-a', type=float, default=2.0)
    b.add_argument('--procs', type=int, default=1)       # reserved; v1 is sequential+resumable
    c = sub.add_parser('check')
    c.add_argument('ledger'); c.add_argument('--rerun-sample', type=int, default=3)
    a = p.parse_args()
    (cmd_build if a.cmd == 'build' else cmd_check)(a)
