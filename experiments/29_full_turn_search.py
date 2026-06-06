"""
Experiment 29: full TURN optimum = search over main words x holistic verticals.

The holistic model (exp28) proves the optimal CONNECTABLE verticals for ONE given main word.
The optimal TURN is max over main words of (main_word_score + optimal_verticals). This wraps it:
  - enumerate main words in decreasing main-word score (a copy of create_horizontal_word_solver)
  - for each, build+prove the holistic stage-2 (copy of exp28's validated model)
  - track best total; stop when main_score + a global vertical upper bound <= best_total.

ASSUMPTION (stated): main-word blanks are forbidden, so the global blank pool is reserved for the
verticals and never double-counted across the two solves. (Relaxing this needs a merged main+vertical
solve with a shared blank pool; flagged for high-confidence v2.)

Run: python experiments/29_full_turn_search.py [board] [vcap] [--scale-tiles] [--hmax N]
"""
import sys, time
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules, get_word_score
from dawg import position_independent_row_automaton, automaton_words_from_list
from solve import (create_board, single_component, limit_letter_count,
                   create_word_mapping, estimate_score, read_board_state, do_solve)

board = sys.argv[1] if len(sys.argv) > 1 else '11'
VCAP = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0     # per-main-word vertical-solve cap
HMAX = int(sys.argv[sys.argv.index('--hmax') + 1]) if '--hmax' in sys.argv else 8
CORES = int(sys.argv[sys.argv.index('--cores') + 1]) if '--cores' in sys.argv else 24
rules = construct_rules('dutch', board)
W, H = rules.W, rules.H
if '--scale-tiles' in sys.argv:
    f = (W * W) / (15 * 15)
    rules.counts = Counter({c: max(round(n * f), 1) for c, n in rules.counts.items()})
    rules.blank_count = round(rules.blank_count * f)
    print(f"--scale-tiles {f:.3f}: bag {sum(rules.counts.values())} tiles, {rules.blank_count} blanks")
ABC = len(rules.abc)

# ---- stage 1: main-word placements in decreasing score (adapted from create_horizontal_word_solver) ----
def main_word_solver(no_main_blanks=True):
    model = cp_model.CpModel(); model.prefix = 'pre'
    one = automaton_words_from_list([(i,) for i in range(len(rules.alphabet))], 1)
    short = automaton_words_from_list([w for w in rules.words_lookup if len(w) <= 3], W)
    cells = create_board(model, [short], [one] * W, alphabet_size=ABC)          # pre-turn row 0
    mult_active = {(x, y): ~cell.active for (x, y), cell in cells.items()
                   if rules.word_multiplier[y][x] > 1 or rules.letter_multiplier[y][x] > 1}
    model.prefix = 'suf'
    full = automaton_words_from_list([w for w in rules.words_lookup if len(w) == W], W)
    cells2 = create_board(model, [full], [one] * W, alphabet_size=ABC)          # post-turn row 0 = main word
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

# ---- stage 2: holistic verticals for a fixed main word (copy of exp28's validated model) ----
def build_holistic(main_word, turn_str, hmax=HMAX):
    main_tup = rules.alphabet.to_tup(main_word)
    scoring = [x for x in range(W) if turn_str[x].isupper()]
    pre = [x for x in range(W) if not turn_str[x].isupper()]
    cands = {}
    for c in scoring:
        L = main_tup[c]; out = []
        for w in rules.words:
            if not w or w[0] != L or len(w) > H: continue
            if len(w) > 1 and w[1:] not in rules.words_lookup: continue
            sc, _ = get_word_score(rules, w, c, 0, 0, [i == 0 for i in range(len(w))])
            out.append((w, sc, Counter(w[1:])))
        cands[c] = out
    nc_ub = sum(max(sc for _, sc, _ in cands[c]) for c in scoring)
    m = cp_model.CpModel(); m.prefix = 'h'
    hw = [w for w in rules.words if len(w) <= hmax]
    row_aut = position_independent_row_automaton(hw)
    rows = [None] + [row_aut] * (H - 1)
    cells = create_board(m, rows, [None] * W, alphabet_size=ABC)
    for x in pre:
        m.add(cells[(x, 0)].letter[main_tup[x]] == 1)
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
    newly = Counter(main_tup[c] for c in scoring)
    limit_letter_count(m, cells, Counter({code: rules.counts[code] - newly[code] for code in rules.counts}))
    over = {code: 0 for code in rules.counts}
    penalty = 0
    m.add(sum(cell.blank for cell in cells.values()) <= rules.blank_count)
    for code in rules.counts:
        terms = []
        for c in scoring:
            for r in range(1, H):
                cell = cells[(c, r)]
                b = m.new_bool_var(f'blk_{c}_{r}_{code}')
                m.add(b <= cell.blank); m.add(b <= cell.letter[code]); m.add(b >= cell.blank + cell.letter[code] - 1)
                terms.append(b)
        o = m.new_int_var(0, rules.blank_count, f'o_{code}')
        m.add(o == sum(terms)); over[code] = o
        penalty = penalty + o * rules.scores[code]
    for code in rules.counts:
        cap = rules.counts[code] - main_tup.count(code)
        usage = [xv[(c, i)] * rq[code] for c in scoring for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over[code] <= cap)
    if pre:   # root connectivity at a pre-placed tile; a full-bingo main word (no pre-placed) needs no setup
        single_component(m, cells, (pre[0], 0))
    m.maximize(sum(xv[(c, i)] * sc for c in scoring for i, (w, sc, rq) in enumerate(cands[c])) - penalty)
    return m, xv, cands, nc_ub, scoring

# ---- global vertical upper bound (stops the main-word enumeration). TILE-AWARE with DISTINCT columns:
# the <=hand_size verticals sit on distinct columns and share the bag, so they can't all max out. Solve an
# assignment-knapsack over per-column candidates (any start letter): <=1 vertical/column, <=hand_size total,
# tile budget (full bag = valid over-estimate; blank relaxation), maximize score. Valid UB on any main
# word's verticals (real verticals are more constrained: fixed letters, connectivity); ~280 vs the tile-
# blind ~415, so the enumeration stops far sooner. (Validated: comes out >= the per-main-word bare-pack ceiling.)
def global_vertical_ub(top_k=200):
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
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 8; s.parameters.max_time_in_seconds = 150
    s.Solve(m)
    return int(s.objective_value)

# ---- per-main-word BARE-PACK upper bound: optimal verticals with the tile budget + blanks but NO
# connectivity and NO cross-word legality. Those only LOWER the verticals, so this is a valid (tight)
# upper bound on the holistic vertical score, and it solves in seconds -> prune expensive holistics.
def barepack_ub(main_word, turn_str):
    main_tup = rules.alphabet.to_tup(main_word)
    scoring = [x for x in range(W) if turn_str[x].isupper()]
    cands = {}
    for c in scoring:
        L = main_tup[c]; out = []
        for w in rules.words:
            if not w or w[0] != L or len(w) > H: continue
            if len(w) > 1 and w[1:] not in rules.words_lookup: continue
            sc, _ = get_word_score(rules, w, c, 0, 0, [i == 0 for i in range(len(w))])
            out.append((w, sc, Counter(w[1:])))
        cands[c] = out
    m = cp_model.CpModel()
    xv = {}
    for c in scoring:
        vs = []
        for i, (w, sc, rq) in enumerate(cands[c]):
            v = m.new_bool_var(f'b_{c}_{i}'); xv[(c, i)] = v; vs.append(v)
        m.add(sum(vs) == 1)
    over = {code: m.new_int_var(0, rules.blank_count, f'bo_{code}') for code in rules.counts} if rules.blank_count else {}
    if over:
        m.add(sum(over.values()) <= rules.blank_count)
    pen = 0
    for code in rules.counts:
        cap = rules.counts[code] - main_tup.count(code)
        usage = [xv[(c, i)] * rq[code] for c in scoring for i, (w, sc, rq) in enumerate(cands[c]) if rq[code]]
        if usage:
            m.add(sum(usage) - over.get(code, 0) <= cap)
        if code in over:
            pen = pen + over[code] * rules.scores[code]
    m.maximize(sum(xv[(c, i)] * sc for c in scoring for i, (w, sc, rq) in enumerate(cands[c])) - pen)
    s = cp_model.CpSolver(); s.parameters.num_search_workers = 8; s.parameters.max_time_in_seconds = 120
    s.Solve(m)
    return int(s.objective_value)
GVUB = global_vertical_ub()
print(f"global vertical UB (stop bound) = {GVUB}; hmax={HMAX}, vcap={VCAP}s")

# ---- search ----
best_total, best = -1, None
mw_model, pre_cells, post_cells = main_word_solver(no_main_blanks=True)
nmain = 0
for msolver in do_solve(mw_model, log=False, cores=CORES):
    main_score = int(msolver.objective_value)
    setup = ''.join(x if x else ' ' for x in read_board_state(msolver, pre_cells, rules.alphabet)[0])
    mword = ''.join(x if x else ' ' for x in read_board_state(msolver, post_cells, rules.alphabet)[0])
    turn_str = ''.join(c.upper() if setup[i] == ' ' else c for i, c in enumerate(mword))
    # no-good so the next solve yields the next main word
    mw_model.add_bool_or([~[v for v in list(cell.letter.values()) + [~cell.active] if msolver.Value(v)][0]
                          for cell in post_cells.values()])
    nmain += 1
    if main_score + GVUB <= best_total:
        print(f"STOP: main #{nmain} score {main_score} + GVUB {GVUB} <= best {best_total}")
        break
    bp = barepack_ub(mword.lower(), turn_str)   # cheap, tight upper bound on this main word's verticals
    if main_score + bp <= best_total:
        print(f"main #{nmain}: {turn_str}  main={main_score} + barepack_ub {bp} = {main_score + bp} <= best {best_total}  -> PRUNED", flush=True)
        continue
    t = time.time()
    hm, xv, cands, nc_ub, scoring = build_holistic(mword.lower(), turn_str)
    vbest = None
    for vsolver in do_solve(hm, log=True, cores=CORES, time_limit=VCAP, extra_probing=6):   # probing to push the UB down (connectivity LP is loose)
        vbest = int(vsolver.objective_value)
        break
    dt = time.time() - t
    if vbest is None:   # holistic infeasible/unsolved (e.g. cannot connect within the bag) -> skip this main word
        print(f"main #{nmain}: {turn_str}  main={main_score}  vert=INFEASIBLE/none ({dt:.0f}s) -> skip", flush=True)
        continue
    total = main_score + vbest
    tag = ''
    if total > best_total:
        best_total = total; best = (mword, turn_str, main_score, vbest); tag = '  <-- NEW BEST'
    print(f"main #{nmain}: {turn_str}  main={main_score} + vert={vbest} = {total}  (nc_ub {nc_ub}, {dt:.0f}s){tag}", flush=True)

print(f"\n==== OPTIMAL TURN (over {nmain} main words): {best[2]+ (best[3] or 0)} ====")
if best:
    print(f"  main word: {best[1]}  (main {best[2]} + verticals {best[3]})")
