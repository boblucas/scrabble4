"""N=15 PHASE-2 lower-bound (LB) pusher -- ADD scoring verticals to beat the phase-1 baseline 1724.

CONTEXT (see experiments/MAXTURN_HANDOFF_V2.md sections 0/6/9 and experiments/n15_greedy_lb.py)
-----------------------------------------------------------------------------------------------
Phase 1 (n15_greedy_lb.py) established the verified LB = 1724 (`geschenkcheques`, mask
{0,3,7,9,11,13,14}) by placing a high-value 15-letter MAIN word on row 0 scored x27 (newly tiles on
the three x3-WORD cols {0,7,14} + x2-LETTER cols {3,11}) + bingo +50, with the newly COLUMNS empty
(no verticals) and only a connecting pre-placed web to keep the board one 4-connected component
including center (7,7).

Phase 2 (this tool) ADDS the best-scoring vertical cross-words to push the verified total ABOVE 1724.

VERTICAL SCORING (recomputed exactly by witness_check / scrabble.get_word_score)
--------------------------------------------------------------------------------
A vertical at a NEWLY column c is the run `main[c] + tail` reading down from (c,0): the top tile
(c,0) is the newly-placed scoring tile (placed[0]=True), the tail tiles (c,1..k) are PRE-PLACED
(placed=False, score face value).  get_word_score gives

    vert_score(c) = word_multiplier[0,c] * ( letter_multiplier[0,c]*val(main[c]) + sum tail values )

(sum(placed)=1 != hand_size, so NO bingo on verticals.)  The premium layout (row 0) is x3 WORD at
cols 0/7/14 and x2 LETTER at cols 3/11, with letter_multiplier=1 on the x3 cols.  Hence:
  * c in {0,7,14} (TWS): bonus = 3 * (val(main[c]) + sum tail values)            <- the big wins
  * c in {3,11}   (DLS): bonus = 2*val(main[c]) + sum tail values                <- small
  * other newly col   : bonus = val(main[c]) + sum tail values                   <- modest
The vertical word `main[c]+tail` must be a legal dict word of length 2..HMAX(8).

THE MODEL (CP-SAT, MAXIMIZE the added vertical score)
-----------------------------------------------------
Identical skeleton to n15_greedy_lb.solve_connector, plus optional verticals at chosen newly cols:
  * row automata on all rows + column automata on NON-newly columns (legal setup runs);
  * row-0 pre-placed letters fixed to the main word; row-0 newly cells EMPTY in the setup;
  * for each newly col c we OPTIONALLY hang a vertical: an `add_allowed_assignments` table over the
    tail cells (c,1)..(c,7) restricts them so that `main[c]+tail` (with the FIXED top letter
    main[c]) is a legal word of length 2..8 (or the column is empty = no vertical).  The table is
    over the tail-cell letter_int vars padded with 0 (empty) for lengths < 7; row >= len are 0.
    This is SOUND: any board found is re-verified end-to-end by witness_check.  We do this for ALL
    newly cols, but the OBJECTIVE only rewards the score, so non-premium cols are added only if free.
  * NO column automaton on newly cols (the table already constrains them; a column automaton would
    wrongly require the tail ALONE -- rows 1..k without the top -- to be a legal word, which is not
    the rule: on the FINAL board the run is main[c]+tail);
  * (7,7) forced active; single_component_flow from (7,7) over the setup cells;
  * bag (full minus the 7 newly main-word tiles, minus reserve=1) + blank limits;
  * OBJECTIVE: maximize sum over cells of (premium-weighted value contribution of the vertical
    tails + top-tile bonus), i.e. the exact added vertical score -- so CP-SAT directly hunts the
    highest-scoring legal connected board.

We then build the FINAL board (setup + the 7 newly row-0 tiles = the full main word) and VERIFY with
witness_check (require_center=True).  A passing witness_check is a SOUND LB regardless of how the
board was found -- that is the deliverable.

Single sequential process (process-kill safety: no parallelism, no group kills).
"""
import sys, os, json, time, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from collections import Counter
from itertools import combinations
from ortools.sat.python import cp_model

from scrabble import construct_rules
from dawg import position_independent_row_automaton
from solve import create_board, single_component_flow, limit_letter_count
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B = '15'
HMAX = 8
RESERVE = 1
CENTER = (7, 7)

r = construct_rules('dutch', B)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]      # row-0 word multipliers (3 at 0/7/14)
LM = np.array(r.letter_multiplier)[0]    # row-0 letter multipliers (2 at 3/11)
TWS = [c for c in range(W) if WM[c] == 3]
print(f"# TWS (x3 word) cols = {TWS}", flush=True)

_AUT_CACHE = {}
def _aut(maxlen):
    a = _AUT_CACHE.get(maxlen)
    if a is None:
        a = position_independent_row_automaton([w for w in r.words if 1 <= len(w) <= maxlen])
        _AUT_CACHE[maxlen] = a
    return a


def x27_proxy(w):
    return 27 * (sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50


def true_main(w, mask):
    """Exact main-word turn score (x27 word mult, x2 letter on newly 3/11, +50 bingo)."""
    ms = set(mask)
    s = 0
    for x in range(W):
        lm = 2 if (x in ms and x in (3, 11)) else 1
        s += val[w[x]] * lm
    return 27 * s + 50


def _pre_runs_legal(w, mask):
    """Every maximal run of >=2 PRE-PLACED row-0 cols must already spell a legal word."""
    wl = r.words_lookup; cba = r.alphabet.cba
    preset = set(range(W)) - set(mask)
    x = 0
    while x < W:
        if x not in preset:
            x += 1; continue
        x2 = x
        while x2 < W and x2 in preset:
            x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in wl:
            return False
        x = x2
    return True


def candidate_masks(w, limit=6):
    """Up to `limit` legal 7-col newly masks for w (all contain {0,7,14}), ranked by x2-letter bonus."""
    free = [c for c in range(W) if c not in (0, 7, 14)]
    good = []
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if not _pre_runs_legal(w, mask):
            continue
        ms = set(mask)
        bonus = 27 * ((val[w[3]] if 3 in ms else 0) + (val[w[11]] if 11 in ms else 0))
        good.append((bonus, mask))
    good.sort(reverse=True)
    return [m for _, m in good[:limit]]


def vert_tables(top_code, top_letter, hmax=HMAX):
    """For a newly column whose top (row-0) letter is `top_letter` (code top_code), enumerate the
    legal vertical words `top_letter + tail` of length 2..hmax.  Return a numpy int matrix of TAIL
    rows: each row is the (hmax-1)-length tail-cell letter codes (rows 1..hmax-1), padded with 0
    (empty) beyond the word, PLUS the all-zero row (no vertical = column empty below row 0).
    The row-0 cell is fixed separately to top_code; the table is over the tail cells only.
    """
    L = hmax - 1                                   # number of tail cells modelled (rows 1..hmax-1)
    rows = [[0] * L]                               # no vertical
    cba = r.alphabet.cba
    wordset = set(r.words_str)                      # for SETUP tail-legality (tail must stand alone)
    for word in r.words_str:
        # SETUP-legality: the tail (word[1:]) hangs as a standalone maximal run below the newly tile
        # in the pre-turn board; if its length >= 2 it must itself be a legal dictionary word.
        if 2 <= len(word) <= hmax and word[0] == top_letter \
                and (len(word) - 1 <= 1 or word[1:] in wordset):
            tail = [cba[c] for c in word[1:]]
            tail = tail + [0] * (L - len(tail))
            rows.append(tail)
    return np.array(rows, dtype=int), L


def solve_push(word, mask, cap, rows=9, maxlen=5, verbose=True):
    """CP-SAT: find a legal connected center-reaching setup board for (word, mask) that MAXIMIZES the
    added vertical score (verticals optional on every newly col; the x3 cols 0/7/14 dominate).
    Returns (grid, objective) on success else (None, 0).  grid row 0 = full main word.
    """
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]

    runlen = 1; cur = 0
    for x in range(W):
        if x in pre:
            cur += 1; runlen = max(runlen, cur)
        else:
            cur = 0
    aut = _aut(max(maxlen, runlen))

    # Verticals only on the x3-WORD (TWS) cols 0/7/14 -- the only columns where a vertical is worth
    # the tiles (x3 on the whole word).  All OTHER columns (pre-placed AND non-TWS newly) get the
    # column automaton so every column run is a legal word.  TWS vert cols get NO column automaton
    # (their legality is the row0-anchored vertical table main[c]+tail; the bare tail without the
    # top must NOT be forced to be a standalone word) -- instead we force the TWS column to hold
    # ONLY the contiguous tail (nothing below it), so the table fully captures its legality.
    vert_cols = [c for c in newly if c in TWS]

    m = cp_model.CpModel(); m.prefix = 'p'
    col_auts = [None if x in vert_cols else aut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))

    # restrict to top `rows` rows
    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)

    # row-0 pre-placed letters fixed; newly row-0 cells EMPTY in the setup
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)

    # non-TWS newly cols stay empty below row 0 (force (c,1) empty) -> no vertical there (phase-1)
    L = HMAX - 1
    Ltail = min(L, rows - 1)                       # tail rows 1..Ltail
    for c in newly:
        if c not in vert_cols:
            m.add(cells[(c, 1)].active == 0)

    obj_terms = []
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]  # code 0=empty ->0
    for c in vert_cols:
        top_letter = word[c]
        table, _L = vert_tables(mt[c], top_letter)
        keep = [row[:Ltail] for row in table if all(v == 0 for v in row[Ltail:])]
        keep = np.array(keep, dtype=int) if keep else np.zeros((1, Ltail), dtype=int)
        tail_vars = [cells[(c, y)].letter_int for y in range(1, 1 + Ltail)]
        m.add_allowed_assignments(tail_vars, keep)
        # the TWS column holds ONLY the contiguous tail rows 1..Ltail (table-controlled); force any
        # cell below the table empty so no stray run forms in this un-automatoned column
        for y in range(1 + Ltail, H):
            m.add(cells[(c, y)].active == 0)
        # objective: bonus = WM[c] * ( LM[c]*val(top)*has_vert + sum tail values ).
        # has_vert = column has a tail tile = cells[(c,1)].active.
        has_vert = cells[(c, 1)].active
        obj_terms.append(int(WM[c]) * int(LM[c]) * int(val[top_letter]) * has_vert)
        for y in range(1, 1 + Ltail):
            cell = cells[(c, y)]
            # FORBID blanks on scored tail cells so the tail value is exactly its letter value
            # (blanks score 0; they only help the bag, never these high-value scored tiles).  Then
            # tail value = add_element(letter_int -> value).
            m.add(cell.blank == 0)
            cv = m.new_int_var(0, max(val_arr), f'{m.prefix}_cv_{c}_{y}')
            m.add_element(cell.letter_int, val_arr, cv)
            obj_terms.append(int(WM[c]) * cv)

    # center occupied + single connected component rooted at center (flow encoding)
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)

    # bag: setup letters = full bag minus the 7 newly main-word tiles, minus reserve
    newly_ct = Counter(mt[c] for c in mask)
    avail = Counter({code: r.counts[code] - newly_ct[code] for code in r.counts})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= r.blank_count)
    total_cap = sum(r.counts.values()) + r.blank_count - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)

    m.maximize(sum(obj_terms))

    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '12'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, 0
    grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
    for x in range(W):
        grid[0][x] = int(mt[x])
    return grid, int(s.objective_value)


def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b,
                              claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def run(top_n, cap, baseline=1724, rows=9):
    words = sorted((w for w in r.words_str if len(w) == 15), key=x27_proxy, reverse=True)
    best = baseline; best_blob = None
    print(f"# N=15 PUSH LB: baseline={baseline}; {len(words)} words; top {top_n}; "
          f"CP-SAT cap={cap}s/mask, rows={rows}, reserve={RESERVE}", flush=True)
    for w in words[:top_n]:
        proxy = x27_proxy(w)
        masks = candidate_masks(w)
        if not masks:
            print(f"  {w} proxy={proxy}: NO LEGAL MASK", flush=True)
            continue
        for mask in masks:
            tm = true_main(w, mask)
            # ceiling: main + an optimistic vertical bonus.  We just try; the objective maximizes.
            t0 = time.time()
            grid, obj = solve_push(w, mask, cap, rows=rows)
            if grid is None:
                print(f"  {w} main={tm} mask={mask}: no board ({time.time()-t0:.0f}s)", flush=True)
                continue
            ok, total, rep = verify(w, mask, grid)
            if not ok:
                print(f"  {w} mask={mask}: REJECT {rep.get('fail')} (obj={obj})", flush=True)
                continue
            verts = rep.get('verticals', {})
            mark = "NEWBEST" if total > best else "ok"
            print(f"  [{mark}] {w} main={tm} mask={mask} obj+{obj} -> VERIFIED TOTAL={total} "
                  f"verts={verts} ({time.time()-t0:.0f}s)", flush=True)
            if total > best:
                best = total
                turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(w))
                best_blob = {'board': B, 'main_word': w, 'turn_str': turn,
                             'require_center': True, 'claimed_total': total, 'grid': grid}
                path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
                json.dump(best_blob, open(path, 'w'))
                print(f"      saved {path}", flush=True)
            break    # first verified mask per word is enough
    print(f"# DONE best verified N=15 LB = {best} "
          f"({best_blob['main_word'] if best_blob else 'baseline'})", flush=True)
    return best, best_blob


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=4)
    ap.add_argument('--cap', type=float, default=60.0, help='CP-SAT wall per (word,mask)')
    ap.add_argument('--rows', type=int, default=9, help='working rows (vertical reach)')
    ap.add_argument('--baseline', type=int, default=1724)
    ap.add_argument('--word', type=str, default=None, help='run a single specific word')
    ap.add_argument('--all-masks', action='store_true',
                    help='with --word: try EVERY legal mask and keep the best (default: first only)')
    a = ap.parse_args()
    if a.word:
        masks = candidate_masks(a.word)
        print(f"# single word {a.word} masks={masks}", flush=True)
        b = a.baseline
        for mask in masks:
            t0 = time.time()
            grid, obj = solve_push(a.word, mask, a.cap, rows=a.rows)
            if grid is None:
                print(f"  mask={mask}: no board ({time.time()-t0:.0f}s)", flush=True)
                if a.all_masks:
                    continue
                break
            ok, total, rep = verify(a.word, mask, grid)
            print(f"  mask={mask} obj+{obj} ok={ok} total={total} verts={rep.get('verticals')} "
                  f"({time.time()-t0:.0f}s)", flush=True)
            if ok and total > b:
                b = total
                turn = ''.join(c.upper() if i in set(mask) else c.lower() for i,c in enumerate(a.word))
                blob={'board':B,'main_word':a.word,'turn_str':turn,'require_center':True,
                      'claimed_total':total,'grid':grid}
                json.dump(blob, open(f'{ROOT}/experiments/results/turns/N15_best_{total}.json','w'))
                print(f"      saved best {total}", flush=True)
            if not a.all_masks:
                break
        print(f"# DONE single-word best = {b}", flush=True)
    else:
        run(a.top, a.cap, a.baseline, a.rows)
