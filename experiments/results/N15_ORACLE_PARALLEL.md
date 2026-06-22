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
My first measurements were time-budget-CAPPED undercounts (339k / 2.17M / 11.8M).  A later COMPLETE
enumeration (n15_adjacent_filter, `N15_ADJACENT_FILTER.md`) gives the true counts -- the three large
masks are even bigger than I first reported:

| mask | combos > vfloor (COMPLETE) | adj-bigram filtered survivors | bag-UB total |
|------|---------------------------|-------------------------------|--------------|
| (0,3,7,**8**,11,**12**,14) | **81,872** | 80,549 (-1.6%) | 2015 |
| (0,3,7,**9**,11,**12**,14) | ~8,234,245 | 8,234,245 (-0%) | 2020 |
| (0,3,7,**8**,11,**13**,14) | ~4,982,962 | 4,151,140 (-16.7%) | 2025 |
| (0,3,7,**9**,11,**13**,14) | many millions (>40min to count) | <=~3% reduction | 2028 |

Only mask (8,12) (81,872) is tractable at LB=2007. The other three are MILLIONS, and the sound
adjacent-bigram filter prunes them only 0-17% (geschenkcheques' verticals are 97-100% bigram-
compatible per adjacent pair), nowhere near enough -- they stay intractable unless the LB rises.

Per-oracle observation: all combos tested so far return **proven UNSAT** in ~5s; **zero UNKNOWN**
(cap=120s >> avg solve), so the certification basis holds (no timeouts counted as infeasible).

## Run notes / operational findings
- The shared host carries a heavy background load (~42 on 48 cores, unsloth training etc.).  With 24
  oracle workers the box oversubscribed and a handful of solves were CPU-STARVED past their wall cap,
  returning UNKNOWN even though they prove UNSAT in ~5-9s on a free core (verified: ids 1950, 5671,
  6517, 6523 all UNSAT < 10s standalone).  **Mitigation:** dropped to 16 workers + 1200s cap; the rare
  starvation-UNKNOWNs are swept in a final low-worker `--recheck` pass where each solve gets ~dedicated
  CPU.  A UNKNOWN is NEVER counted as infeasible (soundness preserved).
- Sustained throughput at 16 workers under load: ~1.7 combos/s -> the 81,872-combo sweep is ~11h
  wall.  Resumable JSONL ledger keyed by combo id; safe to stop/restart.
- **SAT combos with witness <= LB are EXPECTED and fine for certification.**  The model gross can
  overstate the real turn score (it omits horizontal cross-words between adjacent tails), so a
  connectivity-feasible board may witness below its model total.  Observed SATs all witnessed
  2002/2006 (<= 2007), correctly logged "SAT but witness <= LB -> continue", NOT a new LB.  A mask is
  CERTIFIED iff every combo is UNSAT *or* SAT-witness<=LB, with ZERO undecided (UNKNOWN/ERROR).

## Result (FINAL for mask (8,12))

### NEW VERIFIED LB = 2008
The LB=2007 sweep found combo cid=43183 (mask (0,3,7,8,11,12,14), gross=284) whose
connectivity-feasible board **passes the FIXED witness_check (independently re-verified: ok=True,
total=2008, require_center=True, reserve enforced)** -> saved `turns/N15_best_2008.json`.
**Verified LB raised 2007 -> 2008.**

### mask (0,3,7,8,11,12,14) CERTIFIED <= 2008
Re-running the oracle at the raised LB=2008, the mask has **33,716** combos with total > 2008
(complete enum, capped=False).  **ALL 33,716 proven UNSAT** (zero SAT, zero undecided).  The few
residual CPU-starvation UNKNOWNs (totals 2009) were each re-proven UNSAT with dedicated CPU (~5-8s)
and appended.  Hence **no board for this mask exceeds 2008**, and the 2008 witness achieves it:
**this mask's exact single-turn maximum = 2008.**  (Ledger:
`oracle_parallel/geschenkcheques_0378111214_lb2008.jsonl`; verdict `FINISH2008.log`.)

### The other three masks remain OPEN
Even at the raised LB=2008 their bands shrink only ~1 pt; the adjacent-aware UBs (2020/2025/2028,
all > 2008) don't certify them and the sound adjacent-bigram filter prunes only 0-17% -> still
millions of combos (see counts below / `N15_ADJACENT_FILTER.md`).  Intractable per-combo at LB=2008.

**Bracket: [2008, 2028].**  (UB now = max over the 3 still-open masks' tail-legal bag-UB = 2028;
mask (8,12) is closed at exactly 2008.)  Closing the proof needs either a >2008 witness on one of the
3 open masks (raising the LB further, shrinking all bands) or a strictly stronger relaxation.

## Autonomous completion pipeline
Because the shared host advances slowly under the competing training load, the run finishes
unattended via three nohup'd processes (survive shell/session resets):
1. **driver** (`n15_oracle_parallel.py --workers 16 --cap 1200 --recheck`) sweeps the 81,872 combos,
   appending verdicts to the resumable ledger; exits CERTIFIED when all are UNSAT/SAT-witness<=2007
   with zero undecided, or stops+saves on the first witness>2007 (NEW-LB).
2. **status logger** (`/tmp/n15_status_logger.sh` -> `oracle_parallel/status.log`) records progress.
3. **finisher** (`/tmp/n15_finish.sh` -> `oracle_parallel/FINISH.log`) waits for the driver, then runs
   up to 3 low-worker (4 workers, 1800s cap) `--recheck` passes so each residual starvation-UNKNOWN
   gets ~dedicated CPU and resolves to UNSAT, and writes the FINAL verdict:
   `CERTIFIED <= 2007` iff all 81,872 combos decided, zero undecided, no NEW-LB.

To read the outcome later: `cat experiments/results/oracle_parallel/FINISH.log`.

## How to certify the other 3 masks (future work)
At LB=2007 they are intractable (0.34M / 2.2M / 11.8M combos).  Paths: (i) a >2007 witness from
mask (8,12) would raise the LB and shrink every band (cascade); (ii) a still-tighter relaxation than
the adjacent-pair UB (triple-column / full-row-automaton coupling) dropping their UB <=2007;
(iii) the same parallel oracle at a raised LB once (i) lands.
