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
    scoring_wm: Vec<i64>,            // per scoring col: row-0 WORD multiplier (4th SCOL token,
                                     // default 1 for legacy files).  The vertical word's multiplier
                                     // applies to ALL its cells, so blanking a stub cell costs
                                     // value * wm -- the blank penalty must be wm-weighted.
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
    let mut scoring_wm: Vec<i64> = Vec::new();
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
                // optional 4th token: the column's row-0 word multiplier (blank-penalty weight);
                // legacy files omit it -> 1 (old face-value semantics preserved on old inputs).
                let wm: i64 = it.next().and_then(|t| t.parse().ok()).unwrap_or(1);
                scoring_cols.push(col); scoring_len.push(len); scoring_wm.push(wm);
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
    build_inst(w, h, alpha, blanks, counts, scores, &preplaced, &nonscoring,
               scoring_cols, scoring_len, scoring_wm, scoring_words, scoring_gross)
}

// Shared instance assembly (grid kinds, per-cell domain masks, per-col bests) -- used by both the
// per-vector instance-file path (parse) and the base-file path (inst_from_base).
#[allow(clippy::too_many_arguments)]
fn build_inst(w: usize, h: usize, alpha: usize, blanks: i64, counts: Vec<i64>, scores: Vec<i64>,
              preplaced: &[(usize, usize, i16)], nonscoring: &[usize],
              scoring_cols: Vec<usize>, scoring_len: Vec<usize>, scoring_wm: Vec<i64>,
              scoring_words: Vec<Vec<Vec<u8>>>, scoring_gross: Vec<Vec<i64>>) -> Inst {
    // build grid
    let mut grid0 = vec![0i16; w * h];   // default empty
    let mut kind = vec![0u8; w * h];
    let mut scol_of = vec![-1i32; w * h];
    // preplaced (row 0, non-scoring): mandatory active
    for (x, y, c) in preplaced { grid0[idx(*x, *y, w)] = *c; kind[idx(*x, *y, w)] = 0; }
    // scoring columns: stub cells unassigned (kind 1), below-stub & row0 forced empty (kind 0, val 0)
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
    for &col in nonscoring {
        for r in 1..h { let id = idx(col, r, w); grid0[id] = -1; kind[id] = 2; }
    }
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
                let si = scol_of[id] as usize;
                let r = id / w; let posn = r - 1;
                let mut m = 0u32;
                for wd in &scoring_words[si] { m |= bit(wd[posn]); }
                cell_mask[id] = m; can_active[id] = true;
            }
            _ => { cell_mask[id] = all_mask; can_active[id] = true; can_empty[id] = true; } // bridge
        }
    }
    let scoring_best: Vec<i64> = scoring_gross.iter()
        .map(|gs| gs.iter().cloned().max().unwrap_or(0)).collect();
    Inst { w, h, alpha, blanks, counts, scores, grid0, kind, scol_of, scoring_cols, scoring_len,
           scoring_words, scoring_gross, scoring_best, scoring_wm,
           cell_mask, can_active, can_empty }
}

// ---- BASE FILE: per-main-word data shared by ALL length-vectors (the --batchvec scale path) ----
// One base file replaces millions of per-vector instance files: it carries the candidate stub
// words per (scoring column, length) plus the fixed bag/scores/preplaced data; each batch line
// then only names a length-vector and the instance is assembled IN MEMORY (inst_from_base).
struct Base {
    w: usize, h: usize, hmax: usize, alpha: usize, blanks: i64,
    counts: Vec<i64>, scores: Vec<i64>,
    preplaced: Vec<(usize, usize, i16)>,
    nonscoring: Vec<usize>,
    dict_path: String,
    bcols: Vec<usize>,                                   // scoring columns, vector order
    bwm: Vec<i64>,                                       // per scoring col: row-0 word multiplier
    bylen: Vec<std::collections::HashMap<usize, (Vec<Vec<u8>>, Vec<i64>)>>,  // per col: len -> (stub words, gross)
}

fn parse_base(path: &str) -> Base {
    let mut s = String::new();
    fs::File::open(path).unwrap().read_to_string(&mut s).unwrap();
    let (mut w, mut h, mut hmax, mut alpha) = (0usize, 0usize, 8usize, 0usize);
    let mut blanks = 0i64;
    let mut counts: Vec<i64> = Vec::new();
    let mut scores: Vec<i64> = Vec::new();
    let mut preplaced: Vec<(usize, usize, i16)> = Vec::new();
    let mut nonscoring: Vec<usize> = Vec::new();
    let mut dict_path = String::new();
    let mut bcols: Vec<usize> = Vec::new();
    let mut bwm: Vec<i64> = Vec::new();
    let mut bylen: Vec<std::collections::HashMap<usize, (Vec<Vec<u8>>, Vec<i64>)>> = Vec::new();
    let mut cur_len = 0usize;
    for line in s.lines() {
        let mut it = line.split_whitespace();
        match it.next() {
            Some("DIMS") => {
                w = it.next().unwrap().parse().unwrap();
                h = it.next().unwrap().parse().unwrap();
                hmax = it.next().unwrap().parse().unwrap();
                alpha = it.next().unwrap().parse().unwrap();
                blanks = it.next().unwrap().parse().unwrap();
                counts = vec![0; alpha + 1]; scores = vec![0; alpha + 1];
            }
            Some("COUNTS") => for tok in it {
                let mut p = tok.split(':');
                let c: usize = p.next().unwrap().parse().unwrap();
                let n: i64 = p.next().unwrap().parse().unwrap();
                if c < counts.len() { counts[c] = n; }
            },
            Some("SCORES") => for tok in it {
                let mut p = tok.split(':');
                let c: usize = p.next().unwrap().parse().unwrap();
                let n: i64 = p.next().unwrap().parse().unwrap();
                if c < scores.len() { scores[c] = n; }
            },
            Some("PREPLACED") => for tok in it {
                let p: Vec<&str> = tok.split(',').collect();
                preplaced.push((p[0].parse().unwrap(), p[1].parse().unwrap(), p[2].parse().unwrap()));
            },
            Some("NONSCORING") => for tok in it { nonscoring.push(tok.parse().unwrap()); },
            Some("DICT") => dict_path = it.next().unwrap().to_string(),
            Some("BCOL") => {
                let col: usize = it.next().unwrap().parse().unwrap();
                let wm: i64 = it.next().unwrap().parse().unwrap();
                bcols.push(col); bwm.push(wm);
                bylen.push(std::collections::HashMap::new());
            }
            Some("BLEN") => { cur_len = it.next().unwrap().parse().unwrap();
                              bylen.last_mut().unwrap().insert(cur_len, (Vec::new(), Vec::new())); }
            Some("WORDV") => {
                let g: i64 = it.next().unwrap().parse().unwrap();
                let v: Vec<u8> = it.map(|t| t.parse().unwrap()).collect();
                let e = bylen.last_mut().unwrap().get_mut(&cur_len).unwrap();
                e.0.push(v); e.1.push(g);
            }
            _ => {}
        }
    }
    Base { w, h, hmax, alpha, blanks, counts, scores, preplaced, nonscoring, dict_path,
           bcols, bwm, bylen }
}

// Assemble the per-vector instance from the base.  None if a column has no candidate of its length.
fn inst_from_base(b: &Base, lvec: &[usize]) -> Option<Inst> {
    let mut words: Vec<Vec<Vec<u8>>> = Vec::with_capacity(b.bcols.len());
    let mut gross: Vec<Vec<i64>> = Vec::with_capacity(b.bcols.len());
    for (ci, &l) in lvec.iter().enumerate() {
        match b.bylen[ci].get(&l) {
            Some((ws, gs)) if !ws.is_empty() => { words.push(ws.clone()); gross.push(gs.clone()); }
            _ => return None,
        }
    }
    Some(build_inst(b.w, b.h, b.alpha, b.blanks, b.counts.clone(), b.scores.clone(),
                    &b.preplaced, &b.nonscoring,
                    b.bcols.clone(), lvec.to_vec(), b.bwm.clone(), words, gross))
}

impl Inst {
    fn with_dict(self, _p: &str) -> Inst { self }   // dict loaded separately

    // Is cell (col, r) GUARANTEED empty in every legal board of this length-vector?
    // True iff: off-board, OR a scoring column that is inactive at row r (past its length / row 0).
    // A bridge (non-scoring) column is NOT guaranteed empty (it can hold a letter), so returns false.
    fn definitely_empty(&self, col: i64, r: usize) -> bool {
        if col < 0 || col as usize >= self.w { return true; }            // off-board edge
        let c = col as usize;
        let id = idx(c, r, self.w);
        // bridge cell (kind 2) can be active -> not guaranteed empty.
        if self.kind[id] == 2 { return false; }
        // preplaced active row-0 letter (kind 0, grid0>0) is active; forced-empty (kind 0, grid0==0) is empty.
        if self.kind[id] == 0 { return self.grid0[id] == 0; }
        // scoring-stub cell (kind 1) is active here -> not empty.
        false
    }

    // ARC-CONSISTENCY over adjacent scoring-column word-domains via the binary "forced 2-letter word"
    // constraint. SOUND & GLOBAL: when two adjacent scoring columns ca, cb=ca+1 are both active at a row
    // r AND the flanking cells (ca-1, r) and (cb+1, r) are GUARANTEED empty in every legal board, the
    // cells (ca,r),(cb,r) form an isolated maximal horizontal run of length 2 -> their letters MUST be a
    // valid 2-letter dict word, for EVERY legal board. So a candidate word W of column ca is viable only
    // if SOME candidate word of cb is compatible with it across all such rows (and vice versa). Removing a
    // word with no support never discards a feasible board (AC-3 only deletes provably-unsupportable
    // values), so this is sound. It captures the JOINT col-pair infeasibility the row-major letter search
    // discovers only leaf-by-leaf -- e.g. the full-height-col0 + near-full-height-col1 hard tail, where
    // NO (W0,W1) pair forms valid 2-words on all overlap rows, collapsing the domain to empty = instant UNSAT.
    //
    // Returns true if the instance is PROVEN UNSAT (some column's domain became empty). On return the
    // surviving words/gross are kept and cell_mask / scoring_best are recomputed for the search.
    fn arc_consistency(&mut self, dict: &Dict) -> bool {
        let ncols = self.scoring_cols.len();
        if ncols == 0 { return false; }
        // map column position -> scoring index
        let mut si_of_col: std::collections::HashMap<usize, usize> = std::collections::HashMap::new();
        for (si, &c) in self.scoring_cols.iter().enumerate() { si_of_col.insert(c, si); }
        // build binary constraints between adjacent scoring columns: (si_a, si_b, rows[])
        // rows = stub positions (r in 1..) where both active and an isolated 2-run is forced.
        let mut cons: Vec<(usize, usize, Vec<usize>)> = Vec::new();
        for (&ca, &sa) in si_of_col.iter() {
            let cb = ca + 1;
            if let Some(&sb) = si_of_col.get(&cb) {
                let la = self.scoring_len[sa]; let lb = self.scoring_len[sb];
                let mut rows = Vec::new();
                for r in 1..la.min(lb) {           // both active rows
                    if self.definitely_empty(ca as i64 - 1, r) && self.definitely_empty(cb as i64 + 1, r) {
                        rows.push(r);
                    }
                }
                if !rows.is_empty() { cons.push((sa, sb, rows)); }
            }
        }
        if cons.is_empty() { return false; }
        // alive[si] = bitmask-free Vec<bool> over word indices
        let mut alive: Vec<Vec<bool>> = (0..ncols)
            .map(|si| vec![true; self.scoring_words[si].len()]).collect();
        // 2-letter word membership via the dict (key_of([a,b])).
        let two_ok = |a: u8, b: u8| -> bool { dict.words.contains(&key_of(&[a, b])) };
        // does word index `wi` of column `xs` have a supporting alive word in column `ys` over `rows`?
        // `a_is_left` = true when xs is the LEFT column (ca) of the pair, so the 2-word is (x[r], y[r]).
        let has_support = |xs: usize, wi: usize, ys: usize, rows: &[usize],
                           a_is_left: bool, words: &Vec<Vec<Vec<u8>>>, alive: &Vec<Vec<bool>>| -> bool {
            let wx = &words[xs][wi];
            'cand: for (yj, wy) in words[ys].iter().enumerate() {
                if !alive[ys][yj] { continue; }
                for &r in rows {
                    let lx = wx[r - 1]; let ly = wy[r - 1];
                    let (a, b) = if a_is_left { (lx, ly) } else { (ly, lx) };
                    if !two_ok(a, b) { continue 'cand; }
                }
                return true;
            }
            false
        };
        // AC-3 worklist: each directed arc (xs <- ys) means "prune xs against ys".
        let mut queue: std::collections::VecDeque<(usize, usize, usize)> = std::collections::VecDeque::new();
        // store arcs as (xs, ys, cidx) where cidx indexes cons (to recover rows + orientation)
        for (ci, (sa, sb, _)) in cons.iter().enumerate() {
            queue.push_back((*sa, *sb, ci));
            queue.push_back((*sb, *sa, ci));
        }
        while let Some((xs, ys, ci)) = queue.pop_front() {
            let (sa, _sb, ref rows) = cons[ci];
            let a_is_left = xs == sa;          // xs is the left column of this constraint?
            let mut removed_any = false;
            for wi in 0..self.scoring_words[xs].len() {
                if !alive[xs][wi] { continue; }
                if !has_support(xs, wi, ys, rows, a_is_left, &self.scoring_words, &alive) {
                    alive[xs][wi] = false; removed_any = true;
                }
            }
            if removed_any {
                if !alive[xs].iter().any(|&b| b) { return true; }     // domain emptied -> UNSAT
                // re-enqueue arcs pointing INTO xs (neighbors must be re-checked against the shrunk xs).
                for (cj, (sa2, sb2, _)) in cons.iter().enumerate() {
                    if *sb2 == xs { queue.push_back((*sa2, *sb2, cj)); }
                    if *sa2 == xs { queue.push_back((*sb2, *sa2, cj)); }
                }
            }
        }
        // compact each column's words/gross to the survivors and recompute derived fields.
        let mut pruned = false;
        for si in 0..ncols {
            if alive[si].iter().all(|&b| b) { continue; }
            pruned = true;
            let mut nw: Vec<Vec<u8>> = Vec::new();
            let mut ng: Vec<i64> = Vec::new();
            for (wi, &a) in alive[si].iter().enumerate() {
                if a { nw.push(self.scoring_words[si][wi].clone()); ng.push(self.scoring_gross[si][wi]); }
            }
            self.scoring_words[si] = nw;
            self.scoring_gross[si] = ng;
        }
        if pruned { self.recompute_derived(); }
        false
    }

    // Recompute cell_mask (scoring-stub union) and scoring_best after the word-domains change.
    fn recompute_derived(&mut self) {
        let w = self.w;
        for id in 0..w * self.h {
            if self.kind[id] == 1 {
                let si = self.scol_of[id] as usize;
                let r = id / w; let posn = r - 1;
                let mut m = 0u32;
                for wd in &self.scoring_words[si] { m |= bit(wd[posn]); }
                self.cell_mask[id] = m;
            }
        }
        self.scoring_best = self.scoring_gross.iter()
            .map(|gs| gs.iter().cloned().max().unwrap_or(0)).collect();
    }
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
    deadline: Option<std::time::Instant>,  // sound wall-clock abort (batch mode per-instance wall)
    aborted: bool,              // search ended by node_cap/deadline, NOT exhaustion -> the caller MUST
                                // report TO/TIMEOUT, never LE/UNSAT (an aborted search proves nothing).
    no_ub: bool,                // diagnostic: disable the gross-floor UB prune (soundness cross-check)
    best_grid: Vec<i16>,        // snapshot of the grid at the current `best` board (for --emit)
    seen_buf: Vec<u32>,         // reusable BFS visited buffer for sealed_ok (gen-stamped, alloc-free)
    seen_gen: u32,
    bfs_stack: Vec<usize>,      // reusable BFS stack for sealed_ok
    // DYNAMIC per-(scoring-col, stub-position) live letter mask: union of letter (q) over the column's
    // candidate words STILL CONSISTENT with the cells already fixed in that column. Starts at the static
    // union (cell_mask); narrows as stub cells get fixed above. Used by place_ok's right-extension so the
    // horizontal cross-check sees the cell's TRUE current domain (not the loose all-words union) -- this
    // sharply prunes the adjacent-scoring-block explosion. SOUND: a narrower mask is still a relaxation of
    // the real per-cell constraint (any real completion has that cell's letter in its live domain), just
    // tighter than the static union, so no legal board is ever rejected.
    col_live_mask: Vec<Vec<u32>>,   // [si][pos] live letter mask (pos = row-1, 0..len-1)
    use_live: bool,                  // false (NOLIVE=1) -> static union mask in cross-check (A/B toggle)
    // ----- JOINT-KNAPSACK UB (Lever 3 tightener) -----
    // (DIAGUB scaffolding removed; the rowhist + knap-ub call/prune counters remain for diagnostics.)
    // The default UB (committed_gross + sum of per-column best-consistent gross) overcounts because the
    // uncommitted scoring columns SHARE the per-letter tile budget: e.g. col0 and col10 cannot BOTH reach
    // their individual best gross within the remaining tiles. At a node we recompute a SOUND tighter UB by
    // solving the small multidimensional knapsack over the UNCOMMITTED columns: pick one candidate word per
    // uncommitted column (consistent with its already-fixed stub cells), maximizing total gross subject to
    // the shared per-letter budget (counts + `blanks` overflow), starting from the tiles already used. This
    // is an upper bound on the achievable score (bridges/connectivity/horizontal cross-words only LOWER it),
    // so pruning on it is sound. It is CHEAP at the deep frontier where only 1-2 big isolated columns remain
    // uncommitted (col0, col10) -- exactly where the search explodes -- and is gated to run only when the
    // number of uncommitted columns is small. Opt in with KNAP=1 (validated); KNAPCOLS sets the column cap.
    use_knap: bool,
    knap_maxcols: usize,        // run the joint-knapsack UB only when #uncommitted columns <= this
    // scratch (reused across calls to avoid per-call allocation in the hot path): per uncommitted column,
    // the consistent (gross, delta-usage) candidate words; plus the budget snapshot, suffix bounds, the
    // running per-code extra-usage vector, and the uncommitted-column index list.
    // Each candidate word is (gross, delta-usage = (letter,count) pairs at the column's free stub positions).
    knap_words: Vec<Vec<(i64, Vec<(u8, i64)>)>>,   // reused outer buffers (cleared each call)
    knap_budget: Vec<i64>,      // remaining per-code budget snapshot (counts - used)
    knap_extra: Vec<i64>,       // running per-code extra usage during the knapsack DFS (reset each call)
    knap_suffix: Vec<i64>,      // suffix best-gross sums for the DFS bound
    knap_unc: Vec<usize>,       // uncommitted scoring-column indices
    knap_calls: u64, knap_prunes: u64,             // diagnostics
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

    // JOINT-KNAPSACK UB over the uncommitted scoring columns (see the struct field doc). Returns a SOUND
    // upper bound on (committed_gross + best achievable gross of the uncommitted columns) under the shared
    // per-letter tile budget, conditioned on the cells already fixed (in self.grid / self.used). If this is
    // <= self.best the node is pruned. Cheap when few columns are uncommitted (the deep-isolated-column
    // regime). Returns None when too many columns are uncommitted (skip -> fall back to the cheap sum UB).
    //
    // SOUNDNESS: the bound counts ONLY stub-letter usage and ignores bridge tiles, horizontal cross-words,
    // and connectivity -- all of which can only REDUCE feasibility or score. The blank-overflow term uses
    // the same per-code "used minus counts, summed, <= blanks" relaxation as leaf_ok's budget check and is
    // an under-count of the true blank penalty (it charges nothing for the blanks themselves), so the
    // bound never rejects a feasible higher-scoring board. Hence pruning on it can never discard the optimum.
    fn knap_ub(&mut self) -> Option<i64> {
        // collect uncommitted scoring columns (reuse the scratch field to avoid a per-call allocation).
        let ncols = self.inst.scoring_cols.len();
        let mut unc = std::mem::take(&mut self.knap_unc);
        unc.clear();
        for si in 0..ncols { if !self.col_committed[si] { unc.push(si); } }
        if unc.len() > self.knap_maxcols { self.knap_unc = unc; return None; }
        if unc.is_empty() { self.knap_unc = unc; return Some(self.committed_gross); }
        self.knap_calls += 1;
        // Order the uncommitted columns by ASCENDING candidate-word count so the knapsack DFS branches the
        // small, constraining domains FIRST and reaches the big isolated column (e.g. col10, ~315 words)
        // LAST -- by then the per-letter budget is mostly consumed, so col10's words are pruned by the
        // budget/suffix bound without enumerating all of them. (Order is a heuristic; soundness unaffected.)
        unc.sort_by_key(|&si| self.inst.scoring_words[si].len());
        let w = self.inst.w;
        // For each uncommitted column, build its consistent candidate words as (gross, delta-usage), where
        // delta-usage = letters at the column's NOT-YET-FIXED stub positions (the fixed positions are already
        // in self.used). Dedup by (gross, delta) is unnecessary; we just need the per-column option list.
        // Clear & reuse scratch buffers.
        for b in self.knap_words.iter_mut() { b.clear(); }
        while self.knap_words.len() < unc.len() { self.knap_words.push(Vec::new()); }
        for (k, &si) in unc.iter().enumerate() {
            let col = self.inst.scoring_cols[si];
            let len = self.inst.scoring_len[si];
            let buf = &mut self.knap_words[k];
            'words: for (wi, wd) in self.inst.scoring_words[si].iter().enumerate() {
                // consistency with fixed cells + collect delta usage at free cells
                let mut delta: Vec<(u8, i64)> = Vec::new();
                for r in 1..len {
                    let g = self.grid[idx(col, r, w)];
                    let wl = wd[r - 1];
                    if g > 0 { if (wl as i16) != g { continue 'words; } }   // fixed -> must match
                    else {                                                  // free -> contributes delta
                        if let Some(e) = delta.iter_mut().find(|e| e.0 == wl) { e.1 += 1; }
                        else { delta.push((wl, 1)); }
                    }
                }
                buf.push((self.inst.scoring_gross[si][wi], delta));
            }
            if buf.is_empty() { self.knap_unc = unc; return Some(i64::MIN); }  // no consistent word: dead node
            // sort by gross descending so the knapsack DFS finds a strong incumbent / bounds fast.
            buf.sort_by(|a, b| b.0.cmp(&a.0));
        }
        // remaining per-code budget = counts - used (can be negative if already over by blanks).
        let a = self.inst.alpha;
        for c in 0..=a { self.knap_budget[c] = 0; }
        for c in 1..=a { self.knap_budget[c] = self.inst.counts[c] - self.used[c]; }
        // suffix best-gross sums for the knapsack DFS UB (reuse the scratch field).
        let m = unc.len();
        let mut suffix = std::mem::take(&mut self.knap_suffix);
        suffix.clear(); suffix.resize(m + 1, 0);
        for k in (0..m).rev() {
            let cb = self.knap_words[k].iter().map(|e| e.0).max().unwrap_or(0);
            suffix[k] = suffix[k + 1] + cb;
        }
        // current per-code overflow already consumed (used > counts) eats into blanks.
        let mut base_over = 0i64;
        for c in 1..=a { if self.used[c] > self.inst.counts[c] { base_over += self.used[c] - self.inst.counts[c]; } }
        // We only need to know whether the uncommitted columns can add ENOUGH gross to BEAT self.best
        // (the node is pruned iff committed_gross + max_additional <= best). So search as a DECISION:
        // does a feasible word-combo with total additional gross > thresh exist? Stop at the first one.
        // thresh = best - committed_gross. (penalty>=0, so additional > thresh is necessary to beat best.)
        let thresh = self.best - self.committed_gross;
        // branch over uncommitted columns; track extra per-code usage (reuse scratch; reset to 0).
        let mut extra = std::mem::take(&mut self.knap_extra);
        extra.clear(); extra.resize(a + 1, 0);
        let blanks = self.inst.blanks;
        // Returns true as soon as a feasible combo with cur_g + (rest) > thresh is found (improver exists).
        // `cur_over` = current overflow beyond counts given base used + extra so far.
        // NOTE: iterate exactly `m` (= number of uncommitted columns) columns, NOT words.len(): the scratch
        // buffer self.knap_words may be LONGER than m from a previous call (trailing buffers are cleared/
        // empty), and treating an empty buffer as a column would make rec wrongly find no combo.
        fn rec(k: usize, m: usize, cur_g: i64, cur_over: i64, thresh: i64,
               words: &Vec<Vec<(i64, Vec<(u8, i64)>)>>, budget: &[i64], extra: &mut [i64],
               suffix: &[i64], blanks: i64) -> bool {
            if cur_g + suffix[k] <= thresh { return false; }   // even the optimistic rest can't beat thresh
            if k == m { return cur_g > thresh; }
            for &(g, ref delta) in &words[k] {
                if cur_g + g + suffix[k + 1] <= thresh { break; }   // sorted desc -> no later word better
                // apply delta, compute overflow change
                let mut d_over = 0i64;
                for &(l, cnt) in delta {
                    let li = l as usize;
                    let before = extra[li] - budget[li];   // usage beyond budget BEFORE
                    let after = before + cnt;
                    let inc = after.max(0) - before.max(0);
                    d_over += inc; extra[li] += cnt;
                }
                let no = cur_over + d_over;
                let hit = no <= blanks
                    && rec(k + 1, m, cur_g + g, no, thresh, words, budget, extra, suffix, blanks);
                for &(l, cnt) in delta { extra[l as usize] -= cnt; }
                if hit { return true; }
            }
            false
        }
        let improver = rec(0, m, 0, base_over, thresh, &self.knap_words, &self.knap_budget,
                           &mut extra, &suffix, blanks);
        // return the scratch buffers to their fields for reuse next call.
        self.knap_unc = unc; self.knap_suffix = suffix; self.knap_extra = extra;
        // improver=true  -> some uncommitted-column word-combo beats best -> UB > best (no prune).
        // improver=false -> no feasible combo beats best -> sound UB <= best -> prune.
        if improver { Some(self.best + 1) } else { Some(self.best) }
    }

    // Returns true as soon as a legal connected board with score > self.best is found (and sets best to
    // One bookkeeping step per search node: count it and check the abort conditions (node cap /
    // wall deadline).  Returns true if the search must ABORT (caller returns false immediately;
    // `aborted` is set so the result is reported TO, never LE/UNSAT -- an abort proves nothing).
    #[inline]
    fn tick(&mut self) -> bool {
        self.nodes += 1;
        if self.nodes % 20_000_000 == 0 {
            eprintln!("  nodes={}M best={} committed={} rem_best={} rowhist={:?}",
                self.nodes / 1_000_000, self.best, self.committed_gross, self.remaining_best, self.rowhist);
        }
        if self.node_cap > 0 && self.nodes >= self.node_cap { self.aborted = true; return true; }
        if self.nodes & 0xFFF == 0 {
            if let Some(d) = self.deadline {
                if std::time::Instant::now() >= d { self.aborted = true; return true; }
            }
        }
        false
    }

    // that score). Returns false if the whole tree is exhausted without beating best.
    fn dfs_score(&mut self, pos: usize) -> bool {
        if self.tick() { return false; }
        // UB prune: nothing reachable below can STRICTLY beat the current floor (penalty>=0 so score
        // <= committed+remaining_best).
        if !self.no_ub && self.committed_gross + self.remaining_best <= self.best { return false; }
        // tighter JOINT-KNAPSACK UB (budget-coupled, see knap_ub): prunes the deep-isolated-column tail.
        if self.use_knap {
            if let Some(kub) = self.knap_ub() {
                if kub <= self.best { self.knap_prunes += 1; return false; }
            }
        }
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
                // fixing this stub cell narrows the column's live word-domain -> refresh its live masks
                // (used by place_ok's horizontal cross-check on the cells BELOW in this column).
                self.recompute_live_mask(si, col);
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
                self.recompute_live_mask(si, col);   // restore (cell now -1 again)
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

    // Recompute column si's live letter masks: for each stub position q, the union of wd[q] over the
    // column's candidate words still consistent with the cells already FIXED (>0) in this column. Called
    // after a stub cell of the column is placed/removed. SOUND (see col_live_mask doc): tighter relaxation.
    fn recompute_live_mask(&mut self, si: usize, col: usize) {
        if !self.use_live { return; }
        let w = self.inst.w;
        let len = self.inst.scoring_len[si];
        for q in 0..len - 1 { self.col_live_mask[si][q] = 0; }
        'words: for wd in &self.inst.scoring_words[si] {
            for r in 1..len {
                let g = self.grid[idx(col, r, w)];
                if g > 0 && (wd[r - 1] as i16) != g { continue 'words; }
            }
            for q in 0..len - 1 { self.col_live_mask[si][q] |= bit(wd[q]); }
        }
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
        if score > self.best { self.best = score; self.best_grid.copy_from_slice(&self.grid); return true; }
        false
    }

    // Minimum blank penalty for the CURRENT full board. For each over-used letter code we MUST blank
    // (used-count) cells of that code; blanking a bridge cell is free; blanking a scoring-STUB cell
    // loses value * wm(col) from the turn -- the vertical word's WORD multiplier (it comes from the
    // newly placed row-0 tile) applies to every cell of the word, stubs included.  (The old
    // face-value-only penalty UNDERSTATED the loss in wm>1 columns: the bouwfysicus "224" board
    // really scores 216 -- blanking the struggelden 'u' under col10's x3 costs 12, not 4.)
    // Per code: blank bridges first (free), then the CHEAPEST stub cells (smallest value*wm).
    // Codes are independent (a blank for code X sits on a cell holding X) -> greedy is optimal and
    // matches CP-SAT's penalty minimization. (leaf_ok already verified total overflow <= blanks.)
    fn min_blank_penalty(&self) -> i64 {
        let a = self.inst.alpha;
        let mut used = vec![0i64; a + 1];
        let mut bridge = vec![0i64; a + 1];    // bridge cells holding each code (free to blank)
        let mut stub_costs: Vec<Vec<i64>> = vec![Vec::new(); a + 1];   // per code: stub-cell costs
        for id in 0..self.grid.len() {
            let g = self.grid[id];
            if g > 0 {
                used[g as usize] += 1;
                match self.inst.kind[id] {
                    2 => bridge[g as usize] += 1,
                    1 => {
                        let si = self.inst.scol_of[id] as usize;
                        stub_costs[g as usize]
                            .push(self.inst.scores[g as usize] * self.inst.scoring_wm[si]);
                    }
                    _ => {}
                }
            }
        }
        let mut penalty = 0i64;
        for c in 1..=a {
            let overflow = used[c] - self.inst.counts[c];
            if overflow > 0 {
                let on_stub = overflow - bridge[c];     // must blank this many STUB cells of code c
                if on_stub > 0 {
                    let costs = &mut stub_costs[c];
                    costs.sort_unstable();
                    penalty += costs[..on_stub as usize].iter().sum::<i64>();
                }
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
        if self.tick() { return false; }
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
            self.recompute_live_mask(si, col);
            let mut ok = true;
            for k in 0..word.len() { if !self.place_ok(col, k + 1, word[k]) { ok = false; break; } }
            if ok && self.dfs_iso(j + 1) { return true; }
            for k in 1..len { self.grid[idx(col, k, self.inst.w)] = -1; }
            self.recompute_live_mask(si, col);
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
        if self.tick() { return false; }
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
                self.recompute_live_mask(si, col);   // narrow this column's live masks for cells below
                if self.dfs(id + 1) { return true; }
                self.grid[id] = -1;
                self.recompute_live_mask(si, col);   // restore
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
        if self.tick() { return false; }
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
            self.recompute_live_mask(si, col);
            let mut ok = true;
            for k in 0..word.len() { if !self.place_ok(col, k + 1, word[k]) { ok = false; break; } }
            if ok && self.dfs_free(j + 1) { return true; }
            for k in 1..len { self.grid[idx(col, k, self.inst.w)] = -1; }
            self.recompute_live_mask(si, col);
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
        // left forced span: a placed run of >= hmax(8) cells already exceeds any legal word length, so
        // the maximal forced run through (x,y) is illegal -> prune.  (Bound-check mlen like the right
        // extension does; without this the [u32;8] masks array overflows and panics, e.g. col0=1 +
        // center col5>=6 instances with a long forced horizontal span.)
        for cx in sx..x { if mlen >= 8 { bad = true; break; } masks[mlen] = bit(self.grid[idx(cx, y, w)] as u8); mlen += 1; }
        if mlen >= 8 { bad = true; } else { masks[mlen] = bit(l); mlen += 1; }
        // extend right through forced-active cells
        let mut ex = x + 1;
        while ex < w {
            let cid = idx(ex, y, w);
            let g = self.grid[cid];
            if g > 0 { if mlen >= 8 { bad = true; break; } masks[mlen] = bit(g as u8); mlen += 1; ex += 1; }
            else if g == -1 && self.inst.kind[cid] == 1 {            // unplaced active scoring-stub cell
                // use the DYNAMIC live mask (narrowed by this column's already-fixed stub cells), not the
                // static all-words union -- this is the lever that prunes the adjacent-block explosion.
                if mlen >= 8 { bad = true; break; }
                masks[mlen] = if self.use_live {
                    let si2 = self.inst.scol_of[cid] as usize; self.col_live_mask[si2][y - 1]
                } else { self.inst.cell_mask[cid] };
                mlen += 1; ex += 1;
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
    // ---- BATCH MODE: `xfill --batch LISTFILE` ----------------------------------------------------
    // LISTFILE lines: `<key> <instance_path> <floor>`.  Runs each instance in --maxscore mode with a
    // PER-INSTANCE wall (env BATCHWALL seconds, default 300; a sound abort -> "TO", never LE).  The
    // dictionary is loaded ONCE per dict path and shared -- this amortizes the ~0.1s spawn+dict cost
    // that dominates root-pruned vectors, enabling ~ms/vector over multi-million-vector bands.
    // Output: one line per item, `RES <key> <result-line>`, flushed as produced (resumable caller).
    if let Some(bi) = args.iter().position(|a| a == "--batch") {
        let listfile = &args[bi + 1];
        let wall: f64 = std::env::var("BATCHWALL").ok().and_then(|s| s.parse().ok()).unwrap_or(300.0);
        let mut dicts: std::collections::HashMap<String, Dict> = std::collections::HashMap::new();
        let data = fs::read_to_string(listfile).unwrap();
        use std::io::Write as _;
        for line in data.lines() {
            let mut it = line.split_whitespace();
            let (key, p, fl) = (it.next(), it.next(), it.next());
            if key.is_none() || p.is_none() { continue; }
            let floor: i64 = fl.and_then(|s| s.parse().ok()).unwrap_or(-1);
            let (res, _board) = solve_one(p.unwrap(), true, floor, Some(wall), &mut dicts);
            println!("RES {} {}", key.unwrap(), res);
            std::io::stdout().flush().ok();
        }
        return;
    }
    // ---- BATCHVEC MODE: `xfill --batchvec BASEFILE LISTFILE` -------------------------------------
    // The SCALE path: one BASE file (per-main-word candidate domains, see parse_base) + a list of
    // length-vectors.  LISTFILE lines: `<key> <l0> <l1> ... <l_{ncols-1}> <floor>`.  Instances are
    // assembled IN MEMORY (no per-vector files), the dict is loaded once, each item gets a sound
    // per-instance wall (BATCHWALL, default 300s; abort -> TO).  Output: `RES <key> <line>`.
    if let Some(bi) = args.iter().position(|a| a == "--batchvec") {
        let base = parse_base(&args[bi + 1]);
        let listfile = &args[bi + 2];
        let wall: f64 = std::env::var("BATCHWALL").ok().and_then(|s| s.parse().ok()).unwrap_or(300.0);
        let td = std::time::Instant::now();
        let dict = load_dict(&base.dict_path, base.hmax);
        eprintln!("dict loaded: {} words, {} prefixes, {:.2}s",
                  dict.words.len(), dict.prefixes.len(), td.elapsed().as_secs_f64());
        let ncols = base.bcols.len();
        let data = fs::read_to_string(listfile).unwrap();
        use std::io::Write as _;
        for line in data.lines() {
            let toks: Vec<&str> = line.split_whitespace().collect();
            if toks.len() != ncols + 2 { continue; }
            let key = toks[0];
            let lvec: Vec<usize> = toks[1..=ncols].iter().map(|t| t.parse().unwrap()).collect();
            let floor: i64 = toks[ncols + 1].parse().unwrap();
            let res = match inst_from_base(&base, &lvec) {
                None => "NOCAND".to_string(),
                Some(mut inst) => solve_inst(&mut inst, &dict, true, floor, Some(wall)).0,
            };
            println!("RES {} {}", key, res);
            std::io::stdout().flush().ok();
        }
        return;
    }
    // ---- SINGLE MODE (legacy stdout contract preserved) ------------------------------------------
    let path = &args[1];
    // --maxscore [floor]: score-maximization mode. Returns the MAX legal vertical score, or "LE floor"
    // if nothing beats `floor`. floor defaults to -1 (so any legal board reports its score). The floor
    // seeds branch-and-bound: a node is pruned when its UB (committed_gross + remaining_best) <= best.
    let maxscore = args.iter().any(|a| a == "--maxscore");
    let floor: i64 = if maxscore {
        args.iter().position(|a| a == "--maxscore")
            .and_then(|i| args.get(i + 1)).and_then(|s| s.parse().ok()).unwrap_or(-1)
    } else { -1 };
    let wall: Option<f64> = std::env::var("WALL").ok().and_then(|s| s.parse().ok());
    let mut dicts: std::collections::HashMap<String, Dict> = std::collections::HashMap::new();
    let (line, board) = solve_one(path, maxscore, floor, wall, &mut dicts);
    println!("{}", line);
    // --emit: print the best witnessed board (row-major letter codes, 0=empty).
    if args.iter().any(|a| a == "--emit") {
        if let Some(bg) = board {
            print!("BOARD");
            for &g in &bg { print!(" {}", if g > 0 { g } else { 0 }); }
            println!();
        }
    }
}

// Solve one instance file.  Returns (result line, best board if a witness > floor was found).
// `wall` = sound per-instance wall-clock cap: on expiry the search ABORTS and the line is
// "TO ..." (maxscore) / "TIMEOUT ..." (decision) -- never LE/UNSAT (an abort proves nothing).
fn solve_one(path: &str, maxscore: bool, floor: i64, wall: Option<f64>,
             dicts: &mut std::collections::HashMap<String, Dict>) -> (String, Option<Vec<i16>>) {
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
    if !dicts.contains_key(&dict_path) {
        let td = std::time::Instant::now();
        let d = load_dict(&dict_path, hmax);
        eprintln!("dict loaded: {} words, {} prefixes, {:.2}s",
                  d.words.len(), d.prefixes.len(), td.elapsed().as_secs_f64());
        dicts.insert(dict_path.clone(), d);
    }
    let dict = &dicts[&dict_path];
    solve_inst(&mut inst, dict, maxscore, floor, wall)
}

// The solve core shared by the instance-file path (solve_one) and the base path (--batchvec):
// AC presolve, search, sound TO-on-abort result line.
fn solve_inst(inst: &mut Inst, dict: &Dict, maxscore: bool, floor: i64,
              wall: Option<f64>) -> (String, Option<Vec<i16>>) {
    // ARC-CONSISTENCY presolve over adjacent scoring-column word-domains (the forced-2-letter-word join).
    // Sound, global; collapses the full-height adjacent-block hard tail. Opt out with NOAC=1 for A/B.
    if std::env::var("NOAC").is_err() {
        let tac = std::time::Instant::now();
        let unsat = inst.arc_consistency(dict);
        eprintln!("arc-consistency: {} surviving words/col, {:.3}s{}",
            inst.scoring_words.iter().map(|v| v.len()).collect::<Vec<_>>().iter().sum::<usize>(),
            tac.elapsed().as_secs_f64(), if unsat { " -> UNSAT (empty domain)" } else { "" });
        if unsat {
            // No legal board exists for this length-vector (AC proof -- sound, NOT an abort).
            return (if maxscore { format!("LE {} nodes=0 time=0.000s", floor) }
                    else { "UNSAT nodes=0 time=0.000s".to_string() }, None);
        }
    }
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
    // initial live masks = static union over all candidate words at each stub position (no cell fixed yet).
    let col_live_mask: Vec<Vec<u32>> = (0..ncols).map(|si| {
        let len = inst.scoring_len[si];
        let mut v = vec![0u32; len.saturating_sub(1)];
        for wd in &inst.scoring_words[si] { for q in 0..len - 1 { v[q] |= bit(wd[q]); } }
        v
    }).collect();
    let mut solver = Solver { inst: &*inst, dict, grid, mandatory, deferred, free_cols, used,
        overflow, nodes: 0, rowhist: vec![0u64; inst.h], always_conn: std::env::var("ACONN").is_ok(),
        iso_cols, eager_iso,
        maxscore, best: floor, col_committed: vec![false; ncols], committed_gross: 0, remaining_best, col_ub,
        node_cap: std::env::var("MAXNODES").ok().and_then(|s| s.parse().ok()).unwrap_or(0),
        deadline: wall.map(|s| std::time::Instant::now() + std::time::Duration::from_secs_f64(s)),
        aborted: false,
        no_ub: std::env::var("NOUB").is_ok(),
        best_grid: vec![0i16; inst.w * inst.h],
        seen_buf: vec![0u32; inst.w * inst.h], seen_gen: 0, bfs_stack: Vec::with_capacity(inst.w * inst.h),
        // DYNAMIC live-mask cross-check is OFF by default: it is SOUND and cuts nodes on small full-bag
        // cases, but on the N=11 hard tail it does NOT reduce node count (the adjacent-block explosion is
        // in same-row cells whose static union mask is already tight) while DOUBLING per-node cost
        // (recompute_live_mask is O(words) per stub placement) -> a net 2x slowdown on exactly the vectors
        // that matter. Opt in with LIVE=1 for the small/full-bag regime. (See maxturn memo.)
        col_live_mask, use_live: std::env::var("LIVE").is_ok(),
        // JOINT-KNAPSACK UB is DEFAULT-ON in --maxscore mode (validated sound: decision 26/26, score-check
        // 26/32 == baseline with the identical 6 documented full-bag-N7 timeouts and ZERO wrong values; a
        // CP-SAT-independent fuzz of 1000+ random instances found 0 disagreements vs KNAP-off). It cracks
        // the deep-isolated-col10 N=11 hard tail (LE 224 in seconds vs the prior >90s timeout) and never
        // slows the easy / AC-3 vectors. Opt out with NOKNAP=1. KNAPCOLS caps the #uncommitted columns the
        // per-node knapsack runs over (default = all scoring columns -> tightest bound).
        use_knap: maxscore && std::env::var("NOKNAP").is_err(),
        knap_maxcols: std::env::var("KNAPCOLS").ok().and_then(|s| s.parse().ok()).unwrap_or(ncols.max(1)),
        knap_words: Vec::new(), knap_budget: vec![0i64; inst.alpha + 1],
        knap_extra: Vec::new(), knap_suffix: Vec::new(), knap_unc: Vec::new(),
        knap_calls: 0, knap_prunes: 0 };
    let t = std::time::Instant::now();
    let sat = solver.run();
    let dt = t.elapsed().as_secs_f64();
    if std::env::var("ROWHIST").is_ok() {
        eprintln!("rowhist: {:?}", solver.rowhist);
    }
    if solver.use_knap {
        eprintln!("knap-ub: calls={} prunes={}", solver.knap_calls, solver.knap_prunes);
    }
    let board = if maxscore && solver.best > floor { Some(solver.best_grid.clone()) } else { None };
    // An ABORTED search (node cap / wall deadline) proves nothing: report TO/TIMEOUT, never LE/UNSAT.
    // (This also fixes the old MAXNODES footgun where a capped run printed a fake "LE".)
    let line = if solver.aborted {
        if maxscore { format!("TO {} nodes={} time={:.3}s best={}", floor, solver.nodes, dt, solver.best) }
        else { format!("TIMEOUT nodes={} time={:.3}s", solver.nodes, dt) }
    } else if maxscore {
        if solver.best > floor { format!("MAX {} nodes={} time={:.3}s", solver.best, solver.nodes, dt) }
        else { format!("LE {} nodes={} time={:.3}s", floor, solver.nodes, dt) }
    } else {
        format!("{} nodes={} time={:.3}s", if sat { "SAT" } else { "UNSAT" }, solver.nodes, dt)
    };
    (line, board)
}
