"""N=15 INCUMBENT-IMPROVER -- a generalizable, dict-agnostic directed search that hunts a
VERIFIED board scoring higher than a given incumbent (default the 1955 geschenkcheques board).

WHY (the exhaustive maximize drowns)
------------------------------------
The exact full-turn model (main word row 0, 7 newly tiles on a mask containing the three x3-WORD
cols {0,7,14}, an OPTIONAL legal vertical `main[c]+tail` on EVERY newly column, a pre-placed
connector web making the SETUP board one 4-connected component through center (7,7), bag-reserve=1)
is built correctly by `n15_push_lb_v2.solve_push` -- but its CP-SAT `maximize` never closes on a
full N=15 mask (the bridge-fill explosion swamps it; it only ever surfaces ~3-vertical ~1955
boards).  This module attacks the SAME model with DIRECTED incumbent-improvement engines that find
a high-scoring leaf without proving the max:

  * TARGET (feasibility-with-target):  replace `maximize(obj)` with the CONSTRAINT `obj >= T`, and
    ask CP-SAT only for a FEASIBLE board.  Finding *a* board over a threshold is far easier than
    proving the optimum; we ratchet T up (T = best+1) every time one is found.  Optionally warm-
    started from a known board's cell assignment (a CP-SAT solution HINT), so the solver starts in
    the incumbent's basin and looks for the nearby +1 improvement.

  * LNS (large-neighbourhood search):  FREEZE most columns to an incumbent board's values (hard
    equality on the frozen newly-column verticals) and re-optimise only a small set of "thawed"
    newly columns + the whole connector, demanding `obj >= incumbent+1`.  The frozen part keeps the
    subproblem tiny and feasible; the thawed columns are free to find a better vertical mix.  This
    is the reusable core engine -- parameterised purely by (word, mask, which columns to thaw).

Everything is pulled from `construct_rules` / the shared v2 model builder -- NO hard-coded lexicon
facts.  Any board found is RE-VERIFIED end to end by witness_check.check_witness(require_center=True,
reserve=1); a passing witness is the SOLE authority and the deliverable.  We save every new best to
experiments/results/turns/N15_best_<total>.json.

GENERALITY
----------
The engines take (word, mask) and operate over the v2 model, which itself derives all dictionary /
multiplier / bag data from `construct_rules('dutch', board)`.  Point it at any 15-letter word, any
legal mask, any board incumbent; the TARGET and LNS loops are word/mask/dict agnostic.  (The board
size B and HMAX are the v2 module's; switching board only needs the v2 constants.)

Process-kill safety: each worker is a single Cp_model.Solve in this process (no child processes,
no group kills).  A portfolio runs several (word,mask,engine) configs SEQUENTIALLY here; to run
several concurrently, launch several `--word/--mask/--engine` invocations as separate processes and
let _save's highest-total file be the shared global best (idempotent: each writes its own total).
"""
import sys, os, json, time, argparse, random
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
import numpy as np
from collections import Counter
from ortools.sat.python import cp_model

import n15_push_lb_v2 as V               # the canonical correct full-turn model (verticals on ALL cols)
from solve import create_board, single_component_flow, limit_letter_count
import witness_check as wc

ROOT = '/home/bob/programming/scrabble4'
B, HMAX, RESERVE, CENTER = V.B, V.HMAX, V.RESERVE, V.CENTER
r, W, H, val = V.r, V.W, V.H, V.val
WM, LM, TWS = V.WM, V.LM, V.TWS


# ----------------------------------------------------------------------------------------------
# Model builder: identical to v2.solve_push, but returns the model + handles so the caller can
# choose maximize / target-constraint / LNS-freeze and inject a warm-start hint.  (Kept here, not
# in v2, because v2 must stay the audited maximize reference.)
# ----------------------------------------------------------------------------------------------
def build_model(word, mask, rows=9, maxlen=5):
    """Build the full-turn CP-SAT model for (word, mask).  Returns a dict with the model, the cells,
    the per-newly-column tail vars, the exact added-vertical-score `obj` LinearExpr, and the layout
    metadata.  No objective / target is set -- the caller decides."""
    mt = r.alphabet.to_tup(word)
    newly = set(mask)
    pre = [x for x in range(W) if x not in newly]

    runlen = 1; cur = 0
    for x in range(W):
        if x in pre:
            cur += 1; runlen = max(runlen, cur)
        else:
            cur = 0
    aut = V._aut(max(maxlen, runlen))

    m = cp_model.CpModel(); m.prefix = 'inc'
    col_auts = [None if x in newly else aut for x in range(W)]
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
    val_arr = [0] + [int(r.scores[code]) for code in range(1, len(r.abc) + 1)]
    obj_terms = []
    tail_vars_by_col = {}
    for c in newly:
        top_letter = word[c]
        table = V.vert_table(top_letter, Ltail)
        tail_vars = [cells[(c, y)].letter_int for y in range(1, 1 + Ltail)]
        tail_vars_by_col[c] = tail_vars
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

    obj = sum(obj_terms)
    return dict(m=m, cells=cells, obj=obj, mt=mt, newly=newly, pre=pre,
                Ltail=Ltail, tail_vars_by_col=tail_vars_by_col, rows=rows)


def _grid_from_solver(s, cells, mt):
    grid = [[int(s.value(cells[(x, y)].letter_int)) for x in range(W)] for y in range(H)]
    for x in range(W):
        grid[0][x] = int(mt[x])
    return grid


def add_hint(mh, cells, grid, Ltail, newly):
    """Warm-start: hint every modelled cell (rows 0..Ltail for newly cols, the working rows for the
    connector) to the values in `grid`.  Hints are advisory (CP-SAT may ignore/repair), so this is
    sound -- it only steers the search toward the incumbent's basin.  We hint letter_int and active."""
    for (x, y), cell in cells.items():
        if y == 0:
            continue                                   # row-0 is fixed by constraints already
        g = grid[y][x] if y < len(grid) else 0
        mh.add_hint(cell.active, 1 if g != 0 else 0)
        mh.add_hint(cell.letter_int, g)


# ----------------------------------------------------------------------------------------------
# Verification (the only authority) + persistence
# ----------------------------------------------------------------------------------------------
def verify(word, mask, grid):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    mask_b = [turn[x].isupper() for x in range(W)]
    r2 = V.construct_rules('dutch', B)
    blank, info = wc.derive_blanks(r2, grid, mask_b, W, H)
    if blank is None:
        return False, None, {'fail': f'blank: {info}'}
    ok, rep = wc.check_witness(r2, W, H, grid, blank, mask_b, claimed_total=None, require_center=True)
    return ok, (int(rep['total']) if ok else None), rep


def save(word, mask, grid, total):
    turn = ''.join(c.upper() if i in set(mask) else c.lower() for i, c in enumerate(word))
    blob = {'board': B, 'main_word': word, 'turn_str': turn, 'require_center': True,
            'claimed_total': total, 'grid': grid}
    path = f'{ROOT}/experiments/results/turns/N15_best_{total}.json'
    json.dump(blob, open(path, 'w'))
    print(f"      saved {path}", flush=True)
    return path


def load_incumbent_total(word, mask, blob_path):
    """Read an incumbent board JSON, extract its added-vertical score for THIS (word,mask) layout so
    LNS / target can ratchet from it.  Returns (grid, vert_obj, total) or (None, baseline, baseline)
    if the blob doesn't match this word/mask (then we improve over the numeric baseline only)."""
    if not blob_path or not os.path.exists(blob_path):
        return None, None, None
    blob = json.load(open(blob_path))
    grid = blob['grid']
    total = int(blob.get('claimed_total', 0))
    main = V.true_main(word, mask)
    return grid, total - main, total


# ----------------------------------------------------------------------------------------------
# ENGINE 1: target / feasibility-with-target (optionally warm-started)
# ----------------------------------------------------------------------------------------------
def engine_target(word, mask, target_obj, cap, rows, hint_grid=None, workers=12):
    """Find ANY legal connected center-reaching board whose added vertical score (obj) >= target_obj.
    Returns (grid, obj, status) or (None, 0, status)."""
    M = build_model(word, mask, rows=rows)
    M['m'].add(M['obj'] >= int(target_obj))
    if hint_grid is not None:
        add_hint(M['m'], M['cells'], hint_grid, M['Ltail'], M['newly'])
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = workers
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(M['m'])
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, 0, st
    grid = _grid_from_solver(s, M['cells'], M['mt'])
    return grid, int(s.value(M['obj'])), st


# ----------------------------------------------------------------------------------------------
# ENGINE 2: LNS -- freeze a set of columns to an incumbent, re-optimise the thawed ones
# ----------------------------------------------------------------------------------------------
def engine_lns_step(word, mask, base_grid, base_obj, thaw_cols, cap, rows, workers=12,
                    maximize=True):
    """One LNS move: FREEZE every newly column NOT in `thaw_cols` to its incumbent tail (and freeze
    the connector cells that the incumbent uses outside the thawed columns is NOT done -- the
    connector stays free so re-wiring can accommodate the new verticals), then either MAXIMIZE the
    objective (default) or just require obj >= base_obj+1.  Returns (grid, obj, status)."""
    M = build_model(word, mask, rows=rows)
    cells = M['cells']
    Ltail = M['Ltail']
    # FREEZE the tails of the non-thawed newly columns to the incumbent's values (hard equality).
    for c in M['newly']:
        if c in thaw_cols:
            continue
        for y in range(1, 1 + Ltail):
            g = base_grid[y][c] if y < len(base_grid) else 0
            if g != 0:
                M['m'].add(cells[(c, y)].letter[g] == 1)
            else:
                M['m'].add(cells[(c, y)].active == 0)
    if maximize:
        M['m'].add(M['obj'] >= int(base_obj))          # never accept worse
        M['m'].maximize(M['obj'])
    else:
        M['m'].add(M['obj'] >= int(base_obj) + 1)
    add_hint(M['m'], cells, base_grid, Ltail, M['newly'])
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = workers
    s.parameters.max_time_in_seconds = cap
    st = s.Solve(M['m'])
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, 0, st
    grid = _grid_from_solver(s, cells, M['mt'])
    return grid, int(s.value(M['obj'])), st


# ----------------------------------------------------------------------------------------------
# Drivers
# ----------------------------------------------------------------------------------------------
def run_target(word, mask, best, cap, rows, hint_grid, workers, ratchets=6):
    """Ratchet the target up from best+1.  best is the TOTAL; obj target = best+1 - main."""
    main = V.true_main(word, mask)
    cur_best = best
    cur_grid = hint_grid
    for it in range(ratchets):
        target_obj = (cur_best + 1) - main
        ceil = V._mask_ceiling(word, mask)
        if cur_best + 1 > ceil:
            print(f"  target {cur_best+1} > mask ceiling {ceil}; stop", flush=True)
            break
        t0 = time.time()
        grid, obj, st = engine_target(word, mask, target_obj, cap, rows,
                                      hint_grid=cur_grid, workers=workers)
        if grid is None:
            print(f"  [target it{it}] {word} mask={mask} need obj>={target_obj} "
                  f"(total>={cur_best+1}): {s_name(st)} ({time.time()-t0:.0f}s)", flush=True)
            break
        ok, total, rep = verify(word, mask, grid)
        if not ok:
            print(f"  [target it{it}] REJECT {rep.get('fail')} (obj={obj})", flush=True)
            break
        print(f"  [target it{it} NEWBEST] {word} mask={mask} obj+{obj} -> VERIFIED TOTAL={total} "
              f"verts={rep.get('verticals')} ({time.time()-t0:.0f}s)", flush=True)
        if total > cur_best:
            cur_best = total; cur_grid = grid
            save(word, mask, grid, total)
        else:
            break
    return cur_best, cur_grid


def run_lns(word, mask, best, base_grid, cap, rows, workers, rounds=20, thaw_k=2, seed=0):
    """Repeatedly thaw a small random set of newly columns and re-optimise.  Keeps the global best."""
    rng = random.Random(seed)
    main = V.true_main(word, mask)
    cur_best = best
    cur_grid = base_grid
    cols = sorted(mask)
    cur_obj = cur_best - main
    for rd in range(rounds):
        thaw = set(rng.sample(cols, min(thaw_k, len(cols))))
        t0 = time.time()
        grid, obj, st = engine_lns_step(word, mask, cur_grid, cur_obj, thaw, cap, rows,
                                        workers=workers, maximize=True)
        if grid is None:
            print(f"  [lns r{rd}] thaw={sorted(thaw)}: {s_name(st)} ({time.time()-t0:.0f}s)",
                  flush=True)
            continue
        ok, total, rep = verify(word, mask, grid)
        if not ok:
            print(f"  [lns r{rd}] thaw={sorted(thaw)} REJECT {rep.get('fail')}", flush=True)
            continue
        mark = "NEWBEST" if total > cur_best else "ok"
        print(f"  [lns r{rd} {mark}] thaw={sorted(thaw)} obj+{obj} total={total} "
              f"verts={rep.get('verticals')} ({time.time()-t0:.0f}s)", flush=True)
        if total > cur_best:
            cur_best = total; cur_grid = grid; cur_obj = total - main
            save(word, mask, grid, total)
    return cur_best, cur_grid


def s_name(st):
    return {cp_model.OPTIMAL: 'OPTIMAL', cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE', cp_model.UNKNOWN: 'UNKNOWN/TO'}.get(st, str(st))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--word', required=True)
    ap.add_argument('--mask', default=None, help='comma cols e.g. 0,3,7,8,11,12,14 (default: best candidate mask)')
    ap.add_argument('--engine', choices=['target', 'lns', 'maximize'], default='target')
    ap.add_argument('--baseline', type=int, default=1955)
    ap.add_argument('--cap', type=float, default=120.0)
    ap.add_argument('--rows', type=int, default=9)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--seed-board', default=None, help='incumbent board JSON to warm-start / LNS from')
    ap.add_argument('--rounds', type=int, default=20)
    ap.add_argument('--thaw-k', type=int, default=2)
    ap.add_argument('--ratchets', type=int, default=6)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()

    mask = tuple(int(c) for c in a.mask.split(',')) if a.mask else V.candidate_masks(a.word, 1)[0]
    print(f"# INCUMBENT {a.engine}: word={a.word} mask={mask} main={V.true_main(a.word, mask)} "
          f"baseline={a.baseline} cap={a.cap} rows={a.rows} workers={a.workers}", flush=True)

    seed_grid, seed_obj, seed_total = (None, None, None)
    if a.seed_board:
        seed_grid, seed_obj, seed_total = load_incumbent_total(a.word, mask, a.seed_board)
        print(f"# seed board total={seed_total} obj={seed_obj}", flush=True)

    if a.engine == 'target':
        run_target(a.word, mask, a.baseline, a.cap, a.rows, seed_grid, a.workers, ratchets=a.ratchets)
    elif a.engine == 'lns':
        if seed_grid is None:
            print("# lns needs --seed-board (an incumbent for THIS word/mask)", flush=True)
            sys.exit(1)
        run_lns(a.word, mask, max(a.baseline, seed_total or 0), seed_grid, a.cap, a.rows,
                a.workers, rounds=a.rounds, thaw_k=a.thaw_k, seed=a.seed)
    else:  # maximize -- delegate to v2 reference
        V.run([a.word], a.cap, a.baseline, a.rows, all_masks=False, mask_limit=8)
