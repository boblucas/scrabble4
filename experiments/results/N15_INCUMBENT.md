# N=15 incumbent-improver — beating the 1955 board

## Result

Starting incumbent: **1955** (`geschenkcheques`, `N15_best_1955.json`, verticals only on the three
×3-WORD columns {0,7,14}, vertical score 231).

A directed incumbent-improver found and **independently verified** (witness_check, require_center=True,
reserve=1) boards strictly above 1955 on the SAME word/mask (`geschenkcheques`, mask
`(0,3,7,8,11,12,14)` — the top-ceiling mask, analytic ceiling 2158):

| total | method | vertical score | verticals (col: word, score) |
|------:|--------|---------------:|------------------------------|
| 1958 | TARGET (feasibility ≥1956, warm-started from 1955) | 234 | 0:garstige 45, 3:cafezaal 25, 7:kuulkjes 72, 8:cel 9, 11:qats 25, 12:uvea 10, 14:steenweg 48 |
| 1995 | LNS (thaw {0,3,11}, re-maximize) | 271 | 0:gymshows 72, 3:chemobox 27, 7:kuulkjes 72, 8:cel 9, 11:qatveld 33, 12:uvea 10, 14:steenweg 48 |

(table updated as the portfolio finds higher boards)

The key structural change vs. the 1955 board: verticals now hang on **all 7 newly columns**
(including the ×2-LETTER cols 3 and 11 and the two plain newly cols 8,12), not just the three ×3
columns — exactly the headroom the prompt's ground-truth pointed at. The pre-placed connector web is
re-wired by the model so the SETUP board (board minus the 7 newly tiles) stays one 4-connected
component through center (7,7), and every maximal run ≥2 is a legal Dutch word; all verified.

## Why a heuristic (and why these two engines work)

The exact full-turn model — main word on row 0, an optional legal vertical `main[c]+tail` on every
newly column, a pre-placed connector keeping the setup 4-connected through center, bag−reserve — is
built correctly by `n15_push_lb_v2.solve_push`. But its CP-SAT `maximize` never closes on a full
N=15 mask (the connector/bridge fill swamps the search), so it only ever surfaced ~3-vertical ~1955
boards. The improver attacks the SAME model without proving the max:

- **TARGET (feasibility-with-target).** Replace `maximize(obj)` with the constraint `obj ≥ T` and ask
  only for a FEASIBLE board, optionally warm-started (CP-SAT solution hint) from a known board.
  Finding *a* board over a threshold is far easier than proving the optimum. Ratchet `T = best+1`.
  This took 1955 → 1958 in ~90 s.
- **LNS (large-neighbourhood search).** FREEZE the verticals of most newly columns to an incumbent
  board (hard equality), THAW a small random set of newly columns, leave the connector free, and
  re-MAXIMIZE the objective over that small neighbourhood (`obj ≥ incumbent`, so never worse). The
  frozen part keeps the subproblem small and feasible; the thawed columns find a better vertical mix
  and the connector re-wires around it. Each accepted move can jump many points at once (1958 → 1995
  in one round thawing {0,3,11}).

## The reusable engine (`experiments/n15_incumbent.py`)

Everything is dict-agnostic: all dictionary / multiplier / bag data comes from
`construct_rules('dutch', board)` via the shared `n15_push_lb_v2` model builder. No lexicon facts are
hard-coded.

- `build_model(word, mask, rows)` — builds the full-turn CP-SAT model and returns the model, the
  cells, the per-newly-column tail vars, and the exact added-vertical-score `obj` LinearExpr, with
  NO objective set. The caller chooses maximize / target / LNS-freeze and may inject a hint.
- `engine_target(word, mask, target_obj, ...)` — adds `obj ≥ target_obj`, solves feasibility,
  optional warm-start hint.
- `engine_lns_step(word, mask, base_grid, base_obj, thaw_cols, ...)` — freezes the non-thawed newly
  columns to `base_grid`, re-maximizes (or asks `obj ≥ base+1`) over the thawed set + free connector.
- `run_target` / `run_lns` — ratchet/loop drivers that re-verify every candidate with
  `witness_check.check_witness(require_center=True)` and save each new best to
  `experiments/results/turns/N15_best_<total>.json`.

The engines are parameterised purely by `(word, mask, which columns to thaw, target)` over the v2
model, so they generalise to any 15-letter word, any legal mask, any board incumbent, any dictionary
the rules object provides. Soundness gate: a total is reported ONLY when witness_check returns
ok=True; CP-SAT is just the proposal mechanism.

### CLI

    # warm-started target ratchet from the 1955 board
    python experiments/n15_incumbent.py --word geschenkcheques --mask 0,3,7,8,11,12,14 \
        --engine target --baseline 1955 --seed-board experiments/results/turns/N15_best_1955.json

    # LNS from an incumbent (thaw k random newly columns per round)
    python experiments/n15_incumbent.py --word geschenkcheques --mask 0,3,7,8,11,12,14 \
        --engine lns --thaw-k 3 --rounds 30 \
        --seed-board experiments/results/turns/N15_best_1958.json

Portfolio: launch several `--word/--mask/--engine` invocations as separate processes; each saves its
own `N15_best_<total>.json`, so the highest-numbered file is the shared global best.
