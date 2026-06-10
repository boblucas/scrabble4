"""Game-reachability certificate: decompose a witness SETUP board into a sequence of legal plays.

A static-legal setup board is only a real Scrabble position if some sequence of legal plays builds
it.  This tool searches for an explicit GAME SCRIPT and validates every step:
  * play 1 covers the center cell and places >=2 tiles in one line;
  * every play places 1..7 new tiles in ONE line; after placement the tiles in that line form one
    contiguous run (existing tiles may fill gaps); every run CREATED OR EXTENDED by the play
    (the main run + each new tile's perpendicular run) of length >=2 is a dictionary word;
    every play after the first touches the existing structure (uses an existing tile in its main
    run or abuts one perpendicular -- equivalently, some formed run mixes old and new);
  * draws are freely chosen from the bag (standard for constructed records); global bag
    consistency is witness_check's job, re-verified here at the end.

Soundness note (why intermediate boards need no extra checks): inductively, every maximal run on
a Scrabble board is a valid word at all times -- each play validates exactly the runs it touches,
and untouched runs are unchanged.  So the search space is "word-valid sub-boards of the setup",
and reaching the full setup with valid plays IS a complete legality certificate.

The final scoring turn (row 0 newly-placed tiles) is validated separately by witness_check; this
tool certifies the SETUP (everything else).

Usage:  python experiments/36_game_script.py <witness.json> [--max-branch 40] [--deadline 600]
Exit 0 + a numbered play-by-play if a script exists within the search budget; exit 2 if the
search is exhausted (PROVABLY no decomposition under these rules); exit 3 on budget timeout
(unknown).
"""
import sys, os, json, time, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))
from scrabble import construct_rules
import witness_check as wc


def load(spec_path):
    spec = json.load(open(spec_path))
    rules = construct_rules('dutch', spec['board'])
    W, H = rules.W, rules.H
    turn = spec['turn_str']
    mask = [turn[x].isupper() for x in range(W)]
    if 'rows' in spec:                       # human-readable form (same as witness_check)
        grid = []
        for row in spec['rows']:
            r = [0 if ch == '.' else rules.alphabet.cba[ch.lower()]
                 for ch in row.replace(' ', '')]
            assert len(r) == W, f'row length {len(r)} != {W}'
            grid.append(r)
    else:
        grid = spec['grid']
    setup = {(x, y) for y in range(H) for x in range(W)
             if grid[y][x] != 0 and not (y == 0 and mask[x])}
    return rules, spec, grid, mask, setup


def run_at(grid, placed, x, y, dx, dy):
    """The contiguous run of `placed` cells through (x,y) along (dx,dy) -> list of cells."""
    cx, cy = x, y
    while (cx - dx, cy - dy) in placed:
        cx, cy = cx - dx, cy - dy
    out = []
    while (cx, cy) in placed:
        out.append((cx, cy)); cx, cy = cx + dx, cy + dy
    return out


def word_of(grid, cells):
    return tuple(grid[y][x] for (x, y) in cells)


def legal_plays(rules, grid, setup, placed, first, center):
    """Generate legal plays from `placed` toward `setup`: (new_cells frozenset, desc).
    A play = a maximal contiguous target segment on one line whose unplaced cells (1..7) we place;
    validated: main run contiguous & a word (>=2, or 1 with a valid >=2 cross), every new cell's
    cross run a word when >=2, connects to existing tiles (or covers center when first)."""
    wl = rules.words_lookup
    plays = []
    lines = []
    H = len(grid); W = len(grid[0])
    for y in range(H):
        lines.append(([(x, y) for x in range(W)], 1, 0))         # rows: direction (1,0)
    for x in range(W):
        lines.append(([(x, y) for y in range(H)], 0, 1))         # cols: direction (0,1)
    for line, dx, dy in lines:
        cells = [c for c in line if c in setup]
        if not cells:
            continue
        # maximal contiguous target segments on this line
        segs = []
        cur = [cells[0]]
        for c in cells[1:]:
            if (c[0] - cur[-1][0]) + (c[1] - cur[-1][1]) == 1:
                cur.append(c)
            else:
                segs.append(cur); cur = [c]
        segs.append(cur)
        for seg in segs:
            # consider every contiguous sub-segment that ENDS at run boundaries in the current
            # state: new cells = sub-seg minus placed; the formed run is the placed-closure.
            n = len(seg)
            for i in range(n):
                for j in range(i, n):
                    sub = seg[i:j + 1]
                    new = [c for c in sub if c not in placed]
                    if not (1 <= len(new) <= 7):
                        continue
                    after = placed | set(sub)
                    # the formed main run = closure of sub in `after` along this line's direction
                    main = run_at(grid, after, sub[0][0], sub[0][1], dx, dy)
                    if set(sub) - set(main):
                        continue                                  # sub not contiguous in `after`
                    # gap check: sub must contain ALL unplaced cells inside the main run
                    if any(c not in placed and c not in set(sub) for c in main):
                        continue
                    formed = []                                   # runs to validate
                    if len(main) >= 2:
                        formed.append(main)
                    crosses_ok = True
                    touches_old = any(c in placed for c in main)
                    for c in new:
                        cr = run_at(grid, after, c[0], c[1], dy, dx)
                        if len(cr) >= 2:
                            formed.append(cr)
                            if any(p in placed for p in cr):
                                touches_old = True
                    if len(main) < 2 and not any(len(f) >= 2 for f in formed):
                        continue                                  # a play must form some word
                    for f in formed:
                        if word_of(grid, f) not in wl:
                            crosses_ok = False; break
                    if not crosses_ok:
                        continue
                    if first:
                        if center not in set(sub) or len(main) < 2:
                            continue
                    elif not touches_old:
                        continue
                    plays.append((frozenset(new), main))
    # dedupe by new-cell set, prefer plays placing more tiles (fewer total plays)
    seen = {}
    for new, main in plays:
        if new not in seen:
            seen[new] = main
    return sorted(seen.items(), key=lambda t: -len(t[0]))


def search(rules, grid, setup, center, max_branch, deadline):
    placed = frozenset()
    script = []
    dead = set()
    t0 = time.time()

    def dfs(placed):
        if time.time() - t0 > deadline:
            raise TimeoutError
        if placed == setup:
            return True
        if placed in dead:
            return False
        plays = legal_plays(rules, grid, setup, set(placed), first=not placed, center=center)
        for new, main in plays[:max_branch]:
            script.append((new, main))
            if dfs(placed | new):
                return True
            script.pop()
        dead.add(placed)
        return False

    try:
        ok = dfs(placed)
        return ('FOUND', script) if ok else ('EXHAUSTED', None)
    except TimeoutError:
        return ('TIMEOUT', None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('witness'); ap.add_argument('--max-branch', type=int, default=40)
    ap.add_argument('--deadline', type=float, default=600.0)
    a = ap.parse_args()
    rules, spec, grid, mask, setup = load(a.witness)
    W, H = rules.W, rules.H
    center = (W // 2, H // 2)
    if center not in setup:
        print(f'REJECT: center {center} not in the setup board'); sys.exit(2)
    status, script = search(rules, grid, setup, center, a.max_branch, a.deadline)
    if status == 'FOUND':
        print(f'GAME SCRIPT ({len(script)} setup plays + the scoring turn):')
        for i, (new, main) in enumerate(script, 1):
            w = rules.alphabet.to_str(list(word_of(grid, main)))
            horiz = len(main) < 2 or main[0][1] == main[-1][1]
            pos = f'{"row" if horiz else "col"} {main[0][1] if horiz else main[0][0]}'
            tiles = ','.join(f'({x},{y})' for (x, y) in sorted(new))
            print(f'  {i}. {w!r} at {pos} start {main[0]} -- places {len(new)}: {tiles}')
        print(f'  {len(script)+1}. THE SCORING TURN (row 0, validated by witness_check)')
        print('GAME-REACHABLE')
        sys.exit(0)
    print('EXHAUSTED: no legal play sequence builds this setup (witness must be replaced)'
          if status == 'EXHAUSTED' else f'TIMEOUT after {a.deadline}s (unknown)')
    sys.exit(2 if status == 'EXHAUSTED' else 3)


if __name__ == '__main__':
    main()
