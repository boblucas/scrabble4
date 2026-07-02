# v1 oracle ledgers QUARANTINED (2026-07-02)

The v1 driver keyed ledger records by POSITIONAL enumeration id. enumerate_above_fast's order is
PYTHONHASHSEED-NONDETERMINISTIC across processes (proven: same 81872-combo band on mask
(0,3,7,8,11,12,14)@lb2007, different id->combo mapping under PYTHONHASHSEED=1 vs 99; see
scratchpad enum_fingerprint test + session notes). Consequences:

- Any RESUMED v1 run has coverage holes (skip-by-id skips different combos than were decided).
- Mask (8,12) "all 33716 UNSAT => EXACTLY 2008" is WITHDRAWN. Direct evidence of holes: the
  lb2007 phase found 68 REAL SAT combos with nominal up to 2010 (witness totals 2002-2006);
  those combos are inside the lb2008 band, yet the lb2008 sweep recorded zero SATs.
- The June "spurious SAT 5806 re-proved UNSAT" was actually a DIFFERENT combo (id drift), so the
  original SAT stands as real.
- Two further v1 semantic holes fixed in v2: the enumeration missed blank-assisted combos, and
  "SAT but witness<=LB -> continue" was unsound (another grid for the same combo can score more).

The verified LB=2008 board (N15_best_2008.json) is UNAFFECTED (witness_check is the arbiter).
v2 = content-keyed ledger + blank-aware band + score-aware oracle_beats_lb.
