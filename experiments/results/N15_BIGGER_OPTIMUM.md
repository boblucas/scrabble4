# N=15 single-turn optimum on the BIGGER Dutch dictionary (`data/words/dutch_bigger`)

Replication of the 3-phase `dutch` gameplan (strong LB via incumbent improver -> analytic threat
collapse at the LB -> certify survivors with parallel xfill_varmax) on the much larger
`dutch_bigger` lexicon (7.58M raw words). Language `dutch` (correct tile values/bag/blanks);
only the word list is swapped via `construct_rules('dutch','15', word_file=...)`.

All totals reported as verified are confirmed by `experiments/witness_check.py`
(`ok=True`, `require_center=True`, reserve=1 enforced explicitly: board <= bag+blanks-1).
Process-kill safety honored (specific PIDs only, no group kills). The concurrent `dutch`
certification (T24 driver + paused run) was left untouched; CPU kept polite (xfill threads <= 16).

## Dictionary
- `dutch_bigger` pre-filtered ONCE to length <= 15 -> `data/words/dutch_bigger_le15`
  (4,956,806 words; untracked, NOT committed). `construct_rules` caps at len<=15 internally,
  leaving 4,117,291 entries; **605,797 are 15-letter words** (vs 116,983 in regular `dutch`).
- `dutch` is a SUBSET of `dutch_bigger`, so any board legal under `dutch` is legal under
  `dutch_bigger` (extra words can only ADD cross-word legality). Build: rules ~14s; the <=HMAX (8)
  cross-word dict for xfill = 255,302 words / 529,194 prefixes (loads in ~0.2s in the Rust solver).

## Self-contained scripts (committed; the running `dutch` scripts were NOT edited)
- `experiments/n15_bigger_verify.py`  -- re-verify a witness JSON under the bigger lexicon.
- `experiments/n15_bigger_v2.py`      -- bigger-lexicon full-turn CP-SAT model (word_file-threaded copy of n15_push_lb_v2).
- `experiments/n15_bigger_incumbent.py` -- bigger-lexicon LNS / target incumbent improver (saves to N15_bigger_best_*).
- `experiments/n15_bigger_analytic.py` -- sound analytic per-word UB sweep (with a fast unconstrained-UB prefilter).
- `experiments/n15_bigger_certify.py`  -- parallel xfill_varmax certification driver (frozen a546 binary, XFILL_THREADS).

## Phase 1 -- strong LB
- The `dutch` 2050 board (`geschenkcheques`, all 7 newly columns scored) RE-VERIFIES byte-for-byte
  under `dutch_bigger`: **total = 2050**, ok=True, center-connected, reserve=1
  (`experiments/results/turns/N15_bigger_best_2050.json`). So the bigger LB starts at 2050.
- The bigger-lexicon incumbent improver (LNS, thaw cols {3,11}) lifted it to a verified
  **2053** (`geschenkcheques`, `turn_str` GesChenKCheQUeS): main 1724 + verticals 329
  (col0 `gezwijmd` 69, col3 `cafevest` 25, col7 `krulwilg` 72, col8 `celgift` 19,
  col11 `quizvorm` 39, col12 `urhebers` 15, col14 `skyboxje` 90).
  Witness: `experiments/results/turns/N15_bigger_best_2053.json` -- witness_check OK, reserve=1.
  (`cafevest`/`quizvorm` are bigger-only words, which is why this board is invalid under plain
  `dutch` -- it is specifically a `dutch_bigger` improvement.)

## Phase 2 -- analytic threat collapse at LB = 2053
Sound per-word UB = main_const(word, mask) + sum_{c in mask} G(c, word[c]), where
G(c, L) = max legal vertical "L+tail" gross over run-lengths 1..HMAX (l=1 = bare tile = 0). This
ignores tile contention, blanks, connectivity, reserve and the center constraint (all only LOWER
the score), so it is a sound over-estimate. A word is OPEN iff max_mask UB > LB.

- **Key analytic fact:** the maximum main-word-only score (x27 proxy) over ALL 605,797 fifteen-letter
  words is **1913** -- already 140 BELOW the LB. So every threat word must gain its ENTIRE margin
  from vertical cross-words.
- Sweep over ALL 605,797 fifteen-letter words @ LB=2053: **605,780 CERTIFIED <= 2053** (no search),
  **17 OPEN** (UB > 2053). Open set (`experiments/results/n15_bigger_open.txt`), by UB:

  | word | UB | slack over LB |
  |---|---|---|
  | recyclingcyclus | 2237 | 184 |
  | psychologenquiz | 2174 | 121 |
  | polycyclischers | 2158 | 105 |
  | babyslaapcyclus | 2154 | 101 |
  | polyglottenquiz | 2150 | 97 |
  | vuurwerkcheques | 2138 | 85 |
  | polycyclischere | 2128 | 75 |
  | polyoxyethyleen | 2110 | 57 |
  | recyclagecyclus | 2109 | 56 |
  | hexyloxyethanol | 2100 | 47 |
  | hypecycluscurve | 2087 | 34 |
  | recyclingstypes | 2079 | 26 |
  | plaquehypothese | 2077 | 24 |
  | geschenkcheques | 2072 | 19 |
  | psychofysischer | 2066 | 13 |
  | jacquetkostuums | 2063 | 10 |
  | copyrightklucht | 2059 | 6 |

  Of these 17 words' 1212 legal masks, only **362** have a per-mask UB > 2053 (the rest are
  analytically certified <= LB); those 362 are the xfill work units.

## Phase 3 -- certification of the open set (parallel xfill_varmax)
_TO BE FILLED IN after the certification run._

## Honest assessment of distance to a proven dutch_bigger optimum
_TO BE FILLED IN._
