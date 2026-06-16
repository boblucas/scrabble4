"""N=15 PHASE-2 LB pusher v2 -- the CORRECTED maximizer: score verticals on ALL 7 newly columns.

WHY v2 (the bug in n15_push_lb.py)
----------------------------------
n15_push_lb.py only ever hung a scoring vertical on the THREE x3-WORD (TWS) columns {0,7,14}
(`vert_cols = [c for c in newly if c in TWS]`); it FORCED every other newly column empty below
row 0 (`m.add(cells[(c,1)].active == 0)`).  But a turn newly-places 7 tiles, and EACH of the 7
can complete a vertical cross-word -- including the two x2-LETTER (DLS) cols {3,11} (bonus
2*val(top)+sum tail) and the remaining 2 plain newly cols (bonus val(top)+sum tail).  Ignoring
those 4 columns badly under-counts the achievable total.  The bag-aware sound UB for
geschenkcheques is 2067, well above the verified 1952 the TWS-only model found, so a higher
VERIFIED board provably exists.

THE CORRECTED MODEL (exactly the rules, per witness_check.get_word_score)
-------------------------------------------------------------------------
Main word on row 0; 7 newly tiles on a mask containing {0,7,14} (-> x27 main).  For EACH newly
column c the vertical `main[c]+tail` (tail = pre-placed tiles reading down from (c,1)) is optional;
when present (len 2..HMAX=8) it scores
        vert(c) = WM[c] * ( LM[c]*val(main[c]) + sum val(tail) )
with WM[c]=3 on {0,7,14} else 1, and LM[c]=2 on {3,11} else 1.  Total turn = main(mask) + sum_c
vert(c).  We MAXIMIZE that, jointly over (a) the mask, (b) one vertical (or none) per newly column,
(c) the pre-placed connector web, subject to: SETUP board (final minus the 7 newly tiles) is ONE
4-connected component including center (7,7); every maximal H/V run >=2 is a legal word; tiles fit
the full bag minus reserve=1; blanks kept off scored tiles.

Adjacent newly columns whose tails sit at the same row form HORIZONTAL cross-words between the tail
tiles -- those are constrained legal by the row automaton on every row (already in create_board),
so the model keeps them legal automatically.

IMPLEMENTATION (mask enumerated; verticals on ALL newly cols via per-column tables)
-----------------------------------------------------------------------------------
For a fixed legal mask we build a CP-SAT board:
  * row automaton on every row (legal horizontal runs, incl. tail<->tail cross-words);
  * column automaton on every PRE-PLACED column (legal vertical runs there);
  * NO column automaton on a newly column -- its legality is the row0-anchored vertical
    `main[c]+tail`, captured by an add_allowed_assignments table over the tail cells (c,1..Ltail).
    The table forbids a bare tail (rows 1..k WITHOUT the top) being forced to be a standalone word
    (which a column automaton would wrongly require);
  * below the table region every newly-column cell is forced empty (no stray run);
  * row-0 pre-placed letters fixed to the main word; row-0 newly cells EMPTY in the setup;
  * (7,7) active + single_component_flow from (7,7);  bag (full - 7 main tiles - reserve=1) + blanks;
  * blanks forbidden on scored tail cells (they would score 0; only ever hurt the objective);
  * OBJECTIVE = sum over all newly cols of vert(c) (exact added vertical score) -> CP-SAT directly
    hunts the highest-scoring legal connected center-reaching board.
Any board found is re-assembled (row 0 = full main word) and INDEPENDENTLY verified by witness_check
(require_center=True, reserve=1).  A passing witness_check is the sole authority -> sound LB.

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
WORD_FILE = os.environ.get('N15_WORD_FILE', 'data/words/dutch_bigger_le15')

r = construct_rules('dutch', B, word_file=WORD_FILE)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]      # row-0 word multipliers (3 at 0/7/14)
LM = np.array(r.letter_multiplier)[0]    # row-0 letter multipliers (2 at 3/11)
TWS = [c for c in range(W) if WM[c] == 3]
DLS = [c for c in range(W) if LM[c] == 2]
print(f"# TWS (x3 word) cols = {TWS}; DLS (x2 letter) cols = {DLS}", flush=True)

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
    """Exact main-word turn score for this mask (x27 word mult on {0,7,14}, x2 letter on newly
    3/11, +50 bingo)."""
    ms = set(mask)
    s = sum(val[w[x]] * (2 if (x in ms and x in (3, 11)) else 1) for x in range(W))
    return 27 * s + 50


def _pre_runs_legal(w, mask):
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


def candidate_masks(w, limit=8):
    """Up to `limit` legal 7-col newly masks for w (all contain {0,7,14}), ranked by an OPTIMISTIC
    per-mask vertical+main ceiling so the most promising masks are tried first."""
    free = [c for c in range(W) if c not in (0, 7, 14)]
    good = []
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if not _pre_runs_legal(w, mask):
            continue
        good.append((_mask_ceiling(w, mask), mask))
    good.sort(reverse=True)
    return [m for _, m in good[:limit]]


# best single-column tail value over dict words "L+tail", len 2..8, per first letter
_TAILMAX = {}
for word in r.words_str:
    if 2 <= len(word) <= HMAX:
        tv = sum(val[c] for c in word[1:])
        if tv > _TAILMAX.get(word[0], -1):
            _TAILMAX[word[0]] = tv


def _best_vert_bonus(c, L):
    if L not in _TAILMAX:
        return 0
    return int(WM[c]) * (int(LM[c]) * val[L] + _TAILMAX[L])


def _mask_ceiling(w, mask):
    """Optimistic (per-column independent) ceiling for this mask = true_main + sum best_vert_bonus
    over the mask's newly columns.  Used only to ORDER masks; never reported as sound."""
    return true_main(w, mask) + sum(_best_vert_bonus(c, w[c]) for c in mask)


def vert_table(top_letter, Ltail):
    """For a newly column whose top (row-0) letter is `top_letter`, the table of legal TAIL rows
    (rows 1..Ltail): each row is the tail-cell letter codes padded with 0 (empty) beyond the word,
    PLUS the all-zero row (no vertical).  Only words `top_letter+tail` of length 2..Ltail+1 fit."""
    cba = r.alphabet.cba
    rows = [[0] * Ltail]                              # no vertical
    seen = {tuple([0] * Ltail)}
    for word in r.words_str:
        if 2 <= len(word) <= Ltail + 1 and word[0] == top_letter:
            tail = [cba[c] for c in word[1:]]
            tail = tail + [0] * (Ltail - len(tail))
            t = tuple(tail)
            if t not in seen:
                seen.add(t); rows.append(tail)
    return np.array(rows, dtype=int)


def solve_push(word, mask, cap, rows=9, maxlen=5):
    """CP-SAT: maximise the full added vertical score over a legal connected center-reaching setup
    board for (word, mask), with verticals OPTIONAL on EVERY newly column.  Returns (grid, obj)."""
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

    m = cp_model.CpModel(); m.prefix = 'q'
    # Column automaton on PRE-PLACED columns only.  Newly columns carry an OPTIONAL vertical
    # main[c]+tail captured by a per-column table; a column automaton there would wrongly force the
    # bare tail (rows 1..k without the row-0 top) to be a standalone word.
    col_auts = [None if x in newly else aut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))

    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)

    # row-0 pre-placed letters fixed; newly row-0 cells EMPTY in the setup
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)

    L = HMAX - 1
    Ltail = min(L, rows - 1)                          # tail rows 1..Ltail
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]  # code 0 -> 0
    obj_terms = []
    for c in newly:
        top_letter = word[c]
        table = vert_table(top_letter, Ltail)
        tail_vars = [cells[(c, y)].letter_int for y in range(1, 1 + Ltail)]
        m.add_allowed_assignments(tail_vars, table)
        # below the table region: force empty (no stray run in this un-automatoned column)
        for y in range(1 + Ltail, H):
            m.add(cells[(c, y)].active == 0)
        # vert(c) = WM[c] * ( LM[c]*val(top)*has_vert + sum tail values )
        has_vert = cells[(c, 1)].active              # a tail tile present <=> vertical exists
        obj_terms.append(int(WM[c]) * int(LM[c]) * int(val[top_letter]) * has_vert)
        for y in range(1, 1 + Ltail):
            cell = cells[(c, y)]
            m.add(cell.blank == 0)                    # no blanks on scored tail cells (score 0)
            cv = m.new_int_var(0, max(val_arr), f'{m.prefix}_cv_{c}_{y}')
            m.add_element(cell.letter_int, val_arr, cv)
            obj_terms.append(int(WM[c]) * cv)

    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)

    newly_ct = Counter(mt[c] for c in mask)
    avail = Counter({code: r.counts[code] - newly_ct[code] for code in r.counts})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= r.blank_count)
    total_cap = sum(r.counts.values()) + r.blank_count - RESERVE - 7
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)

    m.maximize(sum(obj_terms))

    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '6'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, 0, st
    grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
    for x in range(W):
        grid[0][x] = int(mt[x])
    return grid, int(s.objective_value), st


def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B, word_file=WORD_FILE)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b,
                              claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def _save(best_blob, total):
    path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
    json.dump(best_blob, open(path, 'w'))
    print(f"      saved {path}", flush=True)


def push_word(w, cap, rows, baseline, all_masks=False, mask_limit=8):
    """Run all candidate masks for w; return (best_total, best_blob)."""
    masks = candidate_masks(w, limit=mask_limit)
    if not masks:
        print(f"  {w}: NO LEGAL MASK", flush=True)
        return baseline, None
    best = baseline; best_blob = None
    for mask in masks:
        tm = true_main(w, mask)
        ceil = _mask_ceiling(w, mask)
        if ceil <= best:
            print(f"  {w} mask={mask}: ceiling {ceil} <= best {best}, skip", flush=True)
            continue
        t0 = time.time()
        grid, obj, st = solve_push(w, mask, cap, rows=rows)
        if grid is None:
            print(f"  {w} main={tm} mask={mask} ceil={ceil}: no board "
                  f"(st={st}, {time.time()-t0:.0f}s)", flush=True)
            continue
        ok, total, rep = verify(w, mask, grid)
        if not ok:
            print(f"  {w} mask={mask}: REJECT {rep.get('fail')} (obj={obj})", flush=True)
            continue
        verts = rep.get('verticals', {})
        mark = "NEWBEST" if total > best else "ok"
        print(f"  [{mark}] {w} main={tm} mask={mask} ceil={ceil} obj+{obj} -> VERIFIED "
              f"TOTAL={total} verts={verts} ({time.time()-t0:.0f}s)", flush=True)
        if total > best:
            best = total
            turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(w))
            best_blob = {'board': B, 'main_word': w, 'turn_str': turn,
                         'require_center': True, 'claimed_total': total, 'grid': grid}
            _save(best_blob, total)
        if not all_masks:
            break
    return best, best_blob


def run(words, cap, baseline, rows, all_masks, mask_limit):
    best = baseline; best_blob = None
    print(f"# N=15 PUSH LB v2 (ALL 7 newly cols): baseline={baseline}; {len(words)} words; "
          f"cap={cap}s/mask, rows={rows}, reserve={RESERVE}, all_masks={all_masks}", flush=True)
    for w in words:
        proxy = x27_proxy(w)
        if proxy <= best:
            print(f"# x27_proxy({w})={proxy} <= best {best}; remaining ranked-lower words "
                  f"cannot beat best. stopping.", flush=True)
            break
        b, blob = push_word(w, cap, rows, best, all_masks=all_masks, mask_limit=mask_limit)
        if b > best:
            best = b; best_blob = blob
    print(f"# DONE best verified N=15 LB = {best} "
          f"({best_blob['main_word'] if best_blob else 'baseline'})", flush=True)
    return best, best_blob


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', type=str, default=None, help='run a single specific word')
    ap.add_argument('--top', type=int, default=8, help='(no --word) sweep top-N x27 words')
    ap.add_argument('--cap', type=float, default=120.0, help='CP-SAT wall per (word,mask)')
    ap.add_argument('--rows', type=int, default=9, help='working rows (vertical reach)')
    ap.add_argument('--baseline', type=int, default=1952)
    ap.add_argument('--all-masks', action='store_true', help='try EVERY candidate mask, keep best')
    ap.add_argument('--mask-limit', type=int, default=8)
    a = ap.parse_args()
    if a.word:
        run([a.word], a.cap, a.baseline, a.rows, all_masks=a.all_masks, mask_limit=a.mask_limit)
    else:
        words = sorted((w for w in r.words_str if len(w) == 15), key=x27_proxy, reverse=True)[:a.top]
        run(words, a.cap, a.baseline, a.rows, all_masks=a.all_masks, mask_limit=a.mask_limit)
