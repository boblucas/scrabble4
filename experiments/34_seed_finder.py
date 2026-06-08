"""
Experiment 34: STRONG-LOWER-BOUND seed finder for the exp33 full-turn bracket.

GOAL: exhibit the highest-scoring REAL, LEGAL, 4-connected single turn we can per board size, to SEED
exp33's proven_lower (the inner's IMPROVER direction is weak at N>=11, so from-scratch witnessing fails --
the bracket lower needs a constructed-and-verified seed).  A turn here = a row-0 main word (some tiles
newly placed = "scoring" columns hosting DOWN verticals, the rest pre-placed) + the verticals + bridge
tiles, all one component, every cross-word a valid <=HMAX word, within the scaled bag (with blanks).

  turn score = main_score(word, placed-mask) + vertical_score(down-words).

WHY a SEARCH OVER (word, placed-mask), not just the top main word:  main_score depends only on WHICH
multiplier cells (TW/DW/TL/DL) are newly placed -- the plain placed cells are score-invariant.  So a word
admits MANY placed-masks of equal (or near-equal) main_score, and they differ wildly in whether a legal
connected board EXISTS (adjacent scoring columns force long horizontal cross-words; rare letters q/x/y eat
the tile budget).  Empirically the single best-main-score mask of the very top N=13/15 words is INFEASIBLE
(holistic INFEASIBLE in presolve).  So we enumerate (word desc by main_score) x (a few promising masks)
and let the legality-fixed HOLISTIC (exp28's validated model) WITNESS the best legal connected board.

The holistic in INCUMBENT mode is cheap and gives a REAL board (its first feasible solution / best within
the cap); the scaled bag keeps the model small (~15-30k vars, no OOM).  Its incumbent placement is a genuine
legal connected turn -> a sound lower bound.

VERIFICATION (every claimed lower bound is independently re-validated -- a wrong/too-high lower is worse
than a loose one):
  * the holistic itself enforces: one valid vertical word per scoring column (w[1:] in dict), every row+col
    cross-word a valid <=HMAX word (position-independent automaton both directions), shared per-letter tile
    budget + blank relaxation, and single_component over the setup board.
  * we then RE-CHECK the extracted board with an INDEPENDENT python checker (build_and_check): connectivity
    (RustOracle / components) AND every maximal horizontal+vertical run of >=2 cells is a dict word AND the
    tile/ blank budget -- recomputing the score from scratch.  Mismatch => rejected.
  * --certify additionally restricts the inner xfill_frozen word-domain to the EXACT chosen verticals and
    confirms `--maxscore score-1` returns MAX >= score (a legal 4-connected board at that score), the same
    external certification used for the bouwfysicus 224 seed.

Run:
  python experiments/34_seed_finder.py <11|13|15> [--scale-tiles] [--blanks]
        [--topwords K]      consider the top-K main words by best main_score (default 40)
        [--masks M]         masks tried per word (default 6)
        [--hcap S]          per-(word,mask) holistic wall cap seconds (default 90)
        [--cores N]         holistic search workers (default 8)
        [--seed-lower N]    skip any (word,mask) whose main_score + GVUB <= N (already can't beat the seed)
        [--gvub N]          supply the global vertical UB (else computed)
        [--certify]         re-certify the best board via xfill_frozen restricted-domain --maxscore
        [--only WORD:TURN]  evaluate exactly one explicit (word, turn) pair (turn = upper=scoring)
        [--out PATH]        result JSON (default experiments/results/turns/N<W>_seed.json)
"""
import sys, os, time, json, subprocess, itertools, math
from collections import Counter, defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count
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
TOPWORDS = arg('--topwords', 40, int)
NMASKS = arg('--masks', 6, int)
HCAP = arg('--hcap', 90.0, float)
KEEP_SECS = arg('--keep', 25.0, float)   # after the first feasible incumbent, keep improving this long
CORES = arg('--cores', 8, int)
SEED_LOWER = arg('--seed-lower', -1, int)
GVUB_OVERRIDE = arg('--gvub', -1, int)
CERTIFY = '--certify' in sys.argv
ONLY = arg('--only', '')

rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
ABC = len(rules.abc)
hand = rules.hand_size
# scaled bag (main-word-INDEPENDENT floor, matching exp33's enumeration; the per-(word,mask) holistic
# re-derives the exact per-word bag with the mc[c] floor below).
if SCALE:
    f = (W * W) / (15 * 15)
    BASE_COUNTS = Counter({c: max(round(n * f), 1) for c, n in rules.counts.items()})
    BASE_BLANKS = round(rules.blank_count * f)
else:
    BASE_COUNTS = Counter(rules.counts)
    BASE_BLANKS = rules.blank_count
if not BLANKS:
    BASE_BLANKS = 0
LM = [[int(rules.letter_multiplier[y][x]) for x in range(W)] for y in range(H)]
WM = [[int(rules.word_multiplier[y][x]) for x in range(W)] for y in range(H)]
MULT_COLS = [x for x in range(W) if LM[0][x] > 1 or WM[0][x] > 1]
PLAIN_COLS = [x for x in range(W) if x not in MULT_COLS]
ORACLE = RustOracle(W, H)
OUT = arg('--out', os.path.join(ROOT, f'experiments/results/turns/N{W}_seed.json'))
BESTTXT = os.path.join(ROOT, f'experiments/results/turns/N{W}_seed_BEST.txt')
xtest.write_dict(board)

print(f"=== exp34 seed finder  board {W}x{H}  scale={SCALE} blanks={BASE_BLANKS} "
      f"bag={sum(BASE_COUNTS.values())}+{BASE_BLANKS}  hand={hand} ===", flush=True)


# ----------------------------------------------------------------------------------------------------
#  main_score for a (word, placed-mask).  placed[i]=True means tile i is newly placed this turn (gets the
#  cell's letter/word multipliers); a full-row word with exactly `hand` placed earns the bingo bonus.
# ----------------------------------------------------------------------------------------------------
def main_score(tup, mask):
    sc, _ = get_word_score(rules, list(tup), 0, 0, 0, mask)
    return int(sc)


def best_main_for_word(tup):
    """Max main_score over masks with exactly `hand` placed tiles, and the achieving mask.  Plain (lm=wm=1)
    placed cells are score-invariant, so we only brute-force WHICH multiplier cells are placed and fill the
    rest with plain columns -> fast & exact."""
    best, bestmask = -1, None
    for r in range(0, min(len(MULT_COLS), hand) + 1):
        for mp in itertools.combinations(MULT_COLS, r):
            need = hand - len(mp)
            if need < 0 or need > len(PLAIN_COLS):
                continue
            mask = [False] * W
            for i in mp:
                mask[i] = True
            for i in PLAIN_COLS[:need]:
                mask[i] = True
            sc = main_score(tup, mask)
            if sc > best:
                best, bestmask = sc, mask
    return best, bestmask


def enumerate_main_words(top_k):
    """All W-letter dict words placeable in the bag (no main blanks), by best main_score descending."""
    res = []
    for w in rules.words:
        if len(w) != W:
            continue
        wc = Counter(w)
        if any(wc[c] > BASE_COUNTS.get(c, 0) for c in wc):   # main word uses no blanks (exp29 assumption)
            continue
        sc, mask = best_main_for_word(w)
        res.append((sc, rules.alphabet.to_str(w), tuple(w)))
    res.sort(key=lambda t: -t[0])
    return res[:top_k]


# ----------------------------------------------------------------------------------------------------
#  candidate placed-masks for a word, biased toward FEASIBLE layouts (spread scoring columns, keep the
#  high-value multiplier cells).  We score each mask by its main_score and a feasibility heuristic, and
#  return the best NMASKS distinct ones (always including the global best-main mask).
# ----------------------------------------------------------------------------------------------------
def _letter_vrichness():
    """How many valid down-words (len>=2, w[1:] in dict, len<=H) start with each letter code.  A scoring
    column whose letter is vertical-poor (rare q/x/y) is a feasibility risk; the mask ranker avoids them."""
    rich = Counter()
    for w in rules.words:
        if w and 2 <= len(w) <= H and w[1:] in rules.words_lookup:
            rich[w[0]] += 1
    return rich


LETTER_VRICH = _letter_vrichness()


def candidate_masks(tup, nmasks):
    """Generate masks (exactly `hand` placed) ranked by (main_score desc, then a feasibility heuristic:
    fewer adjacent scoring pairs + scoring columns on vertical-RICH letters).  The mult cells drive
    main_score; plain placed cells are score-free, so we vary them to spread the scoring columns out
    (adjacent scoring cols force long horizontal cross-words) and to land scoring on common letters
    (rare-letter columns q/x/y have almost no legal verticals -> infeasible)."""
    cand = {}   # mask-tuple -> (main_score, feas_penalty, adj)

    def feas_pen(cols):
        adj = sum(1 for i in range(len(cols) - 1) if cols[i + 1] - cols[i] == 1)
        # vertical-poverty penalty: a scoring col whose letter has < 30 verticals is risky
        poor = sum(1 for c in cols if LETTER_VRICH[tup[c]] < 30)
        # spread bonus: penalize if all scoring cols clustered in one half
        return adj * 2 + poor * 5, adj

    # the achievable main_score per choice of placed mult cells; plain placed cells are score-free, so we
    # enumerate plain placements that minimize adjacency.
    for r in range(0, min(len(MULT_COLS), hand) + 1):
        for mp in itertools.combinations(MULT_COLS, r):
            need = hand - len(mp)
            if need < 0 or need > len(PLAIN_COLS):
                continue
            # base score uses any plain choice; compute it once with the first `need` plain cols
            mask0 = [False] * W
            for i in mp:
                mask0[i] = True
            for i in PLAIN_COLS[:need]:
                mask0[i] = True
            base_sc = main_score(tup, mask0)
            # try several plain selections to reduce adjacency among scoring columns
            from random import Random
            rng = Random(12345 + r * 31 + sum(mp))
            plain_options = [PLAIN_COLS[:need]]
            for _ in range(40):
                pick = rng.sample(PLAIN_COLS, need) if need <= len(PLAIN_COLS) else PLAIN_COLS
                plain_options.append(sorted(pick))
            for plain in plain_options:
                cols = sorted(list(mp) + list(plain))
                mask = tuple(x in cols for x in range(W))
                pen, adj = feas_pen(cols)
                if mask not in cand or (base_sc, -pen) > (cand[mask][0], -cand[mask][1]):
                    cand[mask] = (base_sc, pen, adj)
    # rank: highest main_score first, then lowest feasibility penalty
    ranked = sorted(cand.items(), key=lambda kv: (-kv[1][0], kv[1][1]))
    return [(list(m), sc, adj) for m, (sc, pen, adj) in ranked[:nmasks]]


# ----------------------------------------------------------------------------------------------------
#  legality-fixed HOLISTIC (exp28's validated model) in INCUMBENT mode: best legal connected verticals
#  for a fixed (word, mask) within the cap.  Returns (status, vert_obj, solver, xv, cands, scoring, cells)
# ----------------------------------------------------------------------------------------------------
def per_word_bag(tup):
    mc = Counter(tup)
    counts = Counter({c: max(BASE_COUNTS[c], mc[c]) for c in BASE_COUNTS})
    return counts, BASE_BLANKS


def candidates_for(tup, x, counts):
    L = tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H:
            continue
        if len(w) > 1 and w[1:] not in rules.words_lookup:
            continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, int(sc), Counter(w[1:])))
    return out


def build_holistic(tup, mask, counts, blanks):
    scoring = [x for x in range(W) if mask[x]]
    pre = [x for x in range(W) if not mask[x]]
    cands = {c: candidates_for(tup, c, counts) for c in scoring}
    if any(not cands[c] for c in scoring):
        return None
    m = cp_model.CpModel(); m.prefix = 'h'
    hw = [w for w in rules.words if len(w) <= HMAX]
    row_aut = position_independent_row_automaton(hw)
    rows = [row_aut] * H
    cols = [row_aut if x not in scoring else None for x in range(W)]
    cells = create_board(m, rows, cols, alphabet_size=ABC)
    for x in pre:
        m.add(cells[(x, 0)].letter[tup[x]] == 1)
    for x in scoring:
        m.add(cells[(x, 0)].active == 0)
    xv = {}
    for c in scoring:
        vs = []
        for i, (w, sc, rq) in enumerate(cands[c]):
            v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
            for r in range(1, H):
                if r < len(w):
                    m.add(cells[(c, r)].letter[w[r]] == 1).only_enforce_if(v)
                else:
                    m.add(cells[(c, r)].active == 0).only_enforce_if(v)
        m.add(sum(vs) == 1)
    newly = Counter(tup[c] for c in scoring)
    limit_letter_count(m, cells, Counter({code: counts[code] - newly[code] for code in counts}))
    penalty = 0
    over = {}
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    if blanks:
        for code in counts:
            terms = []
            for c in scoring:
                for r in range(1, H):
                    cell = cells[(c, r)]
                    b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                    m.add(b <= cell.blank); m.add(b <= cell.letter[code])
                    m.add(b >= cell.blank + cell.letter[code] - 1)
                    terms.append(b)
            o = m.new_int_var(0, blanks, f'o_{code}'); m.add(o == sum(terms)); over[code] = o
            penalty = penalty + o * rules.scores[code]
    for code in counts:
        cap = counts[code] - Counter(tup).get(code, 0)
        usage = [xv[(c, i)] * rq[code] for c in scoring for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= cap)
    if pre:
        single_component(m, cells, (pre[0], 0))
    m.maximize(sum(xv[(c, i)] * sc for c in scoring for i, (w, sc, rq) in enumerate(cands[c])) - penalty)
    return m, xv, cands, scoring, pre, cells


class _Capture(cp_model.CpSolverSolutionCallback):
    """Capture the latest incumbent's variable values and optionally stop after the first feasible one
    (or after `keep_improving_for` seconds past the first incumbent) so a (word,mask) yields a real legal
    board FAST instead of waiting for the full optimize -- crucial under heavy machine load."""
    def __init__(self, xv, cands, scoring, pre, cells, stop_after_first, keep_secs):
        super().__init__()
        self.xv, self.cands, self.scoring, self.pre, self.cells = xv, cands, scoring, pre, cells
        self.stop_after_first = stop_after_first
        self.keep_secs = keep_secs
        self.best = None
        self.snapshot = None
        self._first_t = None

    def on_solution_callback(self):
        obj = int(self.ObjectiveValue())
        if self.best is None or obj > self.best:
            self.best = obj
            # snapshot all needed values now (callback solver state is valid here)
            chosen = {}
            for c in self.scoring:
                for i, (w, sc, rq) in enumerate(self.cands[c]):
                    if self.Value(self.xv[(c, i)]):
                        chosen[c] = (w, sc); break
            grid = {}
            blk = {}
            for (x, y), cell in self.cells.items():
                a = self.Value(cell.active)
                if not a:
                    continue
                code = 0
                for cc, bv in cell.letter.items():
                    if self.Value(bv):
                        code = cc; break
                grid[(x, y)] = code
                blk[(x, y)] = bool(self.Value(cell.blank))
            self.snapshot = (obj, chosen, grid, blk)
        if self._first_t is None:
            self._first_t = self.WallTime()
        if self.stop_after_first:
            self.StopSearch()
        elif self.keep_secs is not None and self.WallTime() - self._first_t >= self.keep_secs:
            self.StopSearch()


def solve_holistic(tup, mask, cap, stop_after_first=False, keep_secs=None):
    counts, blanks = per_word_bag(tup)
    built = build_holistic(tup, mask, counts, blanks)
    if built is None:
        return 'NOCAND', None, None
    m, xv, cands, scoring, pre, cells = built
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = CORES
    s.parameters.max_time_in_seconds = cap
    s.parameters.max_presolve_iterations = 1
    cb = _Capture(xv, cands, scoring, pre, cells, stop_after_first, keep_secs)
    r = s.Solve(m, cb)
    name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE'}.get(r, 'UNKNOWN')
    if cb.snapshot is not None:
        return name, cb.snapshot[0], (cb.snapshot, scoring, pre, counts, blanks)
    if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # solver returned feasible but no callback fired (rare) -- read directly
        return name, int(s.objective_value), None
    return name, None, None


# ----------------------------------------------------------------------------------------------------
#  extract the board from a holistic solution and INDEPENDENTLY re-check it (connectivity + every cross
#  word a dict word + tile/blank budget + recomputed score).  Returns (ok, recomputed_vert, board_rows,
#  chosen, blanks_used) -- ok=False means the extracted board failed an independent invariant.
# ----------------------------------------------------------------------------------------------------
def extract_and_check(tup, mask, sol):
    (snapshot, scoring, pre, counts, blanks) = sol
    obj, chosen, snap_grid, snap_blk = snapshot
    grid = [[0] * W for _ in range(H)]
    blank = [[False] * W for _ in range(H)]
    # row 0: pre-placed tiles
    for x in pre:
        grid[0][x] = tup[x]
    # chosen verticals -> grid (incl. row-0 newly-placed top tile)
    for c in scoring:
        w, sc = chosen[c]
        for r in range(len(w)):
            grid[r][c] = w[r]
    # all active fill / bridge cells from the snapshot
    for (x, y), code in snap_grid.items():
        if y == 0:
            continue
        if grid[y][x] == 0:
            grid[y][x] = code
        if snap_blk.get((x, y)):
            blank[y][x] = True

    # --- independent invariant checks ---
    occupied = {(x, y) for y in range(H) for x in range(W) if grid[y][x] != 0}
    # 1) connectivity: the SETUP board (everything except the newly-placed row-0 tiles at scoring cols).
    #    Only required when there ARE pre-placed tiles (matching exp28's `if pre:` -- a full-bingo opening
    #    with every column newly placed has no setup board to connect to).
    setup_cells = {(x, y) for (x, y) in occupied if not (y == 0 and mask[x])}
    has_pre = any(not mask[x] for x in range(W))
    if has_pre:
        comps = _components(setup_cells, W, H)
        if len(comps) > 1:
            return False, None, None, None, f"setup not connected ({len(comps)} comps)"
    # 2) every maximal horizontal/vertical run of length>=2 must be a valid dict word
    wl = rules.words_lookup
    def runs_ok():
        for y in range(H):                       # horizontal
            x = 0
            while x < W:
                if grid[y][x] == 0:
                    x += 1; continue
                x2 = x
                while x2 < W and grid[y][x2] != 0:
                    x2 += 1
                if x2 - x >= 2:
                    word = tuple(grid[y][k] for k in range(x, x2))
                    if word not in wl:
                        return False, ('H', y, x, rules.alphabet.to_str(list(word)))
                x = x2
        for x in range(W):                       # vertical
            y = 0
            while y < H:
                if grid[y][x] == 0:
                    y += 1; continue
                y2 = y
                while y2 < H and grid[y2][x] != 0:
                    y2 += 1
                if y2 - y >= 2:
                    word = tuple(grid[k][x] for k in range(y, y2))
                    if word not in wl:
                        return False, ('V', x, y, rules.alphabet.to_str(list(word)))
                y = y2
        return True, None
    ok, bad = runs_ok()
    if not ok:
        return False, None, None, None, f"illegal cross-word {bad}"
    # 3) tile budget: setup tiles (everything except newly-placed row-0 scoring tiles) consume the bag;
    #    blanked cells consume a blank instead of a real letter.
    used = Counter(); nblank = 0
    for (x, y) in setup_cells:
        if blank[y][x]:
            nblank += 1
        else:
            used[grid[y][x]] += 1
    # the newly placed main tiles at scoring cols come from the hand (counted in main_score, not the bag);
    # but the bag must still physically contain them (they were drawn) -- exp33 budgets only setup cells,
    # so we mirror that: check setup tile usage against the bag minus the newly-placed main tiles.
    newly = Counter(tup[c] for c in scoring)
    if nblank > blanks:
        return False, None, None, None, f"blank budget {nblank}>{blanks}"
    for code in used:
        if used[code] > counts.get(code, 0) - newly.get(code, 0):
            return False, None, None, None, f"tile budget letter {code}: {used[code]} > {counts.get(code,0)-newly.get(code,0)}"
    # 4) recompute the vertical score from the chosen verticals minus blank penalty on stub cells
    vert = 0
    for c in scoring:
        w, sc = chosen[c]
        vert += sc
    pen = 0
    for c in scoring:
        for r in range(1, len(chosen[c][0])):
            if blank[r][c]:
                pen += rules.scores[grid[r][c]]
    vert_recompute = vert - pen
    return True, vert_recompute, grid, chosen, None


def render_board(grid, tup, mask, scoring):
    lines = []
    for y in range(H):
        row = []
        for x in range(W):
            code = grid[y][x]
            if y == 0 and mask[x]:
                row.append(rules.alphabet.to_str((tup[x],)).upper())
            elif y == 0:
                row.append(rules.alphabet.to_str((tup[x],)).lower())
            elif code:
                row.append(rules.alphabet.to_str((code,)))
            else:
                row.append('.')
        lines.append(' '.join(row))
    return '\n'.join(lines)


def certify_board(tup, mask, scoring, chosen, target):
    """Restrict the inner word-domain to the EXACT chosen verticals and confirm xfill_frozen --maxscore
    target-1 returns MAX >= target -- an independent legal-4-connected certification of the score."""
    main = rules.alphabet.to_str(list(tup))
    turn = ''.join(main[i].upper() if mask[i] else main[i].lower() for i in range(W))
    Lvec = {c: len(chosen[c][0]) for c in scoring}
    inst, meta = xtest.build_instance(board, main, turn, Lvec, scale=SCALE)
    if inst is None:
        return None, "build_instance None"
    for blk in inst['scoring']:
        c = blk['col']; w = chosen[c][0]; stub = list(w[1:])
        sc, _ = get_word_score(rules, w, c, 0, 0, [i == 0 for i in range(len(w))])
        blk['words'] = [stub]; blk['gross'] = [int(sc)]
    path = os.path.join(xtest.TESTDIR, f"cert{board}_{main}_certseed.txt")
    xtest.dump_simple(inst, 'UNKNOWN', path)
    try:
        r = subprocess.run([FROZEN, path, '--maxscore', str(target - 1)],
                           capture_output=True, text=True, timeout=180.0, cwd=ROOT)
        out = r.stdout.strip()
    except subprocess.TimeoutExpired:
        return None, "inner timeout"
    return out, None


# ----------------------------------------------------------------------------------------------------
#  global vertical UB (exp29) -- the STOP bound for the (word, mask) enumeration
# ----------------------------------------------------------------------------------------------------
def global_vertical_ub(top_k=200, cap=120.0):
    words = []
    for w in rules.words:
        if not w or (len(w) > 1 and w[1:] not in rules.words_lookup):
            continue
        words.append((sum(rules.scores[c] for c in w), rules.scores[w[0]], Counter(w[1:])))
    cols = {}
    for x in range(W):
        lm = LM[0][x]; wm = WM[0][x]
        cols[x] = sorted(((base + tv * (lm - 1)) * wm, req) for base, tv, req in words)[-top_k:]
    m = cp_model.CpModel(); yv = {}
    for x in range(W):
        vs = [m.new_bool_var(f'y{x}_{i}') for i in range(len(cols[x]))]
        for i, v in enumerate(vs):
            yv[(x, i)] = v
        m.add(sum(vs) <= 1)
    m.add(sum(yv.values()) <= hand)
    over = {c: m.new_int_var(0, BASE_BLANKS, f'go{c}') for c in BASE_COUNTS} if BASE_BLANKS else {}
    if over:
        m.add(sum(over.values()) <= BASE_BLANKS)
    for code in BASE_COUNTS:
        u = [yv[(x, i)] * cols[x][i][1][code] for x in range(W) for i in range(len(cols[x])) if cols[x][i][1][code]]
        if u:
            m.add(sum(u) - over.get(code, 0) <= BASE_COUNTS[code])
    m.maximize(sum(yv[(x, i)] * cols[x][i][0] for x in range(W) for i in range(len(cols[x]))))
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 8; s.parameters.max_time_in_seconds = cap
    s.Solve(m)
    return int(math.floor(s.best_objective_bound + 1e-6))


# ----------------------------------------------------------------------------------------------------
#  MAIN
# ----------------------------------------------------------------------------------------------------
def geom_gate(tup, mask):
    """Cheap necessary condition: with EVERY scoring vertical at its longest available length (most fixed
    cells, easiest to bridge) and the tile budget, can the setup cells even be 4-connected?  If not at the
    most-permissive lengths, no legal board exists -> skip the holistic.  (Sound: more fixed cells + max
    budget headroom only helps connectivity; if even this fails the real board can't connect.)"""
    scoring = [x for x in range(W) if mask[x]]
    counts, blanks = per_word_bag(tup)
    total = sum(counts.values()) + blanks
    maxlen = {}
    for c in scoring:
        L = tup[c]; best = 0
        for w in rules.words:
            if w and w[0] == L and len(w) <= H and (len(w) == 1 or w[1:] in rules.words_lookup):
                best = max(best, len(w))
        if best == 0:
            return False
        maxlen[c] = best
    turn = ''.join((rules.alphabet.to_str((tup[i],)).upper() if mask[i]
                    else rules.alphabet.to_str((tup[i],)).lower()) for i in range(W))
    chosen = {c: tuple([0] * maxlen[c]) for c in scoring}
    fx = setup_fixed_cells(W, H, turn, tup, chosen)
    stub = sum(maxlen[c] - 1 for c in scoring)
    budget = total - len(tup) - stub
    if budget < 0:
        budget = 0
    return ORACLE.can_connect(fx, budget)


def evaluate(tup, mask, label, keep_secs):
    """Run the holistic for one (word, mask); return ((vert,total,grid,chosen,scoring,main), status)."""
    msc = main_score(tup, mask)
    scoring = [x for x in range(W) if mask[x]]
    # NOTE: a geometric pre-gate is unreliable here (it must pick vertical lengths, but connectivity
    # depends on the joint length+bridge choice the holistic makes), so we let the holistic decide --
    # it detects INFEASIBLE in presolve in ~0-1s, cheap enough to skip a separate gate.
    # first-incumbent then brief improve (keep_secs) -> a real legal board FAST under load.
    status, vert, sol = solve_holistic(tup, mask, HCAP, stop_after_first=False, keep_secs=keep_secs)
    if status in ('INFEASIBLE', 'NOCAND', 'UNKNOWN') or vert is None or sol is None:
        return None, status
    ok, vrec, grid, chosen, why = extract_and_check(tup, mask, sol)
    if not ok:
        return None, f"CHECK-FAIL:{why}"
    vert = vrec        # trust the independently-recomputed score
    total = msc + vert
    return (vert, total, grid, chosen, scoring, msc), status


def main():
    t0 = time.time()
    GVUB = GVUB_OVERRIDE if GVUB_OVERRIDE >= 0 else global_vertical_ub()
    print(f"global vertical UB (STOP bound) = {GVUB}", flush=True)
    best_total = SEED_LOWER
    best = None
    evaluated = []

    if ONLY:
        wstr, turn = ONLY.split(':')
        tup = rules.alphabet.to_tup(wstr)
        mask = [turn[i].isupper() for i in range(W)]
        res, status = evaluate(tup, mask, wstr, KEEP_SECS)
        print(f"ONLY {wstr} turn={turn} main={main_score(tup, mask)} -> {status} "
              f"{'total=' + str(res[1]) if res else ''}", flush=True)
        if res:
            vert, total, grid, chosen, scoring, msc = res
            print(render_board(grid, tup, mask, scoring))
            print("verticals:", {c: rules.alphabet.to_str(list(chosen[c][0])) for c in scoring})
        return

    words = enumerate_main_words(TOPWORDS)
    print(f"enumerated {len(words)} candidate main words; top main_score={words[0][0]} "
          f"({words[0][1]}), GVUB={GVUB} -> turn UB of #1 ~ {words[0][0] + GVUB}", flush=True)

    for rank, (msc_best, wstr, tup) in enumerate(words):
        if msc_best + GVUB <= best_total:
            print(f"STOP at rank {rank}: best-main {msc_best} + GVUB {GVUB} = {msc_best + GVUB} "
                  f"<= best_total {best_total}", flush=True)
            break
        masks = candidate_masks(tup, NMASKS)
        word_best = None
        for mi, (mask, msc, adj) in enumerate(masks):
            if msc + GVUB <= best_total:
                continue
            res, status = evaluate(tup, mask, wstr, KEEP_SECS)
            tag = ''
            if res:
                vert, total, grid, chosen, scoring, m2 = res
                if best is None or total > best_total:
                    best_total = total
                    best = dict(word=wstr, mask=mask, main=m2, vert=vert, total=total,
                                grid=[r[:] for r in grid],
                                verticals={c: rules.alphabet.to_str(list(chosen[c][0])) for c in scoring},
                                scoring=scoring)
                    tag = '  <-- NEW BEST'
                    board_txt = render_board(grid, tup, mask, scoring)
                    save(BESTTXT,
                         f"main_word={wstr}  main={m2} + verticals={vert} = TOTAL {total}\n"
                         f"scoring(newly placed) cols={scoring}\n"
                         f"verticals: " + '  '.join(f"col{c}:{rules.alphabet.to_str(list(chosen[c][0]))}"
                                                    for c in scoring) + "\n\n" + board_txt + "\n",
                         header=f"board {W}x{H}  exp34 seed BEST (rank {rank} mask {mi})")
                print(f"  [{rank}.{mi}] {wstr} main={msc} mask-adj={adj} -> {status} vert={vert} "
                      f"TOTAL={total}{tag}", flush=True)
                if word_best is None or total > word_best:
                    word_best = total
            else:
                print(f"  [{rank}.{mi}] {wstr} main={msc} mask-adj={adj} -> {status}", flush=True)
        evaluated.append(dict(word=wstr, best_main=msc_best, word_best=word_best))
        # persist progress
        with open(OUT, 'w') as fp:
            json.dump(dict(board=W, scale=SCALE, blanks=BASE_BLANKS, gvub=GVUB,
                           best_total=best_total, best=best, evaluated=evaluated,
                           elapsed=time.time() - t0), fp, indent=1)
        print(f"  rank {rank} done: {wstr} best_main={msc_best} word_best={word_best} "
              f"best_total={best_total} [{time.time()-t0:.0f}s]", flush=True)

    print(f"\n==== exp34 N={W} best legal turn lower bound = {best_total} ====", flush=True)
    if best:
        print(f"  main_word={best['word']}  main={best['main']} + vert={best['vert']} = {best['total']}")
        print(f"  scoring cols={best['scoring']}  verticals={best['verticals']}")
        tup = rules.alphabet.to_tup(best['word'])
        print(render_board(best['grid'], tup, best['mask'], best['scoring']))
        if CERTIFY:
            chosen = {c: (rules.alphabet.to_tup(best['verticals'][c]), 0) for c in best['scoring']}
            out, err = certify_board(tup, best['mask'], best['scoring'], chosen, best['vert'])
            print(f"  CERTIFY (restricted-domain inner): {out}  {('('+err+')') if err else ''}")
    with open(OUT, 'w') as fp:
        json.dump(dict(board=W, scale=SCALE, blanks=BASE_BLANKS, gvub=GVUB,
                       best_total=best_total, best=best, evaluated=evaluated,
                       elapsed=time.time() - t0, done=True), fp, indent=1)
    print(f"  result JSON: {OUT}")


if __name__ == '__main__':
    main()
