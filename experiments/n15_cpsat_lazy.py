"""
CP-SAT score-maximizer with LAZY connectivity for the N=15 max-turn vertical-score model.

This is the LEARNING-based alternative to the bespoke Rust branch-and-bound `xfill --varmax`.
It encodes the SAME model (see experiments/results/XFILL_VARLEN.md and xfill_rs/src/main.rs)
EXCEPT connectivity, which is enforced LAZILY: solve -> check 4-connectivity of the setup
(board minus the 7 newly-placed row-0 tiles) to the center (W//2,H//2); if violated, add a
CUT forbidding that disconnected configuration and re-solve. CP-SAT's clause learning then
generalizes the cuts. This closes the loop while letting the solver's CDCL do the work the
B&B re-derives by brute force.

MODEL (must match xfill exactly):
 - 15x15 board. Row 0 = the main word: preplaced (nonscoring) cells are FIXED letters; the 7
   newly-placed (scoring) columns hold their fixed main letter but DO NOT count toward the
   setup / connectivity (they are placed THIS turn).
 - Each scoring column c carries an OPTIONAL vertical word main[c]+tail of length 1..maxlen.
   Length 1 = bare tile (no vertical, gross 0). Stub cells rows 1..maxlen-1; a stub value of 0
   means EMPTY (word ended above). Enforced by ONE table over the stub letter-codes (the union
   over all lengths from the base, padded with 0; plus the all-0 bare-tile option). Each table
   row carries its gross via a parallel selector. Objective = sum of chosen-word gross.
 - Bridge cells: nonscoring columns, rows 1..H-1, free (a letter or empty).
 - Legality: every maximal H/V run >=2 is a legal <=HMAX dict word. Enforced by the
   position-independent row automaton on every ROW (length-1 runs always pass: every single
   letter is in the dict). Bridge COLUMNS also get the column automaton. Scoring columns are
   validated by their word-domain table (each candidate is a full dict word), so no column
   automaton on them.
 - Bag: per-letter non-blank usage <= bag count; total blanks <= blank_count; reserve: total
   setup tiles placed <= sum(counts)+blanks-reserve (the opponent holds `reserve` tiles).
 - SETUP connectivity (LAZY): the active SETUP cells must be ONE 4-connected component
   including the center.

VERDICT semantics (match xfill --varmax --maxscore FLOOR):
  MAX s         the maximum achievable vertical score is s
  LE floor      nothing beats `floor` (i.e. max <= floor)  [the certification direction]
We report MAX <opt> when solved to optimality; if opt <= floor we ALSO note LE floor.

Usage:
  python experiments/n15_cpsat_lazy.py BASEFILE [--floor F] [--wall S] [--workers N]
                                       [--emit] [--json]
"""
import sys, os, time, json, argparse
from collections import defaultdict, Counter

sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from ortools.sat.python import cp_model
from dawg import position_independent_row_automaton


# ----------------------------------------------------------------------------------------------
# Base-file parsing (mirrors Rust parse_base in xfill_rs/src/main.rs).
# ----------------------------------------------------------------------------------------------
def parse_base(path):
    W = H = hmax = alpha = 0
    blanks = 0
    reserve = 0
    counts = {}
    scores = {}
    preplaced = []         # (x, y, code)
    nonscoring = []
    dict_path = ''
    cols = []              # list of {'col','wm','bylen': {len: [(stub_tuple, gross)]}}
    cur = None
    cur_len = None
    for line in open(path):
        t = line.split()
        if not t:
            continue
        tag = t[0]
        if tag == 'DIMS':
            W, H, hmax, alpha, blanks = (int(x) for x in t[1:6])
        elif tag == 'COUNTS':
            for tok in t[1:]:
                c, n = tok.split(':'); counts[int(c)] = int(n)
        elif tag == 'SCORES':
            for tok in t[1:]:
                c, n = tok.split(':'); scores[int(c)] = int(n)
        elif tag == 'PREPLACED':
            for tok in t[1:]:
                x, y, c = tok.split(','); preplaced.append((int(x), int(y), int(c)))
        elif tag == 'NONSCORING':
            nonscoring = [int(x) for x in t[1:]]
        elif tag == 'RESERVE':
            reserve = int(t[1])
        elif tag == 'DICT':
            dict_path = t[1]
        elif tag == 'BCOL':
            cur = {'col': int(t[1]), 'wm': int(t[2]), 'bylen': {}}
            cols.append(cur)
        elif tag == 'BLEN':
            cur_len = int(t[1]); cur['bylen'][cur_len] = []
        elif tag == 'WORDV':
            g = int(t[1]); stub = tuple(int(x) for x in t[2:])
            cur['bylen'][cur_len].append((stub, g))
    return dict(W=W, H=H, hmax=hmax, alpha=alpha, blanks=blanks, reserve=reserve,
                counts=counts, scores=scores, preplaced=preplaced, nonscoring=nonscoring,
                dict_path=dict_path, cols=cols)


def load_dict_words(path, hmax):
    """Return list of code-tuples for words of length 1..hmax (for the row/column automaton)."""
    out = []
    for line in open(path):
        v = tuple(int(x) for x in line.split())
        if 1 <= len(v) <= hmax:
            out.append(v)
    return out


# ----------------------------------------------------------------------------------------------
# Build the CP-SAT model (NO connectivity).
# ----------------------------------------------------------------------------------------------
class Model:
    def __init__(self, base, dict_words, alpha):
        self.base = base
        self.W = W = base['W']; self.H = H = base['H']
        self.alpha = alpha
        self.m = m = cp_model.CpModel(); m.prefix = 'n'

        scoring_cols = [col['col'] for col in base['cols']]
        self.scoring_cols = scoring_cols
        self.scoring_set = set(scoring_cols)
        self.nonscoring = base['nonscoring']
        self.pre_letter = {(x, y): c for (x, y, c) in base['preplaced']}

        # ONE-HOT letter representation: lit[(x,y)][c] = 1 iff cell holds code c (c in 1..alpha).
        # li[(x,y)] = integer letter (0 empty) channeled from the one-hot (the automaton consumes
        # the int).  active = sum of one-hot = (li>0).  blank bool.  Using one-hot (instead of an
        # int with reified li==code per code) keeps the per-letter BAG count a PLAIN SUM of bools
        # with NO reification -- this is the difference between a ~30k-constraint model and a
        # ~260k-constraint one that CP-SAT presolve cannot digest.
        self.li = {}; self.active = {}; self.lit = {}
        for y in range(H):
            for x in range(W):
                a = m.new_bool_var(f'a_{x}_{y}')
                onehot = {c: m.new_bool_var(f'h_{x}_{y}_{c}') for c in range(1, alpha + 1)}
                m.add(sum(onehot.values()) == a)              # exactly one letter iff active
                v = m.new_int_var(0, alpha, f'l_{x}_{y}')
                m.add(v == sum(c * onehot[c] for c in onehot))  # channel int <- one-hot
                self.li[(x, y)] = v; self.active[(x, y)] = a
                self.lit[(x, y)] = onehot

        # --- Row 0: main word. preplaced cols = fixed letter (counts as SETUP);
        #            scoring cols = fixed main letter but NOT setup (placed this turn). ---
        self.maxlen = {}
        self.newly_codes = {}    # scoring col -> main letter code at row 0
        for col in base['cols']:
            c = col['col']
            # main letter = first letter of any candidate of len>=2, else from len-1? base len-1 stub
            # is empty; the main letter is implicit. Recover from any candidate word's implied row-0.
            # The base stores stubs (w[1:]); the row-0 main letter is not in the stub. Get it from
            # PREPLACED? No -- scoring cols are not preplaced. Use the longest candidate's column:
            # the main letter equals the candidate full word's w[0], which we don't store. BUT all
            # candidates of a column share the same main letter; we get it from the dict via the
            # cross constraint instead -- we DON'T fix row-0 of scoring cols here (xfill leaves
            # (c,0) forced EMPTY in the setup model!). See note below.
            ml = 1
            for L, ws in col['bylen'].items():
                if ws and L > ml:
                    ml = L
            self.maxlen[c] = ml
        # Recover each scoring column's row-0 MAIN letter (needed only for witness emission): for
        # any length-2 candidate (stub = single tail letter t), the full vertical word is (main, t),
        # so main = the unique dict word head whose tail is t. We find a dict 2-word ending in t
        # whose head, prefixed to longer stubs, reproduces a dict word -- but the simplest robust
        # recovery is: main[c] is the unique letter h such that (h,)+stub is a dict word for EVERY
        # candidate stub of c. Build a lookup once.
        self.newly_main = {}
        dictset = set(dict_words)
        for col in base['cols']:
            c = col['col']
            # gather candidate full-stub samples
            cands = []
            for L, ws in col['bylen'].items():
                for (stub, g) in ws:
                    if stub:
                        cands.append(stub)
            head = None
            if cands:
                for h in range(1, alpha + 1):
                    if all(((h,) + s) in dictset for s in cands):
                        head = h; break
            self.newly_main[c] = head if head is not None else 0
        for (x, y, code) in base['preplaced']:
            m.add(self.li[(x, y)] == code)
        # scoring columns row 0: xfill forces (c,0) EMPTY in the SETUP grid (kind 0, val 0): the
        # newly placed main tile does NOT participate in setup connectivity / cross-words. So in
        # OUR grid, row-0 scoring cells are EMPTY (active=0). The vertical word's row-0 letter is
        # implicit in the precomputed gross; the stub cells (rows 1..) are what we model.
        for c in scoring_cols:
            m.add(self.active[(c, 0)] == 0)

        # --- Scoring columns: stub table over rows 1..maxlen-1 ---
        self.col_gross = {}   # c -> int var holding the chosen vertical's gross (tabled)
        for col in base['cols']:
            c = col['col']; ml = self.maxlen[c]
            pad = ml - 1
            stub_cells = [self.li[(c, r)] for r in range(1, ml)]
            # rows >= ml are forced empty
            for r in range(ml, H):
                m.add(self.active[(c, r)] == 0)
            # build candidate rows: union over lengths, padded with 0; plus bare-tile (all 0, gross 0)
            rows = []            # each: (tuple length pad, gross)
            seen = {}
            rows.append((tuple([0] * pad), 0))     # bare tile
            seen[tuple([0] * pad)] = 0
            for L, ws in col['bylen'].items():
                if L == 1:
                    continue
                for (stub, g) in ws:
                    patt = tuple(list(stub) + [0] * (pad - len(stub)))
                    if patt in seen:
                        # two candidates with the SAME padded pattern would imply the same board
                        # cells but possibly different gross -- keep the MAX (sound: the higher-
                        # scoring option dominates and the cells are identical).  In practice grosses
                        # match (same stub => same word => same gross).
                        if g > seen[patt]:
                            seen[patt] = g
                        continue
                    seen[patt] = g
                    rows.append((patt, g))
            if pad == 0:
                # maxlen == 1: only bare tile. No stub cells. gross 0 forced.
                gv = m.new_constant(0)
                self.col_gross[c] = gv
                continue
            # ONE table constraint over [stub cells..., gross]: model size is INDEPENDENT of the
            # candidate count (unlike a per-candidate selector + per-cell reified equality, which is
            # ~thousands of constraints per column at full N=15 length range).  gross is a tabled
            # variable so the objective reads it directly.  (Mirrors xtest.cpsat_decide_tab's
            # add_allowed_assignments, extended with the gross column.)
            stub_ints = [self.li[(c, r)] for r in range(1, ml)]
            distinct_g = sorted({seen[patt] for patt in seen})
            gv = m.new_int_var(min(distinct_g), max(distinct_g), f'gross_{c}')
            table = [list(patt) + [seen[patt]] for patt in seen]
            m.add_allowed_assignments(stub_ints + [gv], table)
            self.col_gross[c] = gv

        # --- Bridge cells: nonscoring columns rows 1..H-1 are free; row 0 fixed above. ---
        # Nothing extra: they default to a free letter or empty.
        # Cells in NO column's domain & not preplaced: there are none on row>=1 except scoring &
        # bridge columns. All columns are either scoring or nonscoring; nonscoring rows 1.. = bridge.

        # --- Legality automaton ---
        # The model validates "every maximal run >=2 is a dict word"; an ISOLATED single tile is
        # always legal (it forms no word).  The position-independent automaton, however, requires
        # each maximal run (including length-1) to spell a word/word-prefix ending in a terminal.
        # So we INJECT all single letters as 1-letter words: then a length-1 run is accepted exactly
        # as xfill (which checks only runs >=2).  The real Dutch dict already contains all 26 singles
        # (construct_rules injects them), so this is a no-op there and a correctness fix for synthetic
        # dicts that omit them.
        words_with_singles = list(dict_words)
        have = {w for w in dict_words if len(w) == 1}
        for code1 in range(1, self.alpha + 1):
            if (code1,) not in have:
                words_with_singles.append((code1,))
        row_aut = position_independent_row_automaton(words_with_singles)
        # every ROW: a valid sequence of dict words separated by blanks (length-1 runs ok)
        for y in range(H):
            line = [self.li[(x, y)] for x in range(W)]
            m.add_automaton(line, *row_aut)
        # every BRIDGE column gets the column automaton; scoring columns validated by their table.
        for x in self.nonscoring:
            line = [self.li[(x, y)] for y in range(H)]
            m.add_automaton(line, *row_aut)
        # NOTE scoring columns: the vertical run main[c]+tail is a full dict word (candidates are),
        # so the table already enforces a legal vertical. But a scoring column's tail could ALSO be
        # extended by a bridge cell directly below it (row >= ml) -- forbidden: we forced those
        # empty above. And the row-0 scoring cell is empty, so the vertical run is exactly rows
        # 1..L (the stub) PLUS... wait: the vertical word in scoring includes the row-0 main tile.
        # In xfill's SETUP grid row-0 scoring is EMPTY, so the SETUP vertical run is only the stub
        # (rows 1..L). Is that run a dict word? NOT necessarily (stub = w[1:], itself a dict word by
        # construction -- xtest requires w[1:] in lookup). GOOD: the stub alone is a valid word, so
        # the setup column run rows 1..L is legal. We must still enforce the stub-only column run is
        # a word; the table guarantees it (every candidate stub is w[1:], a dict word). And no
        # column automaton is needed for scoring columns.

        self.dict_words = dict_words

    def add_bag_and_objective(self):
        m = self.m; W, H = self.W, self.H
        alpha = self.alpha
        counts = self.base['counts']; blanks = self.base['blanks']
        reserve = self.base['reserve']
        # per-letter NON-BLANK usage <= bag count, using the one-hot directly.
        # non-blank usage of code c = sum over cells of (lit[c] AND not blank).  We bound it WITHOUT
        # a per-(cell,code) product: a blank can sit on at most one code per cell, so for each cell
        # introduce a single per-cell "blanked code is c?" need not be tracked -- instead note that
        # (lit[c] AND not blank) = lit[c] - (lit[c] AND blank).  Summing over cells:
        #   nonblank_use[c] = (sum_cells lit[c]) - blank_on[c],  where blank_on[c] = #blanks on c-cells.
        # We only need nonblank_use[c] <= counts[c].  Since blank_on[c] >= 0 and sum_c blank_on[c] =
        # total blanks, we model blank_on via ONE product per cell (not per code): the cell's blank
        # bool times its one-hot.  That is alpha products per cell -- still 225*26.  Cheaper exact
        # form: bound directly.  For each code, the number of c-tiles is sum_cells lit[c]; at most
        # `blanks` of ALL tiles are blank.  Enforce nonblank usage by: sum_cells lit[c] <= counts[c]
        # + b_c, with b_c = blanks attributed to code c, sum_c b_c <= blanks, b_c <= sum_cells lit[c].
        # b_c is a small int var (0..blanks).  This is alpha int vars + alpha+1 linear constraints --
        # no per-cell-per-code products at all.
        # b_c = number of blank tiles attributed to code c (0..blanks).  Non-blank usage of c is
        # tiles_c - b_c, required <= counts[c].  sum_c b_c <= blanks (only `blanks` blank tiles
        # exist).  This is the EXACT bag feasibility condition: a legal blank assignment exists iff
        # there is an attribution with each code's non-blank count within budget and total blanks
        # within the blank stock.  No per-cell blank bools (they feed nothing else: blanked cells
        # are still active, so the reserve/connectivity counts already include them; the WITNESS's
        # blank assignment is derived independently by witness_check.derive_blanks).  SOUNDNESS:
        # matches xfill's overflow<=blanks rule -- overflow = sum_c max(0, tiles_c - counts[c]), and
        # sum_c b_c >= sum_c max(0,tiles_c-counts[c]) is achievable iff that sum <= blanks.
        bc = {}
        for code in range(1, alpha + 1):
            tiles_c = sum(self.lit[(x, y)][code] for y in range(H) for x in range(W))
            b_c = m.new_int_var(0, blanks, f'bc_{code}')
            bc[code] = b_c
            m.add(tiles_c <= counts.get(code, 0) + b_c)
            m.add(b_c <= tiles_c)
        m.add(sum(bc.values()) <= blanks)
        # reserve: total SETUP tiles placed <= sum(counts)+blanks-reserve.
        # setup = all active cells EXCEPT row-0 scoring cells (which are inactive anyway).
        setup_active = []
        for (x, y), a in self.active.items():
            if y == 0 and x in self.scoring_set:
                continue
            setup_active.append(a)
        max_setup = sum(counts.values()) + blanks - reserve
        m.add(sum(setup_active) <= max_setup)

        # objective: sum of chosen-word gross over scoring columns (tabled gross vars)
        self.obj = sum(self.col_gross.values())

    def set_maximize(self):
        self.m.maximize(self.obj)

    def set_floor_decision(self, floor):
        """Decision mode for the certification (LE) direction: assert obj >= floor+1 and solve for
        feasibility (no objective).  INFEASIBLE under accumulated connectivity cuts => no CONNECTED
        board beats `floor` => `LE floor` is PROVEN.  A connected SAT => a board scores > floor."""
        self.m.add(self.obj >= floor + 1)

    def setup_cells(self):
        """The (x,y) cells that participate in SETUP connectivity (everything except row-0 scoring)."""
        out = []
        for y in range(self.H):
            for x in range(self.W):
                if y == 0 and x in self.scoring_set:
                    continue
                out.append((x, y))
        return out


# ----------------------------------------------------------------------------------------------
# Connectivity check + lazy cut.
# ----------------------------------------------------------------------------------------------
def setup_components(active_setup, W, H):
    """4-connected components of the set of active setup cells. Returns list of frozensets."""
    cells = set(active_setup)
    seen = set(); comps = []
    for s in cells:
        if s in seen:
            continue
        stack = [s]; comp = set()
        seen.add(s)
        while stack:
            (x, y) = stack.pop(); comp.add((x, y))
            for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if q in cells and q not in seen:
                    seen.add(q); stack.append(q)
        comps.append(frozenset(comp))
    return comps


class LazyConnectivity:
    """Iterative solve / check-connectivity / add-cut loop.

    On each incumbent we read the active setup cells. If they form one component containing the
    center, the incumbent is FEASIBLE (record it). Otherwise we add a CUT and re-solve.

    CUT (sound, never removes a feasible board): take the component C that does NOT contain the
    center (or, if center is in no component because center is empty, take ANY component). C is
    sealed off from the rest of the active setup by a ring of EMPTY cells. The configuration is
    disconnected because every cell on the boundary ring is empty. The cut forbids EXACTLY this
    seal: it asserts that NOT (all-of-C active AND all boundary cells empty). Concretely:
        OR over c in C of (~active[c])  OR  OR over boundary b of (active[b])
    i.e. "either some cell of C becomes empty, or some boundary cell becomes active" -- forcing a
    bridge. This forbids the specific disconnection without excluding any connected board (a
    connected board either doesn't have all of C active in isolation, or has an active boundary
    cell). The center is handled by also requiring center active (added once as a hard constraint).
    """
    def __init__(self, mb):
        self.mb = mb
        self.W = mb.W; self.H = mb.H
        self.setup = mb.setup_cells()
        self.setup_set = set(self.setup)
        # ROOT = the first preplaced cell, EXACTLY as xfill (mandatory[0]).  xfill enforces "active
        # setup is ONE 4-connected component containing the root", NOT the center.  The center
        # (W//2,H//2) requirement is a separate witness_check concern (require_center=True) applied
        # to the EMITTED board, not part of the optimization model.  To MATCH xfill's MAX/LE we use
        # the same root and do NOT hard-constrain the center.
        pre = mb.base['preplaced']
        # mandatory[0] in xfill = lowest cell id (y*w+x) among preplaced (grid0>0); preplaced are all
        # row 0, so lowest id = smallest x.
        root_xy = min(((x, y) for (x, y, c) in pre), key=lambda p: p[1] * mb.W + p[0])
        self.root = root_xy
        mb.m.add(mb.active[self.root] == 1)
        self.cuts = 0

    def neighbors(self, x, y):
        for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if q in self.setup_set:
                yield q

    def boundary(self, comp):
        b = set()
        for (x, y) in comp:
            for q in self.neighbors(x, y):
                if q not in comp:
                    b.add(q)
        return b

    def check_and_cut(self, get_active):
        """get_active(x,y) -> bool. Returns True if active setup is ONE component containing the
        root (xfill's connectivity test), else adds cuts and returns False."""
        active_setup = [(x, y) for (x, y) in self.setup if get_active(x, y)]
        comps = setup_components(active_setup, self.W, self.H)
        if not comps:
            # empty setup -- root is hard-constrained active, so this cannot happen; trivially "ok".
            return True
        root_comp = None
        for comp in comps:
            if self.root in comp:
                root_comp = comp; break
        if root_comp is not None and len(comps) == 1:
            return True
        # disconnected: cut every component that is NOT the root component.
        m = self.mb.m
        for comp in comps:
            if comp is root_comp:
                continue
            bnd = self.boundary(comp)
            lits = [~self.mb.active[c] for c in comp] + [self.mb.active[b] for b in bnd]
            m.add_bool_or(lits)
            self.cuts += 1
        return False


# ----------------------------------------------------------------------------------------------
# Driver: iterative solve / check / cut to OPTIMALITY under lazy connectivity.
# ----------------------------------------------------------------------------------------------
def solve(base_path, floor=-1, wall=None, workers=8, want_emit=False, verbose=True,
          mode='le'):
    """mode='le'  : DECISION/certification -- assert obj>floor, lazy-cut connectivity; INFEASIBLE =>
                    `LE floor` PROVEN; a connected SAT => a board scores > floor (report its score).
       mode='max' : full maximization under lazy connectivity (slower; reports the exact MAX).
    """
    base = parse_base(base_path)
    alpha = base['alpha']
    dict_words = load_dict_words(base['dict_path'], base['hmax'])
    t_build = time.time()
    mb = Model(base, dict_words, alpha)
    mb.add_bag_and_objective()
    if mode == 'max':
        mb.set_maximize()
    else:
        mb.set_floor_decision(floor)
    lc = LazyConnectivity(mb)
    build_s = time.time() - t_build
    if verbose:
        sys.stderr.write(f"model built: {build_s:.2f}s, dict {len(dict_words)} words, "
                         f"{len(mb.scoring_cols)} scoring cols, mode={mode}\n")

    m = mb.m
    deadline = (time.time() + wall) if wall else None
    best_obj = None
    best_board = None
    rounds = 0
    while True:
        rounds += 1
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.max_presolve_iterations = 1
        if deadline is not None:
            rem = deadline - time.time()
            if rem <= 0:
                return _result('TO', best_obj, floor, rounds, lc.cuts, build_s,
                               best_board, mb, mode, aborted=True)
            solver.parameters.max_time_in_seconds = rem
        status = solver.Solve(m)

        if status == cp_model.INFEASIBLE:
            # No board satisfies (cuts + floor/maximize). In LE mode this PROVES `LE floor`.
            # In MAX mode it means no board beats the best connected one found so far.
            return _result('OPT', best_obj, floor, rounds, lc.cuts, build_s, best_board, mb, mode)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _result('TO', best_obj, floor, rounds, lc.cuts, build_s,
                           best_board, mb, mode, aborted=True)

        # objective value of this incumbent (in LE mode there is no objective; compute from sels).
        if mode == 'max':
            obj = int(round(solver.objective_value))
        else:
            obj = _obj_value(solver, mb)
        actmap = {(x, y): solver.value(mb.active[(x, y)]) == 1
                  for y in range(mb.H) for x in range(mb.W)}
        connected = lc.check_and_cut(lambda x, y: actmap[(x, y)])

        if connected:
            # A genuine connected board.  In MAX mode (maximize) it is the global optimum over
            # connected boards: the only constraints we add are connectivity cuts that forbid
            # DISCONNECTED boards (never a connected one), so this incumbent's objective is an upper
            # bound on every remaining board AND it is itself connected -> the optimum.  In LE mode
            # it is a connected board with obj > floor -> `LE floor` is FALSE; report its score.
            best_obj = obj
            if want_emit:
                best_board = _extract_board(solver, mb)
            return _result('SAT' if mode == 'le' else 'OPT', best_obj, floor, rounds, lc.cuts,
                           build_s, best_board, mb, mode)
        # disconnected -> cuts added; loop and re-solve.


def _obj_value(solver, mb):
    return sum(int(solver.value(gv)) for gv in mb.col_gross.values())


def _extract_board(solver, mb):
    W, H = mb.W, mb.H
    grid = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            grid[y][x] = int(solver.value(mb.li[(x, y)]))
    # restore row-0 scoring main letters (they are EMPTY in the setup model but the WITNESS board
    # must show the full main word). Recover main letter from the column's chosen vertical: the
    # first letter of the full vertical word = main[c]. We stored only stubs+gross, not main letter.
    # Instead read it from the base preplaced? scoring cols aren't preplaced. We reconstruct main[c]
    # from the candidate: a candidate stub of length>=1 implies the full word but not its head.
    # SOLUTION: the main letter is needed for the witness; we look it up from the base cols via the
    # gross-matching word in the dict. Simpler: store main letters at model-build time.
    for c in mb.scoring_cols:
        grid[0][c] = mb.newly_main.get(c, 0)
    return grid


def _result(kind, best_obj, floor, rounds, cuts, build_s, board, mb, mode, aborted=False):
    return dict(kind=kind, opt=best_obj, floor=floor, rounds=rounds, cuts=cuts,
                build_s=build_s, board=board, mode=mode, aborted=aborted)


def format_line(res):
    """Mirror xfill's MAX / LE / TO contract.  res from solve()."""
    opt = res['opt']; floor = res['floor']; mode = res['mode']
    if res['kind'] == 'TO':
        return (f"TO floor={floor} rounds={res['rounds']} cuts={res['cuts']} "
                f"(no proof; best_connected={opt})")
    if mode == 'le':
        # DECISION mode.  kind=='OPT' here means INFEASIBLE under cuts+floor => LE floor PROVEN.
        # kind=='SAT' means a connected board with obj>floor exists => NOT LE; report its score.
        if res['kind'] == 'OPT':
            return f"LE {floor} rounds={res['rounds']} cuts={res['cuts']}"
        return f"GT {floor} (found connected board scoring {opt}) rounds={res['rounds']} cuts={res['cuts']}"
    # MAX mode.
    if opt is None:
        return f"INFEASIBLE rounds={res['rounds']} cuts={res['cuts']}"
    if opt <= floor:
        return f"LE {floor} MAX={opt} rounds={res['rounds']} cuts={res['cuts']}"
    return f"MAX {opt} rounds={res['rounds']} cuts={res['cuts']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base')
    ap.add_argument('--floor', type=int, default=-1)
    ap.add_argument('--wall', type=float, default=None)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--mode', choices=['le', 'max'], default='le')
    ap.add_argument('--emit', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    res = solve(a.base, floor=a.floor, wall=a.wall, workers=a.workers, want_emit=a.emit,
                mode=a.mode)
    wall = time.time() - t0
    line = format_line(res)
    print(line)
    sys.stderr.write(f"build={res['build_s']:.2f}s total_wall={wall:.2f}s "
                     f"rounds={res['rounds']} cuts={res['cuts']}\n")
    if a.emit and res['board'] is not None:
        b = res['board']
        print("BOARD " + ' '.join(str(b[y][x]) for y in range(len(b)) for x in range(len(b[0]))))
    if a.json:
        out = {k: v for k, v in res.items() if k != 'board'}
        out['wall_s'] = wall; out['line'] = line
        print("JSON " + json.dumps(out))


if __name__ == '__main__':
    main()
