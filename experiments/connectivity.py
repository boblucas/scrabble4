"""
Custom connectivity oracle for the max-turn search.

THE QUESTION (a clean, well-defined combinatorial problem, no CP-SAT needed):
  Given the FIXED tiles on the pre-turn setup board (pre-placed row-0 tiles + the scoring-vertical
  stubs) and a budget of K extra tiles, can we add <= K bridge cells so that EVERYTHING forms one
  4-connected component?

This ignores word validity, so it is a strict RELAXATION of the real (legal) connectivity problem:
  min_bridge_cells(fixed) > (tiles left for bridges)  ==>  the legal problem is INFEASIBLE too.
That makes it a SOUND, fast prune: it rejects the "tile-starved" candidates (long verticals that eat
the whole bag, leaving nothing to connect their scattered columns) that CP-SAT wastes ~90s refuting.

min_bridge_cells = minimum number of empty cells whose addition connects all fixed components =
a node-weighted rectilinear Steiner tree (terminals = components, empty cell cost 1, fixed cost 0),
solved exactly by the Steiner-tree subset DP (Dreyfus-Wagner style). Fast for the small number of
components these boards produce; falls back to a sound lower bound if there are too many terminals.
"""
from collections import deque
import heapq


def components(fixed, W, H):
    """4-connected components of the set `fixed` of (x,y) cells."""
    seen = set(); comps = []
    for cell in fixed:
        if cell in seen:
            continue
        comp = []; dq = deque([cell]); seen.add(cell)
        while dq:
            x, y = dq.popleft(); comp.append((x, y))
            for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if (nx, ny) in fixed and (nx, ny) not in seen:
                    seen.add((nx, ny)); dq.append((nx, ny))
        comps.append(comp)
    return comps


def _cost(cell, fixed):
    return 0 if cell in fixed else 1            # entering a fixed cell is free; an empty cell costs a tile


def min_bridge_cells(fixed, W, H, max_terminals=14):
    """Minimum empty cells to merge all fixed components into one (exact Steiner DP).
    Returns (value, exact: bool). If #components > max_terminals, returns a SOUND LOWER BOUND
    with exact=False (still valid for a >budget infeasibility prune)."""
    comps = components(fixed, W, H)
    t = len(comps)
    if t <= 1:
        return 0, True
    if t > max_terminals:
        # sound lower bound: one empty cell merges at most 3 separate components (it joins itself +
        # up to 4 neighbours -> reduces the count by <=3), and we must connect t comps.
        return -(-(t - 1) // 3), False          # ceil((t-1)/3)

    cells = [(x, y) for x in range(W) for y in range(H)]
    idx = {c: i for i, c in enumerate(cells)}
    n = len(cells)
    INF = float('inf')
    # one terminal per component (any representative cell)
    terms = [comp[0] for comp in comps]
    # dp[mask][v] = min empty-cells in a tree spanning terminals in `mask` and containing node v
    dp = [[INF] * n for _ in range(1 << t)]
    for i, term in enumerate(terms):
        dp[1 << i][idx[term]] = _cost(term, fixed)
    adj = []
    for (x, y) in cells:
        nb = []
        for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if 0 <= nx < W and 0 <= ny < H:
                nb.append(idx[(nx, ny)])
        adj.append(nb)
    for mask in range(1, 1 << t):
        row = dp[mask]
        # merge two sub-trees meeting at v
        sub = (mask - 1) & mask
        while sub:
            other = mask ^ sub
            if sub < other:
                ds, do = dp[sub], dp[other]
                for v in range(n):
                    a = ds[v]
                    if a == INF:
                        continue
                    b = do[v]
                    if b == INF:
                        continue
                    c = a + b - _cost(cells[v], fixed)      # v counted twice
                    if c < row[v]:
                        row[v] = c
            sub = (sub - 1) & mask
        # Dijkstra relaxation: extend the tree to neighbouring cells
        pq = [(row[v], v) for v in range(n) if row[v] < INF]
        heapq.heapify(pq)
        while pq:
            d, v = heapq.heappop(pq)
            if d > row[v]:
                continue
            for u in adj[v]:
                nd = d + _cost(cells[u], fixed)
                if nd < row[u]:
                    row[u] = nd
                    heapq.heappush(pq, (nd, u))
    best = min(dp[(1 << t) - 1])
    return int(best), True


def setup_fixed_cells(W, H, turn_str, main_tup, chosen):
    """Cells occupied on the PRE-TURN setup board.
    chosen: {col: word_tuple} for scoring columns (word[0]=main tile placed this turn -> NOT on the
    setup board; word[1:] = stub on rows 1..len-1). Pre-placed (lowercase in turn_str) sit at row 0.
    """
    fixed = set()
    for x in range(W):
        if not turn_str[x].isupper():          # pre-placed tile present at row 0
            fixed.add((x, 0))
    for c, w in chosen.items():
        for r in range(1, len(w)):             # w[1:] stub
            fixed.add((c, r))
    return fixed


def can_connect(fixed, W, H, budget):
    """True iff the fixed cells can be merged into one component by adding <= budget empty cells
    (ignoring word validity). budget = tiles available for bridges. SOUND necessary condition for
    the full legal connectivity: if this is False, the legal problem is infeasible."""
    mb, _ = min_bridge_cells(fixed, W, H)
    return mb <= budget


import os, subprocess


class RustOracle:
    """Fast connectivity oracle backed by the persistent Rust binary (experiments/conn_rs).
    Returns sound bounds on min_bridge_cells; can_connect prunes only when PROVEN infeasible."""
    def __init__(self, W, H, bin_path=None):
        self.W, self.H = W, H
        if bin_path is None:
            bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'conn_rs', 'target', 'release', 'conn')
        self.p = subprocess.Popen([bin_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1)

    def bounds(self, fixed):
        cells = ' '.join(f'{x} {y}' for (x, y) in fixed)
        self.p.stdin.write(f'{self.W} {self.H} 0 {len(fixed)} {cells}\n')
        self.p.stdin.flush()
        lb, ub = map(int, self.p.stdout.readline().split())
        return lb, ub

    def can_connect(self, fixed, budget):
        lb, _ub = self.bounds(fixed)
        return lb <= budget          # False only when PROVABLY unconnectable (sound prune)
