# N=15 max-turn: parallel per-combo oracle (geschenkcheques {3,11} masks)

**Status: IN PROGRESS** (this file is finalized when the mask-(8,12) run completes).

## Setup
- Verified LB on entry: **2007** (`experiments/results/turns/N15_best_2007.json`, FIXED witness_check,
  `geschenkcheques`, mask (0,3,7,8,11,12,14), require_center=True, reserve=1).
- Only open word: `geschenkcheques`; 4 masks with both scoring cols 3 & 11. All 25 other threat
  words already certified <= 2007.

## Method (sound two-level decomposition)
For a fixed mask, `total = main_const(M, mask) + sum_c vert_gross(c)`. `main_const = 1724` for all
4 masks (same 7 row-0 main tiles charged once). A **combo** = one tail-legal vertical (or none) per
scoring column whose tails fit the shared bag.

1. **Enumerate** every combo with `total > LB` (vfloor = LB - main_const = 283), descending by gross,
   via `enumerate_above_fast` (multiple-choice-knapsack DFS, suffix-gross UB — never discards a
   feasible higher-gross combo, so the set is COMPLETE).
2. **Oracle** each combo with the EXACT CP-SAT feasibility solve `oracle_feasible` (full row+col
   <=HMAX legality, flow-to-center connectivity, bag/blank/reserve, verticals FIXED, connectors
   allowed below): proven SAT / proven UNSAT / UNKNOWN(timeout).
3. First SAT whose **FIXED witness_check** total > LB -> raise LB (save board). All UNSAT -> mask
   CERTIFIED <= LB. Any UNKNOWN (timeout, never counted as infeasible) -> mask OPEN.

Parallel driver `experiments/n15_oracle_parallel.py`: process pool, `CPSAT_WORKERS=1` per solve so
N solves run concurrently; resumable JSONL ledger keyed by combo id; targeted-PID cleanup only.

## Combo counts at LB=2007 (vfloor=283)
| mask | combos > vfloor | complete? | bag-UB total |
|------|-----------------|-----------|--------------|
| (0,3,7,**8**,11,**12**,14) | **81,872** | YES | 2015 |
| (0,3,7,**9**,11,**12**,14) | 339,539+ | capped (>>) | 2020 |
| (0,3,7,**8**,11,**13**,14) | 2,169,393+ | capped (>>) | 2025 |
| (0,3,7,**9**,11,**13**,14) | 11,840,826+ | capped (>>) | 2028 |

Only mask (8,12) is tractable at LB=2007 (~5s/oracle, ~82k combos). The other three are millions+
and remain intractable unless the LB rises substantially (which would shrink their bands).

Per-oracle observation: all combos tested so far return **proven UNSAT** in ~5s; **zero UNKNOWN**
(cap=120s >> avg solve), so the certification basis holds (no timeouts counted as infeasible).

## Result
_(filled in on completion)_
