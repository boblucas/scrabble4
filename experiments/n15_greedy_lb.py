"""N=15 greedy lower-bound (LB) finder -- the CORRECTED (verticals-optional) model.

THE MODEL (see experiments/MAXTURN_HANDOFF_V2.md sections 0/6/9)
---------------------------------------------------------------
The optimal N=15 turn is a high-value 15-letter MAIN word on row 0, with the 7 newly-placed
(this-turn) tiles on a column mask that includes the three x3-WORD squares {0,7,14} (-> x27 word
multiplier) and ideally the two x2-LETTER squares {3,11}.  7 newly tiles => bingo +50.  The
newly-placed COLUMNS are otherwise EMPTY (no verticals => no cross-word constraint), so the whole
score is just the main word scored at its multiplier plus the bingo.  The proxy LB of a word is

    x27_proxy(w) = 27 * ( sum(value(letter)) + value(w[3]) + value(w[11]) ) + 50

(the x2-letter cols 3 and 11 add their letter value once more; everything is under the x27 word
multiplier from cols 0,7,14).

THE REAL CHALLENGE -- setup connectivity
-----------------------------------------
witness_check requires the SETUP board (final board MINUS the 7 newly tiles) to be ONE 4-connected
component that INCLUDES the center (7,7), with every maximal H/V run of length >=2 a legal word.
A bare row-0 main word with the 7 newly columns removed leaves the 8 pre-placed row-0 tiles in
several disconnected fragments, none reaching center.  So we must add a PRE-PLACED connector web
(scores 0) that ties the pre-placed fragments together and reaches (7,7), WITHOUT placing any tile
directly below a newly-placed column at row 1 (that would form an unwanted vertical cross-word on a
newly column at (c,0)-(c,1)).

We solve this connector with CP-SAT (reusing solve.create_board / single_component):
  * every row 0..14 must read as legal words (row automaton over dict words <= HMAX=8);
  * every NON-newly column must read as legal words (column automaton);
  * newly columns get NO column automaton, but we force (c,1) EMPTY for every newly col c so the
    lone newly tile at (c,0) forms no vertical.  Newly columns MAY carry connector tiles at rows
    >=2 (separated from row 0 by the empty (c,1)); in particular this lets the connector reach the
    center (7,7) even though col 7 is a newly column;
  * row-0 pre-placed letters are fixed to the main word; row-0 newly cells are EMPTY in the setup
    (the scored tile only lands in the final turn);
  * (7,7) forced active; single_component from (7,7); bag (reserve=1) and blank limits enforced;
  * minimize the number of active setup cells (smallest, cleanest connector -> fast & easy to read).

We then assemble the FINAL board (setup + the 7 newly row-0 tiles = the full main word on row 0)
and verify it with witness_check (require_center=True).  A passing witness_check is a SOUND LB no
matter how the board was found -- that is the deliverable.

MASK CHOICE / TRADE-OFFS
------------------------
The mask must contain {0,7,14}.  Beyond that we have 4 free newly columns; their placement controls
how fragmented the pre-placed row-0 tiles are and how hard the connector is.  We try a small ordered
list of masks per word (most-valuable-extra-cols first, which captures the x2 bonus at 3/11, then a
"clustered" mask that leaves the pre-placed columns in fewer/larger blocks for an easier connector).
Dropping 3/11 from the mask only costs 27*value(letter) which is tiny vs the x27 main, so when the
preferred mask's connector is infeasible/slow we fall back to easier masks.

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
from solve import create_board, single_component, single_component_flow, limit_letter_count
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B = '15'
HMAX = 8
RESERVE = 1
CENTER = (7, 7)

r = construct_rules('dutch', B)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}

# Connector legality automata, keyed by max word length.  The full <=8 automaton has ~120k edges,
# which makes the CP-SAT board model (15 rows + 15 columns each unrolling that automaton) far too
# heavy to even propagate within any wall.  The CONNECTOR only needs SHORT words: in the SETUP board
# the newly columns are empty, so every row/column run is either a pre-placed row-0 fragment (a short
# substring of the main word) or a connector word we are free to choose -- short words suffice.
# Restricting the connector automaton to length <= maxlen is SOUND (it only shrinks the search; any
# board found is still independently re-verified by witness_check against the FULL dictionary).
_AUT_CACHE = {}
def _aut(maxlen):
    a = _AUT_CACHE.get(maxlen)
    if a is None:
        a = position_independent_row_automaton([w for w in r.words if 1 <= len(w) <= maxlen])
        _AUT_CACHE[maxlen] = a
    return a


def x27_proxy(w):
    return 27 * (sum(val[c] for c in w) + val[w[3]] + val[w[11]]) + 50


def _pre_runs_legal(w, mask):
    """True iff every maximal run of >=2 PRE-PLACED row-0 tiles (the lowercase columns) is a legal
    Dictionary word.  The pre-placed row-0 letters are FIXED substrings of the main word, so for a
    contiguous block of >=2 pre-placed cols their letters must already spell a dict word -- otherwise
    no setup board can be legal for this mask.  (Length-1 pre-placed runs are always legal: single
    letters are injected into the dictionary.)  This is a fast, exact necessary condition that lets
    us skip masks that CP-SAT would only refute slowly.
    """
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
    """Up to `limit` legal 7-col newly masks for w, ranked by the x2-letter bonus they capture.
    All masks contain {0,7,14} (the three x3-WORD cols -> x27).  Among the C(12,4) ways to choose
    the 4 extra newly cols, we keep only those whose PRE-PLACED row-0 runs are all legal words
    (_pre_runs_legal), and rank by the captured x2-letter bonus 27*(val[w[3]] if 3 newly)+(... 11 ...).
    Returns [] when the word admits no legal mask at all (its pre-placed substrings can never spell
    words -- e.g. croquemboucheje) -> the word is skipped.
    """
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


def true_proxy(w, mask):
    """The exact main-word turn score for this mask (x27 word mult on cols 0/7/14, x2 letter on any
    of cols 3/11 that are newly, +50 bingo).  This is what witness_check will compute for an
    empty-column board, so it's the verified TOTAL when the connector adds no scoring words."""
    ms = set(mask)
    wm = 27                                            # cols 0,7,14 always newly -> 3*3*3
    s = 0
    for x in range(W):
        lm = 2 if (x in ms and x in (3, 11)) else 1
        s += val[w[x]] * lm
    return wm * s + 50


def solve_connector(word, mask, cap, rows=9, maxlen=5):
    """CP-SAT: find a legal setup board (a pre-placed connector web) for (word, mask).
    Returns grid (HxW codes, row 0 = full main word) on success, else None.

    Tractability choices (the full <=8-word board model is far too heavy for CP-SAT to even
    propagate):
      * SMALL connector automaton (words <= maxlen, raised to fit the longest pre-placed run) ->
        the row/column DFAs unroll to a few-thousand-edge automaton instead of ~120k (SOUND: only
        the search is shrunk; witness_check re-verifies against the full dictionary);
      * restrict the connector to the top `rows` rows (force the rest empty) -> ~half the board;
      * FEASIBILITY only (no objective) -- any legal connected center-reaching setup is a witness;
      * depth-based single_component (small var domains -> light model).
    """
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]

    # raise maxlen to cover the longest contiguous pre-placed row-0 run (it must be a legal word)
    runlen = 1; cur = 0
    for x in range(W):
        if x in pre:
            cur += 1; runlen = max(runlen, cur)
        else:
            cur = 0
    aut = _aut(max(maxlen, runlen))

    m = cp_model.CpModel(); m.prefix = 'c'
    # EVERY column must read as legal words too -- including newly columns: the connector may place
    # tiles in a newly column at rows >=2 (separated from the empty row-0/row-1 by the forced gap),
    # and any such vertical RUN must still be a legal word.  (Giving newly columns no automaton let
    # the connector spell junk like "tsy" there, which witness_check correctly rejected.)
    cells = create_board(m, [aut] * H, [aut] * W, alphabet_size=len(r.abc))

    # restrict the working area to the top `rows` rows (force the rest empty)
    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)

    # row-0 pre-placed letters fixed; newly row-0 cells EMPTY in the setup
    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)
        m.add(cells[(x, 1)].active == 0)        # no vertical hanging off the (future) newly tile

    # center occupied + single connected component rooted at center.  Use the FLOW encoding: its LP
    # relaxation is tight, so CP-SAT decides feasibility within the wall here (the depth encoding's
    # loose LP did NOT terminate on this board).
    m.add(cells[CENTER].active == 1)
    single_component_flow(m, cells, CENTER)

    # bag: SETUP letters available = full bag minus the 7 newly main-word tiles, minus reserve.
    newly_ct = Counter(mt[c] for c in mask)
    avail = Counter({code: r.counts[code] - newly_ct[code] for code in r.counts})
    limit_letter_count(m, cells, avail)
    m.add(sum(cell.blank for cell in cells.values()) <= r.blank_count)
    total_cap = sum(r.counts.values()) + r.blank_count - RESERVE - 7   # 7 newly tiles reserved off-board
    m.add(sum(cell.active for cell in cells.values()) <= total_cap)

    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '12'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    # extract grid; overwrite row 0 with the FULL main word (newly tiles now placed)
    grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
    for x in range(W):
        grid[0][x] = int(mt[x])
    return grid


def verify(word, mask, grid):
    """Independently verify with witness_check (require_center=True).  Returns (ok, total, rep)."""
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b,
                              claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def run(top_n, cap, out_only_best=True):
    words = sorted((w for w in r.words_str if len(w) == 15), key=x27_proxy, reverse=True)
    best = 0; best_blob = None
    print(f"# N=15 greedy LB: {len(words)} fifteen-letter words; trying top {top_n}, "
          f"CP-SAT cap={cap}s/mask, reserve={RESERVE}", flush=True)
    for w in words[:top_n]:
        proxy = x27_proxy(w)                         # upper bound (both x2 bonuses captured)
        if proxy <= best:
            print(f"# upper-bound proxy of {w} ({proxy}) <= best verified {best}; "
                  f"stopping (ranked desc).", flush=True)
            break
        masks = candidate_masks(w)
        if not masks:
            print(f"  {w} proxy={proxy}: NO LEGAL MASK (pre-placed substrings never spell words)",
                  flush=True)
            continue
        landed = False
        for mask in masks:
            tp = true_proxy(w, mask)
            if tp <= best:                           # this mask (and the rest, ranked) can't beat best
                break
            t0 = time.time()
            grid = solve_connector(w, mask, cap)
            if grid is None:
                print(f"  {w} tp={tp} mask={mask}: no connector ({time.time()-t0:.0f}s)",
                      flush=True)
                continue
            ok, total, rep = verify(w, mask, grid)
            if not ok:
                print(f"  {w} mask={mask}: REJECT {rep.get('fail')}", flush=True)
                continue
            turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(w))
            mark = "NEWBEST" if total > best else "ok"
            print(f"  [{mark}] {w} tp={tp} mask={mask} -> VERIFIED TOTAL={total} "
                  f"({time.time()-t0:.0f}s)", flush=True)
            if total > best:
                best = total
                best_blob = {'board': B, 'main_word': w, 'turn_str': turn,
                             'require_center': True, 'claimed_total': total, 'grid': grid}
                path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
                json.dump(best_blob, open(path, 'w'))
                print(f"      saved {path}", flush=True)
            landed = True
            break          # first verified mask for this word is enough; move to next word
        if not landed:
            print(f"  {w} proxy={proxy}: no mask landed", flush=True)
    print(f"# DONE best verified N=15 LB = {best} ({best_blob['main_word'] if best_blob else None})",
          flush=True)
    return best, best_blob


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--cap', type=float, default=40.0, help='CP-SAT wall per (word,mask)')
    a = ap.parse_args()
    run(a.top, a.cap)
