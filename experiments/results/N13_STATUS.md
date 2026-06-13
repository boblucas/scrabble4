# N=13 max-turn — CENTER-CONSTRAINED status (witness-first phase)

Board W=H=13, center cell (6,6), scaled bag = round(count·169/225) = **82 tiles + 2 blanks**,
cross-words HMAX=8, main word pinned to row 0, blanks on. THE binding constraint: the single
4-connected setup component MUST include the center (6,6). Captured exactly as 35_certify's
`--center` mode: the center COLUMN (col 6) must be a SCORING column whose vertical reaches the
center row, i.e. length >= H//2 + 1 = **7** (and <= HMAX = 8). All claims below are
center-constrained. Scope: ONLY the center-constrained variant (per mandate).

## BRACKET (center-constrained)

    [ <verified lower>, 2032 ]        (lower = best independently-verified center-connected witness)

- **Global SOUND UPPER = 2032** = max-main-score (1643, `polycyclische`, optimal bingo mask
  {0,3,4,5,6,9,12}) + GVUB (389). Sound for the center-constrained problem because center-valid
  boards are a SUBSET of all boards (an upper over the superset bounds the subset), and GVUB is a
  valid upper on ANY main word's vertical score (tile-aware assignment-knapsack, full bag,
  blank-relaxed). LOOSE — no single board approaches it; most high-main-score words are infeasible.
- **GVUB = 389** (global vertical UB / STOP bound), reused from the prior N=13 enum (exp34/exp33
  agree). Verified value.

## VERIFIED CENTER-CONNECTED WITNESSES (the lower bound)

Every witness below passes the INDEPENDENT checker `experiments/witness_check.py` (full-rules
score recompute, setup 4-connectivity, CENTER (6,6) occupancy, bag, optimal blank). Saved as
JSON with `require_center=true`.

| main word | total | main | vert | mask (scoring cols) | center col-6 vertical | blanks | witness file |
|---|---|---|---|---|---|---|---|
| degenereerden | 316 | 230 | 86 | {0,1,2,3,4,5,6} left block | rechtst (len 7) | 0 | results/turns/N13_witness_degen_lb.json |

(table updated as the ratchet improves; best is mirrored to results/turns/N13_seed.json)

### The witnessable STRUCTURE (the key finding)

Top main words (croquembouche 1616, polycyclische 1643, lunchchequeje, circumflexjes, ...) are
q/x/z/j/y-heavy and **structurally infeasible** under the tight scaled bag + cross-word legality
(confirmed: xfill proves `LE 0` / hard-infeasible, or the bridge search explodes). This reproduces
the documented N>=13 witnessing wall: feasible witnesses live at DEEPER (lower-main-score) words.

The CONNECTIVITY-FRIENDLY structure that DOES witness: a **left-edge contiguous scoring block**
{0,1,2,3,4,5,6} (7 newly-placed cells => bingo) with the center column (6) long (len 7-8) and the
other six columns short (len 2). The six short stubs' row-1 letters + ONE bridge tile in col 7
form a single 8-letter HORIZONTAL word in row 1 that both validates the stubs AND bridges into the
pre-placed right group (cols 7-12), giving ONE component including (6,6). Example (degenereerden):

    row0: degenereerden     (cols 0-6 newly placed, "eerden" pre-placed)
    row1: oxalaten          (8-letter connector word, col7 = bridge tile)
    col6: rechtst           (len-7 vertical, rows 0-6, occupies center (6,6))

This is fast for xfill (`MAX` in ~0.001s once connectable); the hard part is finding a main word
whose left-block letters admit such a word-rectangle within the bag.

## CANDIDATE THREAT WORDS (could still beat the lower if a feasible center-board exists)

Any main word with main_score + GVUB(389) > current_lower is a threat. Highest main_scores
(optimal bingo mask), all q/x/z/y-heavy / so-far infeasible by cross-word legality + rare-letter
budget — must each be RULED OUT (infeasible) or WITNESSED to close the bracket:

    polycyclische 1643, croquembouche 1616, lunchchequeje 1562, circumflexjes 1562,
    hexyleenoxide 1562, bicyclekickje 1562, psycholyticum/psychofysisch/playboyachtig/
    cyclothymisch/chalcedonyxje 1535, exequaturtjes/visquotumpjes/reuzencheques/... 1508, ...

(full ranked list via the main-word scan; the certification step would enumerate these via
exp33 --enum-only and certify each at floor = lower − main_score.)

## NEXT STEP (NOT started here — main session decides)

Band CERTIFICATION (35_certify build --board 13 --center --main <w> --turn <mask> --floor
<lower−main>) per surviving threat word, after the lower is ratcheted quiet. The center mode +
three-pass engine already exist. N=13 bands are ~10× N=11's; the documented perf levers
(Pass-0 exact-knap pre-filter, stub-tries) apply. Do NOT launch the multi-day band run from the
witness phase.

## SOUNDNESS NOTES
- Lower bound = best witness re-checked by witness_check.py (independent of the solvers). Center
  occupancy re-verified per witness.
- Upper bound = main_score(superset) + GVUB(superset), both valid over the unconstrained superset
  => valid for the center subset.
- xfill `MAX v` from a NATURALLY-COMPLETED run is a proven per-vector vertical max; `TO`/aborts
  prove nothing and are never used as bounds.
