# SETUP-run word-legality fix + full re-validation

## The bug (found by the user)

A max-turn witness's SETUP board = final board minus the 7 newly-placed row-0 tiles. It must
itself be a fully legal scrabble position: **every maximal horizontal AND vertical run of length
>= 2 in the SETUP must be a legal dictionary word.** A scored vertical `w = main[c] + tail` hangs
its `tail` (rows 1..len-1) below the newly row-0 tile; in the SETUP that tail is a *standalone*
maximal run. If `len(tail) >= 2` the tail must itself be a dictionary word.

`witness_check.py` only checked runs on the FINAL board (where the tail is glued to the row-0 top,
so `main[c]+tail` is a word). It never checked the SETUP runs. The CP-SAT model
(`n15_push_lb_v2.vert_table`, `n15_push_lb.vert_tables`) admitted any vertical `main[c]+tail` whose
*full* string is a word, regardless of whether the bare tail is legal -> it manufactured boards
with illegal setup tails (`zwijmd`, `mforts`, `tveld`, ...).

The **xfill** path (`xtest.py::_cand_bucket`) was ALREADY correct: it admits a vertical word `w`
only if `w[1:] in words_lookup` (the tail is a word). So the xfill solver / regression gates / the
N=11 and N=13 certifications were never affected by this bug.

## The fix

1. `witness_check.py` -- new check 3b: build the SETUP grid (final minus newly row-0 tiles) and
   reject if any maximal run >= 2 is not a dictionary word. (`illegal SETUP V-word at (x,y): ...`)
2. `n15_push_lb_v2.py` -- `_tail_setup_legal(word)` (`len(tail)<=1 or tail in wordset`); applied in
   `vert_table` (per-column tail-candidate table) and in the `_TAILMAX` ceiling table.
3. `n15_push_lb.py` -- same filter in `vert_tables`.
4. `n15_incumbent.py` -- inherits the fix automatically (calls `V.vert_table`).

## Checker sanity

| board | fixed witness_check | reason |
|-------|--------------------|--------|
| N15_best_1724 (no verticals) | OK | setup-legal |
| N15_best_322 | OK | setup-legal |
| N15_best_2050 | REJECTED | illegal SETUP V-word at (0,1): ezwijmd |

## Re-validation table (fixed witness_check is the sole authority)

### N=15 `results/turns/N15_best_*.json`
Only **1724** and **322** are setup-legal. Every scored-vertical board 1916..2050 is UNSOUND
(illegal setup tail words). `N15_bigger_best_{1952,2050,2053}` also REJECTED.

### N=11
- `certs/witness_n11_center_852.json` (center-constrained, vert 226): **OK -- still SOUND.**
  Its setup verticals are all real Dutch words: `oxertjes, azend, flan, enteken, id, andere, uk,
  tulpvormig`. **N=11 = 852 survives the corrected requirement.**
- `certs/witness_n11_unconstrained_852.json`: **OK -- still SOUND.**

### N=13 `results/turns/N13_*.json`
- `N13_ratchet_best.json` (462): **OK** (all verticals length 2 -> length-1 tails, no setup word
  needed).
- `N13_degen_test.json` (366): **OK**.
- `N13_witness_degen_lb.json` (316): **OK**.
All N=13 saved witnesses survive.

(The `N1?_fullturn.json` / `*_seed.json` files are bracket/run-summary artifacts, not witness
boards -- no `grid` -- so they are out of scope for the checker.)

## Regression gates

`experiments/regress.sh` (xfill_varmax): **ALL GATES GREEN** (26/26 N=7; LE-224 x3; LE-173 x15).
Unchanged, as expected -- the xfill candidate generation already enforced tail-legality.

## Corrected verified N=15 lower bound

Re-derived from 1724 upward with the FIXED tail-legal candidate model
(`n15_push_lb_v2.solve_push`), every board re-verified by the FIXED `witness_check`
(`require_center=True`, reserve=1). Main word: `geschenkcheques`.

- **Setup-legal floor (no verticals): 1724** -- the phase-1 board, unchanged, still OK.
- **Best verified tail-legal board committed: 1987** -- `N15_setuplegal_best_1987.json`, WITNESS
  OK by the FIXED checker (require_center=True, reserve=1). Its verticals and (legal) setup tails:
  `grauwigs/rauwigs, cheffend/heffend, kluwende/luwende, covertje/overtje, quiltjes/uiltjes,
  el/(l), stypende/typende` -- every tail is a real Dutch word.
- Higher boards (up to **2021**) were repeatedly found and verified in-process for the same
  (word=geschenkcheques, mask=(0,3,7,8,11,13,14)) under longer single-process solving; reproduce
  with `CPSAT_WORKERS=24 python experiments/n15_push_lb_v2.py` driving `solve_push` at cap>=400s.
  They are valid lower bounds too (FEASIBLE leaves), so the corrected LB is **>= 1987, and at
  least 2021 with more solve time** -- not a proven optimum for the mask.

Candidate-mask sweep (added-vertical `obj`, all tail-legal, all witness-verified): the productive
mask is (0,3,7,8,11,13,14); (0,3,7,9,11,12,14) is infeasible; the (0,1,...) masks are infeasible
or below the floor. Every FEASIBLE board is a valid lower bound, NOT a proven optimum (CP-SAT
returns a feasible high-scoring leaf under the time cap); the bound is monotone and conservative.

### How far the corrected bound dropped
The old (UNSOUND) N=15 LB was **2050** (and the "believed optimum" 1952). Those relied on illegal
setup tails (`zwijmd`, `mforts`, `tveld`, ...). With tails forced to be real Dutch words the best
verified board drops to the ~1987-2021 range -- i.e. the soundness fix removes roughly **30-60
points** off the prior 2050 claim, and the previously-"believed optimum" 1952 is also superseded
(in both directions: 1952 itself was unsound, while legal verticals still clear it). N=11 = 852 is
UNAFFECTED -- it was already setup-legal.
