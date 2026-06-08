"""
Experiment 33: FULL-TURN [proven-lower, sound-upper] BRACKET.

Combines the two existing layers:
  * exp29's MAIN-WORD enumeration: row-0 main words by main_score DESCENDING (main_word_solver + do_solve
    no-goods), a GLOBAL-vertical-UB STOP bound, and a per-main-word barepack_ub prune.
  * exp32's per-main-word VERTICAL BRACKET: enumerate that main word's length-vectors by descending
    optimistic UB, geom-prune (RustOracle), tile-aware multiple-choice knapsack UB (LEVER 1), and the FAST
    RUST inner `xfill --maxscore floor` (using the FROZEN binary) to either PROVE a vector's max or LE it.

THE FULL TURN = max over row-0 words of  main_score(word) + vertical_score(its down-words).
  proven_lower = max over EVALUATED main words of (main_score + vertical_lower)
                 -- a REAL achievable legal turn (main word placeable + a legal connected board whose
                    verticals score vertical_lower; the inner witnessed that board).
  sound_upper  = an upper bound on the TRUE turn optimum that never drops below it.  Every main word
                 contributes  main_score + (its vertical sound-upper)  to the running upper; a main word
                 PRUNED before evaluation (main_score + GVUB <= proven_lower, or barepack_ub) is provably
                 dominated and contributes nothing above proven_lower.  An UNRESOLVED vector (inner cap hit)
                 keeps its tile-aware effUB as the vertical sound-upper for its main word.

SOUNDNESS (the load-bearing invariants -- see module docstrings of exp29/exp32):
  * GVUB (exp29.global_vertical_ub) is a valid upper bound on ANY main word's vertical score (tile-aware
    assignment-knapsack over distinct columns, full bag, blank-relaxed).  So once main_score + GVUB <=
    proven_lower for the current (descending) main word, NO later (lower-main-score) word can beat the
    incumbent -> STOP is sound.
  * barepack_ub (exp29) is a per-main-word tile-aware knapsack UB on that word's verticals (no connectivity
    /legality, which only LOWER score) -> main_score + barepack_ub <= proven_lower => safely skip.
  * Per length-vector: effUB = min(optimistic UB, knap_ub) is a sound upper bound on the vector's vertical
    max (knap_ub = exp32's LEVER-1 tile-aware knapsack; budget counts only stub letters so it never rejects
    a feasible word-set; connectivity/legality only lower the score).  geom-prune (RustOracle) only drops
    PROVABLY unconnectable vectors.  So a vector dropped by geom/knap cannot raise the vertical_lower.
  * vertical_lower for a main word = the best inner-WITNESSED legal board score across its vectors (MAX
    verdicts and captured incumbents) -- always a real legal connected board.

The exact optimum stays UNPROVEN wherever the inner can't close a vector's [lower, effUB] bracket within
the cap (the documented wall): such a main word contributes main_score + vertical_upper to the sound upper.
We report a BRACKET, never overclaim.

PERSISTENCE + RESUME: progress is written to a JSON file under experiments/results/turns/ after every main
word: proven_lower, the winning turn, and a list of already-evaluated main words (by their row-0 string)
each tagged proven/bracketed with (main_score, vlow, vup).  On restart we re-enumerate main words in the
same descending order and SKIP any already recorded -> cheap resume of a days-long run.

Run:
  python experiments/33_full_turn_bracket.py <board> [--scale-tiles] [--blanks]
        [--seed-lower N]            initial global proven_lower (e.g. a known bouwfysicus turn = 850)
        [--vcap S]                  per-inner-call wall cap (default 60s)
        [--vmaxsec S]               per-MAIN-WORD overall vertical-search wall cap (default 1200s)
        [--maxmain K]               stop after K evaluated main words (0 = unbounded; for bounded validation)
        [--maxcand K] [--knap-cap S] [--knap-cand K] [--hmax N]
        [--out PATH]                progress file (default experiments/results/turns/N<W>_fullturn.json)
        [--xfill PATH]              inner binary (default the FROZEN xfill_frozen)
"""
import sys, os, time, json, subprocess, math
from collections import Counter, defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import (position_independent_row_automaton, automaton_words_from_list)
from solve import (create_board, single_component, limit_letter_count,
                   create_word_mapping, estimate_score, read_board_state, do_solve)
from connectivity import setup_fixed_cells, RustOracle, components as _components
from turn_render import save
import xtest

ROOT = '/home/bob/programming/scrabble4'
FROZEN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill_frozen')


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


board = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '11'
SCALE = '--scale-tiles' in sys.argv
BLANKS = '--blanks' in sys.argv
HMAX = arg('--hmax', 8, int)
SEED_LOWER = arg('--seed-lower', -1, int)
VCAP = arg('--vcap', 60.0, float)            # per-inner-call wall cap (seconds)
VMAXSEC = arg('--vmaxsec', 1200.0, float)    # per-main-word vertical-search overall cap
MAXMAIN = arg('--maxmain', 0, int)           # 0 = unbounded
MAXCAND = arg('--maxcand', 600, int)
KNAP_CAP = arg('--knap-cap', 20.0, float)
KNAP_CAND = arg('--knap-cand', 4000, int)
CORES = arg('--cores', 12, int)
GVUB_CAP = arg('--gvub-cap', 60.0, float)    # cap for the global-vertical-UB knapsack solve (bound is sound on timeout)
GVUB_OVERRIDE = arg('--gvub', -1, int)       # supply a precomputed sound GVUB to skip the solve (must be a valid UB)
XFILL = arg('--xfill', FROZEN)

rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
ABC = len(rules.abc)
if SCALE:
    f = (W * W) / (15 * 15)
    # NOTE: the per-main-word bag must MATCH xtest.build_instance's scaling (max(round(n*f), mc[c], 1)),
    # but mc[c] (main-word letter counts) is main-word-specific.  build_instance applies it per call; the
    # main-word ENUMERATION here uses the main-word-INDEPENDENT floor max(round(n*f), 1).  This is the same
    # bag exp29 used.  The inner (xtest.build_instance) re-derives the exact per-main-word bag, so the
    # vertical bracket is always computed against the correct counts; the only place the enumeration bag is
    # used is the GVUB/barepack/length-model UBs, all of which are UPPER bounds and stay sound (a slightly
    # larger floor count only loosens an upper bound).
    rules.counts = Counter({c: max(round(n * f), 1) for c, n in rules.counts.items()})
    rules.blank_count = round(rules.blank_count * f)
    print(f"--scale-tiles {f:.4f}: bag {sum(rules.counts.values())} tiles, {rules.blank_count} blanks")
if not BLANKS:
    rules.blank_count = 0
TOTAL_PHYSICAL = sum(rules.counts.values()) + rules.blank_count
ORACLE = RustOracle(W, H)
OUT = arg('--out', os.path.join(ROOT, f'experiments/results/turns/N{W}_fullturn.json'))
BESTTXT = os.path.join(ROOT, f'experiments/results/turns/N{W}_fullturn_BEST.txt')

print(f"=== exp33 full-turn bracket  board {W}x{H}  scale={SCALE} blanks={rules.blank_count} "
      f"total tiles={TOTAL_PHYSICAL}  inner={os.path.basename(XFILL)} ===")
if not os.path.exists(XFILL):
    sys.exit(f"missing inner binary {XFILL}")
xtest.write_dict(board)


# ====================================================================================================
#  exp29 LAYER: main-word enumeration (descending main_score), global vertical UB, barepack UB
# ====================================================================================================
def main_word_solver(no_main_blanks=True):
    model = cp_model.CpModel(); model.prefix = 'pre'
    one = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
    short = automaton_words_from_list([w for w in rules.words_lookup if len(w) <= 3], W)
    cells = create_board(model, [short], [one] * W, alphabet_size=ABC)
    mult_active = {(x, y): ~cell.active for (x, y), cell in cells.items()
                   if rules.word_multiplier[y][x] > 1 or rules.letter_multiplier[y][x] > 1}
    model.prefix = 'suf'
    full = automaton_words_from_list([w for w in rules.words_lookup if len(w) == W], W)
    cells2 = create_board(model, [full], [one] * W, alphabet_size=ABC)
    limit_letter_count(model, cells2, rules.counts)
    model.add(sum(c.blank for c in cells2.values()) <= rules.blank_count)
    if no_main_blanks:
        for x in range(W):
            model.add(cells2[(x, 0)].blank == 0)
    for p, a in cells.items():
        model.add(cells2[p].active == 1).only_enforce_if(a.active)
        for c in a.letter:
            model.add(a.letter[c] == cells2[p].letter[c]).only_enforce_if(a.active)
    slots = create_word_mapping(model, cells2, None, alphabet_size=ABC)
    score = estimate_score(model, slots, rules.word_multiplier, rules.letter_multiplier,
                           mult_active, rules.scores, {(0, 0, 1)}, bingo=False)
    is_bingo = model.new_bool_var('is_bingo')
    placed = W - sum(c.active for c in cells.values())
    model.add(placed == rules.hand_size).only_enforce_if(is_bingo)
    model.add(placed <= rules.hand_size)
    score += is_bingo * rules.emptyhand_bonus
    model.maximize(score)
    return model, cells, cells2


def global_vertical_ub(top_k=200):
    """Valid upper bound on ANY main word's vertical score (tile-aware assignment-knapsack, full bag)."""
    words = []
    for w in rules.words:
        if not w or (len(w) > 1 and w[1:] not in rules.words_lookup):
            continue
        words.append((sum(rules.scores[c] for c in w), rules.scores[w[0]], Counter(w[1:])))
    cols = {}
    for x in range(W):
        lm = int(rules.letter_multiplier[0][x]); wm = int(rules.word_multiplier[0][x])
        cols[x] = sorted(((base + tv * (lm - 1)) * wm, req) for base, tv, req in words)[-top_k:]
    m = cp_model.CpModel(); yv = {}
    for x in range(W):
        vs = [m.new_bool_var(f'y{x}_{i}') for i in range(len(cols[x]))]
        for i, v in enumerate(vs):
            yv[(x, i)] = v
        m.add(sum(vs) <= 1)
    m.add(sum(yv.values()) <= rules.hand_size)
    over = {c: m.new_int_var(0, rules.blank_count, f'go{c}') for c in rules.counts} if rules.blank_count else {}
    if over:
        m.add(sum(over.values()) <= rules.blank_count)
    for code in rules.counts:
        u = [yv[(x, i)] * cols[x][i][1][code] for x in range(W) for i in range(len(cols[x])) if cols[x][i][1][code]]
        if u:
            m.add(sum(u) - over.get(code, 0) <= rules.counts[code])
    m.maximize(sum(yv[(x, i)] * cols[x][i][0] for x in range(W) for i in range(len(cols[x]))))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 8
    s.parameters.max_time_in_seconds = GVUB_CAP
    s.Solve(m)
    # best_objective_bound is a SOUND upper bound on the (integer) optimum even on a cap-hit timeout,
    # so this stays a valid GLOBAL vertical UB regardless of GVUB_CAP.
    return int(math.floor(s.best_objective_bound + 1e-6))


def candidates_for(main_tup, x):
    """Per scoring-col candidate verticals: (word, gross vertical score, stub letter Counter)."""
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H:
            continue
        if len(w) > 1 and w[1:] not in rules.words_lookup:
            continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, int(sc), Counter(w[1:])))
    return out


def barepack_ub(main_tup, scoring, cands):
    """Per-main-word tile-aware knapsack UB on the verticals (no connectivity/legality)."""
    m = cp_model.CpModel(); xv = {}
    for c in scoring:
        vs = [m.new_bool_var(f'b_{c}_{i}') for i in range(len(cands[c]))]
        for i, v in enumerate(vs):
            xv[(c, i)] = v
        m.add(sum(vs) == 1)
    over = {code: m.new_int_var(0, rules.blank_count, f'bo_{code}') for code in rules.counts} \
        if rules.blank_count else {}
    if over:
        m.add(sum(over.values()) <= rules.blank_count)
    pen = 0
    newly = Counter(main_tup[c] for c in scoring)
    for code in rules.counts:
        cap = rules.counts[code] - newly[code]
        usage = [xv[(c, i)] * rq[code] for c in scoring for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= cap)
        if code in over:
            pen = pen + over[code] * rules.scores[code]
    m.maximize(sum(xv[(c, i)] * sc for c in scoring for i, (w, sc, rq) in enumerate(cands[c])) - pen)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 8; s.parameters.max_time_in_seconds = 60
    s.Solve(m)
    return int(math.floor(s.best_objective_bound + 1e-6))


# ====================================================================================================
#  exp32 LAYER: per-main-word vertical bracket (descending-UB length-vectors + knapsack + Rust inner)
# ====================================================================================================
def _prune_dominated(cands):
    items = sorted(cands, key=lambda t: (-t[1], sum(t[2].values())))
    kept = []
    for w, sc, rq in items:
        dominated = False
        for w2, sc2, rq2 in kept:
            if sc2 >= sc and all(rq2[c] <= rq.get(c, 0) for c in rq2):
                dominated = True; break
        if not dominated:
            kept.append((w, sc, rq))
    return kept


class VerticalBracket:
    """Per-main-word vertical search: returns (vlow, vup, proven, winning_lvec) where
       vlow  = best inner-witnessed legal vertical score (a REAL board) -- a sound LOWER bound,
       vup   = sound UPPER bound on this main word's vertical max,
       proven= (no unresolved vector with effUB > vlow) i.e. vlow == vertical optimum for this word.
    `floor0` seeds the inner's rising floor with the GLOBAL proven_lower's vertical headroom so the inner
    runs its FAST `LE` direction; vlow may still rise if the inner witnesses a better board.
    """
    def __init__(self, main_word, turn_str):
        self.main_word = main_word
        self.turn_str = turn_str
        self.main_tup = rules.alphabet.to_tup(main_word)
        self.scoring = [x for x in range(W) if turn_str[x].isupper()]
        self.preplaced = [x for x in range(W) if not turn_str[x].isupper()]
        # candidate verticals grouped by length (top-MAXCAND for the outer model; top-KNAP_CAND for knap)
        by_len = {c: defaultdict(list) for c in self.scoring}
        knap_by_len = {c: defaultdict(list) for c in self.scoring}
        self.best_at = {c: {} for c in self.scoring}
        for c in self.scoring:
            allc = defaultdict(list)
            for w, sc, rq in candidates_for(self.main_tup, c):
                allc[len(w)].append((w, sc, rq))
            for l in list(allc):
                allc[l].sort(key=lambda t: -t[1])
                self.best_at[c][l] = int(allc[l][0][1])
                by_len[c][l] = [(w, sc) for w, sc, rq in allc[l][:MAXCAND]]
                knap_by_len[c][l] = allc[l][:KNAP_CAND]
        self.by_len = by_len
        self.lengths = {c: sorted(by_len[c]) for c in self.scoring}
        self.knap_pruned = {c: {l: _prune_dominated(knap_by_len[c][l]) for l in knap_by_len[c]}
                            for c in self.scoring}
        self.newly = Counter(self.main_tup[c] for c in self.scoring)
        self.avail = {code: rules.counts[code] - self.newly[code] for code in rules.counts}
        self.minb_global = len(_components({(x, 0) for x in self.preplaced}, W, H))
        self._knap_cache = {}
        self._inst_cache = {}

    # ---- tile-aware knapsack UB per length-vector (LEVER 1) ----
    def knap_ub(self, Lvec):
        key = tuple(Lvec[c] for c in self.scoring)
        if key in self._knap_cache:
            return self._knap_cache[key]
        items = {c: self.knap_pruned[c].get(Lvec[c], []) for c in self.scoring}
        if any(not items[c] for c in self.scoring):
            self._knap_cache[key] = None
            return None
        m = cp_model.CpModel(); xv = {}
        for c in self.scoring:
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
            cap = self.avail[code]
            usage = [xv[(c, i)] * rq[code]
                     for c in self.scoring for i, (w, sc, rq) in enumerate(items[c]) if rq[code]]
            if usage:
                m.add(sum(usage) - over.get(code, 0) <= cap)
            if code in over:
                pen = pen + over[code] * rules.scores[code]
        m.maximize(sum(xv[(c, i)] * sc for c in self.scoring
                       for i, (w, sc, rq) in enumerate(items[c])) - pen)
        s = cp_model.CpSolver(); s.parameters.num_search_workers = 4
        s.parameters.max_time_in_seconds = KNAP_CAP
        s.Solve(m)
        v = int(math.floor(s.best_objective_bound + 1e-6))
        self._knap_cache[key] = v
        return v

    def _bridge_budget(self, Lvec):
        stub = sum(l - 1 for l in Lvec.values())
        return TOTAL_PHYSICAL - len(self.main_tup) - stub

    def build_outer(self):
        m = cp_model.CpModel(); m.prefix = 'L'
        lv = {}
        for c in self.scoring:
            vs = []
            for l in self.lengths[c]:
                v = m.new_bool_var(f'l_{c}_{l}'); lv[(c, l)] = v; vs.append(v)
            m.add(sum(vs) == 1)
        m.add(sum(lv[(c, l)] * (l - 1) for c in self.scoring for l in self.lengths[c])
              <= TOTAL_PHYSICAL - len(self.main_tup) - self.minb_global)
        m.maximize(sum(lv[(c, l)] * self.best_at[c][l] for c in self.scoring for l in self.lengths[c]))
        return m, lv

    def _dump_for(self, Lvec):
        key = tuple(Lvec[c] for c in self.scoring)
        if key in self._inst_cache:
            return self._inst_cache[key]
        inst, meta = xtest.build_instance(board, self.main_word, self.turn_str, Lvec, scale=SCALE)
        if inst is None:
            self._inst_cache[key] = None
            return None
        name = (f"t{board}_{self.main_word}_{'-'.join(str(Lvec[c]) for c in self.scoring)}"
                f"{'_sc' if SCALE else ''}")
        path = os.path.join(xtest.TESTDIR, name + '.txt')
        xtest.dump_simple(inst, 'UNKNOWN', path)
        self._inst_cache[key] = path
        return path

    def inner_maxscore(self, Lvec, floor, cap):
        path = self._dump_for(Lvec)
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
            out = (e.stdout or '') or ''
            err = (e.stderr or '') or ''
            if isinstance(out, bytes): out = out.decode(errors='replace')
            if isinstance(err, bytes): err = err.decode(errors='replace')
        incumbent = -1
        for line in err.splitlines():
            if '[iter]' in line and 'found=true' in line:
                for tok in line.split():
                    if tok.startswith('best='):
                        incumbent = int(tok.split('=')[1]); break
        toks = out.split()
        if timed_out or not toks:
            return 'TO', None, incumbent, cap
        tt = next((float(t.split('=')[1].rstrip('s')) for t in toks if t.startswith('time=')), 0.0)
        if toks[0] == 'MAX':
            return 'MAX', int(toks[1]), max(incumbent, int(toks[1])), tt
        if toks[0] == 'LE':
            return 'LE', int(toks[1]), incumbent, tt
        return 'TO', None, incumbent, cap

    def search(self, floor0, log_prefix=''):
        """Run the per-main-word descending vertical sweep with rising floor seeded at floor0.
        Returns dict(vlow, vup, proven, vlvec, n_max, n_le, n_to, geom, knap, time).

        SOUND vertical UPPER bound for the whole main word (vup):
          Classify every length-vector this word can have.  At the moment we decide a vector, the inner
          floor in force is some `floor` (>= floor0, monotonically non-decreasing as vlow rises).
            * geom-cut / knap-cut (effUB <= floor): that vector's vertical max <= floor  (effUB is sound).
            * inner LE floor: vector's max <= floor.
            * inner MAX m: vector's max == m  (exact for that vector).
            * inner TO (unresolved): vector's max <= effUB.
            * NEVER REACHED (outer STOP UB <= floor, or VMAXSEC break before exhaustion): the outer
              optimistic UB bounds ALL remaining vectors, and at the break point that UB <= the current
              `floor` (STOP) or == the last popped UB (VMAXSEC break) -> bound the remainder by that UB.
          So vup = max over: every floor we cut/LE'd at, every MAX m, every live unresolved effUB, and the
          remainder-UB.  We accumulate `bound_from_cuts` = the max floor at which any vector was bounded
          (covers geom/knap/LE), `max_witnessed` (max MAX m), live unresolved effUBs, and `remainder_ub`.
        """
        t0 = time.time()
        vlow, vlvec = -1, None                 # best WITNESSED legal vertical score (a real board) -> lower
        n_max = n_le = n_to = geom = knap = nocand = 0
        unresolved = []                        # (effUB, lvec_key) for inner-TO vectors with effUB>floor
        bound_from_cuts = -1                   # max floor at which some vector was proven <= floor
        max_witnessed = -1                     # max MAX-verdict value (exact per-vector maxima)
        remainder_ub = -1                      # optimistic UB bounding all NOT-yet-decided vectors
        exhausted = False
        timed_out = False
        mo, lv = self.build_outer()
        solver = cp_model.CpSolver(); solver.parameters.num_search_workers = 4
        solver.parameters.max_presolve_iterations = 1
        it = 0
        while True:
            if solver.Solve(mo) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                exhausted = True
                break
            UB = int(solver.objective_value)
            Lvec = {c: next(l for l in self.lengths[c] if solver.Value(lv[(c, l)])) for c in self.scoring}
            mo.add_bool_or([lv[(c, Lvec[c])].Not() for c in self.scoring])
            # floor the inner with the better of: this main word's own witnessed vlow, and the global
            # headroom floor0.  A vector whose optimistic UB <= that floor cannot beat it -> STOP sweep.
            floor = max(vlow, floor0)
            if UB <= floor:
                # outer STOP: every remaining (this + lower-UB) vector has optimistic UB <= floor.
                remainder_ub = max(remainder_ub, UB)
                exhausted = True
                break
            if time.time() - t0 > VMAXSEC:
                remainder_ub = max(remainder_ub, UB)    # this UB bounds the unexplored remainder
                timed_out = True
                break
            it += 1
            fx = setup_fixed_cells(W, H, self.turn_str, self.main_tup,
                                   {c: tuple([0] * Lvec[c]) for c in self.scoring})
            if not ORACLE.can_connect(fx, self._bridge_budget(Lvec)):
                geom += 1                                   # vertical max for this vector = 0 (no board)
                continue
            kUB = self.knap_ub(Lvec)
            effUB = UB if kUB is None else min(UB, kUB)
            if effUB <= floor:
                knap += 1
                bound_from_cuts = max(bound_from_cuts, effUB)   # this vector's max <= effUB(<=floor)
                continue
            v, val, inc, tt = self.inner_maxscore(Lvec, floor, VCAP)
            if v == 'NONE':
                nocand += 1
                continue
            if inc is not None and inc > vlow:              # a real legal board -> sound lower bound
                vlow, vlvec = inc, dict(Lvec)
            if v == 'MAX':
                n_max += 1
                max_witnessed = max(max_witnessed, val)     # exact max for this vector
            elif v == 'LE':
                n_le += 1
                bound_from_cuts = max(bound_from_cuts, floor)  # this vector's max <= floor
            else:                                            # TO -- unresolved
                n_to += 1
                unresolved.append((effUB, tuple(Lvec[c] for c in self.scoring)))
        # assemble the sound vertical upper bound.  Live unresolved vectors are those whose effUB exceeds
        # what we've already PROVEN achievable (vlow): they alone can still hide a higher vertical.
        live_unres = [ub for ub, _ in unresolved if ub > vlow]
        vup = max(vlow, bound_from_cuts, max_witnessed, remainder_ub,
                  max(live_unres) if live_unres else -1)
        # `resolved` = this main word's vertical bracket is CLOSED on the upper side: the sweep finished
        # without a VMAXSEC timeout and no length-vector is left unresolved (live_unres empty).  Then vup is
        # a TIGHT, FINAL upper bound on this word's verticals (it equals the witnessed vlow whenever vlow was
        # the best, or the floor below which the word was proven not to beat the incumbent).
        resolved = (not timed_out) and (not live_unres)
        # PROVEN-OPTIMAL for this word = resolved AND a board was witnessed that meets the upper (vlow==vup).
        proven = resolved and vlow >= 0 and vup <= vlow
        return dict(vlow=vlow, vup=vup, proven=proven, resolved=resolved, vlvec=vlvec,
                    n_max=n_max, n_le=n_le, n_to=n_to, geom=geom, knap=knap, time=time.time() - t0)


# ====================================================================================================
#  PERSISTENCE
# ====================================================================================================
def load_progress():
    if os.path.exists(OUT):
        try:
            with open(OUT) as fp:
                return json.load(fp)
        except Exception:
            pass
    return {'board': W, 'scale': SCALE, 'blanks': rules.blank_count, 'proven_lower': -1,
            'best_turn': None, 'evaluated': {}, 'sound_upper': None, 'stopped': False}


def save_progress(prog):
    tmp = OUT + '.tmp'
    with open(tmp, 'w') as fp:
        json.dump(prog, fp, indent=1)
    os.replace(tmp, OUT)


def emit_best_board(main_word, turn_str, vb, vlvec, vlow):
    """Re-run the inner with --emit on the winning length-vector to render+persist the board.
    `vlvec` is the {col: length} dict returned by VerticalBracket.search (already keyed by scoring col)."""
    Lvec = dict(vlvec)
    path = vb._dump_for(Lvec)
    grid = None
    if path is not None:
        try:
            r = subprocess.run([XFILL, path, '--maxscore', str(vlow - 1), '--emit'],
                               capture_output=True, text=True, timeout=max(VCAP, 120.0), cwd=ROOT)
            for line in r.stdout.splitlines():
                if line.startswith('BOARD'):
                    grid = [int(t) for t in line.split()[1:]]
                    break
        except subprocess.TimeoutExpired:
            grid = None
    abc_to_str = rules.alphabet.to_str
    main_tup = rules.alphabet.to_tup(main_word)
    lines = []
    if grid is not None:
        for y in range(H):
            cells = []
            for x in range(W):
                code = grid[y * W + x]
                if y == 0 and x in vb.scoring:
                    cells.append(abc_to_str((main_tup[x],)).upper())
                elif y == 0:
                    cells.append(abc_to_str((main_tup[x],)).lower())
                else:
                    cells.append(abc_to_str((code,)) if code > 0 else '.')
            lines.append(' '.join(cells))
        verts = []
        for c in vb.scoring:
            word = abc_to_str((main_tup[c],))
            for r in range(1, Lvec[c]):
                code = grid[r * W + c]
                word += (abc_to_str((code,)) if code > 0 else '.').lower()
            verts.append(f"col{c}:{word}")
        lines += ['', 'verticals: ' + '  '.join(verts)]
    return '\n'.join(lines) if lines else '(board not re-emitted)'


# ====================================================================================================
#  MAIN
# ====================================================================================================
def main():
    t0 = time.time()
    prog = load_progress()
    if GVUB_OVERRIDE >= 0:
        GVUB = GVUB_OVERRIDE
        print(f"global vertical UB (STOP bound) = {GVUB}  (supplied via --gvub)", flush=True)
    elif prog.get('gvub') is not None and prog.get('gvub', -1) >= 0:
        GVUB = prog['gvub']
        print(f"global vertical UB (STOP bound) = {GVUB}  (reused from progress file)", flush=True)
    else:
        GVUB = global_vertical_ub()
        print(f"global vertical UB (STOP bound) = {GVUB}", flush=True)
    proven_lower = max(prog.get('proven_lower', -1), SEED_LOWER)
    best_turn = prog.get('best_turn')
    evaluated = prog.get('evaluated', {})   # mword -> [main_score, vlow, vup, proven]
    print(f"resume: {len(evaluated)} main words already evaluated, proven_lower={proven_lower}", flush=True)

    mw_model, pre_cells, post_cells = main_word_solver(no_main_blanks=True)
    nmain = 0
    n_new = 0
    stopped_clean = False
    for msolver in do_solve(mw_model, log=False, cores=CORES):
        main_score = int(msolver.objective_value)
        setup = ''.join(x if x else ' ' for x in read_board_state(msolver, pre_cells, rules.alphabet)[0])
        mword = ''.join(x if x else ' ' for x in read_board_state(msolver, post_cells, rules.alphabet)[0])
        turn_str = ''.join(c.upper() if setup[i] == ' ' else c for i, c in enumerate(mword))
        mw_model.add_bool_or([~[v for v in list(cell.letter.values()) + [~cell.active]
                                if msolver.Value(v)][0] for cell in post_cells.values()])
        nmain += 1

        # STOP: descending main_score; once main_score + GVUB <= proven_lower no later word can beat it.
        if main_score + GVUB <= proven_lower:
            print(f"STOP: main #{nmain} '{mword}' score {main_score} + GVUB {GVUB} = "
                  f"{main_score + GVUB} <= proven_lower {proven_lower}  -> sweep complete", flush=True)
            stopped_clean = True
            break

        # resume: skip already-evaluated main words (re-enumerated in the same order).
        if mword in evaluated:
            continue

        # cheap per-main-word barepack prune (tile-aware, no connectivity) -> skip dominated words.
        main_tup = rules.alphabet.to_tup(mword.lower())
        scoring = [x for x in range(W) if turn_str[x].isupper()]
        cands = {c: candidates_for(main_tup, c) for c in scoring}
        if any(not cands[c] for c in scoring):
            # A scoring column with NO valid vertical word (of any length >=2, nor a 1-letter word) cannot
            # host a legal down-word; the holistic/inner model (which requires one chosen word per scoring
            # column) is then infeasible -- exactly as exp29 skips such a main word ("vert=INFEASIBLE/none").
            # We do NOT claim a lower bound for it, but to keep the GLOBAL upper sound we bound its verticals
            # by GVUB (a valid upper on ANY main word's verticals).  Since main_score is descending, such a
            # word near the top would already STOP the sweep if main_score+GVUB<=proven_lower; otherwise it
            # honestly widens the upper.  Marked NOT resolved.
            evaluated[mword] = [main_score, None, GVUB, False, False]
            n_new += 1
            if n_new % 25 == 0:
                save_progress({**prog, 'proven_lower': proven_lower, 'best_turn': best_turn,
                               'evaluated': evaluated, 'sound_upper': None, 'gvub': GVUB})
            continue
        bp = barepack_ub(main_tup, scoring, cands)
        if main_score + bp <= proven_lower:
            # pruned: verticals can't exceed bp (a sound tile-aware upper), so main_score+bp<=proven_lower
            # means this word can't beat the incumbent.  bp is a FINAL sound vertical upper -> resolved.
            evaluated[mword] = [main_score, None, bp, False, True]
            if n_new % 25 == 0:
                save_progress({**prog, 'proven_lower': proven_lower, 'best_turn': best_turn,
                               'evaluated': evaluated, 'sound_upper': None, 'gvub': GVUB})
            n_new += 1
            continue

        # full per-main-word vertical bracket.  Seed the inner floor with the headroom the GLOBAL
        # proven_lower leaves for THIS main word: floor0 = proven_lower - main_score (a vertical score
        # at/below floor0 can't make this word beat the incumbent, so proving LE floor0 is enough).
        floor0 = max(0, proven_lower - main_score)
        vb = VerticalBracket(mword.lower(), turn_str)
        res = vb.search(floor0, log_prefix=f"#{nmain} {mword}")
        vlow, vup, vproven, vlvec = res['vlow'], res['vup'], res['proven'], res['vlvec']
        # a main word always at least achieves vlow=verticals if the inner witnessed one; if NO vector was
        # ever evaluated (all geom/knap-cut because effUB<=floor0) then the word is provably <= proven_lower
        # and vlow stays -1 (it contributes nothing to the lower bound; vup<=floor0+something stays sound).
        tot_low = main_score + max(vlow, 0)
        tot_up = main_score + max(vup, 0)
        vresolved = res['resolved']
        evaluated[mword] = [main_score, vlow, vup, bool(vproven), bool(vresolved)]
        rose = ''
        if vlow >= 0 and tot_low > proven_lower:
            proven_lower = tot_low
            best_turn = {'main_word': mword.lower(), 'turn_str': turn_str, 'main_score': main_score,
                         'vertical': vlow, 'total': tot_low,
                         'lvec': list(vlvec.values()) if vlvec else None,
                         'scoring': scoring}
            rose = '  <-- NEW BEST'
            # persist a viewable board
            board_txt = emit_best_board(mword.lower(), turn_str, vb, vlvec, vlow) if vlvec else ''
            save(BESTTXT,
                 f"main_word={mword.lower()}  turn={turn_str}\n"
                 f"main={main_score} + verticals={vlow} = TOTAL {tot_low}  "
                 f"(vertical {'PROVEN' if vproven else 'bracketed up to '+str(vup)})\n"
                 f"lengths={tuple(vlvec.values()) if vlvec else None}\n\n{board_txt}\n",
                 header=f"board {W}x{H}  full-turn BEST after main #{nmain}")
        n_new += 1
        print(f"#{nmain} '{mword}' main={main_score} vert=[{max(vlow,0)},{max(vup,0)}] "
              f"{'PROVEN' if vproven else 'BRACKET'} -> turn=[{tot_low},{tot_up}]  "
              f"(MAX={res['n_max']} LE={res['n_le']} TO={res['n_to']} geom={res['geom']} "
              f"knap={res['knap']} {res['time']:.0f}s) proven_lower={proven_lower}{rose} "
              f"[{time.time()-t0:.0f}s]", flush=True)

        # persist every main word (cheap resume).
        save_progress({**prog, 'proven_lower': proven_lower, 'best_turn': best_turn,
                       'evaluated': evaluated, 'sound_upper': None, 'gvub': GVUB})

        if MAXMAIN and n_new >= MAXMAIN:
            print(f"(maxmain {MAXMAIN} reached after {n_new} new evaluations)", flush=True)
            break

    # ---- final sound upper bound over the WHOLE search --------------------------------------------
    # proven_lower is a real achievable turn.  The sound upper = max over all main words of
    # (main_score + that word's vertical upper).  For evaluated words we stored vup; for words NOT yet
    # reached (if we stopped via MAXMAIN, not the GVUB STOP) the bound is main_score_of_next + GVUB, but
    # since we only stop cleanly via GVUB STOP (=> all unevaluated words have main_score+GVUB<=proven_lower),
    # a CLEAN finish makes sound_upper = max(proven_lower, max evaluated (main+vup)).  A MAXMAIN/timeout
    # finish leaves the frontier open: the upper is then max(evaluated uppers, last_main_score + GVUB).
    sound_upper = proven_lower
    n_unresolved_words = 0
    for mw, rec in evaluated.items():
        ms, vlo, vup, pv, rsv = (rec + [True])[:5]
        if vup is not None:
            sound_upper = max(sound_upper, ms + max(vup, 0))
        if not rsv:
            n_unresolved_words += 1
    if not stopped_clean:
        # frontier still open -> the next unevaluated main word could score up to (its main_score) + GVUB.
        # We don't have it cheaply post-loop; record honestly that the global upper is NOT closed.
        sound_upper_note = ("FRONTIER OPEN (stopped early via maxmain/timeout): the GLOBAL sound upper also "
                            "includes unevaluated main words bounded by main_score+GVUB; re-run to closure "
                            "for the global bracket. The number below is the upper over EVALUATED words only.")
    else:
        sound_upper_note = ("CLEAN GVUB STOP: all unevaluated main words have main_score+GVUB<=proven_lower, "
                            "so this upper is the GLOBAL sound turn upper bound.")

    prog_final = {'board': W, 'scale': SCALE, 'blanks': rules.blank_count, 'gvub': GVUB,
                  'proven_lower': proven_lower, 'best_turn': best_turn, 'evaluated': evaluated,
                  'sound_upper': sound_upper, 'sound_upper_note': sound_upper_note,
                  'stopped_clean': stopped_clean, 'main_words_enumerated': nmain,
                  'unresolved_words': n_unresolved_words}
    save_progress(prog_final)

    print(f"\n==== exp33 N={W} FULL-TURN result ====")
    # PROVEN-OPTIMAL TURN requires: clean GVUB stop (frontier closed) AND every evaluated main word's
    # vertical bracket is resolved (upper closed) AND the global upper meets the proven lower.
    if stopped_clean and n_unresolved_words == 0 and sound_upper <= proven_lower:
        print(f"  PROVEN OPTIMAL TURN = {proven_lower}")
    elif stopped_clean:
        print(f"  GLOBAL BRACKET [{proven_lower}, {sound_upper}]  (clean GVUB stop; "
              f"{n_unresolved_words} main words with an unresolved vertical bracket)")
    else:
        print(f"  PARTIAL: proven_lower={proven_lower}, upper-over-evaluated={sound_upper} (frontier open)")
    if best_turn:
        print(f"  best turn: main_word={best_turn['main_word']} turn={best_turn['turn_str']}  "
              f"main={best_turn['main_score']} + vert={best_turn['vertical']} = {best_turn['total']}")
    print(f"  {sound_upper_note}")
    print(f"  main words enumerated={nmain}, evaluated={len(evaluated)}, time={time.time()-t0:.0f}s")
    print(f"  progress file: {OUT}")


if __name__ == '__main__':
    main()
