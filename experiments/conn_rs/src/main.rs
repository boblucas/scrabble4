// Fast connectivity oracle for the max-turn search.
//
// THE QUESTION: given the fixed tiles on the pre-turn board and a budget of K extra tiles, can we
// add <= K bridge cells so everything is one 4-connected component? (Word validity ignored -> a
// strict relaxation, so "no" here proves the real legal problem infeasible.)
//
// min_bridge_cells = node-weighted rectilinear Steiner tree (terminals = components, empty cell
// cost 1, fixed cost 0). Exact via the Steiner subset DP for few components; MST gives an upper
// bound and ceil(MST/2) & ceil((t-1)/3) give sound lower bounds so most queries skip the DP.
//
// Persistent line protocol (no per-call spawn cost):
//   in : "W H K x0 y0 x1 y1 ... x{K-1} y{K-1}"   (K fixed cells)
//   out: "LB UB"   (lower & upper bound on min_bridge_cells; LB==UB when exact)
// Python prunes (infeasible) iff LB > budget; treats UB <= budget as geometrically connectable.

use std::io::{self, BufRead, Write};

const T_EXACT_MAX: usize = 14; // exact Steiner DP up to this many components

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = stdout.lock();
    for line in stdin.lock().lines() {
        let line = match line { Ok(l) => l, Err(_) => break };
        let t = line.trim();
        if t.is_empty() { continue; }
        let nums: Vec<i64> = t.split_whitespace().filter_map(|x| x.parse().ok()).collect();
        let (lb, ub) = solve(&nums);
        writeln!(out, "{} {}", lb, ub).unwrap();
        out.flush().unwrap();
    }
}

fn solve(nums: &[i64]) -> (i64, i64) {
    let w = nums[0] as usize;
    let h = nums[1] as usize;
    let _k = nums[3] as usize; // budget (unused: we return bounds, Python compares)
    let mut fixed = vec![false; w * h];
    let cells = &nums[4..];
    let mut nfixed = 0usize;
    let mut i = 0;
    while i + 1 < cells.len() {
        let x = cells[i] as usize;
        let y = cells[i + 1] as usize;
        fixed[y * w + x] = true;
        nfixed += 1;
        i += 2;
    }
    if nfixed == 0 { return (0, 0); }

    // components of fixed cells
    let mut comp = vec![usize::MAX; w * h];
    let mut ncomp = 0usize;
    let mut reps: Vec<usize> = Vec::new();
    for s in 0..w * h {
        if fixed[s] && comp[s] == usize::MAX {
            reps.push(s);
            let mut stack = vec![s];
            comp[s] = ncomp;
            while let Some(p) = stack.pop() {
                for q in neigh(p, w, h) {
                    if fixed[q] && comp[q] == usize::MAX {
                        comp[q] = ncomp;
                        stack.push(q);
                    }
                }
            }
            ncomp += 1;
        }
    }
    let tt = ncomp;
    if tt <= 1 { return (0, 0); }

    // pairwise distances between components: 0-1 BFS from each component (fixed cost 0, empty cost 1)
    // dist counts empty cells crossed to go from comp a to any cell.
    let mut compdist = vec![vec![i64::MAX; tt]; tt];
    for a in 0..tt {
        let d = bfs01(a, &comp, &fixed, w, h);
        for s in 0..w * h {
            if fixed[s] {
                let b = comp[s];
                if d[s] < compdist[a][b] { compdist[a][b] = d[s]; }
            }
        }
    }

    // MST over components using compdist -> upper bound on min_bridge_cells
    let mut in_tree = vec![false; tt];
    let mut key = vec![i64::MAX; tt];
    key[0] = 0;
    let mut mst: i64 = 0;
    for _ in 0..tt {
        let mut u = usize::MAX;
        let mut best = i64::MAX;
        for v in 0..tt {
            if !in_tree[v] && key[v] < best { best = key[v]; u = v; }
        }
        if u == usize::MAX { break; }
        in_tree[u] = true;
        mst += if key[u] == i64::MAX { 0 } else { key[u] };
        for v in 0..tt {
            if !in_tree[v] && compdist[u][v] < key[v] { key[v] = compdist[u][v]; }
        }
    }
    let ub_mst = mst; // achievable connection cost (paths may overlap -> actual <= this)
    let lb_count = ((tt as i64) - 1 + 2) / 3; // ceil((t-1)/3)
    let lb_mst = (mst + 1) / 2;               // Steiner >= MST/2
    let lb = lb_count.max(lb_mst);

    if tt <= T_EXACT_MAX {
        let exact = steiner_exact(&fixed, &comp, &reps, w, h);
        return (exact, exact);
    }
    (lb, ub_mst)
}

fn neigh(p: usize, w: usize, h: usize) -> Vec<usize> {
    let x = p % w;
    let y = p / w;
    let mut v = Vec::with_capacity(4);
    if x > 0 { v.push(p - 1); }
    if x + 1 < w { v.push(p + 1); }
    if y > 0 { v.push(p - w); }
    if y + 1 < h { v.push(p + w); }
    v
}

// 0-1 BFS from all cells of component `a`: cost to ENTER an empty cell = 1, fixed = 0.
fn bfs01(a: usize, comp: &[usize], fixed: &[bool], w: usize, h: usize) -> Vec<i64> {
    let n = w * h;
    let mut dist = vec![i64::MAX; n];
    let mut dq: std::collections::VecDeque<usize> = std::collections::VecDeque::new();
    for s in 0..n {
        if fixed[s] && comp[s] == a {
            dist[s] = 0;
            dq.push_back(s);
        }
    }
    while let Some(p) = dq.pop_front() {
        let dp = dist[p];
        for q in neigh(p, w, h) {
            let wq = if fixed[q] { 0 } else { 1 };
            if dp + wq < dist[q] {
                dist[q] = dp + wq;
                if wq == 0 { dq.push_front(q); } else { dq.push_back(q); }
            }
        }
    }
    dist
}

// Exact node-weighted Steiner tree: min empty cells to connect all components.
// dp[mask][v] = min empty cells in a tree spanning the components in `mask` and containing node v.
fn steiner_exact(fixed: &[bool], comp: &[usize], reps: &[usize], w: usize, h: usize) -> i64 {
    let n = w * h;
    let t = reps.len();
    let cost = |v: usize| -> i64 { if fixed[v] { 0 } else { 1 } };
    let full = 1usize << t;
    let inf = i64::MAX / 4;
    let mut dp = vec![inf; full * n];
    for (i, &r) in reps.iter().enumerate() {
        dp[(1 << i) * n + r] = cost(r);
    }
    for mask in 1..full {
        // merge two subtrees at v
        let mut sub = (mask - 1) & mask;
        while sub > 0 {
            let other = mask ^ sub;
            if sub < other {
                for v in 0..n {
                    let a = dp[sub * n + v];
                    if a >= inf { continue; }
                    let b = dp[other * n + v];
                    if b >= inf { continue; }
                    let c = a + b - cost(v);
                    if c < dp[mask * n + v] { dp[mask * n + v] = c; }
                }
            }
            sub = (sub - 1) & mask;
        }
        // Dijkstra relaxation over the grid for this mask (0/1 node costs, arbitrary seed values)
        let base = mask * n;
        use std::cmp::Reverse;
        use std::collections::BinaryHeap;
        let mut heap: BinaryHeap<Reverse<(i64, usize)>> = BinaryHeap::new();
        for v in 0..n {
            if dp[base + v] < inf { heap.push(Reverse((dp[base + v], v))); }
        }
        while let Some(Reverse((d, v))) = heap.pop() {
            if d > dp[base + v] { continue; }
            for q in neigh(v, w, h) {
                let nd = d + cost(q);
                if nd < dp[base + q] {
                    dp[base + q] = nd;
                    heap.push(Reverse((nd, q)));
                }
            }
        }
    }
    let _ = comp;
    let mut best = inf;
    for v in 0..n {
        if dp[(full - 1) * n + v] < best { best = dp[(full - 1) * n + v]; }
    }
    best
}
