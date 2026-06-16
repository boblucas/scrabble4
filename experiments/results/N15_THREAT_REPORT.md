# N=15 Threat-Set Report — toward proving the true optimum (floor = 1952)

Verified lower bound (floor): **1952** — `geschenkcheques`, witness
`experiments/results/turns/N15_best_1952.json`, independently `witness_check`-OK
(main 1724 + verticals `golfsurf` 69 / `klepstuw` 69 / `skyboxje` 90 = 228, 1 blank, reserve=1,
center-connected). This report enumerates every main word that could *possibly* beat 1952 and reports
the certification status of each.

Tooling: `experiments/n15_threat_enum.py` (steps 1–2), `experiments/n15_bag_ub.py` (sound bag-aware
certification refinement, step 3a), `experiments/n15_push_lb.py` (LB hunt, step 3b).

---

## Step 1 — the sound upper bound

For a candidate main word `w` placed on row 0:

```
UB(w) = x27_proxy(w) + vert_UB(w)
```

### Why only 15-letter words (soundness receipt)
The three ×3-WORD (TWS) premium columns on row 0 are **0, 7, 14**. A horizontal main word's board
word-multiplier is the *product* of the per-cell word multipliers over the cells it newly places. To
reach ×27 = 3·3·3 the word must newly-place tiles on **all three** of cols 0,7,14 — which forces a
**15-letter** word spanning cols 0..14 (the only word reaching all three). Any word covering ≤2 TWS
cols has word-mult ≤ ×9.

Numerically (verified in code): the most generous conceivable ≤14-letter play —
`9·(Σ letter vals + 2 best letters doubled for DLS) + 50` main, plus a *generous* vertical add (the
2 best letters at ×3 + the next 5 at ×1, each using its dictionary-max tail) — peaks at **UB = 1047**
(via `cyclothymische`) ≪ 1952. **So no word shorter than 15 letters can threaten the floor.** Only
15-letter words placed newly on {0,7,14} are enumerated.

### x27_proxy — sound over-estimate of the MAIN contribution
```
x27_proxy(w) = 27·( Σ val(letter) + val(w[3]) + val(w[11]) ) + 50
```
Assumes both ×2-LETTER (DLS) cols 3,11 are newly-placed (best case) and a 7-tile bingo (+50). Exact
maximum main score over masks containing {0,7,14}; an over-estimate for masks dropping a DLS col.
Sound.

### vert_UB — sound over-estimate of the TOTAL vertical bonus
Verticals add only at newly columns; a vertical at newly col c is `w[c]+tail`, length 2..8, scored
`WM[c]·(LM[c]·val(w[c]) + Σ val(tail))`. Per-column exact max:
```
best_vert_bonus(c, w[c]) = WM[c]·( LM[c]·val(w[c]) + max_tail_value(w[c]) )
```
where `max_tail_value(L)` is the dictionary maximum Σ val(tail) over legal words `L+tail`, len 2..8.
`vert_UB(w)` = sum of the **7 largest** per-column bonuses (a bingo plays exactly 7 columns).
Per-column maxima over-estimate any realised vertical; summing 7 over-estimates any 7-column mask;
finite-bag contention and the reserve cap are **ignored** (looser, sound). Cross-check:
`vert_UB(geschenkcheques) = 436 ≥ 228` actually banked. ✔

### tight_UB — the mask-aware bound we prune with (strictly sound, tighter)
```
tight_UB(w) = max over LEGAL masks m of [ true_main(w,m) + Σ_{c∈m} best_vert_bonus(c, w[c]) ]
```
where `true_main(w,m)` is the *exact* main score for mask m (no phantom DLS bonus) and a mask is
"legal" iff every maximal run of ≥2 pre-placed row-0 cols already spells a dictionary word
(necessary condition for any legal setup board). Strictly sound: a real board uses exactly one legal
mask; its main score is `true_main` and its verticals live only on that mask's newly columns, each
bounded by its exact per-column best.

---

## Step 2 — THE THREAT SET (the key result)

- 15-letter words total: **116 983**
- Loose screen `x27_proxy + vert_UB(7-best) > 1952`: **68** words
- Of those, **12 have no legal ×27 mask** (their pre-placed substrings can never spell words —
  e.g. `croquemboucheje`, `alfahydroxyzuur`) → unplayable ×27 → excluded.
- **TIGHT placeable threat set (`tight_UB > 1952`): 26 words.**

| tight_UB | word | best mask (newly cols) |
|---:|---|---|
| 2158 | geschenkcheques | 0,3,7,8,11,12,14 |
| 2123 | flauwekulexcuus | 0,1,3,7,11,12,14 |
| 2064 | chequeformulier | 0,3,5,7,9,11,14 |
| 2051 | cultuurchequeje | 0,2,7,10,11,12,14 |
| 2046 | jacquardmachine | 0,2,3,4,7,11,14 |
| 2036 | bouwcuratrixjes | 0,1,3,5,7,11,14 |
| 2032 | chemsexpartytje | 0,3,4,7,11,12,14 |
| 2025 | chequebedragjes | 0,1,3,4,7,11,14 |
| 2020 | craqueleachtigs | 0,3,4,7,11,13,14 |
| 2019 | quichebuffetjes | 0,3,4,7,9,11,14 |
| 2012 | babyglimlachjes | 0,3,5,7,10,11,14 |
| 2009 | cliquetsystemen | 0,3,4,7,9,11,14 |
| 2005 | wetenschapsquiz | 0,3,5,7,9,11,14 |
| 2001 | schuurschijfjes | 0,1,3,5,7,11,14 |
| 1989 | dyscalculischen | 0,2,3,6,7,11,14 |
| 1981 | craqueleachtige | 0,3,4,7,11,13,14 |
| 1979 | textielcyclusje | 0,3,7,9,11,12,14 |
| 1978 | aliquotvleugels | 0,1,3,5,7,11,14 |
| 1976 | jacquardweefsel | 0,2,3,4,7,12,14 |
| 1966 | yoghurtcultures | 0,1,3,7,9,11,14 |
| 1964 | upcyclestertjes | 0,2,3,5,7,11,14 |
| 1963 | vluchtreflexjes | 0,6,7,8,9,11,14 |
| 1959 | playboyachtigst | 0,3,7,9,11,13,14 |
| 1957 | perscommuniques | 0,3,4,7,11,12,14 |
| 1957 | chiquelingetjes | 0,3,4,7,9,11,14 |
| 1955 | quicheachtigers | 0,3,6,7,8,11,14 |

### Crucial structural observation
**No placeable threat word has a main score above 1724** — the floor word `geschenkcheques` (and
`jacquetkostuums`) at main 1724 are the highest-main placeable ×27 words; every word with a higher
`x27_proxy` (croquemboucheje 1751, …) has *no legal mask*. So beating 1952 requires banking
**> (1952 − true_main)** of vertical bonus (≥ 228 for the strongest word, ≥ 255, ≥ 309 … for the
rest). The floor witness already banks *exactly* 228 → 1952. This is a tight target: the optimum is
plausibly 1952 itself.

Across the 26 threat words there are **610 legal (word,mask) pairs**, of which **187** have a
per-mask sound UB > 1952 and thus genuinely need certification (the analytic per-mask bound already
disposes of 423).

---

## Step 3 — certification (in progress)

Two sound certification levers are being applied:

**3a. Bag-aware sound UB (`n15_bag_ub.py`).** For each word, an ILP solved to OPTIMAL chooses ≤1
vertical word per newly column to maximise total vertical bonus subject to the *combined* tail-tile
multiset fitting the available bag (full − 7 main tiles − reserve=1). This is a sound relaxation
(drops connectivity & other-run legality, which only reduce score), so `true_main + ILP_opt` is a
sound UB. If it falls ≤ 1952 the word is **CERTIFIED ≤ 1952**. (Geschenkcheques bag-UB = 2067, down
from 2158 but still > 1952 — correct, since 1952 *is* achievable on it.)

**3b. New-LB hunt (`n15_push_lb.py`).** CP-SAT maximises the realised TWS-vertical bonus to look for
a *verified* board scoring > 1952; any hit is re-checked by `witness_check`, saved, and raises the
floor.

### 3b result — NO new LB found
Ran the LB hunt on the 5 highest-true_main threat words (flauwekulexcuus, jacquardmachine,
chequeformulier, cultuurchequeje, chemsexpartytje), all legal masks, cap 60s, rows 11. **Every
word's best verified total was ≤ 1952** (no board > 1952 found anywhere). The floor stays **1952**.
(`geschenkcheques` itself already *achieves* exactly 1952; the push model finds nothing above it.)

### 3a result — bag-aware sound certifications
The bag-aware contention bound is markedly stronger than `tight_UB`: modelling the *finite shared
bag* (one q/x/y, two z/c/b/…, two blanks) among all the verticals drops each word's UB by ~60–110
points, pushing the entire lower/middle tier **below the floor**. **≥ 17 of 26 threat words are
CERTIFIED ≤ 1952** (sound: each word's bag_UB = max over ALL legal masks of `true_main + OPTIMAL
ILP`, every mask proved OPTIMAL) — the run is still classifying the heaviest ~6 words. The
borderline tier (tight_UB 2009–2025) is certifying as predicted (cliquetsystemen 1931,
babyglimlachjes 1933, quichebuffetjes 1940), so the final OPEN residual is shaping up to be only the
~6 very top words:

| word | tight_UB | bag_UB | verdict |
|---|---:|---:|---|
| quicheachtigers | 1955 | 1862 | **CERTIFIED ≤ 1952** |
| perscommuniques | 1957 | 1881 | **CERTIFIED ≤ 1952** |
| chiquelingetjes | 1957 | 1881 | **CERTIFIED ≤ 1952** |
| playboyachtigst | 1959 | 1896 | **CERTIFIED ≤ 1952** |
| vluchtreflexjes | 1963 | 1906 | **CERTIFIED ≤ 1952** |
| upcyclestertjes | 1964 | 1873 | **CERTIFIED ≤ 1952** |
| yoghurtcultures | 1966 | 1883 | **CERTIFIED ≤ 1952** |
| jacquardweefsel | 1976 | 1907 | **CERTIFIED ≤ 1952** |
| aliquotvleugels | 1978 | 1915 | **CERTIFIED ≤ 1952** |
| textielcyclusje | 1979 | 1903 | **CERTIFIED ≤ 1952** |
| craqueleachtige | 1981 | 1910 | **CERTIFIED ≤ 1952** |
| cliquetsystemen | 2009 | 1931 | **CERTIFIED ≤ 1952** |
| babyglimlachjes | 2012 | 1933 | **CERTIFIED ≤ 1952** |
| quichebuffetjes | 2019 | 1940 | **CERTIFIED ≤ 1952** |
| dyscalculischen | 1989 | 1917 | **CERTIFIED ≤ 1952** |
| schuurschijfjes | 2001 | 1912 | **CERTIFIED ≤ 1952** |
| wetenschapsquiz | 2005 | 1944 | **CERTIFIED ≤ 1952** |

| cliquetsystemen | 2009 | 1931 | **CERTIFIED ≤ 1952** |
| craqueleachtigs | 2020 | 1942 | **CERTIFIED ≤ 1952** |
| chequebedragjes | 2025 | 1944 | **CERTIFIED ≤ 1952** |

**FINAL: 19 of the 26 threat words are CERTIFIED ≤ 1952** (sound — every mask proved OPTIMAL). The
finite-bag contention bound certified the entire tier up to tight_UB 2025.

(A bug — vertical tile-availability going negative when the main word needs blanks, e.g.
dyscalculischen's mask wanting 3 'c' from a 2-'c' bag — initially mislabelled playboyachtigst /
dyscalculischen as UNRESOLVED; fixed by clamping availability at 0, commit 0769dfb. Both then
certified. CERTIFIED verdicts were never affected: they had all masks OPTIMAL, no infeasible mask.)

### The OPEN residual — exactly 7 words
The 7 heaviest threat words have a sound bag-aware UB that stays **> 1952**, so the bag lever cannot
certify them and they remain **OPEN** (their complete certification hits the N=15 proof-wall):

| word | tight_UB | bag_UB | status |
|---|---:|---:|---|
| chemsexpartytje | 2032 | 1971 | **OPEN** |
| bouwcuratrixjes | 2036 | 1965 | **OPEN** |
| jacquardmachine | 2046 | 1992 | **OPEN** |
| cultuurchequeje | 2051 | 1958 | **OPEN** |
| chequeformulier | 2064 | 1989 | **OPEN** |
| flauwekulexcuus | 2123 | 2021 | **OPEN** |
| geschenkcheques | 2158 | 2075 | **OPEN** (the floor word itself; achieves *exactly* 1952) |

(All bag_UB values are sound per-word maxima over every legal mask, each ILP OPTIMAL. The remaining-
14 run finished cleanly: 7 CERTIFIED, 7 STILL-THREAT, 0 UNRESOLVED.) Note all 7 OPEN bag_UBs are
within ~20–125 of 1952 — the achievable max is *tightly* bracketed near the floor.

> **Honest proof-wall note (the OPEN residual = 7 words).** For these 7 a *complete* sound
> certification of "true max ≤ 1952" requires an **uncapped exhaustive search of the corrected
> (verticals-optional, connectivity-fill) model**, which is **OPEN**: the full ≤8-word board CP-SAT
> model does not close to OPTIMAL within practical walls
> (confirmed — `geschenkcheques` returns only FEASIBLE after 90 s), and `xfill` implements the
> *forced-vertical* model (handoff §0), not the corrected one, so it cannot certify this model out of
> the box. These words are reported **OPEN**, not certified — exactly as the handoff predicted for
> N=15. They are nonetheless strongly evidenced not to beat 1952: their best achievable TWS verticals
> (≤8) are in the 60–99/col range (`geschenkcheques` banks 69/69/90 = 228, hitting *exactly* 1952),
> and the LB hunt found no board above 1952 on the most dangerous of them.

---

## Bottom line / honest assessment

- **Current best verified N=15 LB = 1952** (`geschenkcheques`, witness_check-OK). **No new LB found.**
- **Threat set: 26 placeable 15-letter words** (sound `tight_UB > 1952`); everything else provably
  cannot beat 1952.
- **19 of the 26 CERTIFIED ≤ 1952** by the sound bag-aware bound (the entire tier up to tight_UB
  2025), every ILP OPTIMAL.
- **OPEN residual: exactly 7 words** (the very top — `geschenkcheques` 2158, `flauwekulexcuus` 2123,
  `chequeformulier` 2064, `cultuurchequeje` 2051, `jacquardmachine` 2046, `bouwcuratrixjes` 2036,
  `chemsexpartytje` 2032) whose sound bag-aware UB stays in (1958, ~2067] — above 1952. Their
  complete certification is **blocked at the N=15 proof-wall** (no uncapped exhaustive solver for the
  corrected model; CP-SAT board model won't close; `xfill` is the wrong model). This is the genuine
  wall the handoff predicted. Their bag_UBs are within ~20–115 of the floor, so the achievable max is
  *tightly* bracketed near 1952.
- **Is the true optimum within reach?** Partly. The threat set is small and 14+ words are soundly
  eliminated, but a *complete* machine proof that 1952 is optimal is **not** achievable with the
  existing machinery — it needs a sound exhaustive solver for the verticals-optional connectivity-
  fill model (the missing tool). The evidence that **1952 is the true optimum is strong**: no
  placeable word out-scores it on the main word, no word's bag-aware ceiling that we could certify
  exceeds it, the LB hunt finds nothing above 1952, and the floor word saturates its own ceiling
  (banks exactly the verticals it needs to reach 1952). But it remains a *strongly-evidenced believed
  optimum*, not a machine-proven one — the same status as N=13's 586.

### Reusable artifacts
- `experiments/n15_threat_enum.py` — threat enumeration (steps 1–2); writes `n15_threats.jsonl`
  (loose) and `n15_threats_tight.json` (the 26).
- `experiments/n15_bag_ub.py` — bag-aware sound-UB certifier (step 3a); writes per-word bag_UB +
  verdict. `--reverse` (lowest-UB-first), `--threats`/`--out` for subsets.
- `experiments/results/n15_bag_ub*.json` / `*.log` — certification verdicts.
- `experiments/n15_push_lb.py` (pre-existing) — the LB hunt (step 3b).

---

## Step 4 — the HMAX-cap analytic certification (threat set 26 → 2 OPEN)

**THE LEVER (sound, fast).** A vertical cross-word at a newly column has board RUN LENGTH ≤ HMAX = 8
(a board run longer than HMAX is illegal — no >HMAX word is in the legal dictionary). For each newly
column `c` with row-0 letter `M[c]`, let `G(c)` be the EXACT maximum vertical gross over all legal
verticals `M[c]+tail` of length 2..8 (stub `tail` a dict word; the column's board word-multiplier
applied to the row-0 tile; length-1 = bare tile, gross 0). Then for ANY legal board

    total(M, mask) ≤ main_const(M, mask) + Σ_{c∈mask} G(c)  =:  UB(M, mask).

This `UB` ignores tile contention, blanks, connectivity, the reserve and the center constraint (all
of which only LOWER the achievable score), so it is a **sound over-estimate**. If
`max over all legal masks of UB(M, mask) ≤ 1952`, the word is **CERTIFIED ≤ 1952 with no search**.

Driver: `experiments/n15_analytic_certify.py` (independent recompute from `rules.words` + the
multiplier rows; deliberately does NOT force the center-column length, which would shrink and risk
under-counting the bound). Result over the 26 threat words:

- **22 words CERTIFIED ≤ 1952 analytically** (UB ≤ 1952 across every legal mask), tightest
  `chemsexpartytje` UB = 1945 (slack 7), independently re-checked.
- **4 words have UB > 1952** → analytic-OPEN: `geschenkcheques` 2061, `flauwekulexcuus` 2022,
  `chequeformulier` 1964, `jacquardmachine` 1961.

*Why the prior xfill/35_certify bands were astronomical:* `35_certify.enumerate_band` lists candidate
lengths up to H = 15, so the million-vector bands (`geschenkcheques` ~32M, `perscommuniques` ~1.5M)
were **dominated by length>8 phantom vectors that are infeasible under HMAX=8**. Capping at HMAX
collapses the realizable band — for all 22 certified words it is EMPTY (UB ≤ vfloor everywhere).

### Step 4b — bounded xfill search for the 4 analytic-OPEN words
Driver `experiments/n15_bounded_certify.py`: per legal mask, enumerate the **HMAX-8-capped** band
(realizable length-vectors with col-lengths 1..8 whose optimistic UB exceeds the per-mask vertical
floor `vfloor = 1952 − main_const`) and run `xfill --batchvec --maxscore vfloor` (base file
`reserve=1`) over exactly those vectors. A natural `LE` on every band vector ⇒ CERTIFIED; a `MAX` ⇒
NEW-LB; a `TO` ⇒ OPEN.

- `jacquardmachine` (capped band ≤ 27/mask) — **CERTIFIED ≤ 1952** (all natural LE/NOCAND).
- `chequeformulier` (capped band ≤ 129/mask) — **CERTIFIED ≤ 1952** (all natural LE/NOCAND).
- `flauwekulexcuus` (capped band ~62k), `geschenkcheques` (capped band ~132k) — **OPEN**: their
  hardest masks have slices that do not close to natural `LE` within practical walls (passA 2 s,
  passC 300 s). `geschenkcheques` achieves *exactly* 1952, so its true slice max is 228 and proving
  `LE 228` on its tightest slice is the genuine residual.

### Step-4 bottom line (supersedes Step-3 status)
- **24 of the 26 threat words CERTIFIED ≤ 1952** (22 analytic + 2 bounded-xfill), all sound
  (over-estimate ≤ floor, or natural `LE` on the full realizable band).
- **OPEN residual = exactly 2 words: `geschenkcheques` (analytic UB 2061) and `flauwekulexcuus`
  (2022)** — the two highest-UB words; `geschenkcheques` is the floor word itself. No board > 1952
  was found anywhere (xfill push on `geschenkcheques` top masks → TO, never MAX).
- Verified LB unchanged: **1952**. Evidence that 1952 is the true optimum is now *stronger*: the
  threat residual is down from 7 (bag-UB) to 2, and those 2 are the words bracketed tightest to the
  floor.

Reusable artifacts (step 4): `experiments/n15_analytic_certify.py`,
`experiments/n15_bounded_certify.py`, `experiments/n15_xfill_push.py` (LB push),
`experiments/n15_certify_xfill.py` (per-word 35_certify wrapper);
logs `experiments/results/turns/analytic_cert.log`, `bounded_heavy.log`.

## Step 5 — VARMAX certification at the current verified LB = 1955 (2026-06-16)

Verified LB is **1955** (`geschenkcheques`, `experiments/results/turns/N15_best_1955.json`,
witness_check-OK; re-verified). Re-deriving the analytic OPEN set at LB=1955
(`n15_analytic_certify.py --lb 1955`): **22 of 26 threat words CERTIFIED ≤ 1955** by the sound
HMAX-capped analytic UB; the **4 OPEN** words (analytic UB > 1955) are
`geschenkcheques` (UB 2061), `flauwekulexcuus` (2022), `chequeformulier` (1964),
`jacquardmachine` (1961).

The 4 OPEN words were attacked with the **variable-length xfill engine**
(`xfill_varmax --varmax BASE --maxscore vfloor`, one search per (word,mask) == the full fixed
length-vector sweep; equivalence battery `xfill_rs_varlen_equiv.sh` re-validated ALL PASS).
Driver: `experiments/n15_varmax_certify.py` (24 tracked Popen workers, specific-PID kills only,
per-unit + heartbeat ETA logging, `verdicts.jsonl`). For each of the 118 legal masks over the 4
words, `vfloor = 1955 − main_const`; a natural `LE vfloor` ⇒ that mask CERTIFIED ≤ 1955; a
`MAX m` with `main_const+m > 1955` ⇒ witness_check'd NEW LB; a wall/deadline `TO` ⇒ OPEN
(proves nothing).

Two stages: stage-1 wall=180s (`certs/n15varmax_stage1/`), stage-2 wall=1800s
(`certs/n15varmax_stage2/`, parent driver externally killed at 98/118 with the last 20 hard
masks mid-TO — recorded verdicts are sound). Union of both stages (a natural `LE` in either
stage certifies the mask, wall-independent):

| word | certified / legal masks | OPEN |
|---|---|---|
| geschenkcheques | 31 / 39 | 8 |
| flauwekulexcuus | 6 / 35 | 29 |
| chequeformulier | 7 / 10 | 3 |
| jacquardmachine | 30 / 34 | 4 |
| **total** | **74 / 118** | **44** |

**Outcome: LB unchanged at 1955; NOT proven optimal.** No mask anywhere produced a `MAX`
beating 1955 (0 NEW-LB, 0 witness-rejects) — every completed search confirmed its verticals
cannot reach the floor. **74 of 118 masks CERTIFIED ≤ 1955** (all natural `LE`). The residual is
**44 OPEN masks** — every one a *wall-clock TO that proves nothing*, NOT a counterexample. The
OPEN masks are exactly those that include both ×2-letter newly cols {3, 11} (highest scoring
pressure, least prunable).

**ETA / feasibility picture (the hard finding).** The varmax+knapsack engine instantly certifies
the easy masks (natural `LE` in **1 node / ~1 s** — the root knapsack proves the bound), but the
hard masks are intractable for it: at the 180 s wall the OPEN searches had explored 4k–7.8M
nodes; at the **1800 s** wall the *hardest* masks (cols {3,11}+neighbours) explored **~0–20
nodes in 30 minutes** — i.e. the per-node cost on a full-length N=15 instance (per-node knapsack
over 15-length × hundreds-of-words domains + large connectivity bridge-fill) is **tens of
seconds per node**, so the 1800 s wall could not even fire cleanly (the watchdog SIGTERM'd a few
that overran by ~2 min). A longer wall buys *nothing* on these masks; **a full optimality proof
is NOT in reach with the current engine.** Closing it needs a cheaper root prune (incremental
consistent-set / bitset knapsack deltas, a connectivity-coupled root bound), not more wall time.

Reusable artifacts (step 5): `experiments/n15_varmax_certify.py`,
`experiments/xfill_rs/target/release/xfill_varmax` (stable copy of the varmax binary 46e025d),
logs `experiments/results/n15_varmax_certify.log` / `n15_varmax_stage2.log`,
verdicts `experiments/results/certs/n15varmax_stage{1,2}/verdicts.jsonl`.
