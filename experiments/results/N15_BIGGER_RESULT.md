# N=15 single-turn optimization on the BIGGER Dutch dictionary (`data/words/dutch_bigger`)

Self-contained run, independent of the concurrent `dutch` run. Language `dutch` (correct tile
values/bag/blanks), only the word list changed. Scripts: `experiments/n15_bigger_lb.py`,
`experiments/n15_bigger_threat.py`. All totals verified by `experiments/witness_check.py`
(`ok=True`, `require_center=True`, `reserve=1`). Process-kill safety honored (no group kills).

## Filtered-dict stats / build notes
- `dutch_bigger` = 7,579,858 lines (116 MB). Pre-filtered ONCE to words of length 1..15 →
  `data/words/dutch_bigger_le15` = **4,956,806 words** (untracked, NOT committed). Words >15 are
  unplaceable on a 15x15 board, so dropping them removes no legal play (SOUND). `construct_rules`
  additionally caps at len<=N internally, leaving **4,117,291** dict entries; **605,797** are
  15-letter words (vs 116,983 in regular `dutch`, ~5.2x more).
- Build times: `construct_rules(...word_file=dutch_bigger_le15)` ~13s; connector row automaton
  len<=5 ~1s (20k edges), len<=8 ~4.4s (217k edges, ~1.8x regular dutch). Acceptable — no further
  filtering needed.

## Best VERIFIED N=15 total for dutch_bigger = **1952**
- Main word **geschenkcheques** (rank-19 by x27 proxy), `turn_str` `GesChenKCheQUeS`, 1 blank.
- Breakdown: main 1724 (x27 word mult on cols 0/7/14 + x2 letter on 3/11 + 50 bingo) + verticals
  228 (col0 `golfsurf` 69, col7 `klepstuw` 69, col14 `skyboxje` 90) = **1952**.
- Witness: `experiments/results/turns/N15_bigger_best_1952.json` — `witness_check` WITNESS OK,
  center-connected, reserve=1.
- Provenance note: the dutch run's verified 1952 witness re-verifies *byte-for-byte* against the
  bigger lexicon (the bigger dict is a superset; every run in that board is a bigger-dict word), so
  it is a SOUND dutch_bigger LB. All my own push attempts on the bigger lexicon (below) found
  nothing higher.

## Threat set (sound upper bound vs floor 1952)
- Only a 15-letter word newly-placed on all of cols {0,7,14} can reach x27; any other placement is
  <=x9 with ceiling 9*(59+16)+50 = 761 << 1952 (max 15-letter raw letter-sum = 59). So only x27
  15-letter words can threaten.
- UB(word) = x27_proxy(word) + vert_UB(7-best per-column verticals, bag/connectivity ignored).
  Threat set = {UB > 1952} = **505 words** (504 with a legal x27 mask). Written to
  `experiments/results/n15_bigger_threats.jsonl`. Top: recyclagecyclus UB 2351, recyclingcyclus
  2342, psychologenquiz 2269.
- KEY tightening (sound, analytic): **NO 15-letter word has x27_proxy (main score alone) > 1952**
  — the maximum main-only score is 1913 (recyclingcyclus/recyclagecyclus). Therefore EVERY threat
  word must gain its margin entirely from VERTICAL cross-words: 2 words need verticals to add >39,
  9 need 100-200, and 494 need >200. The 1952 floor already sits only 39 below the absolute
  main-only ceiling.

## Certification outcomes / where the wall is
- The connector/empty-column feasibility model decides the highest-proxy words **infeasible fast**:
  recyclingcyclus, recyclagecyclus (CP-SAT INFEASIBLE in 1-2s), babyslaapcyclus, luchtdrukcyclus,
  polycyclischers (1-2s). psychologenquiz did not resolve within the wall (OPEN). These words'
  pre-placed row-0 fragments cannot be assembled into one center-reaching connected component of
  legal words within the bag — the same connector-legality obstruction documented for N=13/N=15 in
  the handoff.
- The **full per-(word,mask) certification model** (verticals allowed on all 7 newly cols, full
  len<=8 connector automaton, maximize-to-optimality) is **intractable at this lexicon size**: a
  single mask of geschenkcheques did not finish model-build+solve in 300s (the 217k-edge automaton
  unrolled across 15 rows + ~8 columns is the bottleneck; CP-SAT `max_time` does not bound model
  construction). So machine-certifying all 505 threats to a complete LE-floor proof is **blocked** —
  a genuine compute wall, consistent with the handoff's N=15 proof-wall expectation.
- Push attempts to BEAT 1952 (add x3-col verticals to feasible high words via the lighter model):
  geschenkcheques best mask reached only 1862 under the maxlen-5 search; vuurwerkcheques masks were
  infeasible/hard within the wall. No board exceeding 1952 was found.

## Honest assessment of distance to the true optimum
1952 is a strong, soundly-verified LB. The true dutch_bigger optimum is **>= 1952 and < ~2351**
(the loosest sound UB). The evidence that 1952 is at or very near optimal:
- No word can beat it on the main word alone (ceiling 1913 < 1952); any improvement must come from
  stacking >=175 of vertical score onto a feasible high-main board.
- Every word with main >= ~1670 that I could test was either connector-infeasible (the top
  cyclus/quiz/cheques-proxy families) or did not yield a verified board above 1952.
- The concurrent `dutch` run independently stalled at the same 1952 and is still grinding lower-UB
  words — corroborating that 1952 is a hard plateau for this turn structure.
The remaining gap to a *proof* of optimality is the 505-word threat set, whose complete
certification is blocked by the certification model's build cost on the 4.1M-word lexicon. So:
**1952 verified; believed at/near optimal; full machine proof OPEN (compute wall on certification
model build).**
