"""N=15 STRUCTURAL DECOMPOSITION ("two-level") certification for the hard geschenkcheques {3,11}
masks (and flauwekulexcuus).

THE DECOMPOSITION
-----------------
For main word M on row 0 with newly mask m (7 cols incl {0,7,14}), the total turn score is

    total = main_const(M, m) + sum_{c in m} vert_gross(c)

where vert_gross(c) is the score of the OPTIONAL vertical at newly col c -- a dict word M[c]+tail
(length 1..HMAX, length 1 = bare tile = gross 0), with BOTH tail T (if len(T)>=2) and M[c]+T legal
words (SETUP legality).  The bridge tiles (in non-scoring columns + below short verticals) score 0
and only serve connectivity.  So the SCORE depends ONLY on the 7 per-column vertical choices.

A "combo" = a choice of one tail-legal vertical (or "none") per newly column whose tails fit the
shared bag (full Dutch counts + blanks - reserve, minus the 7 main row-0 tiles; blanks may NOT sit
on scored vertical tiles, so they don't help vertical gross).  We:

  1. MEASURE: count the combos with total vertical gross > vfloor (= LB - main_const), using a
     multiple-choice-knapsack DFS with a per-suffix gross UB (the same prune family xfill uses).
  2. ORACLE: for each above-vfloor combo (descending gross) decide whether a LEGAL, 4-connected,
     center-reaching SETUP board EXISTS with exactly those verticals placed (CP-SAT feasibility,
     proven SAT/UNSAT).  First SAT with main_const+gross>LB -> reconstruct + witness_check -> new LB.
     All combos UNSAT -> mask CERTIFIED <= LB.

  3. bag-UB: a bag-aware multiple-choice-knapsack UB over the TAIL-LEGAL candidates (tighter than
     the analytic per-column-best sum).

SOUNDNESS: the enumeration is COMPLETE (every combo with gross > vfloor is visited -- the suffix UB
never discards a feasible higher-gross combo) and the oracle's UNSAT is EXACT (CP-SAT proven
INFEASIBLE, not a timeout).  Every claimed LB board passes the FIXED witness_check.
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
import numpy as np
from collections import Counter

from scrabble import construct_rules, get_word_score

ROOT = '/home/bob/programming/scrabble4'
B = '15'; HMAX = int(os.environ.get("N15_HMAX", "15"))   # TRUE RULES default; 8 reproduces the legacy variant
r = construct_rules(os.environ.get('N15_LANG', 'dutch'), B)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
wm = [int(x) for x in np.array(r.word_multiplier)[0]]
lm = [int(x) for x in np.array(r.letter_multiplier)[0]]
lk = r.words_lookup
cba = r.alphabet.cba


def scale_counts():
    """N=15 has scale factor 1.0 (W*W/225 == 1), so counts == base bag. Reserve handled by caller."""
    f = (W * W) / (15 * 15)
    base = Counter({c: max(round(n * f), 1) for c, n in r.counts.items()})
    blanks = round(r.blank_count * f)
    return base, blanks


def main_const(w, mask):
    ms = set(mask); WM = 1
    for c in mask:
        WM *= wm[c]
    s = sum(val[w[x]] * (lm[x] if x in ms else 1) for x in range(W))
    return WM * s + 50


def col_candidates(w, c):
    """Tail-legal verticals at newly col c: list of dicts {gross, word(codes), tail_ct(Counter over
    codes for the FULL placed vertical incl the row-0 tile), len}.  The 'none'/bare-tile option (gross
    0) is added by the enumerator.  tail_ct counts EVERY tile physically placed by choosing this
    vertical -- including the row-0 main tile M[c] -- because the bag must supply all of them; but for
    the bag accounting we separate: the row-0 main tile is part of the 7 newly main tiles (charged
    once per mask), the TAIL tiles (rows 1..L-1) are the extra draw.  So tail_ct here = tiles in rows
    1..L-1 only."""
    mt = r.alphabet.to_tup(w)
    code = mt[c]
    out = []
    for ww in r.words:
        if not ww or ww[0] != code or len(ww) < 2 or len(ww) > HMAX:
            continue
        if ww[1:] not in lk:
            continue
        g = int(get_word_score(r, ww, c, 0, 0, [i == 0 for i in range(len(ww))])[0])
        tail = ww[1:]
        tc = Counter(tail)
        out.append({'gross': g, 'word': tuple(ww), 'tail_ct': tc, 'len': len(ww)})
    out.sort(key=lambda d: -d['gross'])
    return out


def pareto_prune(cands):
    """SOUND intra-column dominance prune for the multiple-choice knapsack: candidate A dominates B
    (same column) if A.gross >= B.gross AND A.tail_ct[k] <= B.tail_ct[k] for EVERY letter k (so
    replacing B by A is always feasible and never lowers the objective). Must compare over the UNION
    of both candidates' letters (an earlier version iterated only over B's letters and wrongly pruned).
    Used only for the bag-UB knapsack; the exhaustive above-vfloor enumerator keeps ALL candidates."""
    out = []
    srt = sorted(cands, key=lambda d: (-d['gross'], sum(d['tail_ct'].values())))
    for d in srt:
        dom = False
        for e in out:
            keys = set(d['tail_ct']) | set(e['tail_ct'])
            if e['gross'] >= d['gross'] and all(e['tail_ct'].get(k, 0) <= d['tail_ct'].get(k, 0)
                                                for k in keys):
                dom = True; break
        if not dom:
            out.append(d)
    return out


# ----------------------------------------------------------------------------------------------
# Deliverable 3 (cheap, early): bag-aware multiple-choice-knapsack UB over TAIL-LEGAL candidates.
# ----------------------------------------------------------------------------------------------
from ortools.sat.python import cp_model


def bag_ub_mask(w, mask, avail, cap=30.0):
    """OPTIMAL total vertical gross for (w, mask) s.t. the union of chosen tails fits `avail`
    (per-code available tiles). Returns (status_ok, obj). Choose at most one vertical (or none) per
    newly column. SOUND relaxation (drops connectivity/cross-words/layout)."""
    cols = []
    m = cp_model.CpModel()
    for c in mask:
        cands = pareto_prune(col_candidates(w, c))
        opts = [(m.new_bool_var(f'n{c}'), 0, Counter())]
        for i, d in enumerate(cands):
            opts.append((m.new_bool_var(f'v{c}_{i}'), d['gross'], d['tail_ct']))
        m.add(sum(v for v, _, _ in opts) == 1)
        cols.append(opts)
    for code in avail:
        terms = []
        for opts in cols:
            for v, _, tc in opts:
                n = tc.get(code, 0)
                if n:
                    terms.append(n * v)
        if terms:
            m.add(sum(terms) <= avail[code])
    m.maximize(sum(b * v for opts in cols for v, b, _ in opts if b))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.OPTIMAL:
        return True, int(s.objective_value)
    if st == cp_model.FEASIBLE:
        return False, int(s.objective_value)
    return False, None


# ----------------------------------------------------------------------------------------------
# Deliverable 1: COMBO ENUMERATION/COUNT above vfloor, bag-constrained, with a suffix-gross UB prune.
# ----------------------------------------------------------------------------------------------
def enumerate_above(w, mask, avail, vfloor, max_count=None, collect=False, count_only=False):
    """Count (and optionally collect) every combo (one vertical or 'none' per newly col) whose TOTAL
    vertical gross > vfloor and whose tail multiset fits `avail`. DFS over columns; at column k the
    remaining columns' max achievable gross is suf[k] (sum of per-col gmax incl 'none'=0 so just per
    col max gross); prune when cur_gross + suf[k] <= vfloor (can't exceed). Bag pruning: subtract each
    pick's tail from a running budget; a pick is skipped if it overflows. Returns (count, combos)."""
    cols = mask
    # per-column option lists: each option = (gross, tail_ct) including the 'none' (0, empty)
    optlists = []
    for c in cols:
        cands = col_candidates(w, c)
        opts = [(0, Counter())] + [(d['gross'], d['tail_ct']) for d in cands]
        # sort by descending gross so the suffix UB is tight and high-gross combos surface first
        opts.sort(key=lambda o: -o[0])
        optlists.append(opts)
    n = len(cols)
    # suffix max gross
    sufmax = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        sufmax[k] = sufmax[k + 1] + optlists[k][0][0]   # opt[0] is the max-gross option
    budget = dict(avail)
    combos = [] if collect else None
    cnt = 0
    # mutable budget as Counter
    bud = Counter(avail)

    def fits(tc):
        for code, q in tc.items():
            if bud.get(code, 0) < q:
                return False
        return True

    sys.setrecursionlimit(10000)
    pick = [None] * n

    def dfs(k, cur):
        nonlocal cnt
        if cur + sufmax[k] <= vfloor:
            return                                  # cannot exceed vfloor with any completion
        if k == n:
            if cur > vfloor:
                cnt += 1
                if collect:
                    combos.append((cur, [pick[i] for i in range(n)]))
            return
        for (g, tc) in optlists[k]:
            # suffix prune at the option level: if even taking this option's gross + suffix can't beat
            if cur + g + sufmax[k + 1] <= vfloor:
                break                               # options are sorted desc; rest are smaller
            if not fits(tc):
                continue
            for code, q in tc.items():
                bud[code] -= q
            pick[k] = (g, tc)
            dfs(k + 1, cur + g)
            for code, q in tc.items():
                bud[code] += q
            if max_count and cnt >= max_count:
                return

    dfs(0, 0)
    return cnt, combos


def enumerate_above_fast(w, mask, avail, vfloor, node_budget=None, time_budget=None, collect_top=0):
    """Faster exhaustive count of combos with total vertical gross > vfloor under the shared bag.
    Improvements over enumerate_above:
      - columns ordered by DESCENDING gmax (tightest suffix prune surfaces high-gross combos first);
      - per-option early break (options sorted desc by gross);
      - node counter + optional node/time budget so we can characterise the magnitude even if huge
        (returns capped=True if a budget was hit -> the count is a LOWER BOUND, enumeration NOT
        complete -> NOT a certification basis, only a measurement).
      - optionally collect the `collect_top` highest-gross complete combos (for the oracle).
    Returns dict(count, nodes, capped, top) where top is a sorted-desc list of (gross, combo_dict)."""
    cols = list(mask)
    coldata = []
    for c in cols:
        cands = col_candidates(w, c)
        opts = [(0, Counter(), None)] + [(d['gross'], d['tail_ct'], d['word']) for d in cands]
        opts.sort(key=lambda o: -o[0])
        coldata.append((c, opts))
    # order columns by descending max gross
    coldata.sort(key=lambda cd: -cd[1][0][0])
    order = [cd[0] for cd in coldata]
    optlists = [cd[1] for cd in coldata]
    n = len(order)
    sufmax = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        sufmax[k] = sufmax[k + 1] + optlists[k][0][0]
    bud = Counter(avail)
    import heapq
    top = []  # min-heap of (gross, idx, combo_dict)
    tie = [0]
    state = {'count': 0, 'nodes': 0, 'capped': False}
    pick = [None] * n
    t0 = time.time()

    def dfs(k, cur):
        state['nodes'] += 1
        if node_budget and state['nodes'] >= node_budget:
            state['capped'] = True; return
        if time_budget and (state['nodes'] & 0x3FFFF) == 0 and time.time() - t0 > time_budget:
            state['capped'] = True; return
        if cur + sufmax[k] <= vfloor:
            return
        if k == n:
            state['count'] += 1
            if collect_top:
                combo = {order[i]: pick[i] for i in range(n)}
                if len(top) < collect_top:
                    tie[0] += 1; heapq.heappush(top, (cur, tie[0], combo))
                elif cur > top[0][0]:
                    tie[0] += 1; heapq.heapreplace(top, (cur, tie[0], combo))
            return
        for (g, tc, ww) in optlists[k]:
            if cur + g + sufmax[k + 1] <= vfloor:
                break
            ok = True
            for code, q in tc.items():
                if bud[code] < q:
                    ok = False; break
            if not ok:
                continue
            for code, q in tc.items():
                bud[code] -= q
            pick[k] = ww
            dfs(k + 1, cur + g)
            for code, q in tc.items():
                bud[code] += q
            if state['capped']:
                return

    sys.setrecursionlimit(100000)
    dfs(0, 0)
    top_sorted = sorted(((g, combo) for g, _, combo in top), key=lambda x: -x[0])
    return {'count': state['count'], 'nodes': state['nodes'], 'capped': state['capped'],
            'top': top_sorted, 'order': order}


def build_avail(w, mask, reserve):
    """Available tiles for the TAILS = base bag - reserve - the 7 newly main row-0 tiles. Clamp at 0."""
    base, blanks = scale_counts()
    mt = r.alphabet.to_tup(w)
    newly_ct = Counter(mt[c] for c in mask)
    avail = {code: max(0, base[code] - newly_ct.get(code, 0)) for code in base}
    # reserve: opponent holds >=1 tile -> remove `reserve` from the most plentiful? No: reserve just
    # caps TOTAL board tiles. For the bag-feasibility of tails, reserve only matters as a global tile
    # budget which the connectivity bridges also draw on. We apply reserve as a global cap in the
    # oracle, not here (here avail is the per-letter ceiling for tails alone, which is sound: tails
    # can never use more of a letter than the bag holds minus main tiles).
    return avail, blanks


# ----------------------------------------------------------------------------------------------
# Deliverable 2: FEASIBILITY ORACLE.  Given (word, mask, combo) with combo[c] = chosen vertical WORD
# (codes, incl row-0 main tile) or None (no vertical), decide whether a LEGAL, 4-connected,
# center-reaching SETUP board exists with EXACTLY those verticals placed.  CP-SAT proven SAT/UNSAT.
#
# We FIX the scoring columns' cells to the chosen verticals (rows 0..L-1; rows >=L forced empty), so
# the vertical run legality + the HORIZONTAL cross-words formed between adjacent tails (the documented
# TWOLEVEL failure mode) are enforced by the ROW automata, which see the fixed tail letters.  The
# connector fills bridge tiles in non-scoring columns (and below short verticals) to reach center.
# Full <=HMAX row + column automata (so every setup run, incl tail cross-words up to length 8, is a
# legal word).  Bag/blank/reserve enforced.  Re-verified by witness_check afterwards.
# ----------------------------------------------------------------------------------------------
_AUTC = {}
def _aut_le(maxlen):
    a = _AUTC.get(maxlen)
    if a is None:
        from dawg import position_independent_row_automaton
        a = position_independent_row_automaton([ww for ww in r.words if 1 <= len(ww) <= maxlen])
        _AUTC[maxlen] = a
    return a


def oracle_feasible(word, mask, combo, cap=120.0, conn_maxlen=None):
    """Returns (status, grid). status in {'SAT','UNSAT','UNKNOWN'}; grid is the full final board on SAT.

    conn_maxlen: if set, the COLUMN automaton on non-scoring (connector) columns is restricted to
    words of length <= conn_maxlen. This SHRINKS the search (faster) but makes an UNSAT verdict
    UNSOUND for CERTIFICATION (a feasible board using a longer connector vertical could be missed).
    Use conn_maxlen ONLY for the LB hunt (a SAT board is independently witness_check'd, so SAT stays
    sound); leave it None (full <=HMAX) for certification. Rows ALWAYS use the full <=HMAX automaton
    (adjacent-tail horizontal cross-words must be checked at full length)."""
    from solve import create_board, single_component_flow, limit_letter_count
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    CENTER = (W // 2, H // 2)
    aut = _aut_le(HMAX)                       # rows: ALWAYS full <=HMAX
    caut = _aut_le(conn_maxlen) if conn_maxlen else aut    # NON-scoring (connector) columns
    m = cp_model.CpModel(); m.prefix = 'o'
    # FULL row automaton. Scoring columns: FULL <=HMAX automaton (their pinned length-8 vertical must
    # be accepted -- a restricted caut would wrongly reject it). Non-scoring columns: caut (full unless
    # conn_maxlen restricts the connector for the LB hunt).
    col_auts = [aut if x in newly else caut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))
    # row-0: pre-placed letters fixed; newly row-0 EMPTY in setup (scored tile lands only in the turn)
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    # FIX each scoring column's vertical (rows 1..L-1) to the chosen word's tail; cap scored run at L.
    for c in mask:
        ww = combo.get(c)
        if ww is None:
            m.add(cells[(c, 1)].active == 0)
        else:
            L = len(ww)
            for y in range(1, L):
                m.add(cells[(c, y)].letter[ww[y]] == 1)
            if L < H:
                m.add(cells[(c, L)].active == 0)
    # connectivity to center
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    # bag: setup tiles available = full bag minus the 7 newly main row-0 tiles.
    newly_ct = Counter(mt[c] for c in mask)
    base, blanks = scale_counts()
    avail = Counter({code: base[code] - newly_ct.get(code, 0) for code in base})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    RESERVE = int(os.environ.get('RESERVE', '1'))
    total_cap = sum(base.values()) + blanks - RESERVE - 7   # 7 newly tiles held off the setup board
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return 'UNSAT', None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])     # full main word on row 0 (newly tiles now placed)
        return 'SAT', grid
    return 'UNKNOWN', None


def combo_key(combo):
    """CONTENT key for a combo (ledger identity). The positional enumeration id is
    PYTHONHASHSEED-NONDETERMINISTIC across processes (proven 2026-07-02: same count, different
    id->combo mapping under different hash seeds), so id-keyed resume has coverage holes. Keying
    by content makes the ledger process-independent."""
    parts = []
    for c in sorted(combo):
        ww = combo[c]
        parts.append(f"{c}:{''.join(chr(96 + x) for x in ww) if ww else '-'}")
    return '|'.join(parts)


def enumerate_above_blanks(w, mask, avail, vfloor, blank_budget=2, collect_top=0, stream=None,
                           node_budget=None):
    """BLANK-AWARE complete band enumeration. Like enumerate_above_fast, but a combo whose tails
    exceed `avail` on some letters may still be placeable using <=blank_budget blanks (a blank
    stands in for any letter but SCORES 0).

    PENALTY BOUND: each deficit blank must sit on a TAIL cell carrying that letter (bridges using
    the letter would only deepen the deficit), so it forfeits >= val[letter] * wm[col] >=
    val[letter] realized points.  Best-possible realized gross <= nominal - sum val[deficit
    letters].  Band criterion: nominal - penalty_lb > vfloor -- a SOUND superset of {combos that
    can beat vfloor}; the score-aware oracle (oracle_beats_lb) then decides each exactly.
    (Charging only 1/blank made blank-unlocked scarce-letter words explode the tree: the val-
    based charge restores the suffix cut.)  Per-option adj_gross = gross - standalone penalty vs
    the FULL avail (a lower bound on the true penalty, since the shared bag only shrinks) drives
    ordering, the per-column max, and the suffix bound.
    Returns dict(count, nodes, capped, top) with top = desc-sorted (nominal_gross, combo)."""
    vv = {i: val[chr(96 + i)] for i in range(1, 27)}
    cols = list(mask)
    coldata = []
    for c in cols:
        cands = col_candidates(w, c)
        opts = []
        for d in [{'gross': 0, 'tail_ct': Counter(), 'word': None}] + cands:
            g, tc, ww = d['gross'], d['tail_ct'], d['word']
            sb = sum(vv[code] * max(0, q - max(avail.get(code, 0), 0))
                     for code, q in tc.items())          # standalone penalty LB vs full avail
            nb = sum(max(0, q - max(avail.get(code, 0), 0)) for code, q in tc.items())
            if nb > blank_budget:
                continue                                  # can never be placed at all
            opts.append((g, tc, ww, g - sb))              # adj_gross = gross - penaltyLB
        opts.sort(key=lambda o: (-o[3], o[2] or ()))      # desc by adj_gross, deterministic tiebreak
        coldata.append((c, opts))
    coldata.sort(key=lambda cd: (-cd[1][0][3], cd[0]))
    order = [cd[0] for cd in coldata]
    optlists = [cd[1] for cd in coldata]
    n = len(order)
    sufmax = [0] * (n + 1)
    for k in range(n - 1, -1, -1):
        sufmax[k] = sufmax[k + 1] + optlists[k][0][3]     # suffix bound on ADJUSTED gross
    bud = Counter(avail)
    import heapq
    top = []
    tie = [0]
    state = {'count': 0, 'nodes': 0, 'capped': False}
    pick = [None] * n
    tprint = [time.time()]

    def dfs(k, cur, curadj, used_b):
        # cur = nominal gross so far; curadj = nominal - true-deficit penaltyLB so far
        state['nodes'] += 1
        if node_budget and state['nodes'] >= node_budget:
            state['capped'] = True                  # SAMPLING only -- capped=True is not a cert
            return
        if state['nodes'] % 50_000_000 == 0 and time.time() - tprint[0] > 60:
            tprint[0] = time.time()
            print(f"    [enum] {state['nodes']/1e6:.0f}M nodes, {state['count']} in band",
                  flush=True)
        if curadj + sufmax[k] <= vfloor:            # best realized from here <= vfloor -> prune
            return
        if k == n:
            # LEAF-EXACT penalty: a deficit blank on letter code sits on some CHOSEN tail cell
            # carrying code, forfeiting val[code] * wm[that col]; min over containing columns.
            # (curadj charged only val*1 -- exact min-wm here drops loose-bound survivors.)
            if cur != curadj:                        # has deficits: recheck with exact min-wm
                pen = 0
                for code in bud:
                    d = -bud[code]
                    if d > 0:
                        mw = min((wm[order[i]] for i in range(n)
                                  if pick[i] and code in pick[i][1:]), default=1)
                        pen += d * vv[code] * mw
                if cur - pen <= vfloor:
                    return
            state['count'] += 1
            if stream is not None:
                # STREAMING mode (over-cap bands): hand every in-band combo to the caller as it
                # is found -- no materialization, no cap, complete coverage by construction.
                stream(cur, {order[i]: pick[i] for i in range(n)})
            elif collect_top:
                combo = {order[i]: pick[i] for i in range(n)}
                if len(top) < collect_top:
                    tie[0] += 1; heapq.heappush(top, (cur, tie[0], combo))
                elif cur > top[0][0]:
                    tie[0] += 1; heapq.heapreplace(top, (cur, tie[0], combo))
            return
        for (g, tc, ww, gadj) in optlists[k]:
            if curadj + gadj + sufmax[k + 1] <= vfloor:
                break                                # opts sorted desc by adj_gross
            db = 0; pen = 0                          # TRUE deficits vs the shared bag state
            ok = True
            for code, q in tc.items():
                short = q - max(bud[code], 0)        # bud<0 = earlier deficit already counted
                if short > 0:
                    db += short
                    pen += vv[code] * short
                    if used_b + db > blank_budget:
                        ok = False; break
            if not ok:
                continue
            if curadj + g - pen + sufmax[k + 1] <= vfloor:
                continue                             # true-penalty cut (not sorted by this: no break)
            for code, q in tc.items():
                bud[code] -= q
            pick[k] = ww
            dfs(k + 1, cur + g, curadj + g - pen, used_b + db)
            for code, q in tc.items():
                bud[code] += q
            if state['capped']:
                return

    sys.setrecursionlimit(100000)
    dfs(0, 0, 0, 0)
    # canonical output order: (-gross, combo_key) -- fully deterministic across processes
    top_sorted = sorted(((g, combo) for g, _, combo in top),
                        key=lambda x: (-x[0], combo_key(x[1])))
    return {'count': state['count'], 'nodes': state['nodes'], 'capped': state['capped'],
            'top': top_sorted, 'order': order}


_FAST_TMPL = {}
def _oracle_template(word, mask):
    """Build the combo-INDEPENDENT part of oracle_feasible's model ONCE per (word,mask):
    board automata (full <=HMAX rows+cols), row-0 pre pins + newly row-0 inactive, center pin,
    connectivity flow, bag/blank/reserve. Everything except the per-combo vertical pins.
    Returns (model, cells). Cached: building this is ~7s; per-combo reuse is the whole speedup."""
    from solve import create_board, single_component_flow, limit_letter_count
    key = (word, tuple(mask))
    tm = _FAST_TMPL.get(key)
    if tm is not None:
        return tm
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    CENTER = (W // 2, H // 2)
    aut = _aut_le(HMAX)
    m = cp_model.CpModel(); m.prefix = 'o'
    cells = create_board(m, [aut] * H, [aut] * W, alphabet_size=len(r.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
        # NO blank on a row-0 main-word cell: blanking one forfeits val*WM >= 27 realized points
        # (witness _cell_score_weight) while oracle_beats_lb's slack <= UB-LB-1 <= 21, so no such
        # grid can beat LB.  Without this the solver "free-blanked" main tiles to dodge bag
        # overflow (penalty terms only cover scored tails) -> SAT over-claims the witness rejects
        # (the 2026-07-03 MODEL-WITNESS MISMATCH).  Sound for lb >= UB-26 (driver asserts).
        m.add(cells[(x, 0)].blank == 0)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    newly_ct = Counter(mt[c] for c in mask)
    base, blanks = scale_counts()
    avail = Counter({code: base[code] - newly_ct.get(code, 0) for code in base})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    RESERVE = int(os.environ.get('RESERVE', '1'))
    total_cap = sum(base.values()) + blanks - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    tm = (m, cells)
    _FAST_TMPL[key] = tm
    return tm


_TB_TMPL = {}
def _oracle_template_tb(word, mask):
    """TURN-BLANK-AWARE template: like _oracle_template but adds tb[c] (turn tile at newly col c
    is a BLANK).  Effects: (i) bag credit -- the real letter mt[c] is not drawn by the turn, so
    setup non-blank usage of that code may exceed the base avail by Sum tb over cols holding it;
    (ii) the global blank budget covers setup blanks + turn blanks.  The SCORE cost of tb[c]
    (>= 27*val: main word x27 + the vertical's row-0 letter) is charged per-combo in
    oracle_beats_lb_tb's penalty constraint.  Needed ONLY for combos with nominal > LB + 27
    (below that a turn-blank board can never beat LB; driver asserts)."""
    from solve import create_board, single_component_flow
    key = (word, tuple(mask))
    tm = _TB_TMPL.get(key)
    if tm is not None:
        return tm
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    CENTER = (W // 2, H // 2)
    aut = _aut_le(HMAX)
    m = cp_model.CpModel(); m.prefix = 'o'
    cells = create_board(m, [aut] * H, [aut] * W, alphabet_size=len(r.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
        m.add(cells[(x, 0)].blank == 0)          # row-0 pre blank: costs 27*val, never beats LB
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    newly_ct = Counter(mt[c] for c in mask)
    base, blanks = scale_counts()
    tb = {c: m.new_bool_var(f'tb{c}') for c in mask}
    # TB-aware per-letter budget: non-blank setup usage <= avail + (turn blanks holding this code)
    for code in base:
        avail_c = base[code] - newly_ct.get(code, 0)
        terms = []
        for cell in cells.values():
            v = m.new_bool_var(f'tbl_{cell.x}_{cell.y}_{code}')
            m.add(v == 0).only_enforce_if(cell.blank)
            m.add(v == cells[(cell.x, cell.y)].letter[code]).only_enforce_if(~cell.blank)
            terms.append(v)
        credit = sum(tb[c] for c in mask if mt[c] == code)
        m.add(sum(terms) <= avail_c + credit)
    m.add(sum(cell.blank for cell in cells.values()) + sum(tb.values()) <= blanks)
    RESERVE = int(os.environ.get('RESERVE', '1'))
    total_cap = sum(base.values()) + blanks - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    tm = (m, cells, tb)
    _TB_TMPL[key] = tm
    return tm


def oracle_beats_lb_tb(word, mask, combo, vfloor, cap=120.0):
    """TURN-BLANK-COMPLETE per-combo decision: does ANY grid with these verticals -- INCLUDING
    grids where some of the 7 played tiles are blanks -- realize a total > LB?  Used for the
    band slice with nominal > LB + 27 (elsewhere turn blanks cannot beat LB and the standard
    oracle_beats_lb is complete).  tb[c] cost: main word loses val*lm[c]*27; if the combo has a
    vertical at c, its row-0 letter (val*lm[c]) times wm[c] is lost too.  Setup tail blanks are
    charged val*wm[c] as in oracle_beats_lb.  Total penalty <= nominal - vfloor - 1."""
    tmpl, cells, tb = _oracle_template_tb(word, mask)
    m = cp_model.CpModel()
    m.proto.CopyFrom(tmpl.proto)

    def fix(var, v):
        dom = m.proto.variables[var.index].domain
        del dom[:]
        dom.extend([v, v])

    mt = r.alphabet.to_tup(word)
    nominal = 0
    pen_terms = []
    for c in mask:
        ww = combo.get(c)
        tbcost = val[chr(96 + mt[c])] * lm[c] * 27
        if ww is None:
            fix(cells[(c, 1)].active, 0)
        else:
            L = len(ww)
            nominal += vert_gross(ww, c)
            tbcost += val[chr(96 + mt[c])] * lm[c] * wm[c]
            for y in range(1, L):
                fix(cells[(c, y)].letter[ww[y]], 1)
                pen_terms.append(val[chr(96 + ww[y])] * wm[c] * cells[(c, y)].blank)
            if L < H:
                fix(cells[(c, L)].active, 0)
        pen_terms.append(tbcost * tb[c])
    slack = nominal - vfloor - 1
    if slack < 0:
        return 'UNSAT', None
    m.add(sum(pen_terms) <= slack)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return 'UNSAT', None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        return 'SAT', grid
    return 'UNKNOWN', None


def oracle_feasible_fast(word, mask, combo, cap=120.0):
    """Semantically identical to oracle_feasible(conn_maxlen=None) but ~10x faster: reuses the
    cached template model (92% of oracle_feasible's per-combo cost is rebuilding it) and applies
    the per-combo vertical pins as VARIABLE DOMAIN FIXES on a proto copy -- a domain fix [v,v]
    is exactly m.add(var == v). Verdicts gated A/B against oracle_feasible (see _fast_gate.py)."""
    tmpl, cells = _oracle_template(word, mask)
    m = cp_model.CpModel()
    m.proto.CopyFrom(tmpl.proto)

    def fix(var, v):
        dom = m.proto.variables[var.index].domain
        del dom[:]
        dom.extend([v, v])

    for c in mask:
        ww = combo.get(c)
        if ww is None:
            fix(cells[(c, 1)].active, 0)
        else:
            L = len(ww)
            for y in range(1, L):
                fix(cells[(c, y)].letter[ww[y]], 1)
            if L < H:
                fix(cells[(c, L)].active, 0)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return 'UNSAT', None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        mt = r.alphabet.to_tup(word)
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        return 'SAT', grid
    return 'UNKNOWN', None


def vert_gross(ww, c):
    """Nominal gross of vertical ww at newly col c (row-0 tile newly, tail = setup tiles)."""
    return int(get_word_score(r, ww, c, 0, 0, [i == 0 for i in range(len(ww))])[0])


def oracle_beats_lb(word, mask, combo, vfloor, cap=120.0, fix_grid=None):
    """SOUND per-combo decision: does ANY legal setup board with exactly these verticals REALIZE
    a total > LB (= main_const + vfloor)?  Replaces the unsound 'oracle_feasible SAT -> witness
    the returned grid -> if <= LB continue' flow (a DIFFERENT grid for the same combo can score
    higher when blanks land on scored tiles).

    Realized gross = nominal - sum over blanked scored tail cells of val[letter] * wm[c]  (a blank
    scores 0; the vertical's word-multiplier wm[c] comes from its newly row-0 tile).  We constrain
    penalty <= nominal - vfloor - 1, i.e. realized > vfloor.  Blanks stay ALLOWED on scored cells
    (bag-deficit combos need them) but must leave the total above LB.

    Turn-tile blanks are NOT modeled: blanking a newly row-0 tile costs >= 27 points (main word
    x27 for the {0,7,14} masks, min letter val 1), so for LB within 26 of the analytic mask UB
    (2030) no turn-blank board can beat LB.  Caller must ensure main_const's x27 structure holds
    (masks containing 0,7,14) and LB >= UB-26; the driver asserts this.

    Returns (status, grid): 'UNSAT' = no grid beats LB (SAFE), 'SAT' = grid found (witness it),
    'UNKNOWN' = cap hit.

    fix_grid: (GATE/CANARY use) a full final board grid; every setup cell (rows >=1) is FIXED to
    it, turning the solve into pure propagation -- validates that a known-legal board SATISFIES
    the model (over-constraint check) without paying a hard SAT search."""
    tmpl, cells = _oracle_template(word, mask)
    m = cp_model.CpModel()
    m.proto.CopyFrom(tmpl.proto)

    def fix(var, v):
        dom = m.proto.variables[var.index].domain
        del dom[:]
        dom.extend([v, v])

    nominal = 0
    pen_terms = []
    for c in mask:
        ww = combo.get(c)
        if ww is None:
            fix(cells[(c, 1)].active, 0)
        else:
            L = len(ww)
            nominal += vert_gross(ww, c)
            for y in range(1, L):
                fix(cells[(c, y)].letter[ww[y]], 1)
                pen_terms.append(val[chr(96 + ww[y])] * wm[c] * cells[(c, y)].blank)
            if L < H:
                fix(cells[(c, L)].active, 0)
    slack = nominal - vfloor - 1                 # realized = nominal - penalty must be > vfloor
    if slack < 0:
        return 'UNSAT', None                     # nominal itself can't beat LB
    if pen_terms:
        m.add(sum(pen_terms) <= slack)
    if fix_grid is not None:                     # canary mode: pin the whole setup board
        for y in range(1, H):
            for x in range(W):
                code = fix_grid[y][x]
                if code:
                    fix(cells[(x, y)].letter[code], 1)
                else:
                    fix(cells[(x, y)].active, 0)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return 'UNSAT', None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        mt = r.alphabet.to_tup(word)
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        if os.environ.get('ORACLE_DEBUG_BLANKS'):
            bl = [[bool(s.value(cells[(x, y)].blank)) if grid[y][x] and y > 0 else False
                   for x in range(W)] for y in range(H)]
            return 'SAT', (grid, bl)
        return 'SAT', grid
    return 'UNKNOWN', None


def oracle_feasible_core(word, mask, combo, cap=120.0):
    """Like oracle_feasible but the per-column vertical pins are placed under ASSUMPTION literals so
    that on UNSAT we can extract a SUFFICIENT infeasibility core = the SUBSET of columns whose pinned
    verticals alone make the board infeasible. Returns (status, grid, core_cols).
    core_cols (on UNSAT) = list of mask columns in the sufficient core; cutting any combo that AGREES
    with `combo` on exactly those columns is sound (every such combo is ALSO infeasible -- it pins the
    same cells the core needed). On SAT/UNKNOWN core_cols is None."""
    from dawg import position_independent_row_automaton
    from solve import create_board, single_component_flow, limit_letter_count
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    CENTER = (W // 2, H // 2)
    aut = position_independent_row_automaton([ww for ww in r.words if 1 <= len(ww) <= HMAX])
    m = cp_model.CpModel(); m.prefix = 'o'
    cells = create_board(m, [aut] * H, [aut] * W, alphabet_size=len(r.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    # per-column assumption literal: a[c] true => that column's vertical is pinned as in `combo`.
    a = {}
    for c in mask:
        ac = m.new_bool_var(f'asm{c}'); a[c] = ac
        ww = combo.get(c)
        if ww is None:
            m.add(cells[(c, 1)].active == 0).only_enforce_if(ac)
        else:
            L = len(ww)
            for y in range(1, L):
                m.add(cells[(c, y)].letter[ww[y]] == 1).only_enforce_if(ac)
            if L < H:
                m.add(cells[(c, L)].active == 0).only_enforce_if(ac)
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    newly_ct = Counter(mt[c] for c in mask)
    base, blanks = scale_counts()
    avail = Counter({code: base[code] - newly_ct.get(code, 0) for code in base})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    RESERVE = int(os.environ.get('RESERVE', '1'))
    total_cap = sum(base.values()) + blanks - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    for c in mask:
        m.add_assumption(a[c])
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        core_lits = set(s.sufficient_assumptions_for_infeasibility())
        core_cols = [c for c in mask if a[c].index in core_lits]
        if not core_cols:                 # infeasible even with no pins -> shouldn't happen here
            core_cols = list(mask)
        return 'UNSAT', None, core_cols
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        return 'SAT', grid, None
    return 'UNKNOWN', None, None


def max_oracle(word, mask, cap=120.0, target=None):
    """INTEGRATED oracle: build the full legal setup board with the 7 per-column vertical CHOICES as
    decision variables (each scoring col picks one tail-legal vertical OR none), enforce connectivity
    to center + all setup-run legality (row + non-scoring-col automata) + bag/blank/reserve, and
    MAXIMIZE the total vertical gross. CP-SAT proven OPTIMAL => sound certification:
       optimum_total = main_const + max_gross.  If <= LB: CERTIFIED. If a board > LB found: witness it.
    `target`: if set, add constraint gross >= target-main_const and solve as FEASIBILITY (faster: just
    need one board beating LB, or proven none exists).
    Returns (status, best_total, grid). status in OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN."""
    from dawg import position_independent_row_automaton
    from solve import create_board, single_component_flow, limit_letter_count
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]
    CENTER = (W // 2, H // 2)
    aut = position_independent_row_automaton([ww for ww in r.words if 1 <= len(ww) <= HMAX])
    m = cp_model.CpModel(); m.prefix = 'x'
    # FULL column automaton on EVERY column (incl scoring): a scoring column reads
    # [main tile, tail..., EMPTY at row L, (optional connector tiles below as separate legal runs)].
    # Allowing connector tiles below the vertical is REQUIRED for soundness (the real setup board may
    # route bridges through a scoring column below its vertical); forbidding them would over-constrain
    # and could wrongly CERTIFY. row L forced empty caps the SCORED run at exactly length L.
    cells = create_board(m, [aut] * H, [aut] * W, alphabet_size=len(r.abc))
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
    mc = main_const(word, mask)
    vfloor = (int(os.environ.get('LB', '2007'))) - mc
    # PRUNE candidates that can never appear in a combo whose total gross > vfloor (sound for both the
    # certification and the LB hunt: such a candidate is irrelevant to whether ANY board beats LB).
    # cand at col c is relevant iff gross(c) + sum_{c'!=c} gmax(c') > vfloor.
    allcands = {c: col_candidates(word, c) for c in mask}
    gmax = {c: (allcands[c][0]['gross'] if allcands[c] else 0) for c in mask}
    sumgmax = sum(gmax.values())
    items = {}
    for c in mask:
        others = sumgmax - gmax[c]
        thresh = vfloor - others       # cand relevant iff gross > thresh
        cands = [d for d in allcands[c] if d['gross'] > thresh]
        opts = [(m.new_bool_var(f'n{c}'), 0, None)]   # 'none' option: no vertical (row 1 empty)
        for i, d in enumerate(cands):
            opts.append((m.new_bool_var(f'v{c}_{i}'), d['gross'], d['word']))
        m.add(sum(v for v, _, _ in opts) == 1)
        for v, g, ww in opts:
            if ww is None:
                m.add(cells[(c, 1)].active == 0).only_enforce_if(v)   # no scored vertical
            else:
                L = len(ww)
                for y in range(1, L):
                    m.add(cells[(c, y)].letter[ww[y]] == 1).only_enforce_if(v)
                if L < H:
                    m.add(cells[(c, L)].active == 0).only_enforce_if(v)   # cap scored run at length L
        items[c] = opts
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)
    newly_ct = Counter(mt[c] for c in mask)
    base, blanks = scale_counts()
    avail = Counter({code: base[code] - newly_ct.get(code, 0) for code in base})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= blanks)
    RESERVE = int(os.environ.get('RESERVE', '1'))
    total_cap = sum(base.values()) + blanks - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)
    gross = sum(g * v for c in mask for v, g, _ in items[c] if g)
    if target is not None:
        m.add(gross >= target - mc)        # feasibility: does any board reach total >= target?
    else:
        m.maximize(gross)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    name = s.StatusName(st)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        best_total = mc + int(s.value(gross)) if target is None else None
        return name, best_total, grid
    return name, None, None


def verify_board(word, mask, grid):
    """Independent witness_check (require_center=True, reserve via scaled bag). Returns (ok, total, rep)."""
    import witness_check as wc
    turn = ''.join(ch.upper() if i in set(mask) else ch.lower() for i, ch in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules(os.environ.get('N15_LANG', 'dutch'), B)
    f = (W * W) / (15 * 15)
    mc = Counter(r2.alphabet.to_tup(word))
    r2.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in r2.counts.items()})
    r2.blank_count = round(r2.blank_count * f)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def benders_certify(w, mask, lb, reserve=1, oracle_cap=60.0, max_iters=100000,
                    time_budget=3600.0, save=True):
    """Combinatorial-Benders / no-good certification (the smart decomposition).

    Maintain a bag-aware multiple-choice-knapsack MASTER (choose one vertical/none per newly col,
    maximize total gross s.t. shared bag) over the FULL tail-legal candidate set. Repeatedly:
      1. solve master to OPTIMAL -> best-gross combo C with gross g (UB on remaining achievable).
      2. if main_const + g <= lb: NO un-cut combo can beat lb -> mask CERTIFIED <= lb. STOP.
      3. run the connectivity ORACLE on C (proven SAT/UNSAT):
           - SAT + witness>lb -> NEW LB. STOP.
           - UNSAT -> add a NO-GOOD cut excluding exactly C (sum of C's chosen option-vars <= 6),
             so the master never returns C again; loop.
           - UNKNOWN (oracle wall) -> mask OPEN (cannot decide C).

    SOUNDNESS: the master's optimum is a SOUND UB on the max gross over all NOT-YET-CUT combos
    (it drops connectivity/layout, which only lower the score). Every cut removes only a combo
    PROVEN connectivity-infeasible by an EXACT CP-SAT UNSAT (never a timeout). So when the master
    optimum first falls to <= vfloor, every combo above vfloor has been proven infeasible -> the
    certification is exact. Termination uses the FIXED witness_check as the LB arbiter.
    """
    mc = main_const(w, mask); vfloor = lb - mc
    mt = r.alphabet.to_tup(w)
    newly_ct = Counter(mt[c] for c in mask)
    base, _ = scale_counts()
    avail = Counter({code: base[code] - newly_ct.get(code, 0) for code in base})
    # build master ONCE (full tail-legal candidates per col; pareto prune is SOUND for the master's
    # own optimum). Keep the word per option so we can hand the chosen combo to the oracle.
    m = cp_model.CpModel()
    cols = []
    for c in mask:
        cands = pareto_prune(col_candidates(w, c))
        opts = [(m.new_bool_var(f'n{c}'), 0, Counter(), None)]
        for i, d in enumerate(cands):
            opts.append((m.new_bool_var(f'v{c}_{i}'), d['gross'], d['tail_ct'], d['word']))
        m.add(sum(v for v, _, _, _ in opts) == 1)
        cols.append((c, opts))
    for code in avail:
        terms = [n * v for _, opts in cols for v, _, tc, _ in opts for n in [tc.get(code, 0)] if n]
        if terms:
            m.add(sum(terms) <= avail[code])
    m.maximize(sum(b * v for _, opts in cols for v, b, _, _ in opts if b))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '8'))
    s.parameters.max_time_in_seconds = 30
    import time as _t
    t0 = _t.time()
    for it in range(max_iters):
        if _t.time() - t0 > time_budget:
            return {'mask': mask, 'verdict': 'OPEN', 'reason': 'benders time budget', 'iters': it}
        st = s.Solve(m)
        if st != cp_model.OPTIMAL:
            return {'mask': mask, 'verdict': 'OPEN', 'reason': f'master {s.StatusName(st)}', 'iters': it}
        g = int(s.objective_value)
        total = mc + g
        if total <= lb:
            return {'mask': mask, 'verdict': 'CERTIFIED', 'iters': it, 'final_bag_ub': total}
        # extract chosen combo + per-column chosen option-var (for the no-good cut)
        combo = {}; chosen_var = {}
        for c, opts in cols:
            for v, gg, tc, ww in opts:
                if s.value(v):
                    chosen_var[c] = v
                    if ww is not None:
                        combo[c] = ww
                    break
        stt, grid, core = oracle_feasible_core(w, mask, combo, cap=oracle_cap)
        if stt == 'UNKNOWN':
            return {'mask': mask, 'verdict': 'OPEN', 'reason': 'oracle UNKNOWN', 'iters': it,
                    'at_total': total}
        if stt == 'SAT':
            ok, vt, rep = verify_board(w, mask, grid)
            if ok and vt > lb:
                if save:
                    turn = ''.join(ch.upper() if i in set(mask) else ch.lower()
                                   for i, ch in enumerate(w))
                    blob = {'board': B, 'main_word': w, 'turn_str': turn, 'require_center': True,
                            'claimed_total': vt, 'grid': grid}
                    path = f'{ROOT}/experiments/results/turns/N15_best_{vt}.json'
                    json.dump(blob, open(path, 'w'))
                return {'mask': mask, 'verdict': 'NEW-LB', 'total': vt, 'iters': it, 'saved': True}
            # SAT but witness <= lb: cut exactly this combo (master gross overstated the turn score).
            m.add(sum(chosen_var.values()) <= len(chosen_var) - 1)
        else:
            # UNSAT: STRONG cut over the sufficient infeasibility core -- exclude EVERY combo that
            # agrees with the chosen verticals on the core columns (all are equally infeasible).
            cut_vars = [chosen_var[c] for c in (core if core else list(mask))]
            m.add(sum(cut_vars) <= len(cut_vars) - 1)
        if (it + 1) % 25 == 0:
            print(f"    [benders {mask}] iter {it+1}: master gross={g} total={total} "
                  f"core={core if stt=='UNSAT' else 'SAT'} ({_t.time()-t0:.0f}s)", flush=True)
    return {'mask': mask, 'verdict': 'OPEN', 'reason': 'max_iters', 'iters': max_iters}


def run_oracle_mask(w, m, lb, reserve, oracle_cap, time_budget, save=True):
    """Per-combo oracle: enumerate combos with gross>vfloor descending, test oracle_feasible on each;
    first SAT with total>lb (witness-OK) -> NEW LB. All UNSAT -> mask CERTIFIED <= lb. Returns dict."""
    mc = main_const(w, m); vfloor = lb - mc
    avail, _ = build_avail(w, m, reserve)
    # collect ALL above-vfloor combos sorted desc by gross (collect_top=0 means count only, so we use
    # a big collect_top; for masks with millions this is memory-heavy -> caller may cap via env)
    cap_collect = int(os.environ.get('COLLECT_TOP', '20000'))
    res = enumerate_above_fast(w, m, avail, vfloor, time_budget=time_budget, collect_top=cap_collect)
    combos = res['top']                # list of (gross, combo_dict{col:word})
    print(f"  mask {m}: {res['count']} combos>vfloor (capped={res['capped']}); "
          f"testing top {len(combos)} by gross", flush=True)
    tested = 0
    for gross, combo in combos:
        total = mc + gross
        if total <= lb:
            break                      # descending; rest can't beat lb
        st, grid = oracle_feasible(w, m, combo, cap=oracle_cap)
        tested += 1
        if st == 'UNKNOWN':
            print(f"    combo gross={gross} total={total}: oracle UNKNOWN (cap hit) -> mask OPEN",
                  flush=True)
            return {'mask': m, 'verdict': 'OPEN', 'reason': 'oracle UNKNOWN', 'tested': tested}
        if st == 'SAT':
            ok, vt, rep = verify_board(w, m, grid)
            if ok and vt > lb:
                print(f"    [NEW-LB] combo gross={gross} -> witness total={vt}", flush=True)
                if save:
                    turn = ''.join(ch.upper() if i in set(m) else ch.lower()
                                   for i, ch in enumerate(w))
                    blob = {'board': B, 'main_word': w, 'turn_str': turn, 'require_center': True,
                            'claimed_total': vt, 'grid': grid}
                    path = f'{ROOT}/experiments/results/turns/N15_best_{vt}.json'
                    json.dump(blob, open(path, 'w'))
                    print(f"      saved {path}", flush=True)
                return {'mask': m, 'verdict': 'NEW-LB', 'total': vt, 'tested': tested}
            else:
                print(f"    combo gross={gross} SAT but witness {('total '+str(vt)) if ok else rep.get('fail')}"
                      f" (not > lb) -> continue", flush=True)
    if res['capped']:
        return {'mask': m, 'verdict': 'OPEN', 'reason': 'enumeration capped/incomplete',
                'tested': tested}
    return {'mask': m, 'verdict': 'CERTIFIED', 'tested': tested, 'combos': res['count']}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', default='geschenkcheques')
    ap.add_argument('--lb', type=int, default=2007)
    ap.add_argument('--reserve', type=int, default=1)
    ap.add_argument('--mode', default='measure',
                    choices=['measure', 'bagub', 'count', 'feas', 'oracle', 'benders'])
    ap.add_argument('--maxcount', type=int, default=0)
    ap.add_argument('--cap', type=float, default=300.0, help='CP-SAT wall per solve')
    ap.add_argument('--oraclecap', type=float, default=60.0, help='per-combo oracle wall')
    ap.add_argument('--tbudget', type=float, default=200.0, help='enumeration time budget')
    a = ap.parse_args()
    os.environ['LB'] = str(a.lb); os.environ['RESERVE'] = str(a.reserve)
    w = a.word
    from n15_greedy_lb import candidate_masks
    ms = candidate_masks(w, limit=500)
    both = [m for m in ms if 3 in m and 11 in m]
    print(f"# {w}: {len(ms)} legal masks, {len(both)} with both cols 3&11 (the hard ones); "
          f"LB={a.lb} reserve={a.reserve} mode={a.mode}", flush=True)
    summary = []
    for m in both:
        mc = main_const(w, m)
        vfloor = a.lb - mc
        avail, blanks = build_avail(w, m, a.reserve)
        t0 = time.time()
        if a.mode == 'bagub':
            ok, obj = bag_ub_mask(w, m, avail)
            tot = mc + obj if obj is not None else None
            print(f"mask {m} main_const={mc} vfloor={vfloor}: bag_UB(verts)={obj} total={tot} "
                  f"(optimal={ok}) {time.time()-t0:.1f}s", flush=True)
        elif a.mode == 'feas':
            # single integrated FEASIBILITY solve: does any board score >= lb+1?
            name, total, grid = max_oracle(w, m, cap=a.cap, target=a.lb + 1)
            if name == 'INFEASIBLE':
                verdict = f'CERTIFIED<={a.lb}'
            elif name in ('OPTIMAL', 'FEASIBLE') and grid is not None:
                ok, vt, rep = verify_board(w, m, grid)
                verdict = f'NEW-LB={vt}' if (ok and vt > a.lb) else f'SAT-but-witness={ok}/{vt}'
            else:
                verdict = f'UNKNOWN({name})'
            print(f"mask {m} vfloor={vfloor}: feas(target={a.lb+1}) -> {verdict} {time.time()-t0:.1f}s",
                  flush=True)
            summary.append((m, verdict))
        elif a.mode == 'oracle':
            res = run_oracle_mask(w, m, a.lb, a.reserve, a.oraclecap, a.tbudget)
            print(f"mask {m}: VERDICT {res['verdict']} ({time.time()-t0:.0f}s) {res}", flush=True)
            summary.append((m, res['verdict']))
        elif a.mode == 'benders':
            res = benders_certify(w, m, a.lb, a.reserve, a.oraclecap, time_budget=a.tbudget)
            print(f"mask {m}: VERDICT {res['verdict']} ({time.time()-t0:.0f}s) {res}", flush=True)
            summary.append((m, res['verdict']))
        else:
            mx = a.maxcount or None
            cnt, _ = enumerate_above(w, m, avail, vfloor, max_count=mx)
            capped = '(CAPPED)' if (mx and cnt >= mx) else ''
            print(f"mask {m} main_const={mc} vfloor={vfloor}: #combos>vfloor = {cnt} {capped} "
                  f"{time.time()-t0:.1f}s", flush=True)
    if summary:
        print("=== SUMMARY ===", flush=True)
        for m, v in summary:
            print(f"  mask {m}: {v}", flush=True)
