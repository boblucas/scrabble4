"""N=15 per-(word,mask) CERTIFICATION -- step 3 toward proving the N=15 optimum.

For a threat word, prove its TRUE maximum single-turn total <= FLOOR (1952), or find a board that
beats the floor (a NEW verified LB).

THE CERTIFICATION MODEL (CP-SAT, MAXIMIZE total added vertical bonus, solved to OPTIMALITY)
------------------------------------------------------------------------------------------
For a fixed (word, mask) the main-word score is the constant true_main(word, mask).  The only thing
that varies is the added vertical bonus.  We build a CP-SAT model of the SETUP board (identical
skeleton to n15_push_lb.solve_push) that maximizes the EXACT added vertical bonus, but -- crucially
for a SOUND UPPER BOUND -- we allow verticals on EVERY newly column (not just the TWS cols), to full
depth HMAX=8, with the full connector dictionary.  If CP-SAT returns status OPTIMAL, then
    true_max(word, mask) = true_main(word, mask) + objective_value
is PROVEN (the model exactly captures rules: bag w/ reserve=1, connectivity through center, all
runs legal words len<=8).  A TIMEOUT/UNKNOWN status proves nothing -> OPEN.

  * Every column that does NOT host a table-controlled vertical gets the full column automaton (so
    its runs are legal words).  Each newly column c OPTIONALLY hosts a vertical: an
    add_allowed_assignments table over the tail cells (c,1)..(c,HMAX-1) forces `word[c]+tail` to be a
    legal dict word len 2..8 (FIXED top letter), OR the column empty below row 0.  Below the table
    rows the column is forced empty.  No column automaton on a vertical column (the table is its
    legality; the bare tail must not be forced to be a standalone word).
  * objective = sum over newly cols c of WM[c]*(LM[c]*val(word[c])*has_vert_c + sum tail values_c)
    -- the EXACT added vertical bonus per witness_check/get_word_score.  Blanks forbidden on scored
    tail cells (blanks score 0; never help a scored tile) so tail value = letter value.
  * row-0 pre-placed letters fixed; row-0 newly cells empty in setup; center (7,7) active +
    single_component_flow; bag = full minus the newly main tiles minus reserve=1.

A board that beats the floor is re-verified end-to-end by witness_check (require_center=True) and
saved as a new N15_best_<total>.json LB.

We process masks of size 7 (bingo, the dominant case: keeps +50 and maximizes the main).  A
non-bingo mask loses 50 from the main, so true_main is >= 50 lower; we ALSO certify the best-main
(size 7) mask which dominates.  For completeness the script certifies ALL legal size-7 masks of the
word (the only masks that can realize the +50 in the threat UB); if every one is OPTIMAL<=floor the
word is CERTIFIED for the bingo case.  (Soundness note in the report: non-bingo masks have main 50
lower and the same vertical structure, so their UB is also < the bingo UB we certify; a fully
rigorous closure of non-bingo masks is discussed in the report.)

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
WM = np.array(r.word_multiplier)[0]
LM = np.array(r.letter_multiplier)[0]
TWS = [c for c in range(W) if WM[c] == 3]

# Full connector automaton: words len 1..HMAX (the only runs that can appear in a setup board where
# newly columns are empty at row 0/1; verticals are <=HMAX, connector words are <=HMAX).
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
    ms = set(mask)
    s = 0
    for x in range(W):
        lm = 2 if (x in ms and x in (3, 11)) else 1
        s += val[w[x]] * lm
    return 27 * s + 50


# Exact max single-column vertical bonus per (col, top-letter), used for the SOUND per-mask analytic
# UB pre-filter (avoids a CP-SAT call when a mask's optimistic ceiling already <= floor).
_TAILMAX = {}
for _word in r.words_str:
    if 2 <= len(_word) <= HMAX:
        _f = _word[0]
        _tv = sum(val[c] for c in _word[1:])
        if _tv > _TAILMAX.get(_f, -1):
            _TAILMAX[_f] = _tv


def best_vert_bonus(c, L):
    """Exact max ADDED single-column vertical bonus at column c, top letter L (0 if no vertical)."""
    if L not in _TAILMAX:
        return 0
    return int(WM[c]) * (int(LM[c]) * val[L] + _TAILMAX[L])


def mask_UB(w, mask):
    """SOUND per-mask upper bound = true_main(mask) + sum of best per-column vertical bonus over the
    mask's columns (verticals occur only at newly cols).  Per-column exact, ignores bag/connectivity
    -> over-estimate.  If <= floor, the mask's true max is provably <= floor (no CP-SAT needed)."""
    return true_main(w, mask) + sum(best_vert_bonus(c, w[c]) for c in mask)


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


def legal_masks(w):
    """ALL legal size-7 (bingo) newly masks for w (each contains {0,7,14})."""
    free = [c for c in range(W) if c not in (0, 7, 14)]
    out = []
    for extra in combinations(free, 4):
        mask = tuple(sorted((0, 7, 14) + extra))
        if _pre_runs_legal(w, mask):
            out.append(mask)
    return out


def vert_tail_table(top_letter, Ltail):
    """Tail-cell table for verticals `top_letter+tail`, len 2..HMAX, over Ltail tail cells; plus the
    all-empty row (no vertical)."""
    cba = r.alphabet.cba
    rows = [[0] * Ltail]
    for word in r.words_str:
        if 2 <= len(word) <= HMAX and word[0] == top_letter:
            tail = [cba[c] for c in word[1:]]
            if len(tail) > Ltail:
                continue
            rows.append(tail + [0] * (Ltail - len(tail)))
    return np.array(rows, dtype=int)


def certify_mask(word, mask, cap, rows=H, maxlen=HMAX, verbose=False):
    """Maximize the added vertical bonus for (word,mask) to OPTIMALITY.
    Returns (status_str, objective, grid).  status_str in {OPTIMAL, FEASIBLE, TIMEOUT, INFEAS}.
    grid is the best board found (row0=full main) if any feasible solution, else None.
    Verticals allowed on ALL newly columns (sound UB)."""
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
    # vertical columns = ALL newly columns (every newly col may host a vertical -> sound UB)
    vert_cols = sorted(newly)
    col_auts = [None if x in vert_cols else aut for x in range(W)]
    cells = create_board(m, [aut] * H, col_auts, alphabet_size=len(r.abc))

    for y in range(rows, H):
        for x in range(W):
            m.add(cells[(x, y)].active == 0)

    for x in pre:
        m.add(cells[(x, 0)].letter[mt[x]] == 1)
    for x in newly:
        m.add(cells[(x, 0)].active == 0)

    Ltail = min(HMAX - 1, rows - 1)
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]
    obj_terms = []
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

    m.maximize(sum(obj_terms))

    s = cp_model.CpSolver()
    s.parameters.num_search_workers = int(os.environ.get('CPSAT_WORKERS', '12'))
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(m)
    statusmap = {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
                 cp_model.INFEASIBLE: 'INFEAS', cp_model.UNKNOWN: 'TIMEOUT',
                 cp_model.MODEL_INVALID: 'INVALID'}
    sst = statusmap.get(st, str(st))
    grid = None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
        for x in range(W):
            grid[0][x] = int(mt[x])
        return sst, int(s.objective_value), grid
    if st == cp_model.INFEASIBLE:
        return 'INFEAS', None, None
    return sst, None, None


def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = construct_rules('dutch', B)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def certify_word(word, floor, cap, rows=H):
    """Certify a single word across ALL its legal size-7 masks.  Returns a dict verdict."""
    masks = legal_masks(word)
    result = {'word': word, 'n_masks': len(masks), 'masks': [], 'verdict': None,
              'best_total_found': 0, 'best_grid': None, 'best_mask': None}
    if not masks:
        result['verdict'] = 'NO-LEGAL-MASK'
        return result
    all_certified = True
    for mask in masks:
        tm = true_main(word, mask)
        # SOUND analytic pre-filter: if the per-mask optimistic ceiling already <= floor, this mask's
        # true max is provably <= floor -- CERTIFIED without any CP-SAT call.
        mub = mask_UB(word, mask)
        if mub <= floor:
            result['masks'].append({'mask': mask, 'true_main': tm, 'status': 'ANALYTIC',
                                    'obj': None, 'max_total': None, 'mask_UB': mub,
                                    'note': 'CERTIFIED-LE-FLOOR(analytic)', 'secs': 0.0})
            continue
        t0 = time.time()
        sst, obj, grid = certify_mask(word, mask, cap, rows=rows)
        dt = time.time() - t0
        entry = {'mask': mask, 'true_main': tm, 'status': sst, 'obj': obj,
                 'max_total': (tm + obj) if obj is not None else None, 'secs': round(dt, 1)}
        if grid is not None:
            ok, total, rep = verify(word, mask, grid)
            entry['verified_total'] = total if ok else None
            entry['verify_ok'] = ok
            if ok and total > result['best_total_found']:
                result['best_total_found'] = total
                result['best_grid'] = grid
                result['best_mask'] = mask
        if sst == 'OPTIMAL':
            mt = tm + obj
            if mt > floor:
                entry['note'] = 'OPTIMAL-EXCEEDS-FLOOR'
            else:
                entry['note'] = 'CERTIFIED-LE-FLOOR'
        elif sst == 'INFEAS':
            entry['note'] = 'mask-infeasible(<=floor trivially)'
        else:
            entry['note'] = 'OPEN'
            all_certified = False
        result['masks'].append(entry)

    # word verdict
    exceeds = any(e.get('max_total') is not None and e['status'] == 'OPTIMAL'
                  and e['max_total'] > floor for e in result['masks'])
    if exceeds:
        result['verdict'] = 'EXCEEDS-FLOOR'
    elif all_certified:
        result['verdict'] = 'CERTIFIED-LE-FLOOR'
    else:
        result['verdict'] = 'OPEN'
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--floor', type=int, default=1952)
    ap.add_argument('--cap', type=float, default=120.0, help='CP-SAT wall per (word,mask)')
    ap.add_argument('--rows', type=int, default=H, help='working rows (vertical reach, default full)')
    ap.add_argument('--word', type=str, default=None)
    ap.add_argument('--from-threats', action='store_true',
                    help='process all threat words from n15_threats.jsonl by descending UB')
    ap.add_argument('--limit', type=int, default=0, help='with --from-threats: cap #words (0=all)')
    ap.add_argument('--skip', type=int, default=0)
    ap.add_argument('--out', type=str, default=f'{ROOT}/experiments/results/n15_certify.jsonl')
    a = ap.parse_args()

    if a.word:
        res = certify_word(a.word, a.floor, a.cap, rows=a.rows)
        print(json.dumps(res, default=str, indent=2), flush=True)
        return

    if a.from_threats:
        threats = [json.loads(l) for l in open(f'{ROOT}/experiments/results/n15_threats.jsonl')]
        threats.sort(key=lambda x: -x['UB'])
        threats = threats[a.skip:]
        if a.limit:
            threats = threats[:a.limit]
        floor = a.floor
        outf = open(a.out, 'a')
        for t in threats:
            w = t['word']
            print(f"\n=== {w}  UB={t['UB']}  (floor={floor}) ===", flush=True)
            res = certify_word(w, floor, a.cap, rows=a.rows)
            res['UB'] = t['UB']
            for e in res['masks']:
                print(f"   mask={e['mask']} main={e['true_main']} {e['status']} "
                      f"obj={e['obj']} max_total={e['max_total']} {e['note']} ({e['secs']}s)",
                      flush=True)
            print(f"   VERDICT {w}: {res['verdict']}  best_found={res['best_total_found']}",
                  flush=True)
            if res['best_total_found'] > floor and res['best_grid'] is not None:
                total = res['best_total_found']; mask = res['best_mask']
                turn = ''.join(c.upper() if i in set(mask) else c.lower()
                               for i, c in enumerate(w))
                blob = {'board': B, 'main_word': w, 'turn_str': turn, 'require_center': True,
                        'claimed_total': total, 'grid': res['best_grid']}
                path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
                json.dump(blob, open(path, 'w'))
                print(f"   *** NEW LB {total} saved {path} -- RAISE FLOOR & re-run threats ***",
                      flush=True)
                floor = total
            outf.write(json.dumps({k: v for k, v in res.items() if k != 'best_grid'},
                                  default=str) + '\n')
            outf.flush()
        outf.close()
        print(f"\n# certify pass done; results appended to {a.out}", flush=True)


if __name__ == '__main__':
    main()
