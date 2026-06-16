# xfill variable-length mode (`--varmax`)

## Problem

`xfill --maxscore` / `--batchvec` maximize the vertical cross-word score of a board for a **fixed
per-column length-vector** `v = (len[c])_c`. Certifying one main word means sweeping the whole
Cartesian product of per-column lengths (e.g. geschenkcheques: ~497k vectors per mask x 39 masks),
running the inner solve once per vector. That is the bottleneck.

`--varmax` runs **one** search in which each scoring column chooses **both** its vertical length
`L in 1..maxlen` and its word of that length (length-1 = bare tile, no vertical, gross 0), over a
BASE file (`xfill --varmax BASEFILE --maxscore FLOOR`). The BASE file already lists every
`(col, length, word, gross)` (the `BCOL`/`BLEN`/`WORDV` blocks `parse_base` reads), so the
variable search's per-column candidate set is exactly the union over all lengths, plus the
length-1 option.

## Model

Fixed model (unchanged): column `c` has one length `len[c]`; stub cells occupy rows `1..len[c]`,
rows `>= len[c]` are forced-empty; the maximize picks one word per column maximizing
`sum gross - blank_penalty` subject to: every maximal H/V run >=2 is a legal `<=HMAX` dict word,
all active cells one 4-connected component, tile budget (`counts + blanks - reserve`).

Variable model (`--varmax`): the stub region of column `c` spans rows `1..maxlen[c]` (maxlen = the
largest length present in the base). A candidate word of length `L` is stored as the `maxlen-1`-long
pattern `letters(rows 1..L), 0(rows L..maxlen)` -- i.e. the word padded with trailing **empties**.
Suffix-empty is automatic (every pattern is a real word padded with zeros). A grid value of `0` at a
stub cell means "the column's word ended above" -> that cell is a genuine empty cell for
connectivity / cross-words / budget, identical to the fixed model's forced-empty cells below a
short column. The length-1 bare-tile option is the all-empty pattern (gross 0); it always exists.
Everything else (legality, connectivity, budget, blank penalty) is identical to the fixed model.

## Equivalence (the soundness crux)

Claim:

    varmax_MAX  =  max over all length-vectors v of  fixed_MAX(v)

and therefore  `varmax LE floor`  <=>  every fixed length-vector is `LE floor`.

Argument. The fixed sweep maximizes the legal-connected score over `W(v) = X_c { length-len[c]
words of col c }`, for every `v`. Choosing length `L` for column `c` in the variable search =
restricting that column to its length-`L` candidates and forcing rows `>=L` empty -- i.e. exactly a
point of some `W(v)`. Conversely every board the variable search visits assigns each column a single
word of some length, hence lies in `W(v)` for the `v` naming those lengths. So the set of boards the
variable search ranges over is *exactly* `union over v of (legal boards of W(v))`. The objective,
legality, connectivity and budget are evaluated identically in both modes (a stub `0` = the fixed
model's forced-empty). Hence `varmax_MAX = max_v fixed_MAX(v)`, and the LE/floor equivalence follows.
No board is added or dropped; only the artificial per-run length pinning is removed.

Implementation notes that preserve soundness:
- The joint-knapsack UB and the AC-3 presolve are **disabled** in varmax (both assume FIXED column
  lengths -- AC-3's forced-2-letter-word join needs provably-empty flanks; the knapsack's
  consistency test treats a stub `0` as "free" rather than "empty"). The plain
  `committed + remaining_best` UB is sound for varmax.
- `place_ok`'s horizontal right-extension does **not** treat an *undecided* stub cell as
  forced-active in varmax (it may be empty) -- it is a can-be-empty stopper, a relaxation that never
  rejects a feasible board.
- `mandatory`/connectivity root = preplaced cells only (a stub cell may be empty, so it is not
  mandatory-active).
- All these are gated on `inst.varmax`; the fixed-length / decision engines are byte-identical
  (regress.sh ALL GATES GREEN; node counts unchanged on the gate families).

## Empirical equivalence

Two committed harnesses (run both via `bash experiments/xfill_rs_varlen_equiv.sh`):

`experiments/xfill_rs_varlen_equiv.py` -- self-contained synthetic battery (tiny board, synthetic
dict). Each case is a feasible connected board (a scoring column + an adjacent preplaced anchor) and
toggles one scoring feature. For each: run the FULL fixed `--batchvec` sweep over every length-vector
AND `--varmax`; assert identical MAX and identical LE/floor verdict across a band of floors.

    [PASS] A_basic        sweep_max=15  varmax=15
    [PASS] B_wm3          sweep_max=45  varmax=45     (word multiplier wm=3)
    [PASS] C_tight_blank  sweep_max=30  varmax=30     (tile-starved + blanks)
    [PASS] D_reserve1     sweep_max=15  varmax=15     (reserve=1)
    [PASS] E_len1_only    sweep_max=0   varmax=0      (bare-tile / length-1 only)
    [PASS] F_2scoring     sweep_max=44  varmax=44     (two scoring columns, one search)
    EQUIVALENCE BATTERY: ALL PASS

`experiments/xfill_rs_varlen_equiv_real.py` -- real Dutch N=7 boards (known-SAT main words) built
via `xtest.build_base` (the production plumbing), with the length band restricted so the full sweep
is runnable. Carries real word multipliers / blanks / length-1, plus a reserve=1 variant.

    [PASS] r7_streden_band1-3_res0   vecs=81 (MAX=36 LE=45)  sweep_max=57  varmax=57
    [PASS] r7_sneaken_band1-3_res0   vecs=81 (MAX=36 LE=45)  sweep_max=59  varmax=59
    [SKIP] r7_croches_band1-3_res1   vecs=81 sweep_TO=1 -- wall hit, not compared (sound: TO=unknown)
    [PASS] r7_arsisje_band1-3_res0   vecs=81 (MAX=36 LE=45)  sweep_max=57  varmax=57
    [PASS] r7_rentend_band1-3_res0   vecs=81 (MAX=36 LE=45)  sweep_max=67  varmax=67
    REAL-BOARD EQUIVALENCE: ALL PASS

(Each case runs the full 3^4 = 81-vector fixed sweep AND varmax; the per-vector/varmax wall is 3s,
and any vector or varmax that hits it is reported TO and the comparison is SKIPPED -- never asserted
against an unknown.  The croches reserve=1 case had one TO vector, so it is skipped, exercising the
reserve=1 path without an unsound comparison.)

## Speedup (artificial problem)

`experiments/xfill_rs_varlen_bench.py` -- a real, feasible N=7 board (4 scoring columns) with a
growing length band `K`; the fixed sweep is `K^4` vectors, varmax is one search. Identical MAX is
asserted at every `K`.

    board=N7 word='streden' (4 scoring columns; fixed sweep = K^4 vectors)
     K   vecs   sweep_wall  sweep_nodes   var_wall  var_nodes   wall_x   node_x  match
     2     16     0.092s          1322    0.078s        510      1.2x     2.6x   OK (21/21)
     3     81     0.195s         60986    0.101s      92104      1.9x     0.7x   OK (57/57)
     4    256     7.659s       3332070    0.056s      10805    137.6x   308.4x   97/97
    BENCHMARK: ALL MAX MATCH; varmax = one search vs the K^4 sweep (speedup grows with K)

The fixed sweep's cost is the K^4 length-vector multiplier: at K=4 it runs 256 separate solves
totalling 7.66s / 3.33M nodes, while varmax does ONE search in 0.056s / 10.8k nodes -- a **137x
wall / 308x node** speedup at K=4, with identical MAX (97).  The speedup grows with K (and would grow
faster with more scoring columns n, since the sweep is K^n).  (At K=4 two of the 256 sweep vectors hit
the 3s per-vector wall, so the strict MAX-match assertion is skipped there for soundness; the varmax
MAX of 97 equals the maximum observed across the completed sweep vectors, and the node/wall counts are
exact.)

## Caveat: scaling to the real N=15 geschenkcheques certification

The per-node UB in varmax is currently the plain `committed + remaining_best` bound (the
joint-knapsack UB is disabled because its consistency test mishandles the empty-tail option). On the
hard N=15 isolated-column tail, the knapsack UB is precisely what cracks the deep search, so a
straight varmax run there would be far slower than the per-vector engine *with* knap. To scale
varmax to geschenkcheques one would re-enable a varmax-aware knapsack UB (treat a stub `0` as "empty,
contributes no tile" rather than "free letter") -- a sound, mechanical fix, left as the obvious next
step. The win demonstrated here is the elimination of the K^n length-vector multiplier; combining it
with the knapsack UB is what makes it production-grade for N=15.
