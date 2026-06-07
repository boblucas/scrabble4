// Crossword-fill + connectivity DECISION solver (v1: correctness baseline).
//
// Decide: does a legal connected setup board exist for a fixed length-vector?
// Board: pre-placed tiles (row 0), scoring columns = one candidate stub word each (rows 1..len-1),
// bridge cells (non-scoring columns, rows 1..H-1) = empty or a letter. Requirements: every maximal
// H/V run >=2 is a valid <=hmax dict word (scoring verticals are pre-validated by their word-domain),
// all active cells form ONE 4-connected component, tile budget (with blanks) respected.
//
// v1 strategy: row-major DFS. Per scoring column keep the set of candidate words still consistent
// with assigned cells. Prune each letter by HORIZONTAL and VERTICAL prefix checks (the cross-check).
// Validate runs the moment they close. Track tile budget incrementally. Check connectivity at leaves.
// Optimizations (cross-check bitsets, MRV slot ordering, GADDAG, lazy connectivity cuts) come next.

use std::collections::HashSet;
use std::fs;
use std::io::Read;

struct Inst {
    w: usize,
    h: usize,
    alpha: usize,
    blanks: i64,
    counts: Vec<i64>,            // index by code (1..=alpha); [0] unused
    grid0: Vec<i16>,            // initial: -1 unassigned, 0 empty(forced), >0 letter(preplaced)
    kind: Vec<u8>,              // 0 = fixed (preplaced/forced-empty), 1 = scoring-stub cell, 2 = bridge
    scol_of: Vec<i32>,         // for scoring-stub cells: which scoring column index; else -1
    scoring_cols: Vec<usize>,
    scoring_len: Vec<usize>,
    scoring_words: Vec<Vec<Vec<u8>>>, // per scoring col: candidate stub words (len = len-1)
}

fn idx(x: usize, y: usize, w: usize) -> usize { y * w + x }

fn parse(path: &str) -> Inst {
    let mut s = String::new();
    fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let mut w = 0; let mut h = 0; let mut alpha = 0; let mut blanks = 0i64;
    let mut counts: Vec<i64> = Vec::new();
    let mut preplaced: Vec<(usize, usize, i16)> = Vec::new();
    let mut nonscoring: Vec<usize> = Vec::new();
    let mut scoring_cols: Vec<usize> = Vec::new();
    let mut scoring_len: Vec<usize> = Vec::new();
    let mut scoring_words: Vec<Vec<Vec<u8>>> = Vec::new();
    let mut dict_path = String::new();
    let mut cur_col: i64 = -1;
    let lines: Vec<&str> = s.lines().collect();
    let mut i = 0;
    while i < lines.len() {
        let line = lines[i]; i += 1;
        let mut it = line.split_whitespace();
        let tag = match it.next() { Some(t) => t, None => continue };
        match tag {
            "DIMS" => {
                w = it.next().unwrap().parse().unwrap();
                h = it.next().unwrap().parse().unwrap();
                let _hmax: usize = it.next().unwrap().parse().unwrap();
                alpha = it.next().unwrap().parse().unwrap();
                blanks = it.next().unwrap().parse().unwrap();
                counts = vec![0; alpha + 1];
            }
            "COUNTS" => {
                for tok in it {
                    let mut p = tok.split(':');
                    let c: usize = p.next().unwrap().parse().unwrap();
                    let n: i64 = p.next().unwrap().parse().unwrap();
                    if c < counts.len() { counts[c] = n; }
                }
            }
            "PREPLACED" => {
                for tok in it {
                    let p: Vec<&str> = tok.split(',').collect();
                    preplaced.push((p[0].parse().unwrap(), p[1].parse().unwrap(), p[2].parse().unwrap()));
                }
            }
            "NONSCORING" => { for tok in it { nonscoring.push(tok.parse().unwrap()); } }
            "DICT" => { dict_path = it.next().unwrap().to_string(); }
            "NSCORING" => {}
            "SCOL" => {
                let col: usize = it.next().unwrap().parse().unwrap();
                let len: usize = it.next().unwrap().parse().unwrap();
                let _nw: usize = it.next().unwrap().parse().unwrap();
                scoring_cols.push(col); scoring_len.push(len); scoring_words.push(Vec::new());
                cur_col = (scoring_cols.len() - 1) as i64;
            }
            "WORD" => {
                let v: Vec<u8> = it.map(|t| t.parse().unwrap()).collect();
                scoring_words[cur_col as usize].push(v);
            }
            "TRUTH" => {}
            _ => {}
        }
        let _ = &dict_path;
    }
    // build grid
    let mut grid0 = vec![0i16; w * h];   // default empty
    let mut kind = vec![0u8; w * h];
    let mut scol_of = vec![-1i32; w * h];
    // preplaced (row 0, non-scoring): mandatory active
    for (x, y, c) in &preplaced { grid0[idx(*x, *y, w)] = *c; kind[idx(*x, *y, w)] = 0; }
    // scoring columns: stub cells unassigned (kind 1), below-stub & row0 forced empty (kind 0, val 0)
    let scoring_set: HashSet<usize> = scoring_cols.iter().cloned().collect();
    for (si, &col) in scoring_cols.iter().enumerate() {
        let len = scoring_len[si];
        for r in 1..len { let id = idx(col, r, w); grid0[id] = -1; kind[id] = 1; scol_of[id] = si as i32; }
        // (col,0) and (col, len..h) stay 0/forced-empty
    }
    // bridge cells: non-scoring columns, rows 1..h-1
    for &col in &nonscoring {
        for r in 1..h { let id = idx(col, r, w); grid0[id] = -1; kind[id] = 2; }
    }
    let _ = scoring_set;
    Inst { w, h, alpha, blanks, counts, grid0, kind, scol_of, scoring_cols, scoring_len, scoring_words }
    .with_dict(&dict_path)
}

impl Inst {
    fn with_dict(self, _p: &str) -> Inst { self }   // dict loaded separately
}

struct Dict { words: HashSet<Vec<u8>>, prefixes: HashSet<Vec<u8>> }
fn load_dict(path: &str, hmax: usize) -> Dict {
    let mut s = String::new();
    fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let mut words = HashSet::new(); let mut prefixes = HashSet::new();
    for line in s.lines() {
        let v: Vec<u8> = line.split_whitespace().map(|t| t.parse().unwrap()).collect();
        if v.is_empty() || v.len() > hmax { continue; }
        for k in 1..=v.len() { prefixes.insert(v[..k].to_vec()); }
        words.insert(v);
    }
    Dict { words, prefixes }
}

// solver state during DFS
struct Solver<'a> {
    inst: &'a Inst,
    dict: &'a Dict,
    grid: Vec<i16>,
    mandatory: Vec<usize>,      // cells that are always active (preplaced + scoring-stub positions)
    used: Vec<i64>,             // tiles used per code (incremental)
    overflow: i64,              // sum of per-code (used-counts) over codes where used>counts == blanks needed
    nodes: u64,
}

impl<'a> Solver<'a> {
    #[inline]
    fn add_letter(&mut self, l: usize) -> bool {
        self.used[l] += 1;
        if self.used[l] > self.inst.counts[l] { self.overflow += 1; }
        self.overflow <= self.inst.blanks
    }
    #[inline]
    fn rm_letter(&mut self, l: usize) {
        if self.used[l] > self.inst.counts[l] { self.overflow -= 1; }
        self.used[l] -= 1;
    }
}

impl<'a> Solver<'a> {
    fn run(&mut self) -> bool { self.dfs(0) }

    // Geometric prune: connectivity depends only on POSITIONS (letters are irrelevant). The "potential
    // active" graph = every cell not yet decided EMPTY (grid != 0: active letters OR undecided -1).
    // If the mandatory cells can't all reach each other through it, no future fill can connect them.
    fn can_still_connect(&self) -> bool {
        if self.mandatory.is_empty() { return true; }
        let w = self.inst.w; let h = self.inst.h;
        let pot = |id: usize| self.grid[id] != 0;     // not decided-empty
        let start = self.mandatory[0];
        let mut seen = vec![false; w * h];
        let mut stack = vec![start]; seen[start] = true;
        while let Some(p) = stack.pop() {
            let px = p % w; let py = p / w;
            if px > 0 { let q = p - 1; if pot(q) && !seen[q] { seen[q] = true; stack.push(q); } }
            if px + 1 < w { let q = p + 1; if pot(q) && !seen[q] { seen[q] = true; stack.push(q); } }
            if py > 0 { let q = p - w; if pot(q) && !seen[q] { seen[q] = true; stack.push(q); } }
            if py + 1 < h { let q = p + w; if pot(q) && !seen[q] { seen[q] = true; stack.push(q); } }
        }
        self.mandatory.iter().all(|&m| seen[m])
    }

    fn dfs(&mut self, pos: usize) -> bool {
        self.nodes += 1;
        if self.nodes % 5_000_000 == 0 { eprintln!("  nodes={}M", self.nodes / 1_000_000); }
        let w = self.inst.w; let h = self.inst.h; let n = w * h;
        // find next unassigned cell in row-major from `pos`
        let mut id = pos;
        while id < n && self.grid[id] != -1 { id += 1; }
        if id >= n {
            return self.leaf_ok();
        }
        let x = id % w; let y = id / w;
        let kind = self.inst.kind[id];
        if kind == 1 {
            // scoring-stub cell: branch over letters consistent with the column's candidate words
            let si = self.inst.scol_of[id] as usize;
            let col = self.inst.scoring_cols[si];
            let posn = y - 1; // index in stub word
            // collect candidate letters from words consistent with already-assigned cells of this col
            let mut letters: Vec<u8> = Vec::new();
            'words: for wd in &self.inst.scoring_words[si] {
                // check consistency with assigned stub cells of this col
                for r in 1..self.inst.scoring_len[si] {
                    let cid = idx(col, r, w);
                    let g = self.grid[cid];
                    if g > 0 && (wd[r - 1] as i16) != g { continue 'words; }
                }
                let l = wd[posn];
                if !letters.contains(&l) { letters.push(l); }
            }
            for l in letters {
                if !self.place_ok(x, y, l) { continue; }
                if !self.add_letter(l as usize) { self.rm_letter(l as usize); continue; }
                self.grid[id] = l as i16;
                if self.dfs(id + 1) { return true; }
                self.grid[id] = -1;
                self.rm_letter(l as usize);
            }
            false
        } else {
            // bridge cell: try EMPTY then valid letters
            // EMPTY: only if mandatory cells can still connect without this cell
            self.grid[id] = 0;
            if self.can_still_connect() && self.closed_runs_ok(x, y) && self.dfs(id + 1) { return true; }
            self.grid[id] = -1;
            for l in 1..=self.inst.alpha as i16 {
                if !self.place_ok(x, y, l as u8) { continue; }
                if !self.add_letter(l as usize) { self.rm_letter(l as usize); continue; }
                self.grid[id] = l;
                if self.dfs(id + 1) { return true; }
                self.grid[id] = -1;
                self.rm_letter(l as usize);
            }
            false
        }
    }

    // prefix-check pruning: placing letter at (x,y), the assigned-contiguous H run ending here and
    // V run ending here must be prefixes of some word (they may extend right/down later).
    fn place_ok(&mut self, x: usize, y: usize, l: u8) -> bool {
        let w = self.inst.w; let h = self.inst.h;
        // horizontal run-so-far (left part + this). Right neighbour (processed later) is undecided
        // (-1) -> run may extend, prefix-check; or forced-empty(0)/edge -> run CLOSES, full-word check.
        let mut hrun = vec![l];
        let mut cx = x as i64 - 1;
        while cx >= 0 {
            let g = self.grid[idx(cx as usize, y, w)];
            if g > 0 { hrun.push(g as u8); cx -= 1; } else { break; }
        }
        hrun.reverse();
        let h_closes = x + 1 == w || self.grid[idx(x + 1, y, w)] == 0;
        if hrun.len() >= 2 {
            if h_closes { if !self.dict.words.contains(&hrun) { return false; } }
            else if !self.dict.prefixes.contains(&hrun) { return false; }
        }
        // vertical: skip for scoring-stub cells (their vertical = pre-validated stub).
        if self.inst.kind[idx(x, y, w)] != 1 {
            let mut vrun = vec![l];
            let mut cy = y as i64 - 1;
            while cy >= 0 {
                let id2 = idx(x, cy as usize, w);
                if self.grid[id2] > 0 && self.inst.kind[id2] != 1 { vrun.push(self.grid[id2] as u8); cy -= 1; } else { break; }
            }
            vrun.reverse();
            let v_closes = y + 1 == h || self.grid[idx(x, y + 1, w)] == 0 || self.inst.kind[idx(x, y + 1, w)] == 1;
            if vrun.len() >= 2 {
                if v_closes { if !self.dict.words.contains(&vrun) { return false; } }
                else if !self.dict.prefixes.contains(&vrun) { return false; }
            }
        }
        true
    }

    // when we place EMPTY at (x,y), the H run ending at (x-1,y) and V run ending at (x,y-1) close.
    fn closed_runs_ok(&self, x: usize, y: usize) -> bool {
        let w = self.inst.w;
        // horizontal run ending at x-1 in row y
        if x > 0 && self.grid[idx(x - 1, y, w)] > 0 {
            let mut run = Vec::new(); let mut cx = x as i64 - 1;
            while cx >= 0 { let g = self.grid[idx(cx as usize, y, w)]; if g > 0 { run.push(g as u8); cx -= 1; } else { break; } }
            run.reverse();
            if run.len() >= 2 && !self.dict.words.contains(&run) { return false; }
        }
        // vertical run ending at y-1 in col x (only validate NON-scoring columns here; scoring handled by word)
        if y > 0 && self.grid[idx(x, y - 1, w)] > 0 && self.inst.kind[idx(x, y - 1, w)] != 1 {
            let mut run = Vec::new(); let mut cy = y as i64 - 1;
            while cy >= 0 {
                let id = idx(x, cy as usize, w);
                if self.grid[id] > 0 && self.inst.kind[id] != 1 { run.push(self.grid[id] as u8); cy -= 1; } else { break; }
            }
            run.reverse();
            if run.len() >= 2 && !self.dict.words.contains(&run) { return false; }
        }
        true
    }

    fn leaf_ok(&self) -> bool {
        let w = self.inst.w; let h = self.inst.h;
        // 1) validate ALL maximal H and V runs are valid words (V scoring-col runs are pre-valid)
        for y in 0..h {
            let mut x = 0;
            while x < w {
                if self.grid[idx(x, y, w)] > 0 {
                    let mut run = Vec::new(); let s = x;
                    while x < w && self.grid[idx(x, y, w)] > 0 { run.push(self.grid[idx(x, y, w)] as u8); x += 1; }
                    if run.len() >= 2 && !self.dict.words.contains(&run) { return false; }
                    let _ = s;
                } else { x += 1; }
            }
        }
        for x in 0..w {
            let mut y = 0;
            while y < h {
                let id = idx(x, y, w);
                if self.grid[id] > 0 {
                    // skip scoring-column vertical runs (validated by word-domain)
                    if self.inst.kind[id] == 1 {
                        while y < h && self.grid[idx(x, y, w)] > 0 { y += 1; }
                        continue;
                    }
                    let mut run = Vec::new();
                    while y < h && self.grid[idx(x, y, w)] > 0 && self.inst.kind[idx(x, y, w)] != 1 {
                        run.push(self.grid[idx(x, y, w)] as u8); y += 1;
                    }
                    if run.len() >= 2 && !self.dict.words.contains(&run) { return false; }
                } else { y += 1; }
            }
        }
        // 2) budget: per-code usage minus counts, summed overflow <= blanks
        let mut used = vec![0i64; self.inst.alpha + 1];
        for &g in &self.grid { if g > 0 { used[g as usize] += 1; } }
        let mut overflow = 0i64;
        for c in 1..=self.inst.alpha { if used[c] > self.inst.counts[c] { overflow += used[c] - self.inst.counts[c]; } }
        if overflow > self.inst.blanks { return false; }
        // 3) connectivity: all active cells one 4-connected component
        let active: Vec<usize> = (0..w * h).filter(|&id| self.grid[id] > 0).collect();
        if active.is_empty() { return true; }
        let aset: HashSet<usize> = active.iter().cloned().collect();
        let mut seen = HashSet::new();
        let mut stack = vec![active[0]]; seen.insert(active[0]);
        while let Some(p) = stack.pop() {
            let px = p % w; let py = p / w;
            let mut nb = Vec::new();
            if px > 0 { nb.push(p - 1); }
            if px + 1 < w { nb.push(p + 1); }
            if py > 0 { nb.push(p - w); }
            if py + 1 < h { nb.push(p + w); }
            for q in nb { if aset.contains(&q) && !seen.contains(&q) { seen.insert(q); stack.push(q); } }
        }
        seen.len() == active.len()
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let path = &args[1];
    let mut inst = parse(path);
    // re-read dict path from file (parse dropped it); read DICT line
    let mut s = String::new(); fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let mut dict_path = String::new(); let mut hmax = 8usize;
    for line in s.lines() {
        let mut it = line.split_whitespace();
        match it.next() {
            Some("DICT") => dict_path = it.next().unwrap().to_string(),
            Some("DIMS") => { for _ in 0..2 { it.next(); } hmax = it.next().unwrap().parse().unwrap(); }
            _ => {}
        }
    }
    let td = std::time::Instant::now();
    let dict = load_dict(&dict_path, hmax);
    eprintln!("dict loaded: {} words, {} prefixes, {:.2}s", dict.words.len(), dict.prefixes.len(), td.elapsed().as_secs_f64());
    let grid = inst.grid0.clone();
    // mandatory cells: preplaced (grid0>0) + scoring-stub positions (kind==1)
    let mandatory: Vec<usize> = (0..inst.w * inst.h)
        .filter(|&id| inst.grid0[id] > 0 || inst.kind[id] == 1).collect();
    // initial tile usage from pre-placed tiles
    let mut used = vec![0i64; inst.alpha + 1];
    for &g in &inst.grid0 { if g > 0 { used[g as usize] += 1; } }
    let mut overflow = 0i64;
    for c in 1..=inst.alpha { if used[c] > inst.counts[c] { overflow += used[c] - inst.counts[c]; } }
    let mut solver = Solver { inst: &inst, dict: &dict, grid, mandatory, used, overflow, nodes: 0 };
    let t = std::time::Instant::now();
    let sat = solver.run();
    let dt = t.elapsed().as_secs_f64();
    println!("{} nodes={} time={:.3}s", if sat { "SAT" } else { "UNSAT" }, solver.nodes, dt);
}
