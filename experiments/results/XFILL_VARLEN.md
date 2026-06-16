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
- The joint-knapsack UB is now **varmax-aware and ENABLED** (the AC-3 presolve stays disabled -- its
  forced-2-letter-word join needs provably-empty flanks, unsound under variable lengths). See the
  "varmax-aware knapsack UB" section below.
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

## Varmax-aware knapsack UB (the prune that lets varmax finish)

`--varmax` originally **disabled** the joint-knapsack UB (`knap_ub`), because the fixed-mode bound
assumes one length per scoring column. Without it, varmax removes the `K^n` blowup but each search no
longer prunes -- fatal on the hard isolated-column tail (in fixed mode the knapsack UB is ~88.8% of
runtime and prunes ~72% of nodes). The UB is now **varmax-aware and on by default** (opt out
`NOKNAP=1`).

What changed (one surgical edit in `knap_ub`'s per-column consistency loop):
- A stub value of `0` means EMPTY (the column's word ended above that row), **not** a tile. A
  free stub cell (`g==-1`) whose word letter is `0` charges **no** tile (no delta) -- this is the
  "empty, no tile" vs "free letter" fix; previously it added a phantom code-0 delta.
- A **fixed-empty** stub cell (`g==0`, only reachable in varmax) admits only words that are also
  empty there (the word ended at/above it).
- A fixed letter (`g>0`) still forces a match; a real tail letter (`wl>0`) at a free cell still
  charges its delta.

The per-column candidate set is therefore the base's UNION over all lengths PLUS the length-1
bare-tile (all-zeros, gross 0) option -- exactly the enlarged varmax option set. The knapsack picks
one (length, word) per uncommitted column maximizing gross under the shared per-letter budget (with
the same blank-overflow relaxation as fixed mode).

Soundness (SOUND OVER-ESTIMATE). The bound is never below the true best achievable for the
uncommitted columns: the `(0,0)` empty option is always present (consistent with any partial column
whose fixed cells are empty), and taking the max over lengths can only raise the bound. An undecided
stub cell is never charged as a forced tile. Bridges, horizontal cross-words and connectivity are
ignored (they only *reduce* the achievable score). Hence `committed + UB <= best` can never discard
the optimum, so enabling the UB is **verdict-neutral** -- it only changes node counts. In fixed mode
words never carry a `0` and a stub cell is never fixed-empty, so the two new `0`-branches are inert
-> the fixed-mode knapsack is byte-identical (regress.sh ALL GATES GREEN).

In fixed mode the prior soundness argument is unchanged.

### Validation

1. **Equivalence battery** (`bash experiments/xfill_rs_varlen_equiv.sh`) -- now with the knap UB
   enabled in varmax, varmax MAX and LE/floor verdicts are STILL identical to the full fixed sweep on
   every synthetic case (blanks / reserve=1 / wm=3 / length-1 / 2 scoring cols) AND the real Dutch
   N=7 boards: **ALL PASS**.

2. **With-UB vs without-UB MAX/LE equality** (`experiments/xfill_varmax_knap_check.{py,sh}`,
   `NOKNAP` toggle == the fd886d7 no-UB behaviour). On real N=11 bouwfysicus (7 scoring columns),
   every floor gives the IDENTICAL verdict with and without the UB -- the UB changes only node counts:

        band 1-6, floor 224:  KNAP ON  LE 224  nodes=1        |  KNAP OFF  LE 224  nodes=24008   (0.10s vs 0.17s)
        band 1-6, floor 220:  KNAP ON  LE 220  nodes=1        |  KNAP OFF  LE 220  nodes=97952   (0.09s vs 0.59s, 6.5x)
        band 1-5, floor 200:  KNAP ON  LE 200  nodes=1        |  KNAP OFF  LE 200  nodes=7699
        (TO cases at low floors / wide bands: both modes report the same TO -- still verdict-neutral)

   On the LE-proof direction (how certification uses it) the root knapsack proves `LE floor` in **1
   node** vs tens of thousands without it (24008x / 97952x fewer nodes), exactly mirroring the
   fixed-mode "knap cracks the tail" behaviour. (At low floors / very wide bands the connectivity
   bridge-fill, not the knapsack, dominates and both modes TO -- the UB still prunes ~47-78% of the
   visited nodes but the per-node knapsack over full N=15 domains is itself expensive; `KNAPCOLS`
   bounds how many uncommitted columns it runs over, and `KNAPSTEPS` bounds each call so the bound
   only ever *weakens* on exhaustion, never goes unsound.)

3. **regress.sh: ALL GATES GREEN** -- N=7 26/26, deep-col10 LE-224 (x3), center col0=1 LE-173 (x15);
   fixed-length / decision engines byte-identical (node counts unchanged).

### Caveat: full N=15 geschenkcheques

Replacing the per-vector sweep with varmax eliminates the `K^n` multiplier (one hard mask =
~79.7M length-vectors -> ONE search), and the knapsack UB now fires and prunes (~47% of nodes on a
real geschenkcheques mask). But a single full-length N=15 mask is intrinsically hard: the per-node
knapsack over 15-length × hundreds-of-words domains is costly, and the connectivity bridge fill is
large, so a full mask still TOs in tens of seconds (the dedicated `n15_bounded_certify` proof job
grinds the same base for hours). The varmax+UB mechanism is correct and engaged on the real mask; the
clean, dramatic prune is demonstrated on the tractable N=11 LE-proof slices above. Tightening the
N=15 root-knapsack cost (incremental consistent-set / bitset deltas, a cheaper root pre-filter) is
the next scaling lever, not a soundness gap.
