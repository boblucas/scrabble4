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
    Inst { w, h, alpha, blanks, counts, grid0, kind, scol_of, scoring_cols, scoring_len, scoring_words,
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
        if self.eager_iso && !self.iso_cols.is_empty() { self.dfs_iso(0) } else { self.dfs(0) }
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
    let mut solver = Solver { inst: &inst, dict: &dict, grid, mandatory, deferred, free_cols, used, overflow, nodes: 0, rowhist: vec![0u64; inst.h], always_conn: std::env::var("ACONN").is_ok(), iso_cols, eager_iso };
    let t = std::time::Instant::now();
    let sat = solver.run();
    let dt = t.elapsed().as_secs_f64();
    if std::env::var("ROWHIST").is_ok() {
        eprintln!("rowhist: {:?}", solver.rowhist);
    }
    println!("{} nodes={} time={:.3}s", if sat { "SAT" } else { "UNSAT" }, solver.nodes, dt);
}
