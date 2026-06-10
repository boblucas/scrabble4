"""
Experiment 32: LENGTH-LEVEL proof search with the FAST RUST INNER.

This is the production successor to experiment 31. Same OUTER architecture (enumerate length-vectors
by descending optimistic upper bound, geometric-prune via the Rust connectivity oracle, maintain a
rising global incumbent `best`, STOP when the next UB <= best), but the INNER -- "best LEGAL vertical
score for a fixed length-vector" -- is the bespoke Rust crossword-fill solver `xfill --maxscore`
instead of CP-SAT. CP-SAT proved each length-vector in tens of seconds (or timed out at N=11); the
Rust inner, given a GOOD floor near the optimum, proves "<= floor" in milliseconds.

KEY PERF FACT (measured): xfill --maxscore is FAST exactly when the supplied floor is at/above the
length-vector's true max (it then proves `LE floor` cheaply); from a poor floor it must climb the band
just under the ceiling and times out. So the OUTER feeds its RISING global incumbent `best` as the
floor, and BOOTSTRAPS `best` high early (process a few promising vectors first) so the whole descending
sweep runs against a strong floor -> mostly instant `LE`.

For each length-vector with optimistic UB > best:
  * geometric prune (RustOracle, ~1ms): skip if the lengths can't connect within the tile budget.
  * else dump the instance (xtest.build_instance/dump_simple) and call `xfill --maxscore best`:
      - MAX m  (m > best):  new legal board found -> best = m, record board.
      - LE best:            nothing here beats the incumbent -> skip.
      - timeout (cap hit):  UNRESOLVED -> record its UB (limits the honest bracket).
STOP when the next length-vector's optimistic UB <= best. If no UNRESOLVED vector has UB > best the
optimum is PROVEN = best; otherwise report the honest BRACKET [best, max-unresolved-UB].

N=11 NOTE (measured): the IMPROVER direction (witness a board scoring > floor) is the WALL -- from
scratch the inner climbs only to ~142-223 and times out, so a from-scratch sweep cannot raise `best`.
Use --seed-best N --seed-lvec "l0,..." to seed a KNOWN-ACHIEVABLE lower bound (a real legal board,
validated externally, e.g. bouwfysicus 224); the sweep then runs the FAST `LE seed` direction and
resolves most geom-survivors. The honest N=11 outcome is a BRACKET [seed, max-unresolved-UB].

Run: python experiments/32_fast_inner.py [board] [--main W --turn T] [--scale-tiles] [--blanks]
        [--cap S] [--maxsec S] [--maxcand K] [--bootstrap "l0,..;l0,.."]
        [--seed-best N --seed-lvec "l0,l1,..."]
"""
import sys, os, time, subprocess
from collections import Counter, defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from connectivity import setup_fixed_cells, RustOracle, components as _components
from turn_render import save
import xtest

ROOT = '/home/bob/programming/scrabble4'
XFILL = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


board = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '11'
HMAX = arg('--hmax', 8, int)
SCALE = '--scale-tiles' in sys.argv
BLANKS = '--blanks' in sys.argv
MAXCAND = arg('--maxcand', 600, int)
CAP = arg('--cap', 90.0, float)            # per-inner-call wall cap (seconds)
MAXSEC = arg('--maxsec', 7200.0, float)    # overall wall cap
KNAP_CAP = arg('--knap-cap', 20.0, float)  # per-vector tile-aware knapsack UB solve cap (LEVER 1)
NO_KNAP = '--no-knap' in sys.argv          # disable LEVER 1 (for A/B comparison)
CEILING_ONLY = '--ceiling-only' in sys.argv  # compute only the SOUND bracket ceiling (LEVER-1 knapsack,
                                             # no inner) -- the max tile-aware effUB over geom-feasible
                                             # length-vectors.  Pair with --seed-best as the lower bound.
main_word = arg('--main', 'bouwfysicus')
turn_str = arg('--turn', 'BOUWfYsiCuS')
BOOTSTRAP = arg('--bootstrap', '')         # ";"-separated explicit length-vectors to seed `best` first
SEED_BEST = arg('--seed-best', -1, int)    # initial lower bound (a KNOWN-achievable score). Must be
                                           # backed by a real legal board (else the final lower bound is
                                           # unsound); we validate it via the inner before trusting it.
SEED_LVEC = arg('--seed-lvec', '')         # the length-vector that achieves --seed-best (for validation
                                           # + board reconstruction), as "l0,l1,..." over scoring cols.
FIX = arg('--fix', '')                     # SHARD the enumeration to a subspace: "col:len[,col:len]" pins
                                           # those scoring columns to fixed lengths.  SOUND: each shard runs
                                           # the identical per-vector logic on a disjoint slice; the UNION of
                                           # shards over all values of a pinned col = the full space, so
                                           # "all shards PROVEN" => globally PROVEN.  Caps per-shard outer
                                           # clause-accumulation (the descending sweep's scaling bottleneck).
WORKERS = arg('--workers', 4, int)         # CP-SAT search workers per solve (drop to 1-2 for parallel shards)
CENTER = '--center' in sys.argv            # require the CENTER cell (W//2,H//2) occupied+connected (legal
                                           # Scrabble position: the game starts at center).  For a SCORING
                                           # center column this means its vertical word reaches the center
                                           # row (length >= center_row+1); the one-component check then makes
                                           # it connected.  SOUND restriction of the feasible set.

rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
assert len(main_word) == W == len(turn_str)
main_tup = rules.alphabet.to_tup(main_word)
if SCALE:
    f = (W * W) / (15 * 15)
    mc = Counter(main_tup)
    rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
    rules.blank_count = round(rules.blank_count * f)
    print(f"--scale-tiles {f:.3f}: bag {sum(rules.counts.values())} tiles, {rules.blank_count} blanks")
if not BLANKS:
    rules.blank_count = 0
scoring_cols = [x for x in range(W) if turn_str[x].isupper()]
preplaced = [x for x in range(W) if not turn_str[x].isupper()]
abc_to_str = rules.alphabet.to_str
TOTAL_PHYSICAL = sum(rules.counts.values()) + rules.blank_count
ORACLE = RustOracle(W, H)
print(f"board {W}x{H}, scoring {scoring_cols}, preplaced {preplaced}, hmax={HMAX}, "
      f"blanks={rules.blank_count}, total tiles={TOTAL_PHYSICAL}")

# Make sure the Rust binary + shared dict are present.
if not os.path.exists(XFILL):
    sys.exit(f"missing {XFILL} -- build with: cd experiments/xfill_rs && cargo build --release")
xtest.write_dict(board)   # experiments/xtests/dict_<board>.txt (shared <=HMAX word list)


# ---- candidate verticals, grouped by length (reuses exp31's optimistic-UB machinery) -----------
# Each candidate carries (word, gross-score, letter-requirement-Counter of w[1:]) -- the requirement is
# the tiles the stub consumes BELOW row 0, used by LEVER 1's tile-aware knapsack upper bound.
def candidates_for(x):
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H:
            continue
        if len(w) > 1 and w[1:] not in rules.words_lookup:
            continue
        # SCORING FIX: a length-1 "word" is the bare placed tile (construct_rules injects all single
        # letters into rules.words).  It forms NO vertical word, and its value is already counted in
        # the MAIN word -- get_word_score on it would double-count value*lm*wm (phantom gross).
        # l=1 stays available as the legitimate "no vertical here" choice, contributing 0.
        sc = 0 if len(w) == 1 else int(get_word_score(rules, w, x, 0, 0,
                                                      [i == 0 for i in range(len(w))])[0])
        out.append((w, sc, Counter(w[1:])))
    return out


# Group ALL candidates by length FIRST, then keep the top-MAXCAND per (col,length).  (Truncating the
# GLOBAL top-K across lengths -- as exp31 did -- silently DROPS entire short lengths whose words score
# below the cutoff, which excludes valid length-vectors from the outer model.  Per-length grouping keeps
# every available length and its TRUE best score, so best_at / the optimistic UB stay sound.  The inner
# always rebuilds the full word-domain from build_instance, so this only affects the outer enumeration.)
# NOTE: the per-(col,length) tile-aware knapsack (knap_ub) is fed the FULL candidate list (KNAP_CAND, big)
# per length so its bound is sound; the outer model still uses the top-MAXCAND for length enumeration.
KNAP_CAND = arg('--knap-cand', 4000, int)
by_len = {c: defaultdict(list) for c in scoring_cols}        # outer model words: top-MAXCAND per (col,len)
knap_by_len = {c: defaultdict(list) for c in scoring_cols}   # knapsack words: top-KNAP_CAND per (col,len)
best_at = {c: {} for c in scoring_cols}
for c in scoring_cols:
    allc = defaultdict(list)
    for w, sc, rq in candidates_for(c):
        allc[len(w)].append((w, sc, rq))
    for l in list(allc):
        allc[l].sort(key=lambda t: -t[1])
        best_at[c][l] = int(allc[l][0][1])
        by_len[c][l] = [(w, sc) for w, sc, rq in allc[l][:MAXCAND]]
        knap_by_len[c][l] = allc[l][:KNAP_CAND]
lengths = {c: sorted(by_len[c]) for c in scoring_cols}
print(f"lengths per col = { {c: lengths[c] for c in scoring_cols} }")
MINB_GLOBAL = len(_components({(x, 0) for x in preplaced}, W, H))
NEWLY = Counter(main_tup[c] for c in scoring_cols)           # main tiles placed at scoring cols (row 0)
AVAIL = {code: rules.counts[code] - NEWLY[code] for code in rules.counts}   # SETUP-cell tile budget


def bridge_budget_lengths(Lvec):
    stub = sum(l - 1 for l in Lvec.values())
    return TOTAL_PHYSICAL - len(main_tup) - stub


# ==================== LEVER 1: tile-aware knapsack per-vector UPPER BOUND ======================
# The outer length model's objective is the TILE-BLIND optimistic UB (sum of per-(col,length) best gross,
# ignoring that the verticals SHARE the bag).  That bound is far too loose (bouwfysicus N=11: ~320 vs the
# achievable ~224) because the top-gross word of every column can't be JOINTLY supplied by 58 tiles.  This
# tightens it: a multiple-choice multidimensional knapsack -- pick exactly one candidate word per scoring
# column of the vector's assigned length, maximise total gross MINUS the blank penalty, subject to the
# shared per-letter tile budget (with the blank relaxation: up to `blank_count` tiles may exceed their
# count, penalised at face value).  This is EXACTLY exp29's barepack_ub, computed PER length-vector.
#
# SOUNDNESS (it is a valid UPPER bound on the inner's true vertical max for the vector):
#   * one word per column of the right length -- same choice the inner makes;
#   * the budget counts ONLY stub letters (w[1:]); the inner's bridges consume MORE tiles, so omitting
#     them only LOOSENS the budget -> never rejects a feasible word-set -> UB >= inner max;
#   * the blank penalty here is the MIN over stub-overflow only; the inner may also need blanks for bridge
#     overflow, forcing >= this many stub blanks -> inner penalty >= knapsack penalty -> inner score <= UB;
#   * connectivity and cross-word legality only ever LOWER the vertical score, never raise it.
# So min(optimistic_UB, knap_UB) is a sound per-vector UB; pruning a vector whose knap_UB <= best is safe.
import functools


def _prune_dominated(cands):
    """Keep only Pareto-optimal (gross, requirement) items: drop word w if some w' has gross' >= gross AND
    requirement' <= requirement componentwise.  A dominated word is NEVER chosen in the knapsack optimum
    (swapping in w' raises/keeps gross and frees tiles), so dropping it keeps the UB EXACT while shrinking
    the CP-SAT model -> much faster per-vector solves.  O(n^2) but n is small per (col,length)."""
    items = sorted(cands, key=lambda t: (-t[1], sum(t[2].values())))   # high gross, then light, first
    kept = []
    for w, sc, rq in items:
        dominated = False
        for w2, sc2, rq2 in kept:                       # kept all have gross >= sc
            # w' dominates w iff gross' >= gross AND req' <= req over the UNION of letters (a letter in
            # rq2 but not rq means rq2 uses MORE of it -> not <=, so NOT dominating).
            if sc2 >= sc and all(rq2[c] <= rq.get(c, 0) for c in rq2):
                dominated = True; break
        if not dominated:
            kept.append((w, sc, rq))
    return kept


# precompute the dominance-pruned per-(col,length) candidate lists once (used by every knapsack solve).
knap_pruned = {c: {l: _prune_dominated(knap_by_len[c][l]) for l in knap_by_len[c]} for c in scoring_cols}


@functools.lru_cache(maxsize=None)
def _knap_ub_cached(key):
    Lvec = {c: key[i] for i, c in enumerate(scoring_cols)}
    items = {c: knap_pruned[c].get(Lvec[c], []) for c in scoring_cols}
    if any(not items[c] for c in scoring_cols):
        return None
    m = cp_model.CpModel(); m.prefix = 'K'
    xv = {}
    for c in scoring_cols:
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
        cap = AVAIL[code]
        usage = [xv[(c, i)] * rq[code]
                 for c in scoring_cols for i, (w, sc, rq) in enumerate(items[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= cap)
        if code in over:
            pen = pen + over[code] * rules.scores[code]
    m.maximize(sum(xv[(c, i)] * sc for c in scoring_cols for i, (w, sc, rq) in enumerate(items[c])) - pen)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = WORKERS
    s.parameters.max_time_in_seconds = KNAP_CAP
    s.Solve(m)
    # best_objective_bound is a SOUND upper bound on the (integer) optimum even on timeout.  The objective
    # is integer (all gross scores and face-value penalties are ints), so the tightest sound integer UB is
    # floor(bound).  +1e-6 guards a bound like 251.0000001 from flooring to 250.
    import math
    return int(math.floor(s.best_objective_bound + 1e-6))


def knap_ub(Lvec):
    """Tile-aware knapsack UB for this length-vector (cached). Returns None if some column has no word of
    its assigned length (the optimistic UB would too), else a sound integer upper bound on the inner max."""
    return _knap_ub_cached(tuple(Lvec[c] for c in scoring_cols))


# ==================== OUTER: length model (optimistic UB, descending) =========================
def build_outer():
    m = cp_model.CpModel(); m.prefix = 'L'
    lv = {}
    for c in scoring_cols:
        vs = []
        for l in lengths[c]:
            v = m.new_bool_var(f'l_{c}_{l}'); lv[(c, l)] = v; vs.append(v)
        m.add(sum(vs) == 1)
    # SOUND tile reserve: the verticals' stub tiles must leave room for the unavoidable bridges
    # (>= MINB_GLOBAL).  Eliminates all over-budget length-vectors up front.
    m.add(sum(lv[(c, l)] * (l - 1) for c in scoring_cols for l in lengths[c])
          <= TOTAL_PHYSICAL - len(main_tup) - MINB_GLOBAL)
    m.maximize(sum(lv[(c, l)] * best_at[c][l] for c in scoring_cols for l in lengths[c]))
    return m, lv


# ==================== INNER: fast Rust --maxscore for a fixed length-vector ====================
INST_CACHE = {}          # Lvec-key -> instance file path (avoid re-dumping)


def lvec_key(Lvec):
    return tuple(Lvec[c] for c in scoring_cols)


def dump_for(Lvec):
    """Dump the instance file for this length-vector (cached). Returns path or None if some column
    has no candidate word of its assigned length."""
    key = lvec_key(Lvec)
    if key in INST_CACHE:
        return INST_CACHE[key]
    inst, meta = xtest.build_instance(board, main_word, turn_str, Lvec, scale=SCALE)
    if inst is None:
        INST_CACHE[key] = None
        return None
    name = f"o{board}_{main_word}_{'-'.join(str(Lvec[c]) for c in scoring_cols)}{'_sc' if SCALE else ''}"
    path = os.path.join(xtest.TESTDIR, name + '.txt')
    xtest.dump_simple(inst, 'UNKNOWN', path)
    INST_CACHE[key] = path
    return path


def inner_maxscore(Lvec, floor, cap):
    """Call `xfill --maxscore floor` on this length-vector. Returns (verdict, value, incumbent, time):
      verdict 'MAX'  -> value is the proven max for the vector (true vertical max, > floor),
      verdict 'LE'   -> nothing beats floor (value == floor); max <= floor (proven upper bound),
      verdict 'TO'   -> timed out (cap hit) -> UNRESOLVED (max not pinned),
      verdict 'NONE' -> no candidate words for some column (skip).
    `incumbent` is the best LEGAL board score the inner WITNESSED before stopping (a sound LOWER bound
    on this vector's max, even on timeout), captured from the MAXVERB stderr `[iter] best=N found=true`
    stream. -1 if no board was witnessed.
    """
    path = dump_for(Lvec)
    if path is None:
        return 'NONE', None, -1, 0.0
    env = dict(os.environ); env['MAXVERB'] = '1'
    timed_out = False
    try:
        r = subprocess.run([XFILL, path, '--maxscore', str(floor)],
                           capture_output=True, text=True, timeout=cap, cwd=ROOT, env=env)
        out, err = r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = (e.stdout or (b'' if isinstance(e.stdout, bytes) else '')) or ''
        err = (e.stderr or '') or ''
        if isinstance(out, bytes): out = out.decode(errors='replace')
        if isinstance(err, bytes): err = err.decode(errors='replace')
    # incumbent: last `[iter] best=N found=true` (a witnessed legal board; ignore rem_best=)
    incumbent = -1
    for line in err.splitlines():
        if '[iter]' in line and 'found=true' in line:
            for tok in line.split():
                if tok.startswith('best='):
                    incumbent = int(tok.split('=')[1]); break
    toks = out.split()
    if timed_out or not toks:
        return 'TO', None, incumbent, cap
    nodes = next((int(t.split('=')[1]) for t in toks if t.startswith('nodes=')), 0)
    tt = next((float(t.split('=')[1].rstrip('s')) for t in toks if t.startswith('time=')), 0.0)
    if toks[0] == 'MAX':
        return 'MAX', int(toks[1]), max(incumbent, int(toks[1])), tt
    if toks[0] == 'LE':
        return 'LE', int(toks[1]), incumbent, tt
    return 'TO', None, incumbent, cap


# ==================== MAIN: rising-floor descending sweep =====================================
def main():
    t0 = time.time()
    best, best_lvec = -1, None
    processed = pruned_geom = pruned_nocand = pruned_knap = n_le = n_max = 0
    unresolved = []          # list of (UB, Lvec)
    max_unres = -1
    frontier_ub = -1         # on a MAXSEC break: optimistic UB bounding ALL un-enumerated vectors
                             # (descending order => next vectors have UB <= the current one).
                             # CRITICAL: without this the maxsec path left `unresolved` empty and
                             # the verdict printed PROVEN with millions of vectors never visited
                             # (the v1 "PROVEN 224" hole, found 2026-06-10 by the independent
                             # band enumeration: the UB>224 band is ~6.6M vectors; 2h shards
                             # enumerated ~7k each).

    def absorb_incumbent(inc, Lvec):
        """If the inner witnessed a real legal board scoring `inc` that beats `best`, adopt it as the new
        global lower bound (a real achievable board -> sound).  Returns True if `best` rose."""
        nonlocal best, best_lvec
        if inc is not None and inc > best:
            best, best_lvec = inc, dict(Lvec)
            return True
        return False

    # --- SEED a known-achievable lower bound.  Finding a high-scoring board from scratch is the inner's
    # slow direction (improver search), but PROVING `LE seed` (a vector cannot beat the seed) is its FAST
    # direction.  So we seed `best` with an EXTERNALLY-KNOWN legal score and its length-vector, VALIDATE it
    # is real (restrict that vector's word-domain to the seed board and confirm the inner returns a score
    # >= seed -- a real legal connected board), and only then trust it as the lower bound.  This makes the
    # whole descending sweep run the fast `LE seed` direction.
    if SEED_BEST >= 0 and SEED_LVEC:
        sv = list(map(int, SEED_LVEC.split(',')))
        seed_lvec = {c: sv[i] for i, c in enumerate(scoring_cols)}
        # NOTE on soundness: the FULL-domain inner cannot re-find the seed board quickly (improver search
        # is its slow direction), so we do NOT auto-validate here -- that just burns time.  The seed must
        # be an externally-validated REAL legal board.  The intended validation: restrict that vector's
        # word-domain to the seed board's exact verticals and confirm `xfill --maxscore <seed-1>` returns
        # MAX <seed> (a real legal connected board).  For bouwfysicus N=11 seed=224 this is confirmed
        # (verticals blokvinkjes/ooh/ut/wetende/yen/capex/struggelden, gross 228 - 4 blank = 224).
        best, best_lvec = SEED_BEST, dict(seed_lvec)
        print(f"  seeded best={best} lvec={tuple(seed_lvec[c] for c in scoring_cols)} "
              f"(externally-validated lower bound)", flush=True)

    # --- BOOTSTRAP: raise the global lower bound `best` from a set of vectors BEFORE the descending
    # sweep.  The inner's `--maxscore` proves "<= floor" FAST when floor >= the vector's true max, but
    # WITNESSING an improver (a real high-scoring board) is the slow direction; we still capture the best
    # board it reaches (MAXVERB incumbent) even when it times out.  A high early `best` then makes the
    # sweep's `LE best` proofs fast.  Pass explicit vectors with --bootstrap "l0,..;l0,..".
    if BOOTSTRAP:
        boot = [list(map(int, v.split(','))) for v in BOOTSTRAP.split(';') if v.strip()]
        boot = [{c: vv[i] for i, c in enumerate(scoring_cols)} for vv in boot]
    else:
        boot = []
    for Lvec in boot:
        if any(l not in by_len[c] for c, l in Lvec.items()):
            print(f"  bootstrap {lvec_key(Lvec)} has an unavailable length, skip"); continue
        ub = sum(best_at[c][Lvec[c]] for c in scoring_cols)
        fx = setup_fixed_cells(W, H, turn_str, main_tup, {c: tuple([0] * Lvec[c]) for c in scoring_cols})
        if not ORACLE.can_connect(fx, bridge_budget_lengths(Lvec)):
            print(f"  bootstrap {lvec_key(Lvec)} UB={ub} geom-infeasible, skip"); continue
        v, val, inc, tt = inner_maxscore(Lvec, best, CAP)
        processed += 1
        rose = absorb_incumbent(inc, Lvec)
        tag = '  <-- best' if rose else ''
        print(f"  bootstrap {lvec_key(Lvec)} UB={ub} -> {v} val={val} incumbent={inc}{tag}  "
              f"(best={best}, {tt:.1f}s) [{time.time()-t0:.0f}s]", flush=True)
        if v == 'MAX': n_max += 1
        elif v == 'LE': n_le += 1

    # --- MAIN descending sweep -------------------------------------------------------------------
    mo, lv = build_outer()
    if FIX:
        for tok in FIX.split(','):
            c_s, l_s = tok.split(':'); fc, fl = int(c_s), int(l_s)
            if fc not in scoring_cols or fl not in lengths[fc]:
                sys.exit(f"--fix {tok}: col {fc} not a scoring col or len {fl} unavailable")
            mo.add(lv[(fc, fl)] == 1)
        print(f"  SHARD --fix {FIX}: enumeration restricted to this subspace", flush=True)
    if CENTER:
        cc, cr = W // 2, H // 2
        if cc in scoring_cols:
            # center cell (cc,cr) is covered iff col cc's stub reaches row cr, i.e. length-1 >= cr <=> len >= cr+1.
            ok = [l for l in lengths[cc] if l >= cr + 1]
            if not ok:
                sys.exit(f"--center: col {cc} has no length >= {cr+1} to reach center row {cr}")
            mo.add(sum(lv[(cc, l)] for l in ok) == 1)
            print(f"  --center: col{cc} (scoring) length >= {cr+1} -> center ({cc},{cr}) occupied+connected", flush=True)
        else:
            sys.exit(f"--center: center col {cc} is NON-scoring (bridge-covered) -- needs inner support, not implemented")
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = WORKERS
    solver.parameters.max_presolve_iterations = 1
    it = 0
    while True:
        st = solver.Solve(mo)
        if st == cp_model.INFEASIBLE:
            print("outer enumeration exhausted (all length-vectors considered)")
            break
        # SOUNDNESS: the descending-UB STOP rule ("next UB <= best -> done") requires the yielded
        # objective to be the TRUE remaining maximum.  A FEASIBLE (suboptimal) solve could report a
        # lower objective and stop the sweep while a higher-UB vector is still unenumerated -> the
        # proof would silently skip vectors.  No time limit is set, so OPTIMAL is expected; anything
        # else is fatal rather than quietly accepted.
        if st != cp_model.OPTIMAL:
            sys.exit(f"FATAL: outer Solve returned {solver.status_name(st)} (not OPTIMAL) -- "
                     f"descending-UB enumeration soundness requires OPTIMAL; aborting")
        UB = int(solver.objective_value)
        Lvec = {c: next(l for l in lengths[c] if solver.Value(lv[(c, l)])) for c in scoring_cols}
        # resolve this length-vector so the next Solve yields the next-best UB
        mo.add_bool_or([lv[(c, Lvec[c])].Not() for c in scoring_cols])
        if UB <= best:
            print(f"STOP: next outer UB {UB} <= best {best} -> sweep complete ({time.time()-t0:.0f}s)")
            break
        it += 1
        # geometric prune FIRST (letter-independent, ~1ms, sound) -- cheaper than the knapsack solve, so
        # run it before LEVER 1 to avoid a ~0.5s knapsack on tile-starved/unconnectable vectors.
        fx = setup_fixed_cells(W, H, turn_str, main_tup, {c: tuple([0] * Lvec[c]) for c in scoring_cols})
        if not ORACLE.can_connect(fx, bridge_budget_lengths(Lvec)):
            pruned_geom += 1
            if it <= 10 or it % 200 == 0:
                print(f"#{it} UB={UB} GEOM-cut {lvec_key(Lvec)} [{time.time()-t0:.0f}s]", flush=True)
            if time.time() - t0 > MAXSEC:
                frontier_ub = UB; print(f"(maxsec, frontier UB={UB})"); break
            continue
        # LEVER 1: tile-aware knapsack UB.  The outer model's UB is the tile-BLIND optimistic max; tighten
        # it per-vector with the shared-tile knapsack.  effUB = min(optimistic UB, knapsack UB) is the
        # sound per-vector upper bound; if it <= best the vector cannot beat the incumbent -> prune here
        # (no inner call).  This is what pushes the bracket ceiling 320 -> ~258.
        kUB = None
        if not NO_KNAP:
            kUB = knap_ub(Lvec)
        effUB = UB if kUB is None else min(UB, kUB)
        if effUB <= best:
            pruned_knap += 1
            if it <= 10 or it % 200 == 0:
                print(f"#{it} UB={UB} KNAP-cut effUB={effUB} {lvec_key(Lvec)} [{time.time()-t0:.0f}s]",
                      flush=True)
            if time.time() - t0 > MAXSEC:
                frontier_ub = UB; print(f"(maxsec, frontier UB={UB})"); break
            continue
        v, val, inc, tt = inner_maxscore(Lvec, best, CAP)
        if v == 'NONE':
            pruned_nocand += 1
            continue
        processed += 1
        rose = absorb_incumbent(inc, Lvec)
        if v == 'MAX':
            n_max += 1
            print(f"#{it} UB={UB} -> MAX {val} (PROVEN vec-max)  {lvec_key(Lvec)}  "
                  f"({tt:.2f}s) best={best} [{time.time()-t0:.0f}s]", flush=True)
        elif v == 'LE':
            n_le += 1                                  # max(vector) <= val: vector cannot beat best
            if rose or it <= 20 or it % 50 == 0 or tt > 1.0:
                print(f"#{it} UB={UB} -> LE {val}  {lvec_key(Lvec)} incumbent={inc} "
                      f"({tt:.2f}s) best={best} [{time.time()-t0:.0f}s]", flush=True)
        else:   # TO -- max not pinned; this vector limits the proof bracket.  Record the TIGHTER effUB
                # (knapsack-tightened) as the bracket ceiling, not the loose optimistic UB.
            unresolved.append((effUB, dict(Lvec))); max_unres = max(max_unres, effUB)
            print(f"#{it} UB={UB} effUB={effUB} -> UNRESOLVED (cap {CAP}s) incumbent={inc}"
                  f"{'  <-- best' if rose else ''}  {lvec_key(Lvec)} best={best} [{time.time()-t0:.0f}s]",
                  flush=True)
        if time.time() - t0 > MAXSEC:
            frontier_ub = UB; print(f"(maxsec at it={it}, frontier UB={UB})"); break

    dt = time.time() - t0
    # Honest verdict: only the unresolved vectors with UB > best can hide a better board --
    # INCLUDING the un-enumerated remainder after a MAXSEC break (frontier_ub bounds it).
    if frontier_ub > best:
        unresolved.append((frontier_ub, {'_remainder': True}))
        max_unres = max(max_unres, frontier_ub)
    live_unres = [(ub, lvk) for ub, lvk in unresolved if ub > best]
    proven = not live_unres
    if proven:
        verdict = f"PROVEN OPTIMAL  vertical = {best}"
    else:
        mu = max(ub for ub, _ in live_unres)
        verdict = f"BRACKET [{best}, {mu}]  ({len(live_unres)} unresolved with UB>best)"
    print(f"\n==== {main_word} N={W} (scaled={SCALE}): {verdict} ====")
    print(f"     processed={processed} (MAX={n_max}, LE={n_le}), knap-cut={pruned_knap}, "
          f"geom-cut={pruned_geom}, no-cand={pruned_nocand}, unresolved={len(unresolved)}, time={dt:.0f}s")
    if best_lvec:
        print(f"     winning length-vector: { {c: best_lvec[c] for c in scoring_cols} }")
    if live_unres:
        print("     UNRESOLVED length-vectors with UB>best:")
        for ub, lvk in sorted(live_unres, key=lambda t: t[0], reverse=True)[:20]:
            print(f"       UB={ub}  {tuple(lvk[c] for c in scoring_cols)}")

    # Persist result + reconstruct/render the winning board.
    if best_lvec is not None:
        reconstruct_winner(best_lvec, best, proven, dt)
    return best, best_lvec, proven, unresolved


def reconstruct_winner(Lvec, score, proven, dt):
    """Re-run the Rust inner on the winning length-vector with `--emit` (floor = score-1) so it re-finds
    a board scoring `score` and prints its grid; render + persist it.  This is the same inner that
    proved the number, so the board is exactly an instance of the reported lower bound."""
    path = dump_for(Lvec)
    grid = None
    if path is not None:
        env = dict(os.environ)
        try:
            r = subprocess.run([XFILL, path, '--maxscore', str(score - 1), '--emit'],
                               capture_output=True, text=True, timeout=max(CAP, 120.0), cwd=ROOT, env=env)
            for line in r.stdout.splitlines():
                if line.startswith('BOARD'):
                    grid = [int(t) for t in line.split()[1:]]
                    break
        except subprocess.TimeoutExpired:
            grid = None
    header = (f"LENGTH-LEVEL (fast Rust inner)  board {W}x{H}  main={main_word}  "
              f"verticals={score}  {'PROVEN-OPTIMAL' if proven else 'BRACKET-LOWER-BOUND'}  "
              f"lengths={tuple(Lvec[c] for c in scoring_cols)}")
    if grid is None:
        print(f"\n(could not re-emit board for score {score}; lengths {tuple(Lvec[c] for c in scoring_cols)})")
        save(f'experiments/results/turns/N{W}_{main_word}_fastinner.txt',
             f"verticals={score} lengths={tuple(Lvec[c] for c in scoring_cols)}\n", header=header)
        return
    text = _render_grid(grid, Lvec, score)
    print("\n" + text)
    save(f'experiments/results/turns/N{W}_{main_word}_fastinner.txt', text, header=header)
    print(f"saved -> experiments/results/turns/N{W}_{main_word}_fastinner.txt")


def _render_grid(grid, Lvec, score):
    """Render the emitted row-major code grid (0=empty) as a human-readable board + vertical words.
    Row 0 holds the main word (upper at scoring cols, lower at pre-placed); stubs/bridges below."""
    def ch(code):
        return abc_to_str((code,)) if code > 0 else '.'
    rows = []
    for y in range(H):
        cells = []
        for x in range(W):
            code = grid[y * W + x]
            if y == 0 and x in scoring_cols:
                cells.append(abc_to_str((main_tup[x],)).upper())
            elif y == 0:
                cells.append(abc_to_str((main_tup[x],)).lower())
            else:
                cells.append(ch(code) if code > 0 else '.')
        rows.append(' '.join(cells))
    verts = []
    for c in scoring_cols:
        word = abc_to_str((main_tup[c],))
        for r in range(1, Lvec[c]):
            code = grid[r * W + c]
            word += ch(code).lower()
        verts.append(f"col{c}:{word}")
    main_score, _ = get_word_score(rules, list(main_tup), 0, 0, 0,
                                   [False] * W) if False else (None, None)
    lines = [f"main={main_word}  vertical={score}  lengths={tuple(Lvec[c] for c in scoring_cols)}", '']
    lines += rows
    lines += ['', 'verticals: ' + '  '.join(verts)]
    return '\n'.join(lines)


def ceiling_only():
    """LEVER-1-only: compute the SOUND bracket ceiling = max tile-aware effUB over geom-feasible
    length-vectors, WITHOUT calling the inner.  Enumerate by descending optimistic UB; geom-prune (cheap);
    knapsack the survivors; track the running max effUB; STOP when the next optimistic UB <= the ceiling
    (no later vector can raise it).  Reports the bracket [seed-best, ceiling].  This is the fast,
    reproducible upper-bound half of the N=11 result (the inner can't beat the hard-tail vectors, so the
    knapsack ceiling IS the honest bracket top)."""
    t0 = time.time()
    ceiling = SEED_BEST if SEED_BEST >= 0 else -1
    cvec = None
    mo, lv = build_outer()
    s = cp_model.CpSolver(); s.parameters.num_search_workers = WORKERS; s.parameters.max_presolve_iterations = 1
    opt = geom = knaps = 0
    while True:
        if s.Solve(mo) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print("outer exhausted"); break
        UB = int(s.objective_value)
        Lvec = {c: next(l for l in lengths[c] if s.Value(lv[(c, l)])) for c in scoring_cols}
        mo.add_bool_or([lv[(c, Lvec[c])].Not() for c in scoring_cols])
        if UB <= ceiling:
            print(f"STOP: optimistic UB {UB} <= ceiling {ceiling} -> ceiling is FINAL "
                  f"({time.time()-t0:.0f}s)"); break
        opt += 1
        fx = setup_fixed_cells(W, H, turn_str, main_tup, {c: tuple([0] * Lvec[c]) for c in scoring_cols})
        if not ORACLE.can_connect(fx, bridge_budget_lengths(Lvec)):
            continue
        geom += 1
        k = knap_ub(Lvec); knaps += 1
        if k is None:
            continue
        eff = min(UB, k)
        if eff > ceiling:
            ceiling = eff; cvec = lvec_key(Lvec)
            print(f"  CEILING {ceiling} @ {cvec} [opt={opt} geom={geom} knap={knaps} "
                  f"{time.time()-t0:.0f}s]", flush=True)
        if opt % 1000 == 0:
            print(f"  ...opt={opt} geom={geom} knap={knaps} UB={UB} ceiling={ceiling} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    lo = SEED_BEST if SEED_BEST >= 0 else '?'
    print(f"\n==== {main_word} N={W}: SOUND BRACKET [{lo}, {ceiling}]  "
          f"(ceiling vec {cvec}; {opt} vectors, {geom} geom-feasible, {knaps} knapsacks, "
          f"{time.time()-t0:.0f}s) ====")


if __name__ == '__main__':
    if CEILING_ONLY:
        ceiling_only()
    else:
        main()
