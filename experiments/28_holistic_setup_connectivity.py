"""
Experiment 28: holistic model with CORRECT (setup / pre-turn) connectivity.

Fix vs exp27: connectivity is over the board BEFORE the turn. Row 0 holds only the PRE-PLACED
main-word tiles; the newly-placed (scoring) positions are EMPTY. Each scoring vertical contributes
only its w[1:] (the already-on-board part below the not-yet-placed top tile). Those w[1:] stubs +
the scattered pre-placed tiles must form ONE component (via row-2 bridges) -- the binding check.

  - word-choice x[c,word] carry SCORE + tile budget (tight bound, exp26)
  - channel x -> setup cells: scoring col c gets w[1:] in rows 1..len(w)-1, row 0 empty
  - row 0: pre-placed cols pinned to their main letter (active); scoring cols inactive
  - single_component over the setup board, rooted at a pre-placed tile
  - optional <=hmax horizontal-word validity on rows 1+

Question: does real connectivity now BITE (lower the achievable score / reject sets) while STILL
proving fast (bound stays tight because it rides on x)?

Run: python experiments/28_holistic_setup_connectivity.py [board] [cap] [--hmax N] [--no-connect]
"""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton
from solve import create_board, single_component, limit_letter_count

board = sys.argv[1] if len(sys.argv) > 1 else '11'
CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 180.0
HMAX = int(sys.argv[sys.argv.index('--hmax') + 1]) if '--hmax' in sys.argv else None
CONNECT = '--no-connect' not in sys.argv
LITE = '--lite' in sys.argv   # memory levers: cross-word automaton on >=3-vertical rows only + no bridge tile budget
BLANKS = '--blanks' in sys.argv   # model the bag's blank tiles (can shift the optimum -> needed for a true optimum)
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
main_word = sys.argv[sys.argv.index('--main') + 1] if '--main' in sys.argv else "mucolyticum"
turn_str  = sys.argv[sys.argv.index('--turn') + 1] if '--turn' in sys.argv else "MUCOlYtiCuM"
TOPROWS   = int(sys.argv[sys.argv.index('--top-rows') + 1]) if '--top-rows' in sys.argv else None  # cross-word automaton only on rows 1..TOPROWS
assert len(main_word) == W, f"main word {main_word} must be {W} letters"
assert len(turn_str) == W
main_tup = rules.alphabet.to_tup(main_word)
if '--scale-tiles' in sys.argv:
    f = (W * W) / (15 * 15)   # keep tiles-per-cell (hence tile-starvation) comparable to N=15
    mc = Counter(main_tup)
    rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})  # never 0; floor at main-word usage
    rules.blank_count = round(rules.blank_count * f)
    print(f"--scale-tiles factor {f:.3f}: bag now {sum(rules.counts.values())} tiles, {rules.blank_count} blanks")
scoring_cols = [x for x in range(W) if turn_str[x].isupper()]      # newly placed -> empty in setup
preplaced   = [x for x in range(W) if not turn_str[x].isupper()]   # already on board in setup
print(f"board {W}x{H}, scoring(newly placed) {scoring_cols}, preplaced {preplaced}, "
      f"connect={CONNECT}, hmax={HMAX}, cap={CAP}s")

def candidates_for(x):
    L = main_tup[x]; out = []
    for w in rules.words:
        if not w or w[0] != L or len(w) > H: continue
        if len(w) > 1 and w[1:] not in rules.words_lookup: continue
        sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(len(w))])
        out.append((w, sc, Counter(w[1:])))
    return out
cands = {c: candidates_for(c) for c in scoring_cols}
nc_ub = sum(max(sc for _, sc, _ in cands[c]) for c in scoring_cols)
print(f"candidates {{c:len}} = { {c: len(cands[c]) for c in scoring_cols} }; no-contention UB = {nc_ub}")

m = cp_model.CpModel(); m.prefix = 'setup'
# a row can host a cross-word only if >=3 scoring columns have a vertical long enough to reach it
def reaching(y):
    return sum(1 for c in scoring_cols if any(len(w) > y for w, _, _ in cands[c]))
dense_rows = {y for y in range(1, H) if reaching(y) >= 3}
if HMAX is None:
    rows = [None] * H; hrows = set()
else:
    hw = [w for w in rules.words if len(w) <= HMAX]
    row_aut = position_independent_row_automaton(hw)
    if TOPROWS is not None:
        hrows = set(range(1, TOPROWS + 1))        # cross-words only in the top rows ("none in final rows")
    elif LITE:
        hrows = dense_rows                        # >=3-vertical rows only
    else:
        hrows = set(range(1, H))                  # every row 1+
    rows = [row_aut if y in hrows else None for y in range(H)]
    print(f"cross-word automaton (<= {HMAX}) on rows {sorted(hrows)}; rows 1+ outside that forbid horizontal words")
cells = create_board(m, rows, [None] * W, alphabet_size=len(rules.abc))
# rows 1+ WITHOUT the automaton: assume NO connective word there -> forbid adjacent active cells
if HMAX is not None:
    for y in range(1, H):
        if y not in hrows:
            for x in range(W - 1):
                m.add(cells[(x, y)].active + cells[(x + 1, y)].active <= 1)

# row 0 = setup: pre-placed tiles present, newly-placed positions empty
for x in preplaced:
    m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
for x in scoring_cols:
    m.add(cells[(x, 0)].active == 0)

# scoring verticals: channel x -> the w[1:] stub in rows 1..len(w)-1
xv = {}
for c in scoring_cols:
    vs = []
    for i, (w, sc, rq) in enumerate(cands[c]):
        v = m.new_bool_var(f'x_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
        for r in range(1, H):
            if r < len(w):
                m.add(cells[(c, r)].letter[w[r]] == 1).only_enforce_if(v)
            else:
                m.add(cells[(c, r)].active == 0).only_enforce_if(v)
    m.add(sum(vs) == 1)

# tile budgets: correct cell-based (counts pre-placed + stubs + bridges), avail = bag - newly placed.
newly = Counter(main_tup[c] for c in scoring_cols)
avail_setup = Counter({code: rules.counts[code] - newly[code] for code in rules.counts})
if not LITE:        # LITE drops the bridge tile budget (connectivity is feasibility, not minimal-tile)
    limit_letter_count(m, cells, avail_setup)   # blank-aware: a blanked cell consumes no real letter

# blanks: <= blank_count board tiles may be blanks (score 0, no real tile). over[code] = blanked
# vertical-stub tiles of letter `code` -> relaxes the tight vertical budget and costs the tile's face value.
# bridge blanks fall out of the (blank-aware) cell budget above for free, at 0 score, sharing the pool.
over = {code: 0 for code in rules.counts}
penalty = 0
if BLANKS:
    m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
    for code in rules.counts:
        terms = []
        for c in scoring_cols:
            for r in range(1, H):
                cell = cells[(c, r)]
                b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                terms.append(b)
        o = m.new_int_var(0, rules.blank_count, f'over_{code}')
        m.add(o == sum(terms)); over[code] = o
        penalty = penalty + o * rules.scores[code]

# tight x-budget (stubs <= bag - full main word), relaxed by blanked stub tiles
for code in rules.counts:
    cap = rules.counts[code] - main_tup.count(code)
    usage = [xv[(c, i)] * rq[code] for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
    if usage:
        m.add(sum(usage) - over[code] <= cap)

if CONNECT:
    single_component(m, cells, (preplaced[0], 0))   # root at a pre-placed tile (always active)

m.maximize(sum(xv[(c, i)] * sc for c in scoring_cols for i, (w, sc, rq) in enumerate(cands[c])) - penalty)

print(f"model: {len(m.proto.variables)} vars, {len(m.proto.constraints)} constraints")
s = cp_model.CpSolver()
s.parameters.num_search_workers = 24
s.parameters.max_time_in_seconds = CAP
s.parameters.max_presolve_iterations = 1
s.parameters.log_search_progress = True
t = time.time(); r = s.Solve(m); st = time.time() - t
name = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE', cp_model.INFEASIBLE: 'INFEASIBLE'}.get(r, str(r))
obj = int(s.objective_value) if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
bnd = s.best_objective_bound if r in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
print(f"\nRESULT  solve={st:.1f}s {name}  obj={obj}  bound={bnd}  [no-contention UB {nc_ub}, "
      f"exp27 no-real-connect gave 292]")

if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    chosen = {}
    print("\n--- chosen scoring verticals (full word; top letter = main-word tile placed this turn) ---")
    for c in scoring_cols:
        for i, (w, sc, rq) in enumerate(cands[c]):
            if s.value(xv[(c, i)]):
                chosen[c] = w
                print(f"  col {c:2d}: {rules.alphabet.to_str(w):18} len={len(w):2d}  score={sc}")
                break
    print(f"  vertical lengths = {sorted((len(w) for w in chosen.values()), reverse=True)}")
    # reconstruct the full post-turn board: row 0 = main word, verticals hang down, bridges = other active cells
    grid = [['.'] * W for _ in range(H)]
    for x in range(W):
        grid[0][x] = turn_str[x]
    for c, w in chosen.items():
        for ri in range(1, len(w)):
            grid[ri][c] = rules.alphabet.to_str([w[ri]])
    for (x, y), cell in cells.items():
        if grid[y][x] == '.' and s.value(cell.active):
            for code, bv in cell.letter.items():
                if s.value(bv):
                    grid[y][x] = rules.alphabet.to_str([code]) + '*'   # * marks a connectivity bridge tile
                    break
    print("\n--- board (row 0 = main word incl. UPPERCASE newly-placed tiles; verticals hang down; X* = bridge) ---")
    for row in grid:
        print('  ' + ' '.join(f'{c:2}' for c in row))
