# A learning-based solver (CP-SAT + lazy connectivity) for the N=15 max-turn model

**Question.** The bespoke Rust B&B `xfill --varmax` exhaustively maximizes the vertical cross-word
score of an N=15 setup board but has NO conflict learning -- it re-derives the same infeasibilities
billions of times and cannot close the hard `{3,11}` masks (those capturing BOTH x2-letter columns
3 and 11). Can a **learning** solver -- CP-SAT with clause learning, fed connectivity LAZILY -- close
what the B&B can't?

**Answer (honest).** No. A learning solver does NOT close the hard `{3,11}` masks. It is, however,
*correct* (matches xfill everywhere both complete) and on the *easy* high-floor `LE` slices it is
competitive-to-faster than xfill. The decisive obstacle is not the search but the **model**: encoding
the legality dictionary as a CP-SAT `add_automaton` over a 15x15 board produces a model whose
**presolve does not terminate in practical time** once the score floor is low enough to leave a large
feasible region -- exactly the regime the hard masks live in. Clause learning never gets a chance to
help because CP-SAT cannot get through presolve to search.

This corroborates the earlier negative CP-SAT result in MEMORY (`single_component_flow` did not close
hard instances): the wall is structural, and lazy connectivity does not move it.

## What was built

- **`experiments/n15_cpsat_lazy.py`** -- the encoder + solver driver.
  - Encodes the EXACT xfill `--varmax` model from a BASE file (DIMS/COUNTS/SCORES/PREPLACED/
    NONSCORING/RESERVE/DICT/BCOL/BLEN/WORDV), MINUS connectivity:
    - Per scoring column: ONE `add_allowed_assignments` table over the stub cells `[rows 1..maxlen-1]`
      PLUS a tabled `gross` variable (the table is the union over all lengths, padded with 0 = empty
      tail, plus the all-0 bare-tile/length-1 option). The objective is `sum of the tabled gross`.
      Using a table (model size independent of candidate count) instead of a per-candidate selector +
      per-cell reified equality was the single change that made the model loadable -- see "model size".
    - Bridge cells (nonscoring columns, rows 1..H-1): free letter or empty.
    - Row 0: preplaced = fixed letters; scoring cells forced EMPTY in the setup (the newly placed main
      tile does not participate in setup connectivity / cross-words, exactly as xfill's grid).
    - Legality: the minimal position-independent row automaton (`dawg.position_independent_row_automaton`)
      on every ROW and every BRIDGE column; scoring columns are validated by their word-domain table.
      All 26 single letters are injected into the automaton dictionary so an isolated single tile is
      legal (xfill validates only runs >=2; the real Dutch dict already contains all singles, so this
      is a no-op there and a correctness fix for synthetic dicts that omit them).
    - Bag: per-letter non-blank usage <= bag count via the one-hot (`tiles_c <= counts_c + b_c`,
      `sum_c b_c <= blanks`), and `reserve`: total setup tiles <= `sum(counts)+blanks-reserve`.
  - **LAZY connectivity** (iterative solve / check / cut): solve; read the active SETUP cells; if they
    are ONE 4-connected component containing the ROOT (= the first preplaced cell, == xfill's
    `mandatory[0]`; NOT the center -- xfill's optimization model does not enforce the center, that is a
    separate `witness_check(require_center=True)` post-condition), accept; else add a CUT for every
    non-root component C: `OR_{c in C} ~active[c]  OR  OR_{b in boundary(C)} active[b]` ("break C, or
    bridge it"), which forbids exactly that disconnection without excluding any connected board, and
    re-solve. CP-SAT's clause learning generalizes the cuts across re-solves.
  - Two modes:
    - `--mode le` (DECISION / certification): assert `obj >= floor+1` and solve for FEASIBILITY.
      INFEASIBLE under the accumulated cuts => `LE floor` PROVEN (the certification direction).
    - `--mode max` (maximize under lazy connectivity): reports the exact MAX. (Far slower on N=15.)
- **`experiments/n15_cpsat_compare.py`** -- the committed correctness comparison (PASS/FAIL table),
  including an independent re-validation of any emitted SETUP board (legality of every maximal run,
  4-connectivity to the root -- sharing no code with the solver, the witness_check invariants).

Why CP-SAT and not MaxSAT: OR-Tools 9.12 is already integrated and gives the lazy-cut loop + clause
learning in one place; `python-sat` (RC2) was installed and available, but the binding constraint
turned out to be MODEL INGESTION (presolve), which a MaxSAT encoding of the same automaton+table
legality would share (or worsen -- a CNF encoding of the 154k-word automaton is larger still). The
CP-SAT result is therefore the representative learning-solver result.

## Correctness (the bar: match xfill where xfill completes)

`python experiments/n15_cpsat_compare.py` -> **14/14 PASS -- ALL MATCH**:

| family | check | result |
|---|---|---|
| 6 synthetic bases (tiny board, synthetic dict; blanks / wm=3 / reserve=1 / length-1-only / 2 cols) | xfill MAX == cpsat MAX (mode=max) + emitted SETUP board re-validated legal+connected | **6/6 PASS** (15, 45, 30, 15, 0, 44) |
| 8 N=15 already-CERTIFIED masks (4x `LE 501`, ... `LE 636`) | xfill `LE vfloor` == cpsat `LE vfloor` (mode=le) | **8/8 PASS**, each in 3.8-5.6s |

Every emitted SETUP board passed independent re-validation (every maximal run >=2 a dict word; one
4-connected component to the root) -- the witness_check invariants, re-derived from first principles.
(N=15 witnesses in the HARD score region cannot be emitted because the optimum is exactly the part
CP-SAT cannot reach; the emitted-board check is exercised on the synthetic battery, where the optimum
IS reachable. On the real Dutch dict the row-0 main word is itself a real word; in the synthetic
battery it is not, which is why only the SETUP -- the part xfill's model validates -- is re-checked.)

No mismatch was found: where xfill completes, the learning solver returns the identical verdict.

## Benchmark: the hard {3,11} mask

Mask `0,3,7,8,11,12,14` of geschenkcheques (captures both x2 cols 3 and 11), base
`experiments/results/certs/n15hunt_3_11_v2/base_0_3_7_8_11_12_14.txt`. Certification target =
`LE vfloor=231`. Build time (CP-SAT model construction, unbounded by the solve time limit) ~3.3-4.7s;
6,333 vars / 551 constraints (7 tables + 23 automata + 521 linear).

CP-SAT proves `LE floor` for HIGH floors quickly, but the cost EXPLODES super-exponentially as the
floor drops toward the true achievable max, and it cannot reach the certification target:

| floor | xfill `--varmax` | CP-SAT lazy (mode=le) |
|---|---|---|
| 636 / 500 / 460 / 440 | `LE` nodes=1, ~0s (root knapsack) | `LE` **~0.3s** (presolve fixes it) |
| 430 | `LE` ~0s | `LE` **0.2s** |
| 428 | `LE` ~0s | `LE` **0.3s** |
| 425 | `LE` ~0s | `LE` **1.0s** |
| 422 | `LE` ~0s | `LE` **3.9s** |
| 418 | `LE` ~0s | **does NOT finish** (>60s; presolve `PresolveToFixPoint` then stalls) |
| **231 (target)** | **TO** -- 23.6M nodes / 60s, best=231, NO proof | **does NOT finish** -- presolve stalls; no proof |

Both solvers find a board scoring 231 (the verified lower bound) but neither proves it optimal.

**Where the time goes.** With `log_search_progress`, CP-SAT spends its time in *presolve*
(`PresolveToFixPoint`, 3.8-4.9s per loop, then `ExtractEncodingFromLinear`, then a later stall),
NOT in CDCL search. `max_presolve_iterations=1`, `cp_model_probing_level=0`, even
`cp_model_presolve=False` do not help: the `add_automaton` constraints over a 154,955-word dict on
15-cell lines must still be EXPANDED into the internal representation, and that expansion (single
threaded, not subject to `max_time_in_seconds`) is the wall. At a high floor the floor constraint
collapses the model during presolve so it terminates; at a low floor (231) the feasible region is
large, presolve cannot fixpoint, and search never starts -- so clause learning never engages.

This is why "lazy connectivity + clause learning" does not rescue CP-SAT: the bottleneck is upstream
of search. (For reference, the older selector-based encoding was ~234k constraints / 2.76M automaton
transitions and would not even *load*; the table rewrite cut that to 551 constraints and made the
high-floor slices solvable -- but the automaton-expansion presolve wall remains at low floors.)

## Verdict

- **Correctness: PASS.** The CP-SAT lazy-connectivity solver matches xfill on every instance where
  xfill completes (6 synthetic exact-MAX, 8 N=15 CERT `LE`), and every board it emits independently
  re-validates as a legal, connected setup. The lazy-cut loop is sound (cuts forbid only disconnected
  configurations) and the LE-decision proof is sound (INFEASIBLE under cuts+floor => `LE floor`).
- **Does learning close the hard {3,11} masks? NO.** CP-SAT cannot close the certification target
  (`LE 231`); it stalls in presolve before search/learning begins, mirroring the earlier
  `single_component_flow` negative result. The win is narrow: on high-floor `LE` slices (>= ~422) it
  is fast (sub-second to a few seconds) and competitive with -- occasionally faster than -- xfill's
  root knapsack, but those slices are not the hard part.
- **vs the bespoke B&B.** xfill's model-specific machinery (the varmax-aware joint knapsack UB, the
  `sfx2` budget-coupled suffix bound, the incremental consistent-set) prunes the score space far more
  effectively at low floors than CP-SAT's generic CDCL ever reaches, because CP-SAT pays an enormous
  fixed cost just to represent the dictionary. The right lever for the hard masks remains a tighter
  bound INSIDE xfill's interleaved search (per the rootbound / hotspot notes), not an off-the-shelf
  learning solver.

## Reproduce

```
source .venv/bin/activate
python experiments/n15_cpsat_compare.py                 # 14/14 correctness table
# hard-mask benchmark (high floor closes fast; low floor / target does not):
python experiments/n15_cpsat_lazy.py \
    experiments/results/certs/n15hunt_3_11_v2/base_0_3_7_8_11_12_14.txt \
    --mode le --floor 440 --wall 60        # -> LE 440 in ~0.3s
python experiments/n15_cpsat_lazy.py \
    experiments/results/certs/n15hunt_3_11_v2/base_0_3_7_8_11_12_14.txt \
    --mode le --floor 231 --wall 300       # -> does not finish (presolve wall)
```
