# N=15 Adjacent-Pair Legality Filter for the geschenkcheques {3,11} masks

**Goal.** Collapse the per-combo oracle's combo set for the 4 open `geschenkcheques` `{3,11}` masks
by pruning, *during enumeration*, every vertical-combo that is provably board-infeasible because an
adjacent scoring-column pair's chosen verticals form an illegal horizontal run.

**Verified LB = 2007** (`experiments/results/turns/N15_best_2007.json`, FIXED `witness_check`).
Reserve = 1 throughout.

## The filter (sound)

In these masks the scoring columns contain adjacent pairs. When two adjacent columns `c, c+1` both
carry verticals, at every shared row `r >= 1` the two tail letters `(tail_c[r], tail_{c+1}[r])` sit
horizontally side by side. On **any** legal final board the maximal horizontal run through those two
cells is a legal dictionary word of length `<= HMAX` and **contains that ordered bigram as a
contiguous substring**. Hence the connector-independent **necessary condition**:

> for every adjacent scoring pair `(c, c+1)` and every shared row `r`, the ordered pair
> `(tail_c[r], tail_{c+1}[r])` must occur consecutively in some legal word of length `<= HMAX`.

A combo violating this admits **no** legal board (the neighbours `c-1, c+2` are non-scoring columns
whose connector tiles can only *extend* the run, never make an absent bigram appear), so it is
dropped without an oracle solve. We deliberately do **not** require the 2-letter run itself to be a
word (unsound: a longer legal run whose 2-letter substring is not a word can exist). This is exactly
the bigram-membership condition from `experiments/n15_adjacent_ub.py`, applied at the combo level
during the DFS (`experiments/n15_adjacent_filter.py::enumerate_filtered`).

**Soundness of certification.** The filtered enumeration is COMPLETE over
`{combos with total gross > vfloor satisfying the bigram condition}`; every dropped combo is provably
board-infeasible; every kept combo is then decided by the EXACT CP-SAT oracle (proven SAT/UNSAT;
UNKNOWN keeps the mask OPEN). The drop set never contains a feasible combo, so it cannot hide a
board > LB.

**Soundness cross-check (PASS).** `--mode selftest`:
- the known 2007 board's combo (mask `(0,3,7,8,11,12,14)`) SURVIVES the filter;
- all 15 oracle-SAT combos in `results/oracle_parallel/geschenkcheques_0378111214_lb2007.jsonl`
  SURVIVE the filter (0 wrongly rejected).

## Result: the filter does NOT collapse the counts for geschenkcheques

The decisive measurement. At LB=2007, reserve=1, the fraction of (vertical_c, vertical_{c+1})
ordered pairs that are already bigram-legal is very high for this word:

| pair  | bigram-legal pairs |
|-------|--------------------|
| (7,8)   | 98.8% |
| (11,12) | 100.0% |
| (13,14) | 96.8% |

so the filter removes at most ~1-3% of *pairs*, and correspondingly little of the combo space.

| mask | adjacent pairs | unfiltered combos>2007 | filtered (surviving) | reduction |
|------|----------------|------------------------|----------------------|-----------|
| (0,3,7,8,11,12,14) | (7,8),(11,12) | 81,872 | 80,549 | -1.6% |
| (0,3,7,9,11,12,14) | (11,12) | 8,234,245 | 8,234,245 | 0.0% |
| (0,3,7,8,11,13,14) | (7,8),(13,14) | 4,982,962 | 4,151,140 | -16.7% |
| (0,3,7,9,11,13,14) | (13,14) | >>10^7 (DNF in 1200s) | >>10^7 (DNF in 2400s) | <=~3% (pair 96.8% legal) |

(`reduction` is exact where both counts completed; counts are complete enumerations, `capped=False`.
The largest mask `(0,3,7,9,11,13,14)` could not even be **counted** by the pure-Python DFS within
40 min — its surviving space is in the many-millions and its single binding pair (13,14) is 96.8%
bigram-legal, so the filter removes at most ~3%.)

The mid mask `(0,3,7,9,11,12,14)` has only pair (11,12), which is 100% bigram-legal, so the filter
prunes nothing. Even the best case, the two-pair mask `(0,3,7,8,11,13,14)`, only drops 16.7% — still
millions of survivors.

## Per-mask outcome

- **(0,3,7,8,11,12,14)** — 80,549 survivors. Tractable, but already being certified by the
  pre-existing parallel oracle run (`results/oracle_parallel/`, ~12h, 48 UNKNOWN to recheck). Not
  duplicated here (coexistence requirement).
- **(0,3,7,9,11,12,14)** — 8,234,245 survivors. INTRACTABLE at ~5 s/combo (filter pruned 0%).
- **(0,3,7,8,11,13,14)** — 4,151,140 survivors. INTRACTABLE at ~5 s/combo.
- **(0,3,7,9,11,13,14)** — many millions of survivors (uncountable by pure-Python DFS in 40 min).
  INTRACTABLE.

No new LB found (no surviving high-gross combo was oracle-tested to SAT>2007 by this filter; the
existing oracle's SAT witnesses all verify to <=2005).

## Conclusion

The adjacent-pair bigram filter is **sound and correctly implemented** (selftest PASS), but for
`geschenkcheques` its verticals are too bigram-compatible (97-100% legal pairs) for it to collapse
the combo space. **It does not make masks 2-4 tractable for the per-combo oracle, and N=15=2007 is
NOT thereby proven.** The remaining wall is CP-SAT's connectivity feasibility cost per combo combined
with the millions of (already cross-word-legal) combos, not adjacent-pair cross-word illegality — so
this particular pre-filter cannot close the gap for this word. The genuinely binding sound constraint
that the filter could exploit (the ordered bigram must embed in a legal word) is satisfied by almost
all combos here.

Tooling delivered: `experiments/n15_adjacent_filter.py` (`enumerate_filtered`, `run_mask`,
`--mode {count,selftest,oracle}`), writing to a separate ledger dir
`experiments/results/adjacent_filter/` so it never touches the running oracle's files.
