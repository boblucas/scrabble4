# N=13 CENTER-CONSTRAINED — current working state (live handoff)

Snapshot time: 2026-06-13 ~12:24. Branch `experiments/automaton-cpsat-verification` (NOT pushed,
nothing committed yet). Scope: ONLY the center-constrained variant. TIME IS FREE.

## TL;DR

- **Bracket so far: [316, 2032]** (center-constrained).
  - LOWER 316 = a fully INDEPENDENTLY-VERIFIED center-connected witness (degenereerden). Real,
    legal, center-occupying turn. This is the believed-true floor *so far* — actively being
    ratcheted; the verified value will likely rise (feasible high-value words being searched).
  - UPPER 2032 = max main_score (1643 `polycyclische`, optimal bingo mask) + GVUB (389). SOUND
    (center-valid ⊂ all boards). LOOSE — no real board approaches it.
- **GVUB = 389** (global vertical UB / STOP bound), reused/confirmed from prior N=13 enum.
- **Structural blocker (confirmed, as documented for N≥13):** the high-main-score words
  (polycyclische 563 / croquembouche 536 / … in the connectable left-block mask) are q/c/x/y/z-heavy
  and **infeasible** — xfill returns `LE 0 nodes=1` (instant hard-infeasible) or `NOCAND`, or the
  bridge search explodes (`TO`). Feasible witnesses live DEEP (common-letter words, low main_score).

## VERIFIED WITNESS (the current lower bound)

File: `experiments/results/turns/N13_witness_degen_lb.json` (require_center=true). Re-check:
`.venv/bin/python experiments/witness_check.py experiments/results/turns/N13_witness_degen_lb.json`
→ **WITNESS OK, total 316**.

    main word : degenereerden   (turn_str DEGENEReerden — cols 0-6 newly placed = bingo)
    total 316 = main 230 + vertical 86,  0 blanks
    mask (scoring cols) : {0,1,2,3,4,5,6}  (left-edge contiguous block)
    board:
       row0: degenereerden
       row1: oxalaten            (8-letter connector word; col7 = bridge tile)
       col6: rechtst             (len-7 vertical, rows 0-6, OCCUPIES CENTER (6,6))

## THE WITNESSABLE STRUCTURE (key finding — reuse this)

Left-EDGE contiguous scoring block {0,1,2,3,4,5,6}: 7 newly-placed cells ⇒ bingo; center col 6
long (len 7-8 ⇒ reaches center row 6); the other six columns short (len 2). The six len-2 stubs'
row-1 letters + ONE bridge tile in col 7 form a single horizontal word in row 1 that validates the
stubs AND bridges into the pre-placed right group (cols 7-12) ⇒ ONE component incl. (6,6). Once
connectable, xfill witnesses in ~0.001s (`MAX`). Centered/sparse masks instead EXPLODE the bridge
search (`TO`, 60-74M nodes) — avoid them. (Right-edge block {6..12} is the mirror; same premium
count, no gain.)

CONFIG THAT WORKS: clen (col6 length) = 7, others = 2  (clen=8+all-len-2 is too rigid ⇒ infeasible).

## WHAT IS RUNNING NOW (detached, nice -15)

1. `experiments/n13_ratchet.py` clen=7 ol=2 over top-200 left-block-ms words → `experiments/
   results/n13/ratchet_c7.log`. PURPOSE: find the highest-main-score word that WITNESSES in the
   left-block structure. As of snapshot: descended to main≈491, **0 feasible yet** (all higher
   words infeasible). Will keep descending toward common-letter words. Best verified mirrored to
   `experiments/results/turns/N13_ratchet_best.json` + printed `BEST verified total=…`.
2. `33_full_turn_bracket.py 13 … --enum-only --seed-lower 1100 --gvub 389` → `experiments/results/
   n13/enum_seed1100.log`. PURPOSE: the THREAT (word,mask,main_score,barepack_ub) list + clean STOP.
   STATUS: STUCK in CP-SAT model build (~2.5h CPU, 0 main words iterated) — the 13-letter full-word
   automaton + word-binding is pathologically slow under the shared-machine load. May never iterate
   usefully under current load; the global UPPER (2032) and GVUB (389) are already obtained WITHOUT
   it, so it is non-blocking. Consider killing it to free a core if load matters.

CP-SAT witnessing (`xtest.cpsat_maxscore` / `cpsat_decide` holistic) was tried and is TOO SLOW
under current load (model build+solve > 4 min ⇒ killed). The Rust xfill `--emit` path is the only
viable witnessing engine right now.

## HELPER SCRIPTS WRITTEN (N=13-specific; shared tooling untouched/read-only)

- `experiments/n13_witness.py` — build instance (xtest) → `xfill --maxscore F --emit` → assemble
  witness JSON → witness_check verify (center, bag, score). Enforces center precondition (col 6
  scoring + len ≥ 7). USAGE:
  `… --main <w> --turn <TURN> --lvec l0,l1,… --floor F [--wall 60] [--name tag]`.
- `experiments/n13_ratchet.py` — sweeps (word × clen × other-len), keeps best VERIFIED total.
  Env: RWALL (xfill wall s), CLENS (col6 lengths), OLS (other-col lengths). USAGE:
  `RWALL=4 CLENS=7 OLS=2 … "<comma words>" 0,1,2,3,4,5,6`.
- `experiments/n13_holprobe.py` — holistic CP-SAT feasibility/maxscore probe (slow under load).

## GLOBAL UPPER + THREAT WORDS

Global SOUND upper = 2032 = main 1643 (polycyclische, mask {0,3,4,5,6,9,12}) + GVUB 389. Top
main_score words (any one could beat the lower IF a feasible center board exists — must each be
ruled infeasible or witnessed at certification time):
polycyclische 1643, croquembouche 1616, lunchchequeje/circumflexjes/hexyleenoxide/bicyclekickje
1562, psycholyticum/psychofysisch/playboyachtig/cyclothymisch/chalcedonyxje 1535, … (descending).

## NEXT STEPS

1. Let `ratchet_c7.log` finish; record `BEST verified total`. Then re-run the ratchet on a wider /
   deeper common-letter word set (descend past main≈300) — the realistic feasible frontier.
2. For the best feasible WORD, do a focused deep pass: vary lengths (longer verticals / ol=3-4
   where the bridge search stays small) with a longer wall to squeeze a higher verified total.
3. Optionally `hunt_top_ub.py --center --emit`-style probes on the best (word,mask) to raise the
   floor further.
4. Update `experiments/results/N13_STATUS.md` + save the best witness as the seed; write the final
   bracket. (Certification — `35_certify build --center` — is a SEPARATE later decision; do NOT
   launch the multi-day band run from this phase.)

## SOUNDNESS

Lower = best witness re-checked by the independent `witness_check.py` (center occupancy included).
Upper = superset main_score + superset GVUB (both valid over all boards ⇒ valid for the center
subset). xfill `MAX v` from a naturally-completed run = proven per-vector vertical max; `TO`/aborts
prove nothing and are never used as bounds. Resource-polite: all jobs nice -15; bob's Julia + the
N=11 cert (PID 190199) still share the box (load ~30).
