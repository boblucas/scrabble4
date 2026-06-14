# Max-Turn Scrabble — Comprehensive Handoff (2026-06-14)

This is the full project state for the **maximum-scoring single Scrabble turn** work, written as a
self-contained brief so a fresh session can continue without re-deriving anything. It supersedes
`experiments/MAXTURN_HANDOFF.md` (older). Read this top to bottom.

> **Goal:** compute the provably-optimal maximum-scoring single Scrabble turn on boards N=11, N=13,
> and ultimately **N=15**, with machine-checkable certificates. Dutch dictionary. TIME IS FREE
> (month-long runs are fine). The only hard wall is the shared box (bob's Julia jobs + bob's desktop).

> **Where we are right now (one line):** N=11 = 852 PROVEN; N=13 = 586 strongly-evidenced believed
> optimum (complete proof blocked); **N=15 is the active target** — we just had a major modeling
> correction (verticals are OPTIONAL), the LB candidates are ~1700 (`croquemboucheje` 1751,
> `geschenkcheques` 1724), and the next step is the **corrected witness model** (empty newly-placed
> columns; connecting structure only on pre-placed columns) to turn that candidate into a verified
> center-connected witness.

---

## 0. CRITICAL recent realization (read this first — it changes the model)

For most of this project I made a **modeling error** that crippled N=13 and N=15: I forced every
newly-placed (scoring) column to carry a **vertical word**. **That is NOT required by the rules.**

- A newly-placed tile forms a vertical cross-word **only if its column has adjacent tiles** (above/
  below). If the column is otherwise **empty**, the lone tile forms **no word** → **zero cross-word
  constraint**.
- So the optimal play is typically: a **high-value main word** on a row, with the newly-placed tiles
  on the premium squares, **columns empty (no verticals)**, scoring the main word at its full
  multiplier (×27 on N=15 if the three ×3 columns are newly-placed). Verticals are *optional* and
  usually *not* worth the tiles.
- The only structure you genuinely need is whatever is required to keep the board **one connected
  component including the center cell** — and that connecting structure belongs on the **pre-placed
  columns**, not the newly-placed ones.

Consequence: my old `build_instance`/`xfill` model (verticals forced on scoring columns) drove the
search toward junk (e.g. N=15 LB of 322 from `textielcyclusje`) and caused connectivity explosions.
The corrected model (empty newly columns; connectors on pre-placed columns) is the right path and is
*tractable*, because it's a small connectivity fill rather than an all-columns-verticals search.

**This correction has not yet been fully implemented in the solver.** It is the #1 next step.

---

## 1. Problem definition (the model)

A "turn" = placing some tiles this turn to form a **main word** (a maximal horizontal — or, see §9,
possibly vertical — run), scoring it plus any cross-words formed.

Concretely, as modeled in this repo (historically, with the row-0 pinning):
- **Main word pinned to row 0** of a W×W board. `turn_str` like `BOUWfYsiCuS`: UPPERCASE = tiles
  **newly placed this turn** (scoring); lowercase = **pre-placed** (from prior turns).
- **Vertical cross-words** descend from the scoring (newly-placed) columns *if* those columns have
  tiles below row 0. **(Per §0, having verticals is optional.)**
- **Bridge tiles** (in non-scoring columns, rows 1..H-1) connect everything.
- **Legality:** every maximal H/V run of length ≥2 must be a valid dictionary word; cross-words ≤ 8
  letters (`HMAX = 8`); the occupied cells form **ONE 4-connected component** that **INCLUDES the
  center cell (W//2, W//2)** (the game starts at center — user-added constraint).
- **Tile budget:** tiles (incl. blanks) fit the bag. See §2 for scaled vs full bag and the opponent
  rule.
- **Scoring:** main-word score (incl. **bingo +50** for placing 7 tiles, premium letter/word
  multipliers) + sum of vertical cross-word scores. The newly-placed row-0 tile contributes its
  letter+word multipliers to both the main word and its vertical (if any).

### Premium layout (row 0), by board size

| Board | center | ×3 word cols (row 0) | ×2 letter cols (row 0) | notes |
|---|---|---|---|---|
| N=11 | (5,5) | 0, 5, 10 | (per rules) | |
| N=13 | (6,6) | 0, 6, 12 | 3, 9 | center col 6 is itself ×3 |
| N=15 | (7,7) | **0, 7, 14** | **3, 11** | center col 7 is itself ×3 (real Scrabble layout) |

Get the exact arrays at runtime:
```python
from scrabble import construct_rules
import numpy as np
r = construct_rules('dutch', '15')
wm = np.array(r.word_multiplier)[0]   # row-0 word multipliers
lm = np.array(r.letter_multiplier)[0] # row-0 letter multipliers
# x3 word cols = [i for i,v in enumerate(wm) if v==3]; x2 letter cols = [i for i,v in enumerate(lm) if v==2]
```

### Letter values (Dutch), `r.scores` (letter index 1=a..26=z → value)
```
a1 b3 c5 d2 e1 f4 g3 h4 i1 j4 k3 l3 m3 n1 o1 p3 q10 r2 s2 t2 u4 v4 w5 x8 y8 z4
```
Blanks score 0 (and are scarce — see §2). High-value letters (q10, x8, y8, w5, c5): these are exactly
the ones that **cannot start cross-words** in many cases and are bag-scarce, which is why naive
"highest value letters" words are often infeasible for verticals (but fine for an empty-column main).

---

## 2. The tile bag — scaled (N≤13) vs full (N=15), and the opponent-tile rule

- **Full Dutch bag:** 100 letters + 2 blanks = 102 tiles (`r.counts` + `r.blank_count`).
- **Scaled bag (N=11/N=13):** to keep smaller boards interesting, counts are scaled by
  `f = W²/15²`: `counts[c] = max(round(n*f), <main-word demand>, 1)`, `blanks = round(2*f)`.
  - N=11 scaled: ~57 letters + 1 blank, **T=58**.
  - N=13 scaled: 82 letters + 2 blanks, **T=84**.
  - N=15: the **full** bag, **T=102** (no scaling; `f=1`).
- The scaling is **arbitrary** (user's words) — that's why N=11/N=13 are not "the real problem."
  **N=15 with the full bag is the real target.**
- **CRITICAL bag finding:** scaling up to the full bag adds **common** letters (e 14→18, n 8→10, r/t
  +1) but the **rare** letters are unchanged (c=2, y=1, x=1, v=2). So N=15 is *not* meaningfully
  less "rare-letter-starved" than N=13; the feasibility frontier is structurally similar.

### Opponent-tile rule (`RESERVE`) — IMPLEMENTED (commit 0eb0a26)
The opponent must hold ≥1 tile when we play, so the **whole board after our turn uses ≤ T−1 tiles**.
Solver-side bound: total setup tiles placed (`sum used`) ≤ `sum(counts) + blanks − reserve`.
- `reserve = 0` ⇒ equals the pre-existing implicit `overflow ≤ blanks` bound ⇒ **byte-identical**
  (regression stays green).
- `reserve = 1` ⇒ the real rule. **N=11=852 survives** (its board uses exactly T−1 = 50 setup cells).
- xfill: optional `RESERVE n` instance/base line (default 0). `xtest.build_instance(..., reserve=1)`
  emits it. See memory `maxturn-opponent-tile-rule`.
- TODO: wire `reserve=1` into `35_certify.py`/`33_full_turn_bracket.py` when N=15 certification runs.

---

## 3. CURRENT STATUS by board

| Board | Result | Status |
|---|---|---|
| N=7 | afhappe = 151 | proven (CP-SAT-validated end-to-end; stands) |
| **N=11** | **852** (bouwfysicus; main 626 + verticals 226) | ✅ **GLOBALLY PROVEN, center-constrained, game-reachable** |
| **N=13** | **586** (yoghurtcakeje; main 437 + vert 149) | 🟡 strongly-evidenced believed optimum; complete proof **blocked** |
| **N=15** | **~1700** candidate (croquemboucheje 1751 / geschenkcheques 1724) | 🔵 ACTIVE; verified LB so far = **322** (weak, wrong model); corrected model pending |

---

## 4. N=11 — FULLY PROVEN = 852 (done)

- **bouwfysicus**, center-constrained, **852** = main 626 + verticals 226, 1 blank.
- Board (the printed witness; verticals: col0 `boxertjes` 72, col1 `om`, col2 `uh`, col3 `wazend`,
  col5 `yenteken` 34 (spans center (5,5)), col8 `candere`, col10 `stulpvormig` 72).
- **Globally proven** (commit 9339cff): main-word enumeration (`33_full_turn_bracket.py --enum-only`)
  found exactly 4 threat (word,mask) pairs that could beat 852; bouwfysicus already certified
  (vertical ≤ 226), and the 3 rivals at main 599 (whiskyclubs/typosquatte/bouwfysicas) each
  CERTIFIED ≤ floor 253 (`certs/global_*`). So bouwfysicus is the **unique** optimal main word.
- **Game-reachable** (commit de8758f): a concrete 13-setup-play + scored-turn sequence builds the
  852 board, every intermediate board legal, first play covers center, verified by an independent
  replayer (`experiments/verify_gamescript.py`). The board is **bag-saturated** — uses exactly T−1
  tiles, leaving the opponent exactly 1, so it survives the RESERVE rule.
- Certificates: `experiments/results/certs/n11_fixed_221/ledger.json` (unconstrained),
  `n11_center/ledger.json` (center-constrained). Verify: `35_certify.py check <ledger.json>`.
- Six bugs were found+fixed by the certification layer over the project (l=1 phantom gross,
  blank×wm penalty, maxsec false-PROVEN, aborted-flag 1-in-4096, sn cross-word both-directions,
  center-square). See memory `maxturn-certification-plan`.

---

## 5. N=13 — 586, the full saga (believed optimum; proof blocked)

### Verified lower bound
**yoghurtcakeje = 586** = main 437 + vertical 149, left-block mask {0..6}, reserve=1, witness_check OK.
File: `experiments/results/n13/batchscan_feas_best_586.json`. This is the best **left-block**
(xfill-tractable) witness, found by the ranked batch scan over top-10k feasibility-filtered words.

### The LB ladder during the hunt
316 (degenereerden, first witness) → 366 → **369** (capturing the TO incumbent — see below) → **586**
(after the feasibility-aware re-rank + batch scan).

### Why 586 is believed optimal (strong evidence, not proof)
- The only structure that could **dramatically** beat 586 is a **3-×3 spread** (newly-placing all
  three ×3 columns 0/6/12 → main multiplier **×27**, so even a common-letter feasible board would
  score ~900–1300). Any 2-of-3 (×9) structure caps near 586, and left-block already banks the
  col-3 ×2-letter premium.
- **Spread-feasibility survey (CP-SAT, subprocess-walled): 0 feasible of ~722→3000 configs.**
  - First runs: top 240 feasibility-filtered words × 3 3-×3 masks → 634 UNSAT / 66 TIMEOUT / 0 SAT.
  - Big parallel run (free box): **top 1000 words × 3 masks = 3000 configs → 2615 UNSAT, 341
    TIMEOUT, 44 NOCAND, 0 SAT.** No feasible 3-×3 board across the top 1000 highest-value words.
- **Why spreads are infeasible (structural):** in the SETUP board the scoring columns' row-0 cells
  are EMPTY (the scored tile lands only in the final turn), so verticals at 0/6/12 **float** at rows
  1+. Connecting far-apart floating verticals + center needs bridge tiles forming valid ≤8
  cross-words — the **connector-word legality** is the obstruction, NOT tile count (the Steiner
  `min_bridge_cells` oracle shows fixed+bridge cells ≪ T−1).

### The 341-TIMEOUT residual — root-caused, partially fixed
- The TIMEOUTs are **large CP-SAT models**: `cpsat_decide` encoded each scoring column as one bool
  var + ~7 per-cell `only_enforce_if` constraints **per candidate word**. Common spread-column
  letters (r/t/v/e) have 500–650 candidates across the three ×3 cols (vs ~200 for the fast UNSAT
  words) → the model balloons → CP-SAT can't decide it in the wall (and `max_time` doesn't even
  interrupt it). Fast configs: create_board ~3s + solve ~0.2s.
- **Fix:** `xtest.cpsat_decide_tab` (commit 3d6f215) — encode each scoring column with **one
  `add_allowed_assignments` table constraint** over the stub cells' int vars (model size independent
  of candidate count). **Validated verdict-identical** to `cpsat_decide` where the original decides
  (yuppiecultuur/yoghurtcupjes 3-×3 → both UNSAT, MATCH). Decides *some* former TIMEOUTs fast
  (teruggeschopt: 75s-wall TIMEOUT → UNSAT in 5s).
- **BUT only a partial fix:** a 341-config re-run with `cpsat_decide_tab` (8-wide, 120s wall, 6
  workers each) resolved only ~1 of 200 — most still TIMEOUT. So the residual is **genuinely
  CP-SAT-search-hard**, not just large-model-hard. A leaner model helps but doesn't close it. (Note:
  the re-run under-resourced each config; validation at 16 workers decided ~1/3, so well-resourced it
  shrinks the residual by maybe ⅓, not closes it.)

### Bottom line for N=13
586 is a **strongly-evidenced believed optimum**, not machine-proven. The complete proof is blocked
on deciding the intractable spread residual (the full word space + all spread masks + ×9-end spreads
+ the 341 undecidable configs) — a genuine research wall for *this scaled board*. Writeup:
`experiments/results/N13_RESULT.md`. Memory: `maxturn-n13-heuristic-hunt`.

### KEY CAVEAT discovered later (applies to N=13 too)
All the N=13 spread work **forced verticals on scoring columns** (the §0 error). The "best feasible"
witness 586 and the spread infeasibility are *within that wrong model*. Under the corrected model
(empty newly columns; main word scored at its multiplier; connectors on pre-placed columns), N=13's
true optimum could be **higher** — a ×27 N=13 main word with empty columns + a small connecting
structure to center. **This was not re-examined for N=13** because the user dropped N=13 to pivot to
N=15. If N=13 is revisited, apply the corrected model.

---

## 6. N=15 — THE ACTIVE TARGET (real board, full bag)

### The big realization (see §0)
The optimal N=15 turn is a **high-value main word scored ×27** (newly-placed on the three ×3 columns
0/7/14, with productive letters on the ×2 columns 3/11), with the newly-placed **columns empty** (no
verticals → no cross-word constraints), the pre-placed runs being legal words, tiles fitting the bag,
and only a **small connecting structure** (on the pre-placed columns) needed to keep the board one
connected component including center (7,7). This scores **~1700**, not the 322 my wrong model gave.

### The LB candidate ladder (ideal ×27 main score, `27*(Σvalues + val[3] + val[11]) + 50`)
```
1751  croquemboucheje   (x3 cols 0/7/14 = c/b/e ; x2 cols 3/11 = q/h)
1724  geschenkcheques   (g/k/s ; c/q)        <-- user's pick; #2, tiles fit (shortfall 0)
1724  jacquetkostuums   (j/k/s ; q/u)
1697  deuxchevauxtjes / alfahydroxyzuur / croquetmatchjes / flauwekulexcuus / ...
1670  verzamelcheques / cultuurchequeje / jacquardweefsel ...
```
- `geschenkcheques` IS found (rank #2, 1724). `geschenkscheques` (with the extra s) is **16 letters
  and not in the dictionary** — too long for a 15-board.
- A "workable" filter (pre-placed runs are legal words + tiles fit) produced a top of
  `flauwekulexcuus` 1697 over 138 candidates — **but that filter is moot** (see next).

### The ONE genuine remaining constraint (confirmed by witness_check)
A pure row-0 main-word play (no verticals, no connecting structure) is **INVALID**:
`witness_check` rejects it with **"setup board not connected (N components)"**. The newly-placed gaps
split the pre-placed row-0 into disconnected segments (e.g. for `flauwekulexcuus` newly={0,3,7,11,12,
13,14}, the pre-placed runs `la`/`wek`/`lex` are three disconnected pieces). A real prior board must
be **one connected component including center**.

So the ~1700 candidate requires a **connecting pre-placed structure** (scores 0) that:
1. links the disconnected lowercase row-0 segments, and
2. reaches the center cell (7,7),
3. **without routing through any newly-placed column** (a tile directly below a newly tile would form
   a vertical on it — the thing we're avoiding). This bites hardest at **col 7 = center**: making it
   ×27 means col 7's column is empty, so center must be reached by a connector in a *neighboring*
   column + a row-7 word, not through col 7 itself.

### User's (correct) intuition
"Most words have *a* legal play; if you're not spending tiles on verticals it's kind of easy to put
the word down at all." Agreed — the connecting structure has enormous freedom (full 102-tile bag, any
legal connected blob). So the ~1700 LB is very likely achievable; it just needs a small connecting
crossword on the pre-placed columns, which is a **tractable connectivity fill**, not the exploding
all-columns-verticals search I wrongly ran.

### Verified N=15 LB SO FAR = 322 (weak, wrong model — to be superseded)
`textielcyclusje`, right-block {7..13} (captures col 7 = center, ×3), `witness_check` OK.
File: `experiments/results/turns/N15_best_322.json`. This came from `n15_hunt.py` which (wrongly)
forced verticals; the ×9 masks all exploded in xfill. **This number is not meaningful for the real
LB** — the corrected model should produce ~1700.

### Important N=15 facts established
- 3-×3 spreads **with forced verticals** are INFEASIBLE even for the ideal word `geschenkcheques`
  (CP-SAT UNSAT in 6s). At N=15 these decide **fast** (4s), unlike N=13's stall — the full bag
  refutes cleanly. (But this is the *forced-vertical* model; the corrected empty-column model is
  different and is the right one.)
- N=15 tooling works: `construct_rules('dutch','15')`, `build_instance('15', ...)`, premium layout
  ×3 at 0/7/14, ×2 letter at 3/11, center (7,7), 116983 fifteen-letter words.

---

## 7. THE ENGINE / TOOLING (files, flags, behaviors)

### `experiments/xfill_rs/src/main.rs` — the bespoke Rust crossword-fill solver
For a fixed length-vector: `xfill <inst> --maxscore <floor>` →
`MAX v` (proven vector max v>floor) / `LE floor` (exhaustive proof no board beats floor) /
`TO ...` (wall/node abort — proves NOTHING; never trusted as LE). `--emit` prints `BOARD <codes...>`
of the best board whenever `best > floor` (incl. on a TO abort — line ~1514:
`board = if best>floor { Some(best_grid) }`). Modes:
- single `<inst>`; `--batch LISTFILE` (lines `<key> <path> <floor>`, dict cached, prints
  `RES <key> <line>` + with `--emit` a keyed `BOARD <key> ...`); `--batchvec BASE LISTFILE`
  (in-memory instance assembly from a per-main-word BASE — the scale path).
- Sound per-instance wall: env `WALL`/`BATCHWALL` seconds → abort emits `TO`. `tick()` checks the
  abort flag every node.
- `RESERVE n` instance/base line (opponent rule; §2). `placed` counter capped at `max_setup =
  sum(counts)+blanks−reserve` in `add_letter`.
- Perf wins landed (verdict-neutral, byte-identical node counts, gates green): 3bac317
  (most-constrained-column-first in `knap_ub::rec`, ~26%), 65098c9 (inline last uncommitted column,
  −9–15% instrs). 88.8% of runtime is in `knap_ub::rec` (per perf). TWOLEVEL structural cut REFUTED
  (memory `maxturn-twolevel-negative`). Build:
  `cargo build --release --manifest-path experiments/xfill_rs/Cargo.toml` then **always**
  `cp target/release/xfill target/release/xfill_lev3` (the binary the Python tooling invokes). Do NOT
  touch frozen binaries `xfill_frozen`/`xfill_ac3`.

### `experiments/xtest.py` — instance building + CP-SAT ground truth
- `build_instance(board, main, turn, Lvec, scale=True, reserve=0)` → `(inst, meta)`. `Lvec` maps each
  scoring column to its vertical length; **`Lvec[c]=1` = bare tile, NO vertical** (the key to the
  corrected model). Returns `(None, None)` if a scoring col has no candidate vertical of its length.
- `dump_simple(inst, truth, path)` writes the instance file xfill reads; emits `RESERVE n` when set.
- `build_base`/`dump_base` (per-main-word BASE for `--batchvec`).
- **Performance fixes (this session):**
  - `_cand_bucket(rules, board)`: bucket the 33M-word lexicon ONCE by (first-letter, length) →
    O(1) candidate lookup. Was a full rescan per scoring column per build. Commit 1addf48.
  - `_cached_rules(board)`: cache `construct_rules` per board (it rebuilds the 12M-word object,
    ~3.8s; was called per build → the dominant cost). Commit 5ee1bf1. **Only build_instance/
    build_base use the cache (read-only); mutating callers (cpsat helpers, n13_witness's rules2)
    call construct_rules directly.**
- `cpsat_decide(meta, cap)` → 'SAT'/'UNSAT'/'UNKNOWN'. Builds a CP-SAT model
  (`position_independent_row_automaton` over words ≤8, `create_board`, per-column word vars,
  `single_component`, letter/blank limits). `num_search_workers` from env `CPSAT_WORKERS` (default
  24). `max_time_in_seconds = cap` (but does NOT bound model construction / some propagation).
- `cpsat_decide_tab(meta, cap)` (commit 3d6f215): same, but scoring columns use ONE
  `add_allowed_assignments` table constraint over stub cells' `letter_int` vars (model size
  candidate-count-independent). Verdict-identical to `cpsat_decide`; decides more former TIMEOUTs.
- `cpsat_maxscore(meta, cap)` → `(status, score)`: optimal vertical score (slow on feasible configs;
  does NOT return the board — would need a small mod to extract the solution for witnessing).

### `experiments/witness_check.py` — INDEPENDENT witness checker (sole authority)
Recomputes full-rules score (bingo, multipliers, blanks), validates **all maximal runs are words**,
**setup board connectivity** (rejects "setup board not connected (N components)"), **center
occupancy** (`require_center` param), bag consistency, optimal blank derivation (`derive_blanks`,
`_cell_score_weight`). Shares no code with the solvers — this is what caught multiple bugs. Run:
`.venv/bin/python experiments/witness_check.py <witness.json>` → prints score breakdown + `WITNESS OK`.

### `solve.py` (repo root) — CP-SAT board model primitives
- `create_board(model, rows_words, columns_words, alphabet_size=...)`: builds the grid int vars +
  per-row/col automaton constraints. `columns_words[x]` can be a built automaton tuple
  (start,finals,edges) or a word matrix (compiled by `create_scrabble_automaton`), or `None` (no
  constraint). **`model.prefix` must be set before calling** (e.g. `m.prefix='g'`).
- `Cell = namedtuple('Cell', ['active','letter','x','y','blank','letter_int'])` — `cells[(x,y)]`
  exposes `.letter_int` (the int var, usable in table constraints), `.active`, `.letter` (dict of
  bools), `.blank`.
- `single_component(model, cells, start)`: one-connected-component constraint.
- `connectivity.py`: `min_bridge_cells(fixed, W, H)` (exact Steiner DP — minimum empty cells to merge
  components), `components(fixed,W,H)`, `can_connect`.

### N=13/N=15 hunt scripts (this session)
- `experiments/n13_rank.py` — analytic candidate ranker (no search): ranks 13-letter mains by
  `main + Σ bag-aware vertical proxy`, with center feasibility + main-word bag feasibility +
  `--min-vert` (feasibility filter: every len-2 scoring col must have ≥N two-letter verticals — drops
  the vertical-starved words that cause hard-infeasible TOs). **Left-block model (forces verticals)
  — superseded by §0.**
- `experiments/n13_witness.py` — `--board B --main W --turn TURN --lvec L0,...,Lk --floor F
  --reserve r`: builds the instance, runs `xfill --maxscore --emit`, **captures the TO incumbent**
  (a TO board is a valid witness — TO only means "not proven optimal"; witness_check re-verifies),
  saves a witness JSON. Enforces center col (W//2) is a scoring col reaching center.
- `experiments/n13_batchscan.py` — fast batched scan: ONE python pass builds all candidate instances
  (dict written once) + ONE `xfill --batch ... --emit` (dict loaded once) + witness_check each board.
  Ratcheting floor = `best_total − main(word)`.
- `experiments/n13_spread_survey.py` — CP-SAT spread-feasibility survey, **subprocess-per-config with
  a hard OS wall** (so a stuck config is a clean TIMEOUT, not a stall). `--one WORD MASKCSV` worker
  (now uses `cpsat_decide_tab`); driver sweeps top-N (`--top`, `--skip`) rank_feas words × 3 3-×3
  masks. Outputs `SAT-HIT`/UNSAT/TIMEOUT/NOCAND.
- `experiments/n13_ranksweep.py`, `n13_sweep.py` — earlier per-word sweeps (superseded by batchscan).
- `experiments/n15_hunt.py` — N=15 hunt with **forced verticals** (the wrong model → 322). Kept for
  reference; the masks tried + the explosion findings are documented in its commit (9d1708c).
- `experiments/n15_hunt2.py` — N=15 hunt that ranks by ×27 main and tries empty columns + a col-7
  vertical for center — **fails (LE 0 / no-board)** because the col-7 center vertical floats (its
  row-0 cell is the newly-placed scored tile, empty in the setup). This is the bug that revealed the
  correct model: **center must be reached by a connector in a NON-newly column, not col 7.**
- `experiments/bound_study.py` — proved Lever-4 (Steiner tile-reservation root bound) vacuous on the
  N=13 hard slice; surfaced that the exact CP-SAT root knapsack prunes ~22% xfill misses.

### Certifier `experiments/35_certify.py` + enumerator `experiments/33_full_turn_bracket.py`
The proven path used for N=11. `35_certify.py build/check` independently re-enumerates the full band
of length-vectors with optimistic UB > floor and proves each ≤ floor (GEOM/LE/KNAP) or finds a MAX
refutation. Three-pass stage 2. `33 --enum-only` emits THREAT (word,mask,main,barepack_ub) survivors.
`global_n11.sh` drives per-threat-word certification. **These still force the per-column-vertical
model — they'd need the §0 correction (and `reserve=1` wiring) for N=15.**

---

## 8. KEY LESSONS / GOTCHAS (do not relearn the hard way)

1. **PROCESS-KILL SAFETY (memory `process-kill-safety`):** NEVER use `kill -9 -<pgid>` (negative-PID
   / process-GROUP kill) to clean up jobs. On 2026-06-14 this killed bob's **gnome/wayland session**
   (he had to log back in) — a group id from a broad `pgrep` aliased the desktop session. Kill
   SPECIFIC pids only: `pkill -9 -f "<unique script path>"` (e.g. `n13_spread_survey.py --one`) or
   `kill -9 <pid>`. Never `pkill` broad patterns ("bash", a directory path). For a respawning
   xargs-feeder driver, `pkill -9 -f <driver-script-path>` first, then mop up workers by their unique
   path — all plain pid kills.
2. **Detached-job / PID gotchas:** `setsid`/`env`/`nice` launch chains create transient/wrapper PIDs;
   `$!` and `pgrep` often catch the wrapper, not the worker. Prefer plain `nohup .venv/bin/python -u
   script ... &` and `pgrep -f "<unique script signature>"` for the real PID. Background bash waiters
   (`while kill -0 PID; do sleep; done`) repeatedly died across session events — don't rely on them;
   use `ScheduleWakeup` to pace check-ins, or just check on demand.
3. **errexit footgun:** the harness shell runs with errexit-ish behavior; a `pkill`/`pgrep` returning
   nonzero (no match) **aborts the rest of a compound command** (including a launch on the next line).
   Put `|| true` after kills, or run launches as separate commands. Several launches silently didn't
   happen because of this.
4. **Long foreground `sleep` is auto-backgrounded** by the harness (>~120s). Use short sleeps + read,
   or `run_in_background`, or rely on completion notifications.
5. **Trust `LE` only from uncapped, naturally-completed xfill runs.** A wall/MAXNODES abort prints
   `TO` and proves nothing (the old MAXNODES-fake-LE footgun is fixed). For witnesses, a TO-emitted
   board is fine (witness_check is the authority).
6. **CP-SAT `max_time_in_seconds` does NOT bound model construction** (or some propagation) for big
   models — a "cap=30" call ran 535s. The subprocess hard-wall in `n13_spread_survey.py` is the only
   reliable bound for the stalling configs.
7. **The §0 modeling error (verticals optional)** is the single biggest lesson: do NOT force verticals
   on newly-placed columns. They're optional; the main word's multiplier is the score; connectors go
   on pre-placed columns.
8. **Bash classifier intermittently errors** "claude-fable-5 temporarily unavailable" on auto turns —
   read-only tools still work; retry, or have the user run via `! <cmd>`.
9. After rebuilding xfill, **always** `cp target/release/xfill target/release/xfill_lev3`.
10. bob's Julia jobs (multipass.jl, ~36 threads when active) share the 48-core box. Keep `--procs`/
    `CPSAT_WORKERS` modest under load; the box was *free* (post-crash) during the N=15 work but Julia
    will return.

---

## 9. NEXT STEPS (prioritized) — for N=15

### Step 1 (the keystone): the CORRECTED witness model → verified ~1700 N=15 LB
Build a model/search that:
- Places a high-×27 main word on row 0 (newly-placed on 0/7/14 + 3/11 + 2 for bingo = 7 newly).
- Keeps the **newly-placed columns empty** (no verticals; `Lvec[c]=1` for them in the current
  `build_instance` already means "bare tile, no vertical").
- Builds a **connecting structure ONLY on the pre-placed columns** (and bridge cells) that makes the
  setup board one connected component **including center (7,7)**, **without putting any tile directly
  below a newly-placed column** (would create an unwanted vertical there). In particular center is
  reached by a connector in a column **adjacent to col 7** plus a row-7 word — not through col 7.
- Verifies with `witness_check` (require_center=True): all runs legal, connected, center occupied,
  bag OK, reserve=1.

Implementation notes:
- The current `build_instance`/xfill ties "center" to a *scoring* column's vertical (col 7), which
  floats → fails. **The fix is to let center be reached by the bridge/pre-placed structure**, i.e.
  treat center as a free target cell that the non-scoring (bridge) columns must reach, and make the
  scoring columns empty. This likely means a small change to how the center constraint is encoded
  (or a CP-SAT formulation that just asserts `cells[(7,7)].active==1` + single_component, with the
  newly columns forced empty below row 0 and the main word's row-0 letters fixed).
- Because the search is now a **connectivity fill on the pre-placed columns** (not all-columns
  verticals), it should be tractable for xfill OR a modest CP-SAT model.
- Start with the top candidates: `croquemboucheje` (1751), `geschenkcheques` (1724),
  `jacquetkostuums` (1724). For each, you choose which 7 positions are newly-placed (must include
  0,7,14 for ×27; prefer 3,11 for the ×2-letter bonus) and need the 8 pre-placed positions to be
  reconnectable. Their ×3-column letters (c/b/e, g/k/s, j/k/s) are common enough to anchor verticals
  if needed.

### Step 1-alt (may be simpler — try it): main word on the CENTER ROW (row 7)
If the main word goes on **row 7** (through center (7,7)) instead of row 0, **center is included for
free** and the connectivity subtlety largely disappears (the main word itself passes through center).
Row-7 premiums differ from row-0 (real-Scrabble layout: row 7 has ×3 at the ends (7,0),(7,14) and the
center (7,7) is the start square, typically ×2 word) — so the achievable multiplier differs (perhaps
×3·×3·×2 = ×18 rather than ×27). **Compute the row-7 premium layout** (`r.word_multiplier[7]`,
`r.letter_multiplier[7]`) and compare the best row-7 ×18-ish play to the best row-0 ×27-with-connector
play. The model currently pins the main word to row 0; generalizing to an arbitrary row is a modest
change and may give the cleanest path to a verified high LB. **Open question the user asked: should
the main word stay on row 0 or may it go on the center row?** — get this answer / try both.

### Step 2: confirm the LB is the OPTIMUM (the proof) — only after a strong LB
- With a strong LB (~1700), the certification band shrinks dramatically (most masks/words fall below
  the floor). Use the proven `35_certify.py`/`33` pipeline **adapted to the corrected model** and
  `reserve=1`. N=15 spreads decide fast under CP-SAT (the full bag refutes cleanly), so ruling out
  the high-multiplier alternatives is more tractable than at N=13.
- The upper bound: for the corrected (verticals-optional) model, the max main score is just the
  best legal main word's multiplier score; verticals only ADD. So the optimum = max over (main word,
  placement) of (main score + best legal vertical/connector additions). The ×27 main words dominate;
  the question is which is the highest-scoring one that admits a legal connected center-reaching
  board. A clean **upper bound**: the highest ×27 main score among all 15-letter words whose
  placement can be legal (the ranking in §6) — and the optimum is at most that.

### Step 3 (revisit if time): re-examine N=13 under the corrected model
N=13's 586 was found under the forced-vertical model. The corrected model (×27 N=13 main +
connectors) might beat 586. Apply §0 to N=13 if revisited.

---

## 10. VERIFICATION & RUN COMMANDS

```bash
# Python venv + repo
cd /home/bob/programming/scrabble4 ; PY=.venv/bin/python

# Re-check a certificate (N=11)
$PY experiments/35_certify.py check experiments/results/certs/n11_center/ledger.json

# Verify any witness JSON independently
$PY experiments/witness_check.py experiments/results/turns/N15_best_322.json

# Build xfill + refresh the binary the tooling uses
cargo build --release --manifest-path experiments/xfill_rs/Cargo.toml
cp experiments/xfill_rs/target/release/xfill experiments/xfill_rs/target/release/xfill_lev3

# Regression gates (after ANY solver change) -> must print ALL GATES GREEN
bash experiments/regress.sh

# Rank N=15 words by ideal x27 main (the LB candidates) -- inline:
$PY - <<'PY'
import sys; sys.path.insert(0,'experiments'); sys.path.insert(0,'.')
from scrabble import construct_rules
r=construct_rules('dutch','15'); val={chr(96+i):r.scores[i] for i in range(1,27)}
key=lambda w:27*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50
top=sorted((w for w in r.words_str if len(w)==15),key=key,reverse=True)[:10]
for w in top: print(key(w), w)
PY

# CP-SAT decide a config (tab encoding, env-tunable workers)
CPSAT_WORKERS=16 $PY -c "..."   # build_instance('15',...) then xtest.cpsat_decide_tab(meta, cap=...)
```

Witness JSON schema (what witness_check reads): `{board, main_word, turn_str, require_center,
claimed_total, grid}` where `grid[y][x]` is the letter code (0=empty, 1..26). `turn_str` uppercase =
newly-placed.

---

## 11. COMMITS THIS SESSION (branch `experiments/automaton-cpsat-verification`, NOT pushed)

```
9d1708c  N=15: first verified center-connected LB = 322 (textielcyclusje) + n15_hunt.py
3d6f215  N13: cpsat_decide_tab -- table-constraint scoring encoding (shrinks TIMEOUT residual)
ceb485b  N13: root-cause the 341 TIMEOUT residual (large CP-SAT models) + identify the fix
bcb902f  N13 result: strengthen no-feasible-spread evidence to 1000 words (3000 configs, 0 SAT)
59e8d1a  N=13 result: 586 strongly-evidenced believed optimum (not yet machine-proven)
5817905  N=13 spread-feasibility survey (robust, subprocess-walled) + cpsat_decide bucketing
84c90ca  n13_rank: feasibility filter -- drop vertical-starved candidates (--min-vert)
5ee1bf1  xtest: cache construct_rules per board -- kills instance-build bottleneck
1addf48  xtest: bucket lexicon by (first-letter,length) once -> O(1) candidate lookup
6ac4cca  Merge batch-scan overhead fix: xfill --batch --emit + n13_batchscan.py
0eb0a26  xfill: RESERVE constraint (opponent must hold >=1 tile) -- total board <= T-1
de8758f  Game-reachability of certified N=11 852 board: REACHABLE (verified)
9339cff  Global center-constrained N=11 = 852 PROVEN; N=13 heuristic witness pipeline
65098c9  xfill knap rec: inline last uncommitted column (verdict-neutral)
... (earlier: RESERVE, knap perf, certification, N=11 closure)
```
Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit to the
branch; do NOT push.

n15_hunt2.py is uncommitted scratch (the failed col-7-center attempt that revealed the correct model)
— commit or discard as appropriate; its lesson is captured in §6/§9 here.

---

## 12. MEMORY INDEX (persistent notes, `~/.claude/projects/.../memory/`)

- `process-kill-safety` — NEVER group-kill (killed gnome). PID kills only.
- `maxturn-certification-plan` — N=11 = 852 PROVEN (global, center, game-reachable); the cert engine.
- `maxturn-opponent-tile-rule` — RESERVE rule (board ≤ T−1); implemented; wire into N=15 certs.
- `maxturn-n13-heuristic-hunt` — N=13 = 586; spread survey; the TIMEOUT residual + cpsat_decide_tab.
- `maxturn-rootbound-study` — Lever-4 vacuous; exact-knap root pre-filter idea.
- `maxturn-twolevel-negative` — TWOLEVEL structural cut REFUTED.
- `maxturn-center-square-constraint`, `maxturn-board-legality`, `maxturn-proof-wall`,
  `crossword-solver-design`, `maxturn-n11-fastinner-result`, `maxturn-fullturn-exp33`,
  `maxturn-seed-finder-exp34`, `cpsat-automaton-verify-empirically`, `automaton-minimization-findings`.

> **NOTE:** the memory notes for N=13 and the spread work predate the §0 correction (verticals
> optional). Treat their "infeasible spread" conclusions as *within the forced-vertical model*. The
> corrected model is the path forward and is documented here in §0/§6/§9.

---

## 13. THE ONE-PARAGRAPH "START HERE" FOR THE NEXT SESSION

N=11 is done (852, proven, reachable). N=13 is parked at 586 (believed optimal under the old model;
proof blocked). **N=15 is active.** The breakthrough: stop forcing verticals on newly-placed columns
— the optimal play is a high-value main word scored ×27 (newly tiles on the ×3 cols 0/7/14 + ×2 cols
3/11, columns empty) with only a small connecting structure on the *pre-placed* columns to keep the
board connected through center (7,7). The LB candidates are ~1700 (`croquemboucheje` 1751,
`geschenkcheques` 1724). The next concrete task is to **build the corrected witness model** (empty
newly columns; center reached by a connector in a column adjacent to col 7 + a row-7 word, NOT
through col 7; or — simpler — put the main word on the center row 7 so center is free) and produce a
**verified center-connected ~1700 witness** via `witness_check`. Then certify. Ask the user whether
the main word may go on the center row. Mind the process-kill safety rule (no group kills).
