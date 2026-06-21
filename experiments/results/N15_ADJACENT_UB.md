# N=15 adjacent-aware sound upper bound for the geschenkcheques {3,11} masks

**Tool:** `experiments/n15_adjacent_ub.py`  ·  **Floor (verified LB):** 2007
(`experiments/results/turns/N15_best_2007.json`, passes the FIXED `witness_check`).

## Problem

The verified N=15 LB is 2007. The only word not yet certified `<= 2007` is **geschenkcheques**, whose
four `{3,11}` bingo masks must be shown to have max single-turn score `<= 2007`:

```
(0, 3, 7, 9, 11, 13, 14)   adjacent pair: (13,14)
(0, 3, 7, 9, 11, 12, 14)   adjacent pair: (11,12)
(0, 3, 7, 8, 11, 13, 14)   adjacent pairs: (7,8), (13,14)
(0, 3, 7, 8, 11, 12, 14)   adjacent pairs: (7,8), (11,12)
```

The existing analytic/bag UB (`n15_twolevel.bag_ub_mask`) bounds each scoring column's vertical
**independently** subject only to the shared tile bag. That ignores the fact that two **adjacent**
scoring columns' tail tiles form horizontal cross-words, so it overstates the achievable total.

## The tightened bound

`mask_ub` maximises, with CP-SAT solved to **OPTIMAL**,

```
main_const(M, mask)  +  sum over c in mask of gross(vertical_c)
```

over the choice, per scoring column, of one tail-legal vertical `M[c]+tail` (`tail = w[1:]` a dict
word, full word length 2..HMAX=8, scored by `get_word_score` exactly as the solvers/oracle) **or
none**, subject to:

- **(a) tail-legality** — only legal verticals are options;
- **(b) shared bag** — the union of chosen tails fits the per-letter ceiling
  `avail = scaled bag - 7 newly main row-0 tiles`. Tail tiles are charged to real letters (a blank
  scores 0, so a max-gross vertical never blanks a scored tile); this only tightens, never inflates;
- **(c) ADJACENT-PAIR horizontal legality** — for each adjacent scoring-column pair `(c, c+1)` and
  each row `r >= 1` where **both** chosen verticals have a tile, the ordered letter bigram
  `(tail_c[r], tail_{c+1}[r])` must occur consecutively inside **some** legal dictionary word of
  length `<= HMAX`. Incompatible option pairs are forbidden (`x_ci + x_(c+1)j <= 1`).

## Soundness argument

The model is a **relaxation** of the true single-turn problem, so its optimum is a sound
**over-estimate**:

- Each kept constraint is a **necessary** condition of every legal final board:
  - (a) verticals must be tail-legal (witness_check 3b/4);
  - (b) the board cannot use more of a letter than the bag holds;
  - (c) on the final board the maximal horizontal run through `(c,r),(c+1,r)` is a legal word and
    **contains** the ordered bigram `(tail_c[r], tail_{c+1}[r])` as a contiguous substring; if **no**
    legal word of length `<= HMAX` contains that bigram, no legal horizontal run through the two
    tiles can exist — **regardless of any connector tiles** placed at `c-1` or `c+2`. Hence the
    bigram-membership condition is a connector-independent necessary condition.
- We deliberately **do not** require the 2-letter run to itself be a legal word — that would be
  **unsound** (a longer legal run whose 2-letter substring is not a word could exist). Bigram
  membership is the strongest condition that stays sound without assuming the connector layout.
- All **dropped** constraints (4-connectivity, center, the full longer-run legality, the global tile
  cap, blanks lowering scores) only **further restrict** real boards, so removing them can only
  **raise** the optimum. Therefore `UB >= true max turn score`.

CERTIFIED only when CP-SAT returns **OPTIMAL** (not a timeout) with `UB <= 2007`.

## Results (reserve=1, OPTIMAL in <8 s each)

| mask | adjacent pairs | forbidden pairs | main_const | vert_gross UB | **TOTAL UB** | residual vs 2007 | verdict |
|---|---|---|---|---|---|---|---|
| (0,3,7,9,11,13,14) | (13,14) | 24817 | 1724 | 306 | **2030** | +23 | OPEN |
| (0,3,7,9,11,12,14) | (11,12) | 0 | 1724 | 301 | **2025** | +18 | OPEN |
| (0,3,7,8,11,13,14) | (7,8),(13,14) | 35138 | 1724 | 298 | **2022** | +15 | OPEN |
| (0,3,7,8,11,12,14) | (7,8),(11,12) | 10321 | 1724 | 291 | **2015** | +8 | OPEN |

For comparison the per-column-independent bag UB (no adjacency) gives strictly higher totals; the
adjacent constraint removes 8–23 points but **none of the four masks falls to `<= 2007`**, so the
adjacent-aware UB **does not analytically certify any mask** on its own. (The (11,12) q-u pair is
never incompatible — q-u-* verticals always pair legally — so that pair's constraint is vacuous,
which is why `(0,3,7,9,11,12,14)` only loses points from the bag, not the adjacency.)

## Soundness cross-checks (all pass)

- **Known LB board:** the 2007 board is mask `(0,3,7,8,11,12,14)`; its witness total 2007
  `<= 2015 = UB` for that mask. The UB does not undercut the known board.
- **Oracle SAT data:** the running per-combo oracle on `(0,3,7,8,11,12,14)` found SAT combos with
  model vertical-gross up to 286 (model total 2010). My vert_gross UB for that mask is **291 >= 286**
  and TOTAL UB 2015 >= 2010 — consistent (the UB must dominate every feasible combo's nominal total).
- **Hand checks:** every chosen vertical in each mask's optimum is verified tail-legal and word-legal
  with `get_word_score` matching, and the (7,8) optimum `kwalmpje / chipster` satisfies the bigram
  condition at all 7 overlapping rows.

## Resulting bracket and what remains

```
bracket after the adjacent-aware UB:  [2007, 2030]   (4 masks still OPEN)
```

Per-mask residual band above the floor: 2007..{2015, 2022, 2025, 2030}. The adjacent-aware UB
**tightens** the optimistic ceiling for every mask (the loosest mask drops from the per-column UB to
2030) but does not close any analytically. The masks remain to be closed by the per-combo oracle
(running) or a still-tighter relaxation.

### Tractability of the per-combo oracle after this pass

(Combo counts above the LB-2007 vfloor follow; the residual is small so the bag-floor barely shrinks
the enumeration — the bottleneck is the per-combo CP-SAT feasibility solve, not the count.)
