"""N=15 LB finder for the BIGGER dictionary (data/words/dutch_bigger_le15).

SELF-CONTAINED adaptation of experiments/n15_greedy_lb.py + n15_push_lb.py for the much larger
`dutch_bigger` lexicon.  It does NOT import or mutate the dutch run's files; it only reuses the
shared, read-only primitives (scrabble.construct_rules, dawg, solve, witness_check).

THE MODEL (see experiments/MAXTURN_HANDOFF_V2.md sections 0/6/9 -- identical to the dutch run):
  * a high-value 15-letter MAIN word on row 0, 7 newly-placed tiles on a column mask that contains
    the three x3-WORD cols {0,7,14} (-> x27 word multiplier) and ideally the x2-LETTER cols {3,11};
    7 newly tiles => bingo +50.  The newly COLUMNS are otherwise empty (no verticals).
  * a PRE-PLACED connector web (scores 0) ties the disconnected pre-placed row-0 fragments together
    and reaches center (7,7), keeping the SETUP board ONE 4-connected component, with no tile
    directly below a newly col (no unwanted vertical).
  * PHASE 2 (--push): additionally hang the best legal vertical cross-words off the three x3 cols
    {0,7,14} to ADD score, maximised by CP-SAT.

Soundness: every board is re-verified end-to-end by witness_check (require_center=True, reserve=1).
A passing witness_check is a SOUND LB no matter how the board was found.

DICTIONARY: data/words/dutch_bigger_le15 (the 7.58M-word dutch_bigger pre-filtered to words of
length 1..15 -- words >15 are unplaceable on a 15x15 board, so dropping them removes no legal play).
Language stays 'dutch' (correct tile letters/values/bag/blanks); only the word list changes.

Single sequential process (process-kill safety: no parallelism, no group kills).
Output: experiments/results/turns/N15_bigger_best_<total>.json (DISTINCT from the dutch run's
N15_best_<total>.json so the two agents never collide).
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
WORD_FILE = 'data/words/dutch_bigger_le15'
os.environ.setdefault('CPSAT_WORKERS', '6')   # shared box: be polite (HARD CONSTRAINT from the brief)

r = construct_rules('dutch', B, word_file=WORD_FILE)
W = H = r.W
val = {chr(96 + i): r.scores[i] for i in range(1, 27)}
WM = np.array(r.word_multiplier)[0]
LM = np.array(r.letter_multiplier)[0]
TWS = [c for c in range(W) if WM[c] == 3]
DLS = [c for c in range(W) if LM[c] == 2]
assert TWS == [0, 7, 14] and DLS == [3, 11], (TWS, DLS)
print(f"# dutch_bigger N=15: {len(r.words_str)} words; "
      f"{len([w for w in r.words_str if len(w)==15])} fifteen-letter words", flush=True)

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
    """Exact main-word turn score (x27 word mult; x2 letter on newly 3/11; +50 bingo)."""
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


# Precompute short words (len 2..HMAX) by first letter ONCE -> O(words-with-that-letter) tables
# (avoids re-scanning the 4.1M-word lexicon per TWS col per mask).
from collections import defaultdict as _dd
_SHORT_BY_FIRST = _dd(list)
_cba0 = r.alphabet.cba
for _w in r.words_str:
    if 2 <= len(_w) <= HMAX:
        _SHORT_BY_FIRST[_w[0]].append([_cba0[c] for c in _w[1:]])


def vert_tail_table(top_letter, Ltail):
    """Tail-cell table for verticals `top_letter+tail` (len 2..HMAX) over Ltail tail cells, plus the
    all-empty row (no vertical)."""
    rows = [[0] * Ltail]
    for tail in _SHORT_BY_FIRST.get(top_letter, ()):
        if len(tail) > Ltail:
            continue
        rows.append(tail + [0] * (Ltail - len(tail)))
    return np.array(rows, dtype=int)


def solve_board(word, mask, cap, rows=9, maxlen=5, push=False):
    """CP-SAT: find a legal connected center-reaching SETUP board for (word, mask).
    push=False: feasibility only (connector; empty newly columns).
    push=True : maximize added vertical bonus on the three x3 (TWS) cols {0,7,14}.
    Returns (grid, objective) on success, else (None, 0).  grid row 0 = full main word.
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

    vert_cols = [c for c in newly if c in TWS] if push else []

    m = cp_model.CpModel(); m.prefix = 'b'
    col_auts = [None if x in vert_cols else aut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))

    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)

    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)

    L = HMAX - 1
    Ltail = min(L, rows - 1)
    # non-vertical newly cols stay empty below row 0 (no vertical there)
    for c in newly:
        if c not in vert_cols:
            m.add(cells[(c, 1)].active == 0)

    obj_terms = []
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]
    for c in vert_cols:
        top_letter = word[c]
        table = vert_tail_table(top_letter, Ltail)
        tail_vars = [cells[(c, y)].letter_int for y in range(1, 1 + Ltail)]
        m.add_allowed_assignments(tail_vars, table)
        for y in range(1 + Ltail, H):
            m.add(cells[(c, y)].active == 0)
        has_vert = cells[(c, 1)].active
        obj_terms.append(int(WM[c]) * int(LM[c]) * int(val[top_letter]) * has_vert)
        for y in range(1, 1 + Ltail):
            cell = cells[(c, y)]
            m.add(cell.blank == 0)
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

    if push and obj_terms:
        m.maximize(sum(obj_terms))

    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '6'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, 0
    grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
    for x in range(W):
        grid[0][x] = int(mt[x])
    obj = int(s.objective_value) if (push and obj_terms) else 0
    return grid, obj


def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B, word_file=WORD_FILE)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def save(word, mask, grid, total):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    blob = {'board': B, 'main_word': word, 'turn_str': turn, 'require_center': True,
            'claimed_total': total, 'grid': grid}
    path = f'{ROOT}/experiments/results/turns/N15_bigger_best_{total}.json'
    json.dump(blob, open(path, 'w'))
    print(f"      saved {path}", flush=True)


def run(top_n, cap, push, rows, baseline):
    words = sorted((w for w in r.words_str if len(w) == 15), key=x27_proxy, reverse=True)
    best = baseline; best_blob = None
    print(f"# N=15 bigger LB ({'PUSH' if push else 'connector'}): baseline={baseline}; "
          f"top {top_n}; cap={cap}s/mask, rows={rows}, reserve={RESERVE}, "
          f"workers={os.environ.get('CPSAT_WORKERS')}", flush=True)
    for w in words[:top_n]:
        proxy = x27_proxy(w)
        if not push and proxy <= best:
            print(f"# proxy of {w} ({proxy}) <= best {best}; stopping (ranked desc).", flush=True)
            break
        masks = candidate_masks(w)
        if not masks:
            print(f"  {w} proxy={proxy}: NO LEGAL MASK", flush=True)
            continue
        landed = False
        for mask in masks:
            tm = true_main(w, mask)
            if not push and tm <= best:
                break
            t0 = time.time()
            grid, obj = solve_board(w, mask, cap, rows=rows, push=push)
            if grid is None:
                print(f"  {w} main={tm} mask={mask}: no board ({time.time()-t0:.0f}s)", flush=True)
                continue
            ok, total, rep = verify(w, mask, grid)
            if not ok:
                print(f"  {w} mask={mask}: REJECT {rep.get('fail')} (obj={obj})", flush=True)
                continue
            mark = "NEWBEST" if total > best else "ok"
            print(f"  [{mark}] {w} main={tm} mask={mask} obj+{obj} -> VERIFIED TOTAL={total} "
                  f"verts={rep.get('verticals', {})} ({time.time()-t0:.0f}s)", flush=True)
            if total > best:
                best = total
                turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(w))
                best_blob = {'board': B, 'main_word': w, 'turn_str': turn, 'require_center': True,
                             'claimed_total': total, 'grid': grid}
                save(w, mask, grid, total)
            landed = True
            break    # first verified mask per word is enough
        if not landed:
            print(f"  {w} proxy={proxy}: no mask landed", flush=True)
    print(f"# DONE best verified N=15 bigger LB = {best} "
          f"({best_blob['main_word'] if best_blob else 'baseline'})", flush=True)
    return best, best_blob


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=8)
    ap.add_argument('--cap', type=float, default=60.0, help='CP-SAT wall per (word,mask)')
    ap.add_argument('--rows', type=int, default=9, help='working rows (vertical reach)')
    ap.add_argument('--push', action='store_true', help='phase 2: add x3-col verticals (maximize)')
    ap.add_argument('--baseline', type=int, default=0)
    ap.add_argument('--word', type=str, default=None, help='run a single specific word')
    a = ap.parse_args()
    if a.word:
        masks = candidate_masks(a.word)
        print(f"# single word {a.word} proxy={x27_proxy(a.word)} masks={masks}", flush=True)
        b = a.baseline
        for mask in masks:
            t0 = time.time()
            grid, obj = solve_board(a.word, mask, a.cap, rows=a.rows, push=a.push)
            if grid is None:
                print(f"  mask={mask}: no board ({time.time()-t0:.0f}s)", flush=True)
                continue
            ok, total, rep = verify(a.word, mask, grid)
            print(f"  mask={mask} obj+{obj} ok={ok} total={total} verts={rep.get('verticals')} "
                  f"({time.time()-t0:.0f}s)", flush=True)
            if ok and total > b:
                b = total
                save(a.word, mask, grid, total)
            break
        print(f"# DONE single-word best = {b}", flush=True)
    else:
        run(a.top, a.cap, a.push, a.rows, a.baseline)
