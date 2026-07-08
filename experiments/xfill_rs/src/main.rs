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
    reserve: i64,               // tiles to RESERVE (opponent must hold >=1 tile when we play): total
                                // setup tiles placed (sum used) <= sum(counts)+blanks-reserve.  Default 0
                                // = no-op (already implied by overflow<=blanks).  Set 1 for the real rule.
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
    varmax: bool,              // VARIABLE-LENGTH mode: scoring columns choose their own vertical length
                               // in one search (stub cells may be EMPTY = word ended above).  See
                               // inst_var_from_base.  Default false = byte-identical fixed-length engine.
    pinned: bool,              // PINNED-COMBO mode (--pinbatch): every scoring column has EXACTLY ONE
                               // candidate (the combo's vertical) and cells BELOW the pinned word
                               // (rows len+1..h) are legal BRIDGE cells (a separate lower run in a
                               // scoring column is a legal setup -- matches the v2 CP-SAT oracle and
                               // witness_check).  Skips arc_consistency (its adjacent-join assumes
                               // definitely-empty below-stub flanks, invalid under the widening).
                               // Default false = byte-identical legacy engine.
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
    let mut reserve = 0i64;
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
            "RESERVE" => { reserve = it.next().and_then(|t| t.parse().ok()).unwrap_or(0); }
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
    build_inst(w, h, alpha, blanks, reserve, counts, scores, &preplaced, &nonscoring,
               scoring_cols, scoring_len, scoring_wm, scoring_words, scoring_gross)
}

// Shared instance assembly (grid kinds, per-cell domain masks, per-col bests) -- used by both the
// per-vector instance-file path (parse) and the base-file path (inst_from_base).
#[allow(clippy::too_many_arguments)]
fn build_inst(w: usize, h: usize, alpha: usize, blanks: i64, reserve: i64, counts: Vec<i64>, scores: Vec<i64>,
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
                for wd in &scoring_words[si] { if wd[posn] != 0 { m |= bit(wd[posn]); } }  // 0 = empty (varmax pad)
                cell_mask[id] = m; can_active[id] = true;
            }
            _ => { cell_mask[id] = all_mask; can_active[id] = true; can_empty[id] = true; } // bridge
        }
    }
    let scoring_best: Vec<i64> = scoring_gross.iter()
        .map(|gs| gs.iter().cloned().max().unwrap_or(0)).collect();
    Inst { w, h, alpha, blanks, reserve, counts, scores, grid0, kind, scol_of, scoring_cols, scoring_len,
           scoring_words, scoring_gross, scoring_best, scoring_wm,
           cell_mask, can_active, can_empty, varmax: false, pinned: false }
}

// ---- BASE FILE: per-main-word data shared by ALL length-vectors (the --batchvec scale path) ----
// One base file replaces millions of per-vector instance files: it carries the candidate stub
// words per (scoring column, length) plus the fixed bag/scores/preplaced data; each batch line
// then only names a length-vector and the instance is assembled IN MEMORY (inst_from_base).
struct Base {
    w: usize, h: usize, hmax: usize, alpha: usize, blanks: i64, reserve: i64,
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
    let mut reserve = 0i64;
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
            Some("RESERVE") => reserve = it.next().and_then(|t| t.parse().ok()).unwrap_or(0),
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
    Base { w, h, hmax, alpha, blanks, reserve, counts, scores, preplaced, nonscoring, dict_path,
           bcols, bwm, bylen }
}

// ===== VARIABLE-LENGTH ASSEMBLY ================================================================
// Build ONE instance whose scoring columns each choose their OWN vertical length in a single search.
//
// MODEL EQUIVALENCE (the soundness crux):
//   The fixed-length sweep enumerates every length-vector v = (len[c])_c and, per v, maximizes the
//   legal-connected score over the word-choice space W(v) = X_c { length-len[c] words of col c }.
//   The variable search's per-column candidate set is the UNION over ALL lengths in the base, PLUS
//   the length-1 (bare tile, no vertical, gross 0) option.  Choosing length L for column c =
//   restricting that column to its length-L candidates and forcing rows >=L empty -- i.e. exactly a
//   point of some W(v).  Conversely every board the variable search visits assigns each column a
//   single word of SOME length, hence lies in W(v) for the v naming those lengths.  So the set of
//   boards the variable search ranges over is EXACTLY  union over v of (legal boards of W(v)),
//   therefore  varmax_MAX = max over v of fixed_MAX(v),  and  varmax LE floor  <=>  every fixed
//   length-vector is LE floor.  No board is added or dropped; only the artificial per-run length
//   pinning is removed.
//
// REPRESENTATION: stub region of column c spans rows 1..maxlen[c] (maxlen = largest length present
// in the base for that column).  A candidate of length L is stored as a `maxlen-1`-long pattern:
// letters in rows 1..L, then 0 (EMPTY) in rows L..maxlen.  Suffix-empty is automatic (each pattern
// is a real word padded with trailing zeros).  A grid value of 0 at a stub cell therefore means the
// vertical word ended above -> that cell is a genuine empty cell for connectivity / cross-words /
// budget, identical to the fixed model's forced-empty cells below a short column.
//
// The length-1 option is the all-empty pattern (no stub letters) with gross 0; it always exists.
fn inst_var_from_base(b: &Base) -> Option<Inst> {
    let ncols = b.bcols.len();
    let mut maxlen = vec![1usize; ncols];
    for ci in 0..ncols {
        for (&l, (ws, _)) in b.bylen[ci].iter() {
            if !ws.is_empty() && l > maxlen[ci] { maxlen[ci] = l; }
        }
    }
    // Per column: the union candidate set, each padded to maxlen-1 (0 = empty tail).  Includes the
    // length-1 bare-tile option (all zeros, gross 0).
    let mut words: Vec<Vec<Vec<u8>>> = Vec::with_capacity(ncols);
    let mut gross: Vec<Vec<i64>> = Vec::with_capacity(ncols);
    for ci in 0..ncols {
        let pad = maxlen[ci].saturating_sub(1);
        let mut wcol: Vec<Vec<u8>> = Vec::new();
        let mut gcol: Vec<i64> = Vec::new();
        // length-1 bare tile: gross 0, all stub cells empty.
        wcol.push(vec![0u8; pad]); gcol.push(0);
        for (&l, (ws, gs)) in b.bylen[ci].iter() {
            if l == 1 { continue; }                          // length-1 handled above (the bare tile)
            for (wi, w) in ws.iter().enumerate() {
                // w is the stub (len-1 letters); pad rows l..maxlen with 0 (empty).
                let mut p = w.clone();
                p.resize(pad, 0u8);
                wcol.push(p); gcol.push(gs[wi]);
            }
        }
        words.push(wcol); gross.push(gcol);
    }
    let lvec = maxlen.clone();   // scoring_len[c] = full stub span 1..maxlen[c]
    let mut inst = build_inst(b.w, b.h, b.alpha, b.blanks, b.reserve, b.counts.clone(),
                              b.scores.clone(), &b.preplaced, &b.nonscoring,
                              b.bcols.clone(), lvec, b.bwm.clone(), words, gross);
    inst.varmax = true;
    // In varmax a stub cell may be EMPTY (a shorter word ended above), so its static cell_mask must
    // INCLUDE the empty option for the horizontal cross-check: treat stub cells as can-be-empty and
    // never extend a forced horizontal span through an UNDECIDED one (done in place_ok via inst.varmax).
    for id in 0..inst.w * inst.h {
        if inst.kind[id] == 1 { inst.can_empty[id] = true; }
    }
    Some(inst)
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
    Some(build_inst(b.w, b.h, b.alpha, b.blanks, b.reserve, b.counts.clone(), b.scores.clone(),
                    &b.preplaced, &b.nonscoring,
                    b.bcols.clone(), lvec.to_vec(), b.bwm.clone(), words, gross))
}

// ===== PINNED-COMBO ASSEMBLY (--pinbatch) ======================================================
// One instance per COMBO: each scoring column is pinned to exactly one vertical (or the bare
// tile).  picks[ci] = None => bare (len 1, gross 0); Some((stub, gross)) => that word.
//
// RULE WIDENING vs the legacy fixed/varmax models: cells BELOW the pinned word (rows len+1..h)
// become ordinary BRIDGE cells -- a SEPARATE lower vertical run in a scoring column is a legal
// setup position (witness_check accepts it; the v2 CP-SAT oracle models it).  Row `len` stays
// forced-empty: it terminates the SCORED run (the pinned combo's identity).  Without this
// widening an LE verdict would ignore legal boards and be UNSOUND as a certificate.
fn inst_pinned_from_base(b: &Base, picks: &[Option<(Vec<u8>, i64)>]) -> Inst {
    let ncols = b.bcols.len();
    let mut words: Vec<Vec<Vec<u8>>> = Vec::with_capacity(ncols);
    let mut gross: Vec<Vec<i64>> = Vec::with_capacity(ncols);
    let mut lvec: Vec<usize> = Vec::with_capacity(ncols);
    for ci in 0..ncols {
        match &picks[ci] {
            None => { words.push(vec![Vec::new()]); gross.push(vec![0]); lvec.push(1); }
            Some((stub, g)) => {
                words.push(vec![stub.clone()]); gross.push(vec![*g]); lvec.push(stub.len() + 1);
            }
        }
    }
    let mut inst = build_inst(b.w, b.h, b.alpha, b.blanks, b.reserve, b.counts.clone(),
                              b.scores.clone(), &b.preplaced, &b.nonscoring,
                              b.bcols.clone(), lvec, b.bwm.clone(), words, gross);
    inst.pinned = true;
    let all_mask: u32 = if inst.alpha >= 26 { 0x03ff_ffff } else { (1u32 << inst.alpha) - 1 };
    for si in 0..inst.scoring_cols.len() {
        let col = inst.scoring_cols[si];
        let len = inst.scoring_len[si];
        for r in (len + 1)..inst.h {
            let id = idx(col, r, inst.w);
            inst.kind[id] = 2; inst.scol_of[id] = -1; inst.grid0[id] = -1;
            inst.cell_mask[id] = all_mask; inst.can_active[id] = true; inst.can_empty[id] = true;
        }
    }
    inst
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
                for wd in &self.scoring_words[si] { if wd[posn] != 0 { m |= bit(wd[posn]); } }
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
    placed: i64,                // total setup tiles placed = sum(used) (maintained in lockstep with used)
    max_setup: i64,             // cap: placed <= sum(counts)+blanks-reserve (opponent reserves `reserve`
                                // tiles). With reserve=0 this equals the implicit overflow<=blanks bound,
                                // so the check is a no-op -> byte-identical to the pre-reserve engine.
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
    knap_sfx2: Vec<i64>,        // budget-coupled suffix bound, flattened [k*(blanks+1)+r] (see knap_ub)
    knap_unc: Vec<usize>,       // uncommitted scoring-column indices
    // ----- INCREMENTAL CONSISTENT-WORD-SET MAINTENANCE (knap_ub rebuild speedup) -----
    // Per scoring column, the indices of candidate words still consistent with the cells already FIXED
    // in that column.  Maintained in O(survivors) on each stub-cell place/unplace (a fixed cell at row r
    // to value v keeps exactly the words with wd[r-1]==v -- the SAME consistency test the knap_ub rebuild
    // ran over the FULL domain every node).  knap_ub then iterates only this surviving list (per uncommitted
    // column) instead of rescanning hundreds of words -> the dominant 63% rebuild cost drops to O(survivors).
    // VERDICT-NEUTRAL: same consistent set, same per-word delta, same knap -> identical node counts.
    // Gated on `use_inc` (default on with use_knap; INCOFF=1 falls back to the full rescan for A/B).
    use_inc: bool,
    col_consistent: Vec<Vec<u32>>,   // [si] -> live word indices consistent with fixed cells of col si
    // Undo stack: each stub-cell place that filtered a column pushes (si, removed-word-indices) so the
    // matching unplace restores the column's list exactly.  A place that fixes a committed/short column
    // (row >= its len) pushes nothing.  DFS stack discipline guarantees correct LIFO restore.
    inc_undo: Vec<(usize, Vec<u32>)>,
    inc_undo_pool: Vec<Vec<u32>>,    // reuse removed-index buffers to avoid per-place allocation
    knap_calls: u64, knap_prunes: u64,
    lorder: Vec<i16>,           // bridge-cell letter try-order; PINSHUF=<seed> permutes it (pure
                                // search ORDER: LE/UNSAT truth unchanged -- full exhaustion either
                                // way; only TO-vs-found can flip, and MAX stays witness-gated)             // diagnostics
    // ----- PROFILING (gated on env XFILL_PROF=1; zero-cost when off: the `prof` flag is checked once
    // per knap_ub call, and the Instant::now() pair is skipped entirely when prof==false) -----
    prof: bool,
    prof_knap_rebuild_ns: u128,    // time in knap_ub's per-column consistent-candidate REBUILD
    prof_knap_rec_ns: u128,        // time in knap_ub's `rec` DFS (the multiple-choice knapsack search)
    prof_knap_rec_calls: u64,      // number of top-level rec() invocations (== knap_calls that ran rec)
}

impl<'a> Solver<'a> {
    #[inline]
    fn add_letter(&mut self, l: usize) -> bool {
        self.used[l] += 1;
        self.placed += 1;
        if self.used[l] > self.inst.counts[l] { self.overflow += 1; }
        // overflow<=blanks: per-letter shortfall covered by blanks.  placed<=max_setup: reserve the
        // opponent's tile(s) -- total board (= placed + #newly-scoring) must leave `reserve` in the bag.
        self.overflow <= self.inst.blanks && self.placed <= self.max_setup
    }
    #[inline]
    fn rm_letter(&mut self, l: usize) {
        if self.used[l] > self.inst.counts[l] { self.overflow -= 1; }
        self.used[l] -= 1;
        self.placed -= 1;
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
    //
    // VARMAX SOUNDNESS: in variable-length mode an uncommitted column may choose ANY length 1..maxlen.
    // The per-column candidate list (self.inst.scoring_words[si]) is already the UNION over all lengths
    // PLUS the length-1 bare-tile (all-zeros, gross 0) option, so the knapsack ranges over exactly the
    // enlarged option set: one (length,word) per uncommitted column.  The (0,0) empty option is always
    // present (it is consistent with any partial column whose fixed cells are all empty), so the bound is
    // never lower than the true best achievable -- it stays a SOUND OVER-ESTIMATE.  A still-undecided stub
    // cell (g==-1) is NOT charged as a forced tile: only a word's REAL tail letters (wl>0) at free cells
    // count toward usage; an empty tail (wl==0) charges nothing.  A fixed-empty cell (g==0) restricts the
    // column to words that ended at or above it.  Bridges/cross-words/connectivity are still ignored (they
    // only reduce), so pruning on committed+UB <= best can never discard the optimum in varmax either.
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
        let prof_t0 = if self.prof { Some(std::time::Instant::now()) } else { None };
        for b in self.knap_words.iter_mut() { b.clear(); }
        while self.knap_words.len() < unc.len() { self.knap_words.push(Vec::new()); }
        // INCREMENTAL: when on, iterate only each column's maintained consistent-word list (col_consistent)
        // instead of rescanning its full domain.  The maintained list is EXACTLY the set this loop's
        // consistency test selects (proven by inc_fix mirroring the same wd[r-1]==v test), so the resulting
        // (gross, delta) buffers -- and hence the knapsack and every verdict -- are identical; only the scan
        // length differs.  INCOFF=1 scans the full domain (A/B fallback).  Empty scratch index buffer reused.
        let use_inc = self.use_inc;
        for (k, &si) in unc.iter().enumerate() {
            let col = self.inst.scoring_cols[si];
            let len = self.inst.scoring_len[si];
            let nfull = self.inst.scoring_words[si].len() as u32;
            // candidate word indices: the maintained consistent list (no copy -- take it out, iterate,
            // restore at the end of this iteration) when use_inc; else the full 0..nfull range.  Taking
            // col_consistent[si] out resolves the borrow conflict with &mut knap_words[k] (disjoint
            // fields, but both reached through self) at zero allocation/copy cost.
            let cands = if use_inc { std::mem::take(&mut self.col_consistent[si]) } else { Vec::new() };
            let buf = &mut self.knap_words[k];
            let mut early_dead = false;
            'words: for ii in 0..(if use_inc { cands.len() } else { nfull as usize }) {
                let wi = if use_inc { cands[ii] as usize } else { ii };
                let wd = &self.inst.scoring_words[si][wi];
                // consistency with fixed cells + collect delta usage at free cells.
                // VARMAX: a stub value of 0 means EMPTY (the column's word ended above this row), NOT a
                // tile -- so a free 0-cell costs NOTHING (no delta) and a FIXED empty cell (g==0) requires
                // the word to also be empty (wl==0) there.  In fixed mode words never carry a 0 and stub
                // cells are never fixed-empty (g>=1 once placed, -1 while free), so both 0-branches are
                // inert -> byte-identical to the pre-varmax knapsack.
                let mut delta: Vec<(u8, i64)> = Vec::new();
                for r in 1..len {
                    let g = self.grid[idx(col, r, w)];
                    let wl = wd[r - 1];
                    if g > 0 { if (wl as i16) != g { continue 'words; } }   // fixed letter -> must match
                    else if g == 0 { if wl != 0 { continue 'words; } }      // fixed empty (varmax) -> word ended here
                    else if wl != 0 {                                       // free cell, real tile -> charge delta
                        if let Some(e) = delta.iter_mut().find(|e| e.0 == wl) { e.1 += 1; }
                        else { delta.push((wl, 1)); }
                    }                                                       // free cell, empty tail -> no tile
                }
                buf.push((self.inst.scoring_gross[si][wi], delta));
            }
            if buf.is_empty() { early_dead = true; }
            // restore the taken consistent list before any return / next iteration.
            if use_inc { self.col_consistent[si] = cands; }
            if early_dead { self.knap_unc = unc; return Some(i64::MIN); }  // no consistent word: dead node
            // sort by gross descending so the knapsack DFS finds a strong incumbent / bounds fast.
            self.knap_words[k].sort_by(|a, b| b.0.cmp(&a.0));
        }
        // remaining per-code budget = counts - used (can be negative if already over by blanks).
        let a = self.inst.alpha;
        for c in 0..=a { self.knap_budget[c] = 0; }
        for c in 1..=a { self.knap_budget[c] = self.inst.counts[c] - self.used[c]; }
        // suffix best-gross sums for the knapsack DFS UB (reuse the scratch field).
        let m = unc.len();
        // Branch the MOST-CONSTRAINED column (fewest consistent words) first: narrows the rec tree
        // early so the expensive "no improver" proofs (~72% of calls) prune faster.  VERDICT-NEUTRAL
        // -- rec decides whether ANY one-word-per-column combo beats thresh; column order changes
        // only the search, not the answer (suffix is recomputed below over the new order).  rec is
        // 88.8% of runtime (perf), so a narrower tree is the lever.
        self.knap_words[0..m].sort_by_key(|b| b.len());
        let mut suffix = std::mem::take(&mut self.knap_suffix);
        suffix.clear(); suffix.resize(m + 1, 0);
        for k in (0..m).rev() {
            let cb = self.knap_words[k].iter().map(|e| e.0).max().unwrap_or(0);
            suffix[k] = suffix[k + 1] + cb;
        }
        // current per-code overflow already consumed (used > counts) eats into blanks.
        let mut base_over = 0i64;
        for c in 1..=a { if self.used[c] > self.inst.counts[c] { base_over += self.used[c] - self.inst.counts[c]; } }
        // -------- BUDGET-COUPLED SUFFIX BOUND (sfx2) --------------------------------------------------
        // The plain `suffix` ignores the shared blank-overflow budget, so it is far too loose: rec descends
        // a huge subtree before the per-step `no<=blanks` feasibility test prunes it word-by-word, and the
        // KNAPSTEPS budget often EXHAUSTS (-> returns true -> no prune).  sfx2 is a SOUND OVER-ESTIMATE that
        // also accounts for the overflow budget, so the bound fires HIGHER in the tree (more sound prunes).
        //
        // Define, per uncommitted column k, the word's STANDALONE overflow so_w = sum_l max(0, cnt_l - budget[l])
        // (the overflow the word would force if `extra` were all-zero, i.e. it alone competed for the budget).
        // colbest[k][o] = max gross among column-k words with so_w <= o, for o in 0..=blanks.
        // sfx2[k][r] = max over choices for columns k..m-1 of total gross s.t. sum of standalone overflows <= r.
        //   sfx2[k][r] = max over o in 0..=r of ( colbest[k][o] + sfx2[k+1][r-o] ),  sfx2[m][*] = 0.
        // SOUNDNESS: at a rec node with remaining capacity R = blanks - cur_over, any REAL-feasible completion
        // of columns k..m-1 has total REAL overflow <= R.  A word's real overflow (extra>=0 along the path)
        // is always >= its standalone overflow, so its standalone-overflow sum is also <= R, hence that real
        // selection is counted in sfx2[k][R].  Therefore sfx2[k][R] >= true achievable additional gross --
        // a sound over-estimate -- and it is <= suffix[k] (which allows unbounded overflow), so it dominates.
        // Pruning on cur_g + sfx2[k][R] <= thresh never discards a real improver.  blanks is tiny (<=2 here)
        // so the table is m x (blanks+1): built once per knap_ub call, O(m*blanks) lookups in the DFS.
        let blanks = self.inst.blanks;
        let nb = (blanks as usize) + 1;   // overflow levels 0..=blanks
        let mut sfx2 = std::mem::take(&mut self.knap_sfx2);
        sfx2.clear(); sfx2.resize((m + 1) * nb, 0);
        {
            // colbest reuses a small scratch (nb entries) per column.
            let mut colbest = [i64::MIN; 8];   // nb <= blanks+1; blanks small. guard below.
            let nbc = nb.min(colbest.len());
            for k in (0..m).rev() {
                for o in 0..nb { if o < nbc { colbest[o] = i64::MIN; } }
                for &(g, ref delta) in &self.knap_words[k] {
                    // standalone overflow of this word = sum_l max(0, cnt_l - budget_l): the overflow it would
                    // force if `extra` were all-zero (it alone competing for the budget).  budget_l may be
                    // negative (already over by base blanks), which only RAISES so -> still sound (we never
                    // under-count an over-estimate's overflow gate; a higher so only EXCLUDES words, lowering
                    // the bound, which stays >= the true achievable gross because real overflow >= standalone).
                    let mut so = 0i64;
                    for &(l, cnt) in delta {
                        let need = cnt - self.knap_budget[l as usize];
                        if need > 0 { so += need; }
                    }
                    if so > blanks { continue; }   // standalone-infeasible: cannot be in any feasible combo
                    let oi = so as usize;
                    if oi < nbc && g > colbest[oi] { colbest[oi] = g; }
                }
                // prefix-max over overflow level so colbest[o] = best gross with standalone overflow <= o.
                for o in 1..nbc { if colbest[o - 1] > colbest[o] { colbest[o] = colbest[o - 1]; } }
                // DP: sfx2[k][r] = max_o<=r colbest[o] + sfx2[k+1][r-o].
                for r in 0..nb {
                    let mut best = i64::MIN;
                    for o in 0..=r {
                        let cb = if o < nbc { colbest[o] } else { i64::MIN };
                        if cb == i64::MIN { continue; }
                        let rest = sfx2[(k + 1) * nb + (r - o)];
                        if rest == i64::MIN { continue; }   // suffix infeasible at remaining capacity
                        let v = cb + rest;
                        if v > best { best = v; }
                    }
                    // if no feasible word at any level <= r, this column is dead at capacity r: mark MIN so
                    // any path through it is pruned (a column with NO standalone-feasible word at <=r cannot
                    // be completed within r; that branch can't beat thresh -> sound to treat as -inf gross).
                    sfx2[k * nb + r] = best;   // best stays i64::MIN if column infeasible at r
                }
            }
        }
        // We only need to know whether the uncommitted columns can add ENOUGH gross to BEAT self.best
        // (the node is pruned iff committed_gross + max_additional <= best). So search as a DECISION:
        // does a feasible word-combo with total additional gross > thresh exist? Stop at the first one.
        // thresh = best - committed_gross. (penalty>=0, so additional > thresh is necessary to beat best.)
        let thresh = self.best - self.committed_gross;
        // branch over uncommitted columns; track extra per-code usage (reuse scratch; reset to 0).
        let mut extra = std::mem::take(&mut self.knap_extra);
        extra.clear(); extra.resize(a + 1, 0);
        // Returns true as soon as a feasible combo with cur_g + (rest) > thresh is found (improver exists).
        // `cur_over` = current overflow beyond counts given base used + extra so far.
        // NOTE: iterate exactly `m` (= number of uncommitted columns) columns, NOT words.len(): the scratch
        // buffer self.knap_words may be LONGER than m from a previous call (trailing buffers are cleared/
        // empty), and treating an empty buffer as a column would make rec wrongly find no combo.
        fn rec(k: usize, m: usize, cur_g: i64, cur_over: i64, thresh: i64,
               words: &Vec<Vec<(i64, Vec<(u8, i64)>)>>, budget: &[i64], extra: &mut [i64],
               suffix: &[i64], blanks: i64, steps: &mut i64, sfx2: &[i64], nb: usize) -> bool {
            // ITERATION BUDGET: the root-level knapsack (all columns uncommitted, full domains) can
            // blow up combinatorially and run for SECONDS-TO-MINUTES before the search's first tick
            // (measured: a 5s WALL aborting only at 44s -- the deadline lives in tick(), which never
            // runs while the knapsack recurses).  On exhaustion return true ("an improver may
            // exist") -> the caller skips the PRUNE -- always sound; only the bound gets weaker.
            *steps -= 1;
            if *steps < 0 { return true; }
            if cur_g + suffix[k] <= thresh { return false; }   // even the optimistic rest can't beat thresh
            // BUDGET-COUPLED bound (sfx2): tighter sound over-estimate of the best additional gross from
            // columns k..m-1 achievable within the REMAINING overflow capacity R = blanks - cur_over.  R is
            // always in 0..=blanks here (rec is only entered with cur_over <= blanks).  sfx2[k][R]==MIN means
            // NO standalone-feasible completion fits in R -> no real combo can either -> sound to prune.
            if k < m {
                let r = (blanks - cur_over) as usize;          // 0..=blanks
                let s2 = sfx2[k * nb + r];
                if s2 == i64::MIN || cur_g + s2 <= thresh { return false; }
            }
            if k == m { return cur_g > thresh; }
            // LAST-COLUMN FAST PATH: when only one uncommitted column remains we do NOT recurse -- the
            // child rec(m,..) merely returns `cur_g+g > thresh`.  Most-constrained-FIRST ordering puts the
            // BIGGEST domain (e.g. col10, ~315 words) LAST, so this scan dominates rec's leaf work; inlining
            // it drops a recursion frame + the entry checks per surviving word.  Semantics IDENTICAL: same
            // gross break (suffix[m]==0), same overflow feasibility test, same "improver iff some feasible
            // word has cur_g+g > thresh".  Verdict-neutral (knap is a bound; dfs node count unchanged).
            if k + 1 == m {
                for &(g, ref delta) in &words[k] {
                    if cur_g + g <= thresh { break; }   // sorted desc; suffix[m]==0 -> nothing later beats
                    let mut d_over = 0i64;
                    for &(l, cnt) in delta {
                        let li = l as usize;
                        let before = extra[li] - budget[li];
                        let after = before + cnt;
                        d_over += after.max(0) - before.max(0);
                    }
                    if cur_over + d_over > blanks { continue; }   // infeasible budget: original skips rec
                    // The eliminated child rec(m,..) ran ONLY after this overflow check and then
                    // decremented steps (returning true on exhaustion).  Mirror that EXACTLY so the
                    // iteration budget -- hence the bound under exhaustion -- is byte-identical.
                    *steps -= 1;
                    if *steps < 0 { return true; }
                    return true;   // feasible & cur_g+g>thresh -> improver (child rec(m) returns true)
                }
                return false;
            }
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
                    && rec(k + 1, m, cur_g + g, no, thresh, words, budget, extra, suffix, blanks, steps, sfx2, nb);
                for &(l, cnt) in delta { extra[l as usize] -= cnt; }
                if hit { return true; }
            }
            false
        }
        let mut steps: i64 = std::env::var("KNAPSTEPS").ok().and_then(|s| s.parse().ok())
            .unwrap_or(500_000);
        let prof_t1 = if let Some(t0) = prof_t0 {
            let now = std::time::Instant::now();
            self.prof_knap_rebuild_ns += now.duration_since(t0).as_nanos();
            self.prof_knap_rec_calls += 1;
            Some(now)
        } else { None };
        let improver = rec(0, m, 0, base_over, thresh, &self.knap_words, &self.knap_budget,
                           &mut extra, &suffix, blanks, &mut steps, &sfx2, nb);
        if let Some(t1) = prof_t1 {
            self.prof_knap_rec_ns += std::time::Instant::now().duration_since(t1).as_nanos();
        }
        // return the scratch buffers to their fields for reuse next call.
        self.knap_unc = unc; self.knap_suffix = suffix; self.knap_extra = extra; self.knap_sfx2 = sfx2;
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
        if self.aborted { return true; }    // once aborted, EVERY node bails -> instant unwind
                                            // (without this only 1-in-4096 nodes noticed the flag
                                            // and the search ran to natural completion anyway)
        self.nodes += 1;
        if self.nodes % 20_000_000 == 0 {
            eprintln!("  nodes={}M best={} committed={} rem_best={} rowhist={:?}",
                self.nodes / 1_000_000, self.best, self.committed_gross, self.remaining_best, self.rowhist);
        }
        if self.node_cap > 0 && self.nodes >= self.node_cap { self.aborted = true; return true; }
        if self.nodes & 0xFFF == 0 {
            if let Some(d) = self.deadline {
                if std::time::Instant::now() >= d {
                    if !self.aborted {
                        eprintln!("DEADLINE fired at nodes={}", self.nodes);
                    }
                    self.aborted = true; return true;
                }
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
            // candidate cell-values at this cell + the best gross of any consistent word using that
            // value (for descending ordering -> find a strong incumbent fast).  In VARMAX a value may
            // be 0 = EMPTY (the column's word ended above this row); otherwise it is a letter code.
            let mut cand: Vec<(u8, i64)> = Vec::new();   // (cell value: 0=empty / letter, best gross)
            'words: for (wi, wd) in self.inst.scoring_words[si].iter().enumerate() {
                for r in 1..len {
                    let cid = idx(col, r, w);
                    let g = self.grid[cid];
                    // fixed cell (letter g>0, or empty g==0 in varmax) must match the word at row r.
                    if g >= 0 && (wd[r - 1] as i16) != g { continue 'words; }
                }
                let l = wd[posn];
                let g = self.inst.scoring_gross[si][wi];
                if let Some(e) = cand.iter_mut().find(|e| e.0 == l) { if g > e.1 { e.1 = g; } }
                else { cand.push((l, g)); }
            }
            cand.sort_by(|a, b| b.1.cmp(&a.1));          // high-gross values first
            let prev_ub = self.col_ub[si];
            for (l, _) in cand {
                if l == 0 {
                    // EMPTY stub cell (varmax: word ended above).  No tile consumed.  Closing this cell
                    // closes the H run to its left and the V run above (the column's vertical word, which
                    // ends at the cell above) -- closed_runs_ok validates the H run; the V run is owned
                    // by the (pre-validated) scoring word and so needs no dict check here.  We still must
                    // verify the cell ABOVE can reach the root (sealed_ok) just like a bridge empty.
                    self.grid[id] = 0;
                    self.inc_fix(si, y, 0);
                    self.recompute_live_mask(si, col);
                    let new_ub = self.col_best_consistent(si, col);
                    self.remaining_best += new_ub - prev_ub;
                    self.col_ub[si] = new_ub;
                    let committed = self.commit_if_col_done(si, col);
                    let hit = self.closed_runs_ok(x, y) && self.sealed_ok(id) && self.dfs_score(id + 1);
                    self.uncommit(si, committed);
                    self.remaining_best += prev_ub - self.col_ub[si];
                    self.col_ub[si] = prev_ub;
                    self.grid[id] = -1;
                    self.inc_unfix(si);
                    self.recompute_live_mask(si, col);
                    if hit { return true; }
                    continue;
                }
                if !self.place_ok(x, y, l) { continue; }
                if !self.add_letter(l as usize) { self.rm_letter(l as usize); continue; }
                self.grid[id] = l as i16;
                self.inc_fix(si, y, l as i16);
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
                self.inc_unfix(si);
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
                // consistency: a fixed cell (g>0 letter or g==0 empty in varmax) must match the word.
                if g >= 0 && (wd[r - 1] as i16) != g { continue 'words; }
            }
            for q in 0..len - 1 { if wd[q] != 0 { self.col_live_mask[si][q] |= bit(wd[q]); } }
        }
    }

    // INCREMENTAL: a stub cell of column si at row `r` (1-based) was just FIXED to value `v` (0 = empty
    // in varmax, or a letter code).  Remove from col_consistent[si] every word whose row-r letter differs
    // (wd[r-1] != v), saving the removed indices on the undo stack for inc_unfix to restore.  This keeps
    // col_consistent[si] EXACTLY the set the knap rebuild's consistency loop would compute over the full
    // domain, but updates it in O(current-list) instead of O(full-domain).
    #[inline]
    fn inc_fix(&mut self, si: usize, r: usize, v: i16) {
        if !self.use_inc { return; }
        let q = r - 1;
        let live = &mut self.col_consistent[si];
        let mut removed = self.inc_undo_pool.pop().unwrap_or_default();
        removed.clear();
        let words = &self.inst.scoring_words[si];
        let mut i = 0;
        while i < live.len() {
            let wi = live[i] as usize;
            if (words[wi][q] as i16) != v {
                removed.push(live[i]);
                live.swap_remove(i);          // order is irrelevant (knap sorts by gross)
            } else {
                i += 1;
            }
        }
        self.inc_undo.push((si, removed));
    }
    // INCREMENTAL: undo the most recent inc_fix for column si (LIFO with the DFS stack).  Re-append the
    // removed indices to col_consistent[si].
    #[inline]
    fn inc_unfix(&mut self, si: usize) {
        if !self.use_inc { return; }
        let (usi, mut removed) = self.inc_undo.pop().expect("inc_undo underflow");
        debug_assert_eq!(usi, si);
        self.col_consistent[usi].extend_from_slice(&removed);
        removed.clear();
        self.inc_undo_pool.push(removed);
    }

    // Best gross over candidate words of column si consistent with its current partial stub (>0 cells).
    fn col_best_consistent(&self, si: usize, col: usize) -> i64 {
        let w = self.inst.w;
        let len = self.inst.scoring_len[si];
        let mut best = i64::MIN;
        'words: for (wi, wd) in self.inst.scoring_words[si].iter().enumerate() {
            for r in 1..len {
                let g = self.grid[idx(col, r, w)];
                // fixed cell (letter g>0, or empty g==0 in varmax) must match; g==-1 is free.
                if g >= 0 && (wd[r - 1] as i16) != g { continue 'words; }
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
        for r in 1..len { if self.grid[idx(col, r, w)] == -1 { return None; } }
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
                    if on_stub as usize > costs.len() {
                        // Overflow exceeds bridge+stub capacity for this code: a blank would have to
                        // sit on a PREPLACED main-word cell, forfeiting val * WM(main) >= 27 realized
                        // points -- more than any slack we certify at (driver asserts LB >= UB-26).
                        // Treat as never-improving.  (Legacy modes never reached this: their
                        // candidate/vector generation kept overflow within stub capacity.)
                        return i64::MAX / 4;
                    }
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
            for li in 0..self.lorder.len() {
                let l = self.lorder[li];
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
            else if g == -1 && self.inst.kind[cid] == 1 && !self.inst.varmax {  // unplaced active scoring-stub cell
                // VARMAX: an undecided stub cell MAY be empty (the column's word ends above it), so it is
                // NOT forced-active -> treat it as a can-be-empty stopper (break below).  Relaxation: a
                // narrower forced span never rejects a feasible board, so soundness holds.
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
        // --emit: also print a per-instance witness BOARD line (keyed) whenever best>floor (incl. on
        // a TO abort).  OUTPUT-ONLY (the verdict line is unchanged); the board is exactly what
        // single-mode --emit prints and what solve_one already returns, so verdicts stay byte-identical.
        let emit = args.iter().any(|a| a == "--emit");
        let mut dicts: std::collections::HashMap<String, Dict> = std::collections::HashMap::new();
        let data = fs::read_to_string(listfile).unwrap();
        use std::io::Write as _;
        for line in data.lines() {
            let mut it = line.split_whitespace();
            let (key, p, fl) = (it.next(), it.next(), it.next());
            if key.is_none() || p.is_none() { continue; }
            let key = key.unwrap();
            let floor: i64 = fl.and_then(|s| s.parse().ok()).unwrap_or(-1);
            let (res, board) = solve_one(p.unwrap(), true, floor, Some(wall), &mut dicts);
            println!("RES {} {}", key, res);
            if emit {
                if let Some(bg) = board {
                    print!("BOARD {}", key);
                    for &g in &bg { print!(" {}", if g > 0 { g } else { 0 }); }
                    println!();
                }
            }
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
    // ---- PINENUM MODE: `xfill --pinenum BASE --floor F --mainletters c,c,.. --shards N --outdir D`
    // Rust port of Python enumerate_above_blanks (n15_twolevel.py) in STREAMING form: the complete
    // blank-aware band (nominal - deficit-penaltyLB > floor, <=2 blanks, leaf-exact min-wm recheck)
    // written round-robin as pinbatch lines `<key> <floor> <toks>` into shard files.  Semantics
    // must match the Python EXACTLY (gate: key-set equality on known bands).  mainletters = the
    // main word's letter CODES at the scoring columns (bcol order) -- needed for the content key.
    if let Some(bi) = args.iter().position(|a| a == "--pinenum") {
        let base = parse_base(&args[bi + 1]);
        let getf = |name: &str| args.iter().position(|a| a == name).map(|i| args[i + 1].clone());
        let floor: i64 = getf("--floor").expect("--floor").parse().unwrap();
        let mains: Vec<u8> = getf("--mainletters").expect("--mainletters")
            .split(',').map(|t| t.parse().unwrap()).collect();
        let nshard: usize = getf("--shards").map(|s| s.parse().unwrap()).unwrap_or(20);
        let outdir = getf("--outdir").expect("--outdir");
        let blank_budget: i64 = base.blanks.min(2);
        let ncols = base.bcols.len();
        assert_eq!(mains.len(), ncols);
        // avail = base counts CLAMPED at 0 (mirrors build_avail)
        let avail: Vec<i64> = base.counts.iter().map(|&n| n.max(0)).collect();
        // options per column: (gross, tail counts, stub, adj_gross); bare tile = (0, {}, [], 0)
        struct Opt { g: i64, stub: Vec<u8>, ct: Vec<(u8, i64)>, gadj: i64 }
        let mut cols: Vec<(usize, Vec<Opt>)> = Vec::new();
        for ci in 0..ncols {
            let mut opts: Vec<Opt> = vec![Opt { g: 0, stub: Vec::new(), ct: Vec::new(), gadj: 0 }];
            for (_l, (ws, gs)) in base.bylen[ci].iter() {
                for (wi, w) in ws.iter().enumerate() {
                    if w.is_empty() { continue; }
                    let mut cnt = vec![0i64; base.alpha + 1];
                    for &ch in w { cnt[ch as usize] += 1; }
                    let mut ct: Vec<(u8, i64)> = Vec::new();
                    let mut sb = 0i64;                          // standalone penalty vs full avail
                    let mut nb = 0i64;                          // standalone blanks needed
                    for ch in 1..=base.alpha {
                        if cnt[ch] > 0 {
                            ct.push((ch as u8, cnt[ch]));
                            let short = cnt[ch] - avail[ch];
                            if short > 0 { sb += base.scores[ch] * short; nb += short; }
                        }
                    }
                    if nb > blank_budget { continue; }          // never placeable
                    opts.push(Opt { g: gs[wi], stub: w.clone(), ct, gadj: gs[wi] - sb });
                }
            }
            // desc by adj_gross, deterministic tiebreak on stub
            opts.sort_by(|a, b| b.gadj.cmp(&a.gadj).then(a.stub.cmp(&b.stub)));
            cols.push((ci, opts));
        }
        // column order: desc by top adj_gross, tiebreak col index (matches Python coldata.sort)
        cols.sort_by(|a, b| b.1[0].gadj.cmp(&a.1[0].gadj).then(a.0.cmp(&b.0)));
        let order: Vec<usize> = cols.iter().map(|c| c.0).collect();
        let optl: Vec<&Vec<Opt>> = cols.iter().map(|c| &c.1).collect();
        let mut sufmax = vec![0i64; ncols + 1];
        for k in (0..ncols).rev() { sufmax[k] = sufmax[k + 1] + optl[k][0].gadj; }
        // key needs SORTED column order: map order-index -> (col, main letter)
        let colof: Vec<usize> = order.iter().map(|&ci| base.bcols[ci]).collect();
        let mainof: Vec<u8> = order.iter().map(|&ci| mains[ci]).collect();
        let wmof: Vec<i64> = order.iter().map(|&ci| base.bwm[ci]).collect();
        use std::io::Write as _;
        let mut shards: Vec<std::io::BufWriter<fs::File>> = (0..nshard)
            .map(|i| std::io::BufWriter::with_capacity(1 << 20,
                 fs::File::create(format!("{}/shard_{:02}.txt", outdir, i)).unwrap()))
            .collect();
        let mut bud: Vec<i64> = avail.clone();
        let mut pick: Vec<usize> = vec![0; ncols];              // applied option INDEX per depth
        let mut count: u64 = 0; let mut nodes: u64 = 0;
        let mut oi = vec![0usize; ncols + 1];                   // next option index per depth
        let mut curs = vec![0i64; ncols + 1];
        let mut adjs = vec![0i64; ncols + 1];
        let mut ubs = vec![0i64; ncols + 1];
        // key columns in SORTED board order; toks in BCOL order (pinbatch input contract)
        let mut keyorder: Vec<usize> = (0..ncols).collect();
        keyorder.sort_by_key(|&i| colof[i]);
        let mut inv = vec![0usize; ncols];                      // bcol index ci -> depth index
        for (i, &ci) in order.iter().enumerate() { inv[ci] = i; }
        let mut k: i64 = 0;
        let mut returning = false;                              // just came back from depth k+1
        loop {
            if k < 0 { break; }
            let d = k as usize;
            if d == ncols {
                nodes += 1;
                // leaf-exact min-wm penalty recheck (only when deficits exist)
                let mut accept = true;
                if curs[d] != adjs[d] {
                    let mut pen = 0i64;
                    for ch in 1..=base.alpha {
                        let deficit = -bud[ch];
                        if deficit > 0 {
                            let mut mw = i64::MAX;
                            for i in 0..ncols {
                                let o = &optl[i][pick[i]];
                                if o.stub.iter().any(|&c| c as usize == ch) && wmof[i] < mw {
                                    mw = wmof[i];
                                }
                            }
                            if mw == i64::MAX { mw = 1; }
                            pen += deficit * base.scores[ch] * mw;
                        }
                    }
                    if curs[d] - pen <= floor { accept = false; }
                }
                if accept {
                    count += 1;
                    let mut line = String::new();
                    for (n, &i) in keyorder.iter().enumerate() {
                        if n > 0 { line.push('|'); }
                        let o = &optl[i][pick[i]];
                        line.push_str(&colof[i].to_string()); line.push(':');
                        if o.stub.is_empty() { line.push('-'); }
                        else {
                            line.push((96 + mainof[i]) as char);
                            for &c in &o.stub { line.push((96 + c) as char); }
                        }
                    }
                    line.push(' '); line.push_str(&floor.to_string());
                    for ci in 0..ncols {
                        let o = &optl[inv[ci]][pick[inv[ci]]];
                        line.push(' ');
                        if o.stub.is_empty() { line.push('-'); }
                        else {
                            for (j, &c) in o.stub.iter().enumerate() {
                                if j > 0 { line.push(','); }
                                line.push_str(&c.to_string());
                            }
                        }
                    }
                    line.push('\n');
                    shards[(count as usize - 1) % nshard].write_all(line.as_bytes()).unwrap();
                }
                k -= 1;
                returning = true;
                continue;
            }
            if returning {
                // back from the subtree under pick[d]: undo its bag draw before the next option
                let o = &optl[d][pick[d]];
                for &(ch, q) in &o.ct { bud[ch as usize] += q; }
                returning = false;
            }
            // try next option at depth d
            let mut advanced = false;
            while oi[d] < optl[d].len() {
                let idx = oi[d]; oi[d] += 1;
                let o = &optl[d][idx];
                if adjs[d] + o.gadj + sufmax[d + 1] <= floor { oi[d] = optl[d].len(); break; }
                let mut db = 0i64; let mut pen = 0i64; let mut ok = true;
                for &(ch, q) in &o.ct {
                    let short = q - bud[ch as usize].max(0);
                    if short > 0 {
                        db += short; pen += base.scores[ch as usize] * short;
                        if ubs[d] + db > blank_budget { ok = false; break; }
                    }
                }
                if !ok { continue; }
                if adjs[d] + o.g - pen + sufmax[d + 1] <= floor { continue; }
                for &(ch, q) in &o.ct { bud[ch as usize] -= q; }
                pick[d] = idx;
                curs[d + 1] = curs[d] + o.g;
                adjs[d + 1] = adjs[d] + o.g - pen;
                ubs[d + 1] = ubs[d] + db;
                oi[d + 1] = 0;
                k += 1;
                nodes += 1;
                advanced = true;
                break;
            }
            if !advanced {
                k -= 1;
                returning = true;                    // parent must undo ITS pick next
            }
        }
        for s in shards.iter_mut() { s.flush().unwrap(); }
        println!("PINENUM count={} nodes={} floor={} shards={}", count, nodes, floor, nshard);
        return;
    }
    // ---- PINBATCH MODE: `xfill --pinbatch BASEFILE [--emit]` ------------------------------------
    // Per-COMBO decision engine for the N=15 oracle: reads combo lines from STDIN, decides each
    // with --maxscore semantics against the line's floor, streams verdicts to STDOUT.
    //   line:    <key> <floor> <tok_0> ... <tok_{ncols-1}>      (ncols = base BCOL count, in order)
    //   tok:     '-' (bare tile, no vertical)  or  'c1,c2,...' (the STUB codes, rows 1..len-1)
    //   output:  RES <key> <verdict-line>   (+ BOARD <key> <codes...> when --emit and best>floor)
    // The word's gross is LOOKED UP in the base (same get_word_score authority as the enumerator);
    // an unknown (col,stub) -> `RES <key> NOCAND` (loud miscoordination guard, never a guess).
    // Wall per combo: env PINWALL seconds (default 5) -> TO (caller falls back to CP-SAT).
    if let Some(bi) = args.iter().position(|a| a == "--pinbatch") {
        let base = parse_base(&args[bi + 1]);
        let emit = args.iter().any(|a| a == "--emit");
        let wall: f64 = std::env::var("PINWALL").ok().and_then(|s| s.parse().ok()).unwrap_or(5.0);
        let td = std::time::Instant::now();
        let dict = load_dict(&base.dict_path, base.hmax);
        eprintln!("dict loaded: {} words, {} prefixes, {:.2}s",
                  dict.words.len(), dict.prefixes.len(), td.elapsed().as_secs_f64());
        let ncols = base.bcols.len();
        // (len, stub) -> gross lookup per column
        let mut glut: Vec<std::collections::HashMap<Vec<u8>, i64>> = vec![Default::default(); ncols];
        for ci in 0..ncols {
            for (_l, (ws, gs)) in base.bylen[ci].iter() {
                for (wi, w) in ws.iter().enumerate() { glut[ci].insert(w.clone(), gs[wi]); }
            }
        }
        use std::io::{BufRead as _, Write as _};
        let stdin = std::io::stdin();
        for line in stdin.lock().lines() {
            let line = match line { Ok(l) => l, Err(_) => break };
            let toks: Vec<&str> = line.split_whitespace().collect();
            if toks.len() != ncols + 2 { if !line.trim().is_empty() {
                println!("RES {} BADLINE", toks.first().unwrap_or(&"?")); } continue; }
            let key = toks[0];
            let floor: i64 = match toks[1].parse() { Ok(f) => f, Err(_) => {
                println!("RES {} BADLINE", key); continue; } };
            let mut picks: Vec<Option<(Vec<u8>, i64)>> = Vec::with_capacity(ncols);
            let mut bad = false;
            for ci in 0..ncols {
                let t = toks[2 + ci];
                if t == "-" { picks.push(None); continue; }
                let stub: Vec<u8> = t.split(',').filter_map(|s| s.parse().ok()).collect();
                match glut[ci].get(&stub) {
                    Some(&g) => picks.push(Some((stub, g))),
                    None => { bad = true; break; }
                }
            }
            if bad { println!("RES {} NOCAND", key); std::io::stdout().flush().ok(); continue; }
            let mut inst = inst_pinned_from_base(&base, &picks);
            let (res, board) = solve_inst(&mut inst, &dict, true, floor, Some(wall));
            println!("RES {} {}", key, res);
            if emit {
                if let Some(bg) = board {
                    print!("BOARD {}", key);
                    for &g in &bg { print!(" {}", if g > 0 { g } else { 0 }); }
                    println!();
                }
            }
            std::io::stdout().flush().ok();
        }
        return;
    }
    // ---- VARMAX MODE: `xfill --varmax BASEFILE --maxscore FLOOR` --------------------------------
    // VARIABLE-LENGTH score maximization over a BASE file: ONE search in which each scoring column
    // chooses BOTH its vertical length (1..maxlen, from the base) AND its word.  Equivalent to running
    // the fixed-length --batchvec sweep over EVERY length-vector and taking the max (proof in
    // inst_var_from_base).  Prints the usual `MAX <s>` / `LE <floor>` / `TO ...` line; --emit prints
    // the best board.  Optional WALL (env) gives a sound wall-clock abort (-> TO, never LE).
    if let Some(vi) = args.iter().position(|a| a == "--varmax") {
        let base = parse_base(&args[vi + 1]);
        let floor: i64 = args.iter().position(|a| a == "--maxscore")
            .and_then(|i| args.get(i + 1)).and_then(|s| s.parse().ok()).unwrap_or(-1);
        let wall: Option<f64> = std::env::var("WALL").ok().and_then(|s| s.parse().ok());
        let td = std::time::Instant::now();
        let dict = load_dict(&base.dict_path, base.hmax);
        eprintln!("dict loaded: {} words, {} prefixes, {:.2}s",
                  dict.words.len(), dict.prefixes.len(), td.elapsed().as_secs_f64());
        let mut inst = inst_var_from_base(&base).expect("varmax: empty base");
        let (line, board) = solve_inst(&mut inst, &dict, true, floor, wall);
        println!("{}", line);
        if args.iter().any(|a| a == "--emit") {
            if let Some(bg) = board {
                print!("BOARD");
                for &g in &bg { print!(" {}", if g > 0 { g } else { 0 }); }
                println!();
            }
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
    // VARMAX: SKIPPED -- its forced-2-letter-word join assumes FIXED column lengths (definitely_empty
    // flanks).  With variable lengths a flanking stub cell is not provably empty, so the join is unsound.
    if !inst.varmax && !inst.pinned && std::env::var("NOAC").is_err() {
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
    // mandatory cells: preplaced (grid0>0) + scoring-stub positions (kind==1).
    // VARMAX: a stub cell MAY be empty (its column's word ends above), so it is NOT mandatory-active --
    // only the preplaced cells are guaranteed active.  (The root for sealed_ok / connectivity must be a
    // truly-always-active cell; mandatory[0] is used as that root.)
    let mandatory: Vec<usize> = (0..inst.w * inst.h)
        .filter(|&id| inst.grid0[id] > 0 || (!inst.varmax && inst.kind[id] == 1)).collect();
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
    let placed: i64 = used.iter().sum();                 // = #preplaced setup cells (seeded above)
    // opponent-tile cap: total setup tiles placed <= (available letter tiles) + blanks - reserve.
    // reserve=0 -> equals the implicit overflow<=blanks bound (no-op, byte-identical).
    let max_setup: i64 = inst.counts[1..=inst.alpha].iter().sum::<i64>() + inst.blanks - inst.reserve;
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
        for wd in &inst.scoring_words[si] { for q in 0..len - 1 { if wd[q] != 0 { v[q] |= bit(wd[q]); } } }
        v
    }).collect();
    let mut solver = Solver { inst: &*inst, dict, grid, mandatory, deferred, free_cols, used,
        overflow, placed, max_setup,
        nodes: 0, rowhist: vec![0u64; inst.h], always_conn: std::env::var("ACONN").is_ok(),
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
        // VARMAX-AWARE: the joint-knapsack UB's per-column consistency test now treats a stub cell's
        // value 0 as EMPTY (the column's word ended above) -- a free 0-cell charges NO tile and a
        // fixed-empty cell (g==0) only admits words that are also empty there (see knap_ub).  The
        // per-column candidate list is the base's union over ALL lengths PLUS the length-1 bare-tile
        // (all-zeros, gross 0) option, exactly the enlarged option set the varmax model requires, so the
        // knapsack still picks one (length,word) per uncommitted column maximizing gross under the shared
        // per-letter budget -- a SOUND over-estimate (bridges/cross-words/connectivity only reduce it).
        // Hence varmax pruning on it is verdict-neutral.  Opt out with NOKNAP=1.
        use_knap: maxscore && std::env::var("NOKNAP").is_err(),
        knap_maxcols: std::env::var("KNAPCOLS").ok().and_then(|s| s.parse().ok()).unwrap_or(ncols.max(1)),
        knap_words: Vec::new(), knap_budget: vec![0i64; inst.alpha + 1],
        knap_extra: Vec::new(), knap_suffix: Vec::new(), knap_sfx2: Vec::new(), knap_unc: Vec::new(),
        use_inc: maxscore && std::env::var("NOKNAP").is_err() && std::env::var("INCOFF").is_err(),
        col_consistent: (0..ncols).map(|si| (0..inst.scoring_words[si].len() as u32).collect()).collect(),
        inc_undo: Vec::new(), inc_undo_pool: Vec::new(),
        knap_calls: 0, knap_prunes: 0,
        lorder: {
            let mut v: Vec<i16> = (1..=inst.alpha as i16).collect();
            if let Some(seed) = std::env::var("PINSHUF").ok().and_then(|x| x.parse::<u64>().ok()) {
                let mut st = seed.wrapping_mul(2685821657736338717).max(1);
                for i in (1..v.len()).rev() {
                    st ^= st << 13; st ^= st >> 7; st ^= st << 17;
                    let j = (st % (i as u64 + 1)) as usize;
                    v.swap(i, j);
                }
            }
            v
        },
        prof: std::env::var("XFILL_PROF").is_ok(),
        prof_knap_rebuild_ns: 0, prof_knap_rec_ns: 0, prof_knap_rec_calls: 0 };
    let t = std::time::Instant::now();
    let sat = solver.run();
    let dt = t.elapsed().as_secs_f64();
    if std::env::var("ROWHIST").is_ok() {
        eprintln!("rowhist: {:?}", solver.rowhist);
    }
    if solver.use_knap {
        eprintln!("knap-ub: calls={} prunes={}", solver.knap_calls, solver.knap_prunes);
    }
    if solver.prof {
        let total = dt * 1e9;
        let reb = solver.prof_knap_rebuild_ns as f64;
        let rec = solver.prof_knap_rec_ns as f64;
        eprintln!("PROF: total={:.3}s knap_rec_calls={} rebuild={:.3}s({:.1}%) rec={:.3}s({:.1}%) other={:.3}s({:.1}%)",
            dt, solver.prof_knap_rec_calls,
            reb / 1e9, 100.0 * reb / total,
            rec / 1e9, 100.0 * rec / total,
            (total - reb - rec) / 1e9, 100.0 * (total - reb - rec) / total);
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
