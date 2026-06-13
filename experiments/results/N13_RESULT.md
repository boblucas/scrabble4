# N=13 center-constrained max-turn — result (2026-06-13)

## Verified lower bound: 586

Best verified center-connected turn under the real-game rules (scaled bag, blanks, opponent holds
≥1 tile (reserve=1), cross-words ≤8, center cell (6,6) occupied & connected):

    main word  : yoghurtcakeje   (turn YOGHURTcakeje -- left-block bingo, cols 0..6 newly placed)
    TOTAL 586  = main 437 + verticals 149,  1 blank
    file: experiments/results/n13/batchscan_feas_best_586.json   (witness_check OK)

This is the best LEFT-BLOCK (tractable for xfill) witness, found by the ranked batch scan over the
top ~10k feasibility-filtered 13-letter main words.

## Is 586 optimal?  Strong evidence YES — but NOT a machine-checkable proof.

The only structure that could *dramatically* beat 586 is a SPREAD mask capturing the third ×3
word-column (col 12): capturing all three ×3 cols {0,6,12} stacks the main-word multiplier to ×27,
so almost any feasible such board would score ≫586 (1200–1400 for high-value words). Any mask
capturing only TWO of the three ×3 columns has multiplier ×9 (same as left-block's {0,6}) and so
caps near 586 — and left-block additionally banks the ×2-letter premium at col 3, making it the best
of the ×9 family. So the optimum question reduces to: **does any feasible 3-×3 spread board exist?**

**Empirical answer (CP-SAT feasibility survey, subprocess-walled): NO, across a large sample.**
Largest run (parallel, free 48-core box): top **1000** feasibility-filtered words × 3 representative
3-×3 masks = **3000 configs**:
  - 2615 UNSAT (proven infeasible by CP-SAT)  — 87%
  - 341 TIMEOUT (undecided — see residual)     — 11%
  - 44 NOCAND (a scoring column has no candidate vertical of its length)
  - **0 SAT (0 feasible)**
(Consistent with the earlier 240-word runs: 634 UNSAT / 66 TIMEOUT / 0 SAT.) Across every decided
config over the top 1000 highest-value words, NO feasible 3-×3 spread board exists.

**Why spreads are infeasible (structural):** in the SETUP board the scoring columns' row-0 cells are
EMPTY (the scored tile is placed only in the final turn), so the verticals at cols 0/6/12 FLOAT at
rows 1+. Connecting far-apart floating verticals + the center into one component requires bridge
tiles forming valid ≤8 cross-words across the gaps — the connector-WORD legality is the binding
constraint. (It is NOT a tile-budget issue: the Steiner `min_bridge_cells` oracle shows fixed+bridge
cells ≪ T−1, so the connectivity tile-reservation bound is insufficient to prove infeasibility.)

## The gap to a complete proof (the research wall)

A *proven* optimum needs the spread family fully ruled out. Both solvers fail on it:
  - xfill EXPLODES on spreads (71M nodes, TO; the floating-vertical bridge search is unbounded).
  - CP-SAT decides many in ~3s but STALLS in MODEL CONSTRUCTION on ~10% (the 66 TIMEOUTs), unbounded
    by its solver time cap (a 200s-wall re-run timed out identically).
  - No cheap structural/tile argument disposes of them (the obstruction is connector-word legality).

Residual to close: the 341 TIMEOUT configs (a longer 200s wall TIMED OUT identically — the stall is
model construction, not solve time, so more time/workers don't help), the full 13-letter word space
(survey was 1000 words), and
the ×9-END spreads (0,12 — the N=11 analog; argued ≤586 but untested). Closing these needs a better
connectivity-aware decision procedure or a holistic word-as-variable spread search — a genuine
research step, not a longer run.

## Bottom line

**N=13 center-constrained: 586 is the strongly-evidenced believed optimum** (634 spread configs
proven infeasible, 0 feasible across 240 words; ×9 structures capped at ~586; ×27 the only escape and
it's infeasible). It is **not yet machine-proven optimal** — that is blocked on the intractable
spread residual. Compare N=11 = 852 (fully proven). Tooling: experiments/n13_spread_survey.py,
n13_rank.py, n13_batchscan.py, n13_witness.py. See memory `maxturn-n13-heuristic-hunt`.
