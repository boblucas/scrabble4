"""Standalone INDEPENDENT witness checker for max-turn claims (the canonical checker going forward).

A witness = a final board (after the scoring turn): row 0 holds the full main word (pre-placed
lowercase cells + newly-placed cells), scoring verticals hang below newly-placed row-0 cells,
bridge/connector tiles elsewhere.  This module re-validates EVERYTHING from first principles,
sharing no code with the solvers (only scrabble.get_word_score for the rules' scoring semantics
and connectivity.components for 4-connectivity):

  1. row 0 fully occupied (the main word spans the board, len(main)==W by the model);
  2. SETUP legality: the pre-turn board (everything except newly-placed row-0 tiles) is ONE
     4-connected component (when any setup tile exists);
  3. CENTER: the setup contains the center cell (W//2, H//2) -- the game starts there, so every
     legal position includes it (necessary condition of game-reachability);
  4. WORDS: every maximal horizontal and vertical run of >=2 tiles on the FINAL board is a word;
  5. BAG: per letter, non-blank tiles on the final board <= bag count; blank tiles <= blank count
     (physical consistency -- covers both the setup and the newly drawn rack tiles);
  6. SCORE: full turn score recomputed independently (main word incl. multipliers + bingo, plus
     each vertical through a newly placed tile with row-0 multipliers), compared to the claim.

Representation: grid[y][x] = letter code (0 empty), blank[y][x] = bool, mask[x] = True iff the
row-0 tile at column x was newly placed this turn.

If the artifact has no blank annotations (xfill --emit BOARD lines don't carry them),
derive_blanks() computes the minimum-score-penalty blank assignment consistent with the bag:
per letter, usage beyond the bag count MUST be blanked; choosing the cells with the smallest
contribution to the turn score is optimal because the per-letter constraints are independent.

CLI:  python experiments/witness_check.py <witness.json>
  JSON: {"board": "11", "main_word": "...", "turn_str": "BOUWfYsiCuS", "scale": true,
         "blanks": true, "grid": [[codes...]xH], "blank": [[bool...]xH] (optional),
         "claimed_total": 799}
"""
import sys, os, json
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
from scrabble import construct_rules, get_word_score          # scoring semantics (rules ground truth)
from connectivity import components                           # plain-python 4-connectivity


def _runs(grid, W, H):
    """All maximal runs of length>=2, as (direction, x, y, tuple_of_codes)."""
    out = []
    for y in range(H):
        x = 0
        while x < W:
            if grid[y][x] == 0:
                x += 1; continue
            x2 = x
            while x2 < W and grid[y][x2] != 0:
                x2 += 1
            if x2 - x >= 2:
                out.append(('H', x, y, tuple(grid[y][k] for k in range(x, x2))))
            x = x2
    for x in range(W):
        y = 0
        while y < H:
            if grid[y][x] == 0:
                y += 1; continue
            y2 = y
            while y2 < H and grid[y2][x] != 0:
                y2 += 1
            if y2 - y >= 2:
                out.append(('V', x, y, tuple(grid[k][x] for k in range(y, y2))))
            y = y2
    return out


def _cell_score_weight(rules, grid, mask, W, H, x, y):
    """The EXACT marginal turn-score loss of blanking this cell (blanking zeroes the letter value
    but keeps multipliers triggering, per get_word_score).  Used to pick the optimal blank
    assignment.  Let WM = product of word multipliers over all newly-placed (masked) row-0 cells,
    wm_x = word_multiplier[0,x], lm_x = letter_multiplier[0,x], v = the cell's letter value:
      - row-0 masked cell:    v*lm_x*WM (main word)  +  v*lm_x*wm_x if its vertical has len>=2
      - row-0 unmasked cell:  v*WM (face value in the main word; no own multipliers, placed=False)
      - stub cell (y>=1) in a masked column's vertical:  v*wm_x (the vertical's word multiplier
        comes from its placed row-0 cell)
      - any other cell (bridges, cells below pre-placed columns):  0 (no scoring word this turn)
    """
    v = rules.scores[grid[y][x]]
    WM = 1
    for cx in range(W):
        if mask[cx]:
            WM *= int(rules.word_multiplier[0, cx])
    vlen = 0                                                  # vertical run length from (x,0)
    while vlen < H and grid[vlen][x] != 0:
        vlen += 1
    if y == 0:
        lm = int(rules.letter_multiplier[0, x]) if mask[x] else 1
        wgt = v * lm * WM
        if mask[x] and vlen >= 2:
            wgt += v * lm * int(rules.word_multiplier[0, x])
        return wgt
    if mask[x] and y < vlen:
        return v * int(rules.word_multiplier[0, x])
    return 0


def derive_blanks(rules, grid, mask, W, H):
    """Minimum-penalty blank assignment consistent with the bag.  Per letter, overflow cells MUST
    be blanked; choosing the lowest-turn-score-contribution cells is optimal (per-letter
    independence).  Returns (blank, n_used) or (None, reason) if even all blanks don't suffice."""
    cells_by_letter = {}
    for y in range(H):
        for x in range(W):
            if grid[y][x] != 0:
                cells_by_letter.setdefault(grid[y][x], []).append((x, y))
    blank = [[False] * W for _ in range(H)]
    need = 0
    for code, cells in cells_by_letter.items():
        over = len(cells) - rules.counts.get(code, 0)
        if over <= 0:
            continue
        need += over
        cells.sort(key=lambda c: _cell_score_weight(rules, grid, mask, W, H, c[0], c[1]))
        for (x, y) in cells[:over]:
            blank[y][x] = True
    if need > rules.blank_count:
        return None, f"needs {need} blanks > {rules.blank_count} available"
    return blank, need


def check_witness(rules, W, H, grid, blank, mask, claimed_total=None, require_center=True):
    """Returns (ok, report_dict).  ok=False -> report['fail'] explains the violated invariant."""
    rep = {}
    # 0) row 0 fully occupied
    if any(grid[0][x] == 0 for x in range(W)):
        return False, {'fail': 'row 0 not fully occupied (main word must span the board)'}
    occupied = {(x, y) for y in range(H) for x in range(W) if grid[y][x] != 0}
    setup = {(x, y) for (x, y) in occupied if not (y == 0 and mask[x])}
    # 1) setup connectivity
    if setup:
        comps = components(setup, W, H)
        if len(comps) != 1:
            return False, {'fail': f'setup board not connected ({len(comps)} components)'}
    # 2) center cell
    cc, cr = W // 2, H // 2
    if require_center and (cc, cr) not in setup:
        return False, {'fail': f'center cell ({cc},{cr}) not occupied in the setup board '
                               f'(game-start requirement)'}
    # 3) every run >= 2 is a word -- on the FINAL board
    wl = rules.words_lookup
    for (d, x, y, word) in _runs(grid, W, H):
        if word not in wl:
            return False, {'fail': f'illegal {d}-word at ({x},{y}): '
                                   f'{rules.alphabet.to_str(list(word))}'}
    # 3b) SETUP legality: every maximal run >= 2 on the SETUP board (final minus the newly-placed
    #     row-0 tiles) must ALSO be a legal word.  The pre-turn position must itself be a fully
    #     legal scrabble position -- a scored vertical of length L hangs a setup tail (rows 1..L-1)
    #     that, in the pre-turn board, is a STANDALONE maximal vertical run; if its length >= 2 it
    #     must be a dictionary word for the position to be reachable.  (length-1 tails: no run.)
    setup_grid = [[(0 if (yy == 0 and mask[xx]) else grid[yy][xx])
                   for xx in range(W)] for yy in range(H)]
    for (d, x, y, word) in _runs(setup_grid, W, H):
        if word not in wl:
            return False, {'fail': f'illegal SETUP {d}-word at ({x},{y}): '
                                   f'{rules.alphabet.to_str(list(word))}'}
    # 4) physical bag (final board): non-blank usage per letter <= bag; blanks <= blank_count
    used = Counter(); nblank = 0
    for (x, y) in occupied:
        if blank[y][x]:
            nblank += 1
        else:
            used[grid[y][x]] += 1
    if nblank > rules.blank_count:
        return False, {'fail': f'{nblank} blank tiles > {rules.blank_count} in bag'}
    for code, n in used.items():
        if n > rules.counts.get(code, 0):
            return False, {'fail': f'letter {rules.alphabet.to_str([code])}: {n} tiles > '
                                   f'{rules.counts.get(code, 0)} in bag'}
    rep['blanks_used'] = nblank
    # 5) recompute the full turn score
    row0 = tuple(grid[0][x] for x in range(W))
    main_sc, _ = get_word_score(rules, row0, 0, 0, 1, list(mask),
                                [blank[0][x] for x in range(W)])
    vert_sc = 0
    verts = {}
    for x in range(W):
        if not mask[x]:
            continue
        y2 = 0
        while y2 < H and grid[y2][x] != 0:
            y2 += 1
        if y2 >= 2:                                          # vertical word through the new tile
            w = tuple(grid[k][x] for k in range(y2))
            sc, _ = get_word_score(rules, w, x, 0, 0, [i == 0 for i in range(y2)],
                                   [blank[k][x] for k in range(y2)])
            vert_sc += sc
            verts[x] = (rules.alphabet.to_str(list(w)), sc)
    rep.update(main_score=main_sc, vertical_score=vert_sc, total=main_sc + vert_sc,
               verticals=verts)
    if claimed_total is not None:
        rep['claimed_total'] = claimed_total
        # A lower-bound witness is sound iff the board really achieves >= the claim.
        if main_sc + vert_sc < claimed_total:
            return False, {**rep, 'fail': f'recomputed total {main_sc + vert_sc} < claimed '
                                          f'{claimed_total}'}
        if main_sc + vert_sc != claimed_total:
            rep['note'] = (f'recomputed {main_sc + vert_sc} != claimed {claimed_total} '
                           f'(claim is sound but understated)')
    return True, rep


def _main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1]))
    board, scale = spec['board'], spec.get('scale', True)
    rules = construct_rules(os.environ.get('N15_LANG', 'dutch'), board)
    W, H = rules.W, rules.H
    turn_str = spec['turn_str']
    mask = [turn_str[x].isupper() for x in range(W)]
    if scale:                                                # mirror exp32/exp33 scaling exactly
        f = (W * W) / (15 * 15)
        mt = rules.alphabet.to_tup(spec['main_word'])
        mc = Counter(mt)
        rules.counts = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
        rules.blank_count = round(rules.blank_count * f)
    if not spec.get('blanks', True):
        rules.blank_count = 0
    if 'rows' in spec:                                       # human-readable: letters + '.' empty,
        grid = []                                            # UPPERCASE/lowercase both accepted;
        for row in spec['rows']:                             # '*' marks a blank tile whose letter
            r = []                                           # is given in 'blank_letters' (x,y)->ch
            for ch in row.replace(' ', ''):
                r.append(0 if ch == '.' else rules.alphabet.cba[ch.lower()])
            assert len(r) == W, f'row length {len(r)} != {W}'
            grid.append(r)
    else:
        grid = spec['grid']
    if spec.get('blank'):
        blank = [[bool(b) for b in row] for row in spec['blank']]
    else:
        blank, info = derive_blanks(rules, grid, mask, W, H)
        if blank is None:
            sys.exit(f'FAIL: no valid blank assignment: {info}')
        print(f'(derived blank assignment: {info} blanks)')
    ok, rep = check_witness(rules, W, H, grid, blank, mask,
                            claimed_total=spec.get('claimed_total'),
                            require_center=spec.get('require_center', True))
    print(json.dumps(rep, indent=2, default=str))
    print('WITNESS OK' if ok else 'WITNESS REJECTED')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    _main()
