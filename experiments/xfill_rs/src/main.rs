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
    scores: Vec<i64>,           // face value per code (1..=alpha); [0] unused; for blank penalty
    grid0: Vec<i16>,            // initial: -1 unassigned, 0 empty(forced), >0 letter(preplaced)
    kind: Vec<u8>,              // 0 = fixed (preplaced/forced-empty), 1 = scoring-stub cell, 2 = bridge
    scol_of: Vec<i32>,         // for scoring-stub cells: which scoring column index; else -1
    scoring_cols: Vec<usize>,
    scoring_len: Vec<usize>,
    scoring_words: Vec<Vec<Vec<u8>>>, // per scoring col: candidate stub words (len = len-1)
    scoring_gross: Vec<Vec<i64>>,    // per scoring col: vertical score per candidate word (parallel)
    scoring_best: Vec<i64>,          // per scoring col: max gross over its candidates (UB term)
    // static per-cell info (computed once after parse):
    cell_mask: Vec<u32>,       // bit (letter-1) set = letter possible at this cell (preplaced/forced=exact)
    can_active: Vec<bool>,     // cell is or can become active (hold a tile)
    #[allow(dead_code)]
    can_empty: Vec<bool>,      // cell can be empty (no tile); kept for the cell model / future MRV
}

#[inline] fn bit(l: u8) -> u32 { 1u32 << (l - 1) }

fn idx(x: usize, y: usize, w: usize) -> usize { y * w + x }

fn parse(path: &str) -> Inst {
    let mut s = String::new();
    fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let mut w = 0; let mut h = 0; let mut alpha = 0; let mut blanks = 0i64;
    let mut counts: Vec<i64> = Vec::new();
    let mut scores: Vec<i64> = Vec::new();
    let mut preplaced: Vec<(usize, usize, i16)> = Vec::new();
    let mut nonscoring: Vec<usize> = Vec::new();
    let mut scoring_cols: Vec<usize> = Vec::new();
    let mut scoring_len: Vec<usize> = Vec::new();
    let mut scoring_words: Vec<Vec<Vec<u8>>> = Vec::new();
    let mut scoring_gross: Vec<Vec<i64>> = Vec::new();
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
                scores = vec![0; alpha + 1];
            }
            "COUNTS" => {
                for tok in it {
                    let mut p = tok.split(':');
                    let c: usize = p.next().unwrap().parse().unwrap();
                    let n: i64 = p.next().unwrap().parse().unwrap();
                    if c < counts.len() { counts[c] = n; }
                }
            }
            "SCORES" => {
                for tok in it {
                    let mut p = tok.split(':');
                    let c: usize = p.next().unwrap().parse().unwrap();
                    let n: i64 = p.next().unwrap().parse().unwrap();
                    if c < scores.len() { scores[c] = n; }
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
                scoring_cols.push(col); scoring_len.push(len);
                scoring_words.push(Vec::new()); scoring_gross.push(Vec::new());
                cur_col = (scoring_cols.len() - 1) as i64;
            }
            "WORD" => {                                              // legacy: codes only, gross=0
                let v: Vec<u8> = it.map(|t| t.parse().unwrap()).collect();
                scoring_words[cur_col as usize].push(v);
                scoring_gross[cur_col as usize].push(0);
            }
            "WORDV" => {                                             // gross score then codes
                let g: i64 = it.next().unwrap().parse().unwrap();
                let v: Vec<u8> = it.map(|t| t.parse().unwrap()).collect();
                scoring_words[cur_col as usize].push(v);
                scoring_gross[cur_col as usize].push(g);
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
    // bridge cells: non-scoring columns, rows 1..h-1.
    // NOTE on depth: a tempting "no bridge below the deepest scoring column" restriction is UNSOUND --
    // a horizontal word can force bridge letters that only form a VALID vertical word by extending one
    // row past the deepest column (e.g. forced "ci" is invalid but "cid" is a word, needing a bridge at
    // that deeper row). Emptying such a deep cell shortens the vertical run into an INVALID word, so it
    // is not free. We therefore keep the full bridge range and tame the deep-bridge explosion in the
    // search itself (connectivity-aware pruning) rather than by truncating the board.
    for &col in &nonscoring {
        for r in 1..h { let id = idx(col, r, w); grid0[id] = -1; kind[id] = 2; }
    }
    let _ = scoring_set;
    // static per-cell domain info
    let all_mask: u32 = if alpha >= 26 { 0x03ff_ffff } else { (1u32 << alpha) - 1 };
    let mut cell_mask = vec![0u32; w * h];
    let mut can_active = vec![false; w * h];
    let mut can_empty = vec![false; w * h];
    for id in 0..w * h {
        match kind[id] {
            0 => {
                if grid0[id] > 0 { cell_mask[id] = bit(grid0[id] as u8); can_active[id] = true; }
                else { cell_mask[id] = 0; can_empty[id] = true; }   // forced-empty
            }
            1 => {                                                  // scoring-stub: union over candidate words
                let si = scol_of[id] as usize; let col = scoring_cols[si];
                let r = id / w; let posn = r - 1;
                let mut m = 0u32;
                for wd in &scoring_words[si] { m |= bit(wd[posn]); }
                cell_mask[id] = m; can_active[id] = true; let _ = col;
            }
            _ => { cell_mask[id] = all_mask; can_active[id] = true; can_empty[id] = true; } // bridge
        }
    }
    let scoring_best: Vec<i64> = scoring_gross.iter()
        .map(|gs| gs.iter().cloned().max().unwrap_or(0)).collect();
    Inst { w, h, alpha, blanks, counts, scores, grid0, kind, scol_of, scoring_cols, scoring_len,
           scoring_words, scoring_gross, scoring_best,
           cell_mask, can_active, can_empty }
    .with_dict(&dict_path)
}

impl Inst {
    fn with_dict(self, _p: &str) -> Inst { self }   // dict loaded separately
}

// pack a run of letters (each 1..=alpha, <=8 letters) into a u64: key starts at 1 (sentinel) then
// 6 bits per letter -> unique per (length, letters), no allocation, fast to hash.
#[inline] fn key_push(key: u64, l: u8) -> u64 { (key << 6) | (l as u64) }
fn key_of(run: &[u8]) -> u64 { let mut k = 1u64; for &l in run { k = key_push(k, l); } k }

// Forward trie over the <=hmax dict. Nodes hold 27 child slots (index 1..=26 = letter codes; 0 unused)
// and an is_word flag. Backs both membership (words) and prefix queries, and masked pattern matching.
const TR_CH: usize = 27;
struct Dict {
    words: std::collections::HashSet<u64>,
    prefixes: std::collections::HashSet<u64>,
    // trie
    child: Vec<[i32; TR_CH]>,   // child[node][letter] = node index or -1
    is_word: Vec<bool>,
}
fn load_dict(path: &str, hmax: usize) -> Dict {
    let mut s = String::new();
    fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let mut words = HashSet::new(); let mut prefixes = HashSet::new();
    let mut child: Vec<[i32; TR_CH]> = vec![[-1i32; TR_CH]];
    let mut is_word: Vec<bool> = vec![false];
    for line in s.lines() {
        let v: Vec<u8> = line.split_whitespace().map(|t| t.parse().unwrap()).collect();
        if v.is_empty() || v.len() > hmax { continue; }
        let mut k = 1u64;
        let mut node = 0usize;
        for &l in &v {
            k = key_push(k, l); prefixes.insert(k);
            let li = l as usize;
            let nxt = child[node][li];
            node = if nxt < 0 {
                let id = child.len();
                child.push([-1i32; TR_CH]); is_word.push(false);
                child[node][li] = id as i32;
                id
            } else { nxt as usize };
        }
        is_word[node] = true;
        words.insert(k);
    }
    Dict { words, prefixes, child, is_word }
}

impl Dict {
    // Does there exist a complete word whose letter at position i is in masks[i] (bit (letter-1) set)?
    fn pattern_word(&self, masks: &[u32]) -> bool { self.pm(0, masks, 0, true) }
    // Does there exist a word with PREFIX matching masks (i.e. trie path of len masks.len() exists)?
    fn pattern_prefix(&self, masks: &[u32]) -> bool { self.pm(0, masks, 0, false) }
    fn pm(&self, node: usize, masks: &[u32], i: usize, need_word: bool) -> bool {
        if i == masks.len() { return if need_word { self.is_word[node] } else { true }; }
        let mut m = masks[i];
        let row = &self.child[node];
        while m != 0 {
            let b = m.trailing_zeros();      // letter-1
            m &= m - 1;
            let c = row[(b + 1) as usize];
            if c >= 0 && self.pm(c as usize, masks, i + 1, need_word) { return true; }
        }
        false
    }
}

// solver state during DFS
struct Solver<'a> {
    inst: &'a Inst,
    dict: &'a Dict,
    grid: Vec<i16>,
    mandatory: Vec<usize>,      // cells that are always active (preplaced + scoring-stub positions)
    deferred: Vec<bool>,        // free-column stub cells: skipped in phase 1, assigned whole-word last
    free_cols: Vec<usize>,      // scoring-column indices that are isolated (no adjacent scoring col)
    used: Vec<i64>,             // tiles used per code (incremental)
    overflow: i64,              // sum of per-code (used-counts) over codes where used>counts == blanks needed
    nodes: u64,
    rowhist: Vec<u64>,
    always_conn: bool,
    iso_cols: Vec<usize>,       // isolated scoring columns (no adjacent scoring col): assigned EAGERLY
                                // whole-word at the TOP of the search (phase 0) so their large
                                // word-domains are factored to one branch point instead of being
                                // re-multiplied through the interleaved bridge search.
    eager_iso: bool,
    // ----- score-maximization mode -----
    maxscore: bool,             // if true, run() maximizes grossV - penalty instead of deciding
    best: i64,                  // best score strictly greater than the floor found so far (= floor init)
    col_committed: Vec<bool>,   // per scoring col: all its stub cells assigned (word determined)
    committed_gross: i64,       // sum of chosen-word gross over committed columns
    remaining_best: i64,        // sum of col_ub over NOT-yet-committed columns (UB term)
    col_ub: Vec<i64>,           // per col: best gross among candidate words consistent with its partial
                                // stub so far (= scoring_best when untouched); tightens the UB as prefixes
                                // get fixed. For committed columns this is its chosen gross.
    node_cap: u64,              // diagnostic: abort the search after this many nodes (0 = no cap)
    no_ub: bool,                // diagnostic: disable the gross-floor UB prune (soundness cross-check)
    seen_buf: Vec<u32>,         // reusable BFS visited buffer for sealed_ok (gen-stamped, alloc-free)
    seen_gen: u32,
    bfs_stack: Vec<usize>,      // reusable BFS stack for sealed_ok
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
    fn run(&mut self) -> bool {
        if self.maxscore { self.maximize(); return false; }  // result reported via self.best in main
        if self.eager_iso && !self.iso_cols.is_empty() { self.dfs_iso(0) } else { self.dfs(0) }
    }

    // ===== SCORE MAXIMIZATION =====================================================================
    // Maximize (sum of chosen-word vertical gross scores) - (blank penalty), over all LEGAL CONNECTED
    // boards for the fixed length-vector. Same model as 31_length_level.inner_best_legal.
    //
    // STRATEGY (rising-floor decisions, like inner_best_legal's `obj>=floor+1` loop): treat each call as
    // a DECISION "is there a legal connected board whose score strictly beats self.best?". dfs_score
    // STOPS (returns true) at the first such board, recording its score -> self.best ratchets up. Re-run
    // until no board beats best (returns false) -> best is the proven maximum. This is far faster than
    // exhaustively searching for the best leaf: each decision stops at the first feasible improver, and
    // the gross-floor UB prune (committed+remaining_best <= best) makes the final "nothing beats it"
    // proof a fast pruned-infeasibility search (the decision solver's strength), instead of enumerating
    // the whole bridge subtree under every committed column set.
    fn maximize(&mut self) {
        loop {
            let n0 = self.nodes;
            // reset per-attempt search state (grid/budget are restored by the DFS unwind; col_ub/
            // remaining_best/committed are all back to base because dfs_score fully unwinds on return).
            let found = self.dfs_score(0);
            if std::env::var("MAXVERB").is_ok() {
                eprintln!("  [iter] best={} found={} rem_best={} committed={} nodes_delta={}",
                    self.best, found, self.remaining_best, self.committed_gross, self.nodes - n0);
            }
            if !found { break; }   // no board strictly beats self.best -> proven optimum (= self.best)
        }
    }

    // Returns true as soon as a legal connected board with score > self.best is found (and sets best to
    // that score). Returns false if the whole tree is exhausted without beating best.
    fn dfs_score(&mut self, pos: usize) -> bool {
        self.nodes += 1;
        if self.nodes % 20_000_000 == 0 {
            eprintln!("  nodes={}M best={} committed={} rem_best={} rowhist={:?}",
                self.nodes / 1_000_000, self.best, self.committed_gross, self.remaining_best, self.rowhist);
        }
        if self.node_cap > 0 && self.nodes >= self.node_cap { return false; }   // diagnostic abort
        // UB prune: nothing reachable below can STRICTLY beat the current floor (penalty>=0 so score
        // <= committed+remaining_best).
        if !self.no_ub && self.committed_gross + self.remaining_best <= self.best { return false; }
        let w = self.inst.w; let h = self.inst.h; let n = w * h;
        let mut id = pos;
        while id < n && self.grid[id] != -1 { id += 1; }
        if id >= n { return self.score_leaf(); }
        let x = id % w; let y = id / w;
        self.rowhist[y] += 1;
        let kind = self.inst.kind[id];
        if kind == 1 {
            let si = self.inst.scol_of[id] as usize;
            let col = self.inst.scoring_cols[si];
            let posn = y - 1;
            let len = self.inst.scoring_len[si];
            // candidate letters at this cell + the best gross of any consistent word using that letter
            // (for descending ordering -> find a strong incumbent fast, sharpening the B&B floor).
            let mut cand: Vec<(u8, i64)> = Vec::new();   // (letter, best-consistent-gross via this letter)
            'words: for (wi, wd) in self.inst.scoring_words[si].iter().enumerate() {
                for r in 1..len {
                    let cid = idx(col, r, w);
                    let g = self.grid[cid];
                    if g > 0 && (wd[r - 1] as i16) != g { continue 'words; }
                }
                let l = wd[posn];
                let g = self.inst.scoring_gross[si][wi];
                if let Some(e) = cand.iter_mut().find(|e| e.0 == l) { if g > e.1 { e.1 = g; } }
                else { cand.push((l, g)); }
            }
            cand.sort_by(|a, b| b.1.cmp(&a.1));          // high-gross letters first
            let prev_ub = self.col_ub[si];
            for (l, _) in cand {
                if !self.place_ok(x, y, l) { continue; }
                if !self.add_letter(l as usize) { self.rm_letter(l as usize); continue; }
                self.grid[id] = l as i16;
                // tighten this column's UB to the best gross consistent with the now-extended prefix.
                let new_ub = self.col_best_consistent(si, col);
                self.remaining_best += new_ub - prev_ub;
                self.col_ub[si] = new_ub;
                let committed = self.commit_if_col_done(si, col);
                let hit = self.sealed_ok(id) && self.dfs_score(id + 1);
                self.uncommit(si, committed);
                self.remaining_best += prev_ub - self.col_ub[si];
                self.col_ub[si] = prev_ub;
                self.grid[id] = -1;
                self.rm_letter(l as usize);
                if hit { return true; }
            }
            false
        } else {
            // bridge cell: EMPTY then letters
            self.grid[id] = 0;
            if self.closed_runs_ok(x, y) && self.sealed_ok(id) && self.dfs_score(id + 1) {
                self.grid[id] = -1; return true;
            }
            self.grid[id] = -1;
            for l in 1..=self.inst.alpha as i16 {
                if !self.place_ok(x, y, l as u8) { continue; }
                if !self.add_letter(l as usize) { self.rm_letter(l as usize); continue; }
                self.grid[id] = l;
                let hit = self.sealed_ok(id) && self.dfs_score(id + 1);
                self.grid[id] = -1;
                self.rm_letter(l as usize);
                if hit { return true; }
            }
            false
        }
    }

    // SEALED-CELL connectivity prune (sound, for score maximization's deep-bridge tail). Row-major fill
    // means when we decide cell `id`=(x,y), the cell directly ABOVE it, (x,y-1)=s, now has all four
    // neighbours decided -> it is SEALED. If s is active, it must ultimately join the root component.
    // OPTIMISTIC reachability: flood from s through cells that are decided-active (idx<=id, grid>0) OR
    // still-undecided & not-forced-empty (idx>id, grid!=0, i.e. could become active). If even this
    // most-generous flood cannot reach the root, NO completion can connect s -> prune. Sound: undecided
    // cells are treated as freely active, so we never prune a configuration that could still connect.
    // Tight in practice because undecided cells all lie at/after the row-major frontier (current row to
    // the right, or below) -- a deep active cell walled off above by decided-empty cells is caught.
    fn sealed_ok(&mut self, id: usize) -> bool {
        let w = self.inst.w; let h = self.inst.h;
        if id < w { return true; }                 // no cell above
        let s = id - w;                            // the just-sealed cell (x, y-1)
        if self.grid[s] <= 0 { return true; }      // sealed cell empty -> nothing to connect
        let root = self.mandatory[0];
        if s == root { return true; }
        self.seen_gen = self.seen_gen.wrapping_add(1);
        let g = self.seen_gen;
        self.bfs_stack.clear();
        self.bfs_stack.push(s); self.seen_buf[s] = g;
        // traversable = decided-active (idx<=id, grid>0) OR undecided-potential (idx>id, not forced-empty)
        while let Some(p) = self.bfs_stack.pop() {
            let px = p % w; let py = p / w;
            macro_rules! visit { ($q:expr) => {{ let q = $q;
                if self.seen_buf[q] != g {
                    let t = if q <= id { self.grid[q] > 0 } else { self.grid[q] != 0 };
                    if t { if q == root { return true; } self.seen_buf[q] = g; self.bfs_stack.push(q); }
                }
            }}; }
            if px > 0 { visit!(p - 1); }
            if px + 1 < w { visit!(p + 1); }
            if py > 0 { visit!(p - w); }
            if py + 1 < h { visit!(p + w); }
        }
        false                                       // root unreachable even optimistically -> doomed
    }

    // Best gross over candidate words of column si consistent with its current partial stub (>0 cells).
    fn col_best_consistent(&self, si: usize, col: usize) -> i64 {
        let w = self.inst.w;
        let len = self.inst.scoring_len[si];
        let mut best = i64::MIN;
        'words: for (wi, wd) in self.inst.scoring_words[si].iter().enumerate() {
            for r in 1..len {
                let g = self.grid[idx(col, r, w)];
                if g > 0 && (wd[r - 1] as i16) != g { continue 'words; }
            }
            let gr = self.inst.scoring_gross[si][wi];
            if gr > best { best = gr; }
        }
        if best == i64::MIN { 0 } else { best }
    }

    // After assigning a stub cell of column si, if ALL its stub cells are now assigned, the word is
    // determined: commit its gross and remove the column from remaining_best (its col_ub already equals
    // the chosen word's gross, since the full prefix pins exactly one word). Returns Some(gross) so
    // uncommit can undo exactly.
    #[inline]
    fn commit_if_col_done(&mut self, si: usize, col: usize) -> Option<i64> {
        let w = self.inst.w;
        let len = self.inst.scoring_len[si];
        for r in 1..len { if self.grid[idx(col, r, w)] <= 0 { return None; } }
        let g = self.col_ub[si];                  // = chosen word's gross (full prefix pins one word)
        self.col_committed[si] = true;
        self.committed_gross += g;
        self.remaining_best -= self.col_ub[si];
        Some(g)
    }
    #[inline]
    fn uncommit(&mut self, si: usize, committed: Option<i64>) {
        if let Some(g) = committed {
            self.col_committed[si] = false;
            self.committed_gross -= g;
            self.remaining_best += self.col_ub[si];
        }
    }

    // At a complete board: if legal (all runs valid, connected, budget feasible) and its score (gross -
    // minimal blank penalty) STRICTLY beats best, record it and return true (improver found -> unwind).
    // Otherwise return false (keep searching; e.g. a high-gross board whose penalty drags it <= best).
    fn score_leaf(&mut self) -> bool {
        if !self.leaf_ok() { return false; }
        let penalty = self.min_blank_penalty();
        let score = self.committed_gross - penalty;
        if score > self.best { self.best = score; return true; }
        false
    }

    // Minimum blank penalty for the CURRENT full board. For each over-used letter code we MUST blank
    // (used-count) cells of that code; blanking a bridge cell is free, a scoring-stub cell costs its
    // face value. So per code: penalty += face[code] * max(0, overflow[code] - bridge_cells[code]).
    // Codes are independent (a blank for code X sits on a cell holding X) -> this greedy is optimal and
    // matches CP-SAT's penalty minimization. (leaf_ok already verified total overflow <= blanks.)
    fn min_blank_penalty(&self) -> i64 {
        let w = self.inst.w;
        let a = self.inst.alpha;
        let mut used = vec![0i64; a + 1];
        let mut bridge = vec![0i64; a + 1];    // bridge cells holding each code (free to blank)
        for id in 0..self.grid.len() {
            let g = self.grid[id];
            if g > 0 {
                used[g as usize] += 1;
                if self.inst.kind[id] == 2 { bridge[g as usize] += 1; }
            }
        }
        let _ = w;
        let mut penalty = 0i64;
        for c in 1..=a {
            let overflow = used[c] - self.inst.counts[c];
            if overflow > 0 {
                let on_stub = overflow - bridge[c];     // must blank this many STUB cells of code c
                if on_stub > 0 { penalty += on_stub * self.inst.scores[c]; }
            }
        }
        penalty
    }

    // PHASE 0 (eager): assign each ISOLATED scoring column a whole candidate word, recursing over the
    // isolated columns, then hand off to the interleaved row-major DFS (which skips the now-filled
    // cells). SOUND: an isolated column has bridge (or edge) neighbours only, so its cells form no
    // horizontal run until the adjacent bridge is decided as a letter -- so committing the column word
    // here can neither falsely accept nor falsely reject; the later place_ok on that bridge validates
    // the cross-word. Doing this FIRST factors the big word-domains (e.g. col10: 562 words) to a single
    // top-level branch instead of re-multiplying them under every partial bridge assignment.
    fn dfs_iso(&mut self, j: usize) -> bool {
        if j == self.iso_cols.len() { return self.dfs(0); }
        self.nodes += 1;
        let si = self.iso_cols[j];
        let col = self.inst.scoring_cols[si];
        let len = self.inst.scoring_len[si];
        let nwords = self.inst.scoring_words[si].len();
        for wi in 0..nwords {
            let word = self.inst.scoring_words[si][wi].clone();
            let mut bok = true;
            for &l in &word { if !self.add_letter(l as usize) { bok = false; break; } }
            if !bok { for &l in &word { self.rm_letter(l as usize); } continue; }
            for (k, &l) in word.iter().enumerate() { self.grid[idx(col, k + 1, self.inst.w)] = l as i16; }
            let mut ok = true;
            for k in 0..word.len() { if !self.place_ok(col, k + 1, word[k]) { ok = false; break; } }
            if ok && self.dfs_iso(j + 1) { return true; }
            for k in 1..len { self.grid[idx(col, k, self.inst.w)] = -1; }
            for &l in &word { self.rm_letter(l as usize); }
        }
        false
    }

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
        if self.nodes % 20_000_000 == 0 { eprintln!("  nodes={}M rowhist={:?}", self.nodes / 1_000_000, self.rowhist); }
        let w = self.inst.w; let h = self.inst.h; let n = w * h;
        // find next unassigned cell in row-major from `pos`
        let mut id = pos;
        while id < n && (self.grid[id] != -1 || self.deferred[id]) { id += 1; }  // skip assigned + deferred(free)
        if id >= n {
            return self.dfs_free(0);   // phase 2: assign the isolated free columns whole-word, last
        }
        let x = id % w; let y = id / w;
        self.rowhist[y] += 1;
        if self.always_conn && !self.can_still_connect() { return false; }
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

    // PHASE 2: assign the isolated free columns whole-word, last (so their large domains don't
    // multiply the tree). Their horizontal runs are determined by the now-fixed bridges; the
    // vertical is the pre-validated stub. place_ok gives left-anchored prefix/closure pruning;
    // leaf_ok is the final full check.
    fn dfs_free(&mut self, j: usize) -> bool {
        self.nodes += 1;
        if j == self.free_cols.len() { return self.leaf_ok(); }
        let si = self.free_cols[j];
        let col = self.inst.scoring_cols[si];
        let len = self.inst.scoring_len[si];
        let nwords = self.inst.scoring_words[si].len();
        for wi in 0..nwords {
            let word = self.inst.scoring_words[si][wi].clone();
            let mut bok = true;
            for &l in &word { if !self.add_letter(l as usize) { bok = false; break; } }
            if !bok { for &l in &word { self.rm_letter(l as usize); } continue; }
            for (k, &l) in word.iter().enumerate() { self.grid[idx(col, k + 1, self.inst.w)] = l as i16; }
            let mut ok = true;
            for k in 0..word.len() { if !self.place_ok(col, k + 1, word[k]) { ok = false; break; } }
            if ok && self.dfs_free(j + 1) { return true; }
            for k in 1..len { self.grid[idx(col, k, self.inst.w)] = -1; }
            for &l in &word { self.rm_letter(l as usize); }
        }
        false
    }

    // prefix-check pruning: placing letter at (x,y), the assigned-contiguous H run ending here and
    // V run ending here must be prefixes of some word (they may extend right/down later).
    // The HORIZONTAL check additionally looks RIGHT through forced-active cells (placed letters and
    // active scoring-stub cells, whose letters are restricted to their word-domain), so a placement
    // that cannot complete a valid cross-word with the forced right neighbours is pruned now
    // (forward checking via per-cell domain masks).
    fn place_ok(&mut self, x: usize, y: usize, l: u8) -> bool {
        let w = self.inst.w; let h = self.inst.h;
        // horizontal forced span [sx..e]: left = placed letters, then this cell, then right through
        // FORCED-ACTIVE cells (placed letters OR active scoring-stub cells) until a cell that can be
        // empty (bridge undecided / forced-empty / edge) -- the closure boundary.
        let mut sx = x;
        while sx > 0 && self.grid[idx(sx - 1, y, w)] > 0 { sx -= 1; }
        let mut masks: [u32; 8] = [0; 8];
        let mut mlen = 0usize;
        let mut bad = false;
        for cx in sx..x { masks[mlen] = bit(self.grid[idx(cx, y, w)] as u8); mlen += 1; }
        masks[mlen] = bit(l); mlen += 1;
        // extend right through forced-active cells
        let mut ex = x + 1;
        while ex < w {
            let cid = idx(ex, y, w);
            let g = self.grid[cid];
            if g > 0 { if mlen >= 8 { bad = true; break; } masks[mlen] = bit(g as u8); mlen += 1; ex += 1; }
            else if g == -1 && self.inst.kind[cid] == 1 {            // unplaced active scoring-stub cell
                if mlen >= 8 { bad = true; break; } masks[mlen] = self.inst.cell_mask[cid]; mlen += 1; ex += 1;
            } else { break; }                                        // stopper: can-be-empty cell or edge
        }
        if bad { return false; }   // forced run already exceeds hmax -> illegal
        if mlen >= 2 {
            // run can close at e iff the stopper (ex) can be empty / is the edge; it ALWAYS can here
            // because we stopped at a non-forced-active cell. It can EXTEND iff the stopper can be active.
            let closes = ex == w || !self.inst.can_active[idx(ex, y, w)];
            let extends = ex < w && self.inst.can_active[idx(ex, y, w)];
            // need: (closes -> a word of this exact length matches) AND/OR (extends -> a prefix matches)
            let ms = &masks[..mlen];
            if closes && extends {
                // closure boundary is a bridge: either close (word) or extend (prefix). Prefix subsumes word.
                if !self.dict.pattern_prefix(ms) { return false; }
            } else if closes {
                if !self.dict.pattern_word(ms) { return false; }
            } else {
                // extends only (shouldn't happen: stopper non-forced-active is always can_empty), be safe
                if !self.dict.pattern_prefix(ms) { return false; }
            }
        }
        // vertical: skip for scoring-stub cells (their vertical = pre-validated stub).
        if self.inst.kind[idx(x, y, w)] != 1 {
            let mut sy = y;
            while sy > 0 && self.grid[idx(x, sy - 1, w)] > 0 && self.inst.kind[idx(x, sy - 1, w)] != 1 { sy -= 1; }
            let mut vk = 1u64; let mut vlen = 0usize;
            for cy in sy..y { vk = key_push(vk, self.grid[idx(x, cy, w)] as u8); vlen += 1; }
            vk = key_push(vk, l); vlen += 1;
            if vlen >= 2 {
                let v_closes = y + 1 == h || self.grid[idx(x, y + 1, w)] == 0 || self.inst.kind[idx(x, y + 1, w)] == 1;
                if v_closes { if !self.dict.words.contains(&vk) { return false; } }
                else if !self.dict.prefixes.contains(&vk) { return false; }
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
            if run.len() >= 2 && !self.dict.words.contains(&key_of(&run)) { return false; }
        }
        // vertical run ending at y-1 in col x (only validate NON-scoring columns here; scoring handled by word)
        if y > 0 && self.grid[idx(x, y - 1, w)] > 0 && self.inst.kind[idx(x, y - 1, w)] != 1 {
            let mut run = Vec::new(); let mut cy = y as i64 - 1;
            while cy >= 0 {
                let id = idx(x, cy as usize, w);
                if self.grid[id] > 0 && self.inst.kind[id] != 1 { run.push(self.grid[id] as u8); cy -= 1; } else { break; }
            }
            run.reverse();
            if run.len() >= 2 && !self.dict.words.contains(&key_of(&run)) { return false; }
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
                    if run.len() >= 2 && !self.dict.words.contains(&key_of(&run)) { return false; }
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
                    if run.len() >= 2 && !self.dict.words.contains(&key_of(&run)) { return false; }
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
    // --maxscore [floor]: score-maximization mode. Returns the MAX legal vertical score, or "LE floor"
    // if nothing beats `floor`. floor defaults to -1 (so any legal board reports its score). The floor
    // seeds branch-and-bound: a node is pruned when its UB (committed_gross + remaining_best) <= best.
    let maxscore = args.iter().any(|a| a == "--maxscore");
    let floor: i64 = if maxscore {
        args.iter().position(|a| a == "--maxscore")
            .and_then(|i| args.get(i + 1)).and_then(|s| s.parse().ok()).unwrap_or(-1)
    } else { -1 };
    let inst = parse(path);
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
    // free columns = scoring columns with NO adjacent scoring column (isolated -> coupled only via
    // bridges). Defer their stub cells to phase 2 so their large domains don't multiply the search.
    let scol_set: HashSet<usize> = inst.scoring_cols.iter().cloned().collect();
    let is_isolated = |si: usize| { let c = inst.scoring_cols[si];
        !((c > 0 && scol_set.contains(&(c - 1))) || (c + 1 < inst.w && scol_set.contains(&(c + 1)))) };
    let mut free_cols: Vec<usize> = (0..inst.scoring_cols.len()).filter(|&si| is_isolated(si)).collect();
    // isolated scoring columns to assign EAGERLY (whole-word, top of search), largest-domain LAST so the
    // smaller domains commit first and prune the bag before the big column branches.
    let mut iso_cols: Vec<usize> = (0..inst.scoring_cols.len()).filter(|&si| is_isolated(si)).collect();
    iso_cols.sort_by_key(|&si| inst.scoring_words[si].len());
    // NOTE: free-column deferral is now OFF by default. With the forward-checking horizontal
    // cross-check (place_ok extends right/left through forced-active scoring cells using their
    // domain masks), keeping ALL scoring columns IN the interleaved row-major search prunes the
    // bridge cells dramatically -- deferring those columns removes the forced neighbours that make
    // the cross-check bite, so it HURTS badly (small N=11 vec: 23k nodes interleaved vs >1.4B
    // deferred). Opt back in with DEFER=1 only for experiments.
    if std::env::var("DEFER").is_err() { free_cols.clear(); }
    else if free_cols.len() == inst.scoring_cols.len() { free_cols.clear(); }
    let free_col_pos: HashSet<usize> = free_cols.iter().map(|&si| inst.scoring_cols[si]).collect();
    let deferred: Vec<bool> = (0..inst.w * inst.h)
        .map(|id| inst.kind[id] == 1 && free_col_pos.contains(&(id % inst.w))).collect();
    eprintln!("free (isolated) scoring columns: {:?}", free_cols.iter().map(|&si| inst.scoring_cols[si]).collect::<Vec<_>>());
    let mut used = vec![0i64; inst.alpha + 1];
    for &g in &inst.grid0 { if g > 0 { used[g as usize] += 1; } }
    let mut overflow = 0i64;
    for c in 1..=inst.alpha { if used[c] > inst.counts[c] { overflow += used[c] - inst.counts[c]; } }
    // EAGER iso assignment is OFF by default: committing an isolated column's whole word at the TOP
    // of the search forces the entire coupled-block+bridge subtree to be (nearly) re-solved for each
    // of that column's candidate words (e.g. 562 for a len-9 col10), since connectivity/budget don't
    // distinguish them early -- measured strictly worse (a 0.01s vector -> >60s). Opt in with EAGER=1.
    let eager_iso = std::env::var("EAGER").is_ok() && std::env::var("DEFER").is_err();
    eprintln!("eager isolated scoring columns: {:?}", iso_cols.iter().map(|&si| inst.scoring_cols[si]).collect::<Vec<_>>());
    let ncols = inst.scoring_cols.len();
    let remaining_best: i64 = inst.scoring_best.iter().sum();
    let col_ub = inst.scoring_best.clone();
    let mut solver = Solver { inst: &inst, dict: &dict, grid, mandatory, deferred, free_cols, used,
        overflow, nodes: 0, rowhist: vec![0u64; inst.h], always_conn: std::env::var("ACONN").is_ok(),
        iso_cols, eager_iso,
        maxscore, best: floor, col_committed: vec![false; ncols], committed_gross: 0, remaining_best, col_ub,
        node_cap: std::env::var("MAXNODES").ok().and_then(|s| s.parse().ok()).unwrap_or(0),
        no_ub: std::env::var("NOUB").is_ok(),
        seen_buf: vec![0u32; inst.w * inst.h], seen_gen: 0, bfs_stack: Vec::with_capacity(inst.w * inst.h) };
    let t = std::time::Instant::now();
    let sat = solver.run();
    let dt = t.elapsed().as_secs_f64();
    if std::env::var("ROWHIST").is_ok() {
        eprintln!("rowhist: {:?}", solver.rowhist);
    }
    if maxscore {
        if solver.best > floor {
            println!("MAX {} nodes={} time={:.3}s", solver.best, solver.nodes, dt);
        } else {
            println!("LE {} nodes={} time={:.3}s", floor, solver.nodes, dt);
        }
    } else {
        println!("{} nodes={} time={:.3}s", if sat { "SAT" } else { "UNSAT" }, solver.nodes, dt);
    }
}
