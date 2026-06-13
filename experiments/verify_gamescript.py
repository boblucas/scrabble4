"""INDEPENDENT replay verifier for an N=11 max-turn game script.

Shares no search logic with 36_game_script.py.  Replays the ordered setup plays from an empty
board, then the final scored turn (the masked row-0 tiles), and at EVERY intermediate board state
checks, from first principles:
  * the play places 1..7 tiles, all in one row OR one column, and they are contiguous with the
    line's existing tiles (no holes in the spanned segment);
  * play 1 covers the center (W//2,H//2); plays 2.. connect to the existing structure;
  * after the play, the WHOLE board is legal: every maximal H/V run of length>=2 is a dict word;
  * the board is one 4-connected component after each play;
  * physical bag feasibility of the FINAL board (per-letter usage <= scaled bag, overflow<=blanks);
  * the final board equals the certified witness grid and the scored turn totals the claim.

Usage: python experiments/verify_gamescript.py <script.json> <witness.json>
Exit 0 = VERIFIED, 1 = a violation (printed precisely).
"""
import sys, os, json
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
from scrabble import construct_rules, get_word_score
from connectivity import components


def all_runs(occ, grid, W, H):
    """Every maximal run of length>=2 on the CURRENT board, as (dir,x,y,word_tuple)."""
    out = []
    for y in range(H):
        x = 0
        while x < W:
            if (x, y) not in occ:
                x += 1; continue
            x2 = x
            while x2 < W and (x2, y) in occ:
                x2 += 1
            if x2 - x >= 2:
                out.append(('H', x, y, tuple(grid[y][k] for k in range(x, x2))))
            x = x2
    for x in range(W):
        y = 0
        while y < H:
            if (x, y) not in occ:
                y += 1; continue
            y2 = y
            while y2 < H and (x, y2) in occ:
                y2 += 1
            if y2 - y >= 2:
                out.append(('V', x, y, tuple(grid[k][x] for k in range(y, y2))))
            y = y2
    return out


def fail(msg):
    print('REPLAY VIOLATION: ' + msg)
    sys.exit(1)


def main():
    script = json.load(open(sys.argv[1]))
    spec = json.load(open(sys.argv[2]))
    rules = construct_rules('dutch', spec['board'])
    W, H = rules.W, rules.H
    a = rules.alphabet
    wl = rules.words_lookup
    grid = spec['grid']                          # the certified FINAL grid (ground-truth letters)
    turn = spec['turn_str']
    mask = [turn[x].isupper() for x in range(W)]
    center = (W // 2, H // 2)

    # scored-turn cells = masked row-0 cells
    scored_cells = [(x, 0) for x in range(W) if mask[x]]
    setup_target = {(x, y) for y in range(H) for x in range(W)
                    if grid[y][x] != 0 and not (y == 0 and mask[x])}

    occ = set()                                  # currently-placed cells
    hand_size = 7

    # ---- replay the SETUP plays ----
    for i, play in enumerate(script['plays'], 1):
        new = [tuple(c) for c in play['new_cells']]
        if not (1 <= len(new) <= hand_size):
            fail(f'play {i}: places {len(new)} tiles (must be 1..{hand_size})')
        for c in new:
            if c in occ:
                fail(f'play {i}: cell {c} already occupied')
            if c[1] == 0 and mask[c[0]]:
                fail(f'play {i}: places a scored-turn cell {c} during setup')
            if grid[c[1]][c[0]] == 0:
                fail(f'play {i}: cell {c} is empty on the final board')
        # all in one line
        xs = {c[0] for c in new}; ys = {c[1] for c in new}
        if len(xs) != 1 and len(ys) != 1:
            fail(f'play {i}: tiles not in a single row or column')
        occ_before = set(occ)
        occ |= set(new)
        # contiguity: the spanned segment of the play line has no holes
        if len(xs) == 1:                         # vertical play
            x = next(iter(xs)); yy = sorted(c[1] for c in new)
            lo, hi = yy[0], yy[-1]
            for y in range(lo, hi + 1):
                if (x, y) not in occ:
                    fail(f'play {i}: hole at ({x},{y}) in placed column segment')
        else:                                    # horizontal play
            y = next(iter(ys)); xx = sorted(c[0] for c in new)
            lo, hi = xx[0], xx[-1]
            for x in range(lo, hi + 1):
                if (x, y) not in occ:
                    fail(f'play {i}: hole at ({x},{y}) in placed row segment')
        # center / connectivity
        if i == 1:
            if center not in occ:
                fail('play 1 does not cover the center cell')
        else:
            # must touch existing structure: some new cell adjacent to an old cell
            touch = any((c[0] + dx, c[1] + dy) in occ_before
                        for c in new for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if not touch:
                fail(f'play {i}: does not connect to existing tiles')
        # WHOLE-BOARD legality after this play
        for (d, x, y, word) in all_runs(occ, grid, W, H):
            if word not in wl:
                fail(f'play {i}: illegal {d}-run at ({x},{y}) = {a.to_str(list(word))!r}')
        # one connected component
        comps = components(occ, W, H)
        if len(comps) != 1:
            fail(f'play {i}: board has {len(comps)} components (must be 1)')

    if occ != setup_target:
        miss = setup_target - occ; extra = occ - setup_target
        fail(f'setup incomplete after plays: missing {sorted(miss)} extra {sorted(extra)}')
    print(f'OK: {len(script["plays"])} setup plays replayed; every intermediate board legal & connected.')

    # ---- the FINAL scored turn ----
    new = scored_cells
    if not (1 <= len(new) <= hand_size):
        fail(f'scored turn places {len(new)} tiles')
    occ_before = set(occ)
    occ |= set(new)
    if occ != {(x, y) for y in range(H) for x in range(W) if grid[y][x] != 0}:
        fail('after scored turn, board != certified final board')
    # main word spans row 0
    for x in range(W):
        if (x, 0) not in occ:
            fail(f'row 0 cell ({x},0) empty after scored turn')
    for (d, x, y, word) in all_runs(occ, grid, W, H):
        if word not in wl:
            fail(f'final board illegal {d}-run at ({x},{y}) = {a.to_str(list(word))!r}')
    if len(components(occ, W, H)) != 1:
        fail('final board not one component')
    print('OK: scored turn places the 7 masked row-0 tiles; final board == certified board.')

    # ---- physical bag feasibility (whole board) ----
    f = (W * W) / (15 * 15)
    mt = a.to_tup(spec['main_word']); mc = Counter(mt)
    scaled = Counter({c: max(round(n * f), mc[c], 1) for c, n in rules.counts.items()})
    blank_scaled = round(rules.blank_count * f)
    used = Counter(grid[y][x] for y in range(H) for x in range(W) if grid[y][x] != 0)
    overflow = sum(max(0, used[c] - scaled.get(c, 0)) for c in used)
    if overflow > blank_scaled:
        fail(f'bag: overflow {overflow} > {blank_scaled} blanks')
    print(f'OK: whole-board bag feasible (overflow {overflow} <= {blank_scaled} blank(s)).')

    # ---- score of the scored turn ----
    blank = [[False] * W for _ in range(H)]
    # place the single blank on the lowest-weight overflow cell (a u-cell); any valid choice works
    # but to match the witness we recompute the score with NO blank on a scored cell first, then
    # fall back to derive.  Simplest: replicate witness_check's optimal blank.
    import importlib.util
    wc_path = os.path.join(ROOT, 'experiments', 'witness_check.py')
    spec_mod = importlib.util.spec_from_file_location('wc', wc_path)
    wc = importlib.util.module_from_spec(spec_mod); spec_mod.loader.exec_module(wc)
    rules2 = construct_rules('dutch', spec['board'])
    rules2.counts = scaled; rules2.blank_count = blank_scaled
    blank, info = wc.derive_blanks(rules2, grid, mask, W, H)
    if blank is None:
        fail(f'no valid blank assignment: {info}')
    ok, rep = wc.check_witness(rules2, W, H, grid, blank, mask,
                               claimed_total=spec.get('claimed_total'),
                               require_center=spec.get('require_center', True))
    if not ok:
        fail(f'witness_check rejected final board: {rep.get("fail")}')
    print(f'OK: scored-turn total = {rep["total"]} (claim {spec.get("claimed_total")}); '
          f'blanks used {rep["blanks_used"]}.')
    print('GAME-SCRIPT VERIFIED: REACHABLE.')
    sys.exit(0)


if __name__ == '__main__':
    main()
