# Max-Turn Scrabble — Project Handoff (2026-06-13)

Goal: compute the **provably-optimal maximum-scoring single Scrabble turn** on boards N=11, N=13,
and ultimately **N=15**, with machine-checkable certificates. Dutch dictionary. TIME IS FREE
(month-long runs fine); the only hard wall is the user's shared box (bob's Julia jobs run on it).

This doc is the full context dump. Companion long-form memory:
`/home/bob/.claude/projects/-home-bob-programming-scrabble4/memory/` (MEMORY.md index +
`maxturn-certification-plan.md`, `maxturn-center-square-constraint.md`,
`maxturn-n11-fastinner-result.md`, `crossword-solver-design.md`, `maxturn-proof-wall.md`,
`maxturn-board-legality.md`). Plan file: `/home/bob/.claude/plans/mellow-questing-cupcake.md`.
Git branch: `experiments/automaton-cpsat-verification` (commit, do NOT push; commits end with
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`).

## 1. Problem definition (the model)

A turn = a **main word on row 0** (some cells pre-placed = lowercase in a `turn_str` like
`BOUWfYsiCuS`; UPPERCASE = newly placed this turn) + **vertical cross-words** descending from the
newly-placed scoring columns + **bridge tiles** (in non-scoring columns, rows 1..H-1) connecting
everything into ONE 4-connected component. Legality:
- every maximal H/V run of length ≥2 must be a valid dict word (≤8 letters for cross-words: HMAX=8);
- tile counts fit the (scaled) bag incl. blanks; scaled bag = round(count · W²/15²);
- ONE 4-connected component;
- **the component must include the CENTER cell (W//2, W//2)** — the game starts there (user
  constraint, added mid-project). Center-valid boards are a SUBSET of unconstrained, so all proven
  UPPER bounds survive the constraint; only achievability/witnesses must be center-connected.

Scoring = main-word score (incl. **bingo +50** for placing 7 tiles, premium multipliers) + sum of
vertical cross-word scores (the newly-placed row-0 tile contributes its letter+word multipliers to
the vertical too). Main word pinned to row 0; defensible assumptions: cross-words ≤8, scaled bag.

## 2. CURRENT STATUS — certified results

| Claim | Value | Status |
|---|---|---|
| bouwfysicus N=11, unconstrained | **852** (main 626 + verticals 226) | ✅ CERTIFIED `certs/n11_fixed_221` (commit 80eeaa8) |
| bouwfysicus N=11, center-constrained | **852** | ✅ CERTIFIED standalone `certs/n11_center` (f160305); also by composition (the 852 board's col5 `yenteken` spans rows 0-7 ⊇ center, and the unconstrained ledger bounds all boards ≤226) |
| N=7 afhappe | **151** | proven (CP-SAT-validated end-to-end; stands) |
| **global** N=11 (all main words) | 852 expected | 🔄 in progress (agent) |
| N=13, N=15 | — | not started |

The 852 witness board (verticals: col0 boxertjes 72, col1 om, col2 uh, col3 wazend, col5 yenteken
34, col8 candere, col10 stulpvormig 72; 1 blank). Verify any ledger in minutes:
`.venv/bin/python experiments/35_certify.py check experiments/results/certs/<name>/ledger.json`

Witness chain over corrected scoring (each independently verified by `witness_check.py`):
216 → 221 → 222 → **226** (the full-domain engine kept finding better boards than earlier
restricted searches). NOTE the certified 852 EXCEEDS the original buggy "850" — fixing the scoring
bugs AND searching the full domain found genuinely better boards.

## 3. The engine (how a claim gets proven + certified)

**`experiments/xfill_rs/src/main.rs`** — bespoke Rust crossword-fill solver. For a fixed
length-vector: `xfill <inst> --maxscore <floor>` → `MAX v` (proven vector max v>floor) / `LE floor`
(exhaustive proof no board beats floor) / `TO ...` (wall/node abort — proves NOTHING, never trusted
as LE). Soundness levers inside: AC-3 presolve (adjacent scoring cols), joint tile-knapsack UB
(`knap_ub`, runs every node — the hot path, 88.8% of runtime per perf), wm-weighted blank penalty,
center handled by the outer (col-length constraint). Modes: single, `--batch LISTFILE` (path list),
`--batchvec BASE LISTFILE` (in-memory instance assembly from a per-main-word BASE file — THE scale
path; per-vector instance files are impossible at 6.6M-vector scale). Sound per-instance wall via
`BATCHWALL`/`WALL` env → aborts emit `TO`. `tick()` checks the abort flag on EVERY node.

**`experiments/35_certify.py`** — certification ledger (`build` / `check`). Independently
re-enumerates the FULL band of length-vectors with optimistic UB > floor (kills truncation bugs),
requires a sound verdict per vector: GEOM (pure-python/oracle Steiner bound > bridge budget), LE
(receipt = naturally-completed uncapped xfill line + base sha256), KNAP (tile-knapsack bound ≤
floor), MAX>floor = refutation. Three-pass stage 2: pass A short wall (`--wall-a 2`), pass B
tile-knapsack receipts, pass C long-wall residue; survivors processed UB-descending. Append-only
`verdicts.jsonl`. `check` re-derives the base canonically, streams coverage, re-proves GEOM/LE/KNAP
samples, re-verifies the embedded witness. Resumable.

**`experiments/witness_check.py`** — standalone INDEPENDENT witness checker (shares no code with the
solvers): full-rules score recompute (bingo, multipliers, blanks), setup connectivity, center
occupancy, bag consistency, optimal blank derivation. THIS is what caught the blank-penalty bug.

**`experiments/xtest.py`** — `build_instance` / `dump_simple` (per-vector) and `build_base` /
`dump_base` (per-main-word base for batchvec). `regress.sh` is the soundness gate suite.

**Protocol (witness-first):** ratchet the lower bound with witness hunts (`hunt_top_ub.py` top-UB
probe; feasible-region `--emit` probes) BEFORE the band run, so it runs at the believed-true floor;
then the certifier proves no vector beats it. Each `MAX` refutation raises the floor → re-witness →
re-run (the band shrinks). Don't certify at a too-low floor (huge wasteful band).

## 4. Bugs found (the saga — these are the load-bearing lessons)

User-caught: (1) `sn` — cross-words weren't validated both directions; (2) center-square — legal
positions must connect to center. Both → real model fixes.

Certification-layer-caught (each would have produced a wrong "proof"; all fixed + committed):
1. **l=1 phantom gross**: `construct_rules` injects every single letter into `rules.words`, so each
   column had a phantom length-1 "vertical word" scoring value·lm·wm — double-counting the row-0
   tile (a lone tile forms no vertical word). Fixed in candidates_for/build_instance/etc.
2. **blank penalty missing ×wm**: a vertical word's WORD multiplier applies to all its cells, so
   blanking a stub in a wm>1 column loses value·wm, not face value. Lived in THREE places at once
   (xfill, CP-SAT ground truth, exp34) so the 26/32 cross-check never caught it — only the
   from-first-principles `witness_check` did. The "850" board really scores 842 under correct rules.
3. **maxsec FALSE-PROVEN hole**: exp32's maxsec breaks exited without recording the un-enumerated
   remainder → verdict printed "PROVEN" after enumerating ~7k of a 6.6M band. The v1/v3 "proven
   224/173" were false coverage claims. Fixed: frontier_ub recorded at every break.
4. **aborted-flag 1-in-4096**: the wall deadline fired on time but `tick()` only checked it every
   4096 nodes, so "aborted" searches ran to natural completion (WALL=5 → abort at 44s). Fixed:
   tick() bails immediately on the flag (WALL=5 → TO at 5.003s; also retires the MAXNODES fake-LE
   footgun — aborted now prints TO, never LE).

LESSON: claims outran checks repeatedly when evidence lived in ad-hoc shell logs. The
certification-first architecture (independent re-derivation + receipts + a witness checker sharing
no code with the solver) is what made the final 852 trustworthy. Soundness gate after EVERY solver
change: `bash experiments/regress.sh` must print ALL GATES GREEN (N=7 26/26 decision + deep-col10
LE-224 ×3 + center col0=1 LE-173 ×15). Trust `LE` ONLY from uncapped, naturally-completed runs.

## 5. Performance (measured 2026-06-13)

v5 N=11 profile: ~557 core-hours; **6.2% of vectors carry 82% of the time** (the slice whose cheap
root bound can't prune); 66% root-prune at ~1ms. perf (after user set `kernel.perf_event_paranoid=2`)
on a hard vector: **88.8% of runtime in `knap_ub::rec`** (the per-node multiple-choice knapsack
SEARCH — NOT the rebuild, which is ~0%; dfs_score self ~4%). knap is ESSENTIAL (NOKNAP explodes
node count >30×). LANDED WINS (both verdict-neutral, node count byte-identical, gates green):
(a) commit 3bac317 — branch most-constrained column first in `rec`, ~26% faster (4.07s→3.0s);
(b) commit 65098c9 — inline the LAST uncommitted column in `rec` (no recursion frame for the
biggest domain, which most-constrained-first leaves last), −9-15% instructions (23.93B→20.34B on
the hard vector). Tried+reverted: all-free fast-path (a wash); contiguous delta arena (instrs went
UP — slice-indexing cost > malloc saved).

TWOLEVEL structural cut: **REFUTED** (agent, 2026-06-13) — split word-choice from bridges is a
catastrophic regression (~12M vs 22k nodes on the hard vector; sound but slow; reverted). Once
scoring columns are committed the inner bridge search has a large unconstrained branching factor
and gross is pinned (nothing for a knapsack to bound); the interleaving is what tames it. Lesson:
attack the 88.8% WITHIN the interleaved search. See memory `maxturn-twolevel-negative.md`.

Remaining levers (in `mellow-questing-cupcake.md`): incremental consistent-word-set maintenance in the rebuild;
two-pass+knap in the certifier (built, but knap pass B cut 0 on N=11 — redundant there); use the
whole box when bob's Julia is idle (`--procs 40`).

## 6. TWO BACKGROUND AGENTS RUNNING (launched 2026-06-13)

- **Global N=11** (agent a59ebf354c0602b44, main tree): add `--enum-only` to
  `33_full_turn_bracket.py` (emit THREAT (word, turn_str, main_score) survivors above floor 852 via
  the main_word_solver enumeration + barepack prune), then certify each threat word with `35_certify`
  at floor `852 − main_score` (small bands). Outcome: global N=11 = 852 PROVEN, or a refutation
  (a word beating 852). Likely threats: bouwfysicas/typosquatte/whiskyclubs (599), cowboyfilms (590).
  NOTE: exp33's per-word `VerticalBracket` is the OLD slow balloon engine — do NOT use it for the
  vertical work; the certifier is the right tool (a path-1 run that used it churned 1h pointlessly
  re-bracketing the already-certified bouwfysicus to a loose [0,320]).
- **TWOLEVEL prototype** (agent a07efe438b113da47, ISOLATED WORKTREE): prototype the structural cut
  in xfill behind a `TWOLEVEL=1` flag (default off = byte-identical). A/B on the hard vector; adopt
  only if faster + gates green + verdicts/MAX-values match. CAUTION: a naive two-phase rewrite
  previously failed (0/14) by losing the word↔bridge coupling prune — the bridge-decision must keep
  the forward-checking cross-word coupling. Either outcome (win or honest failure mode) is useful.

Continue an agent with SendMessage to its id; you'll get completion notifications. Do NOT tail their
JSONL transcript files via shell (context overflow).

## 7. Roadmap to N=15

1. Global N=11 (running) → fully-proven N=11 = 852 (both flavors).
2. Perf: land TWOLEVEL if it wins (or the incremental-rebuild lever) — needed because N=13's band is
   ~10× N=11's, N=15's ~10× again.
3. N=13: witness-first hunt (the analogous top main word; note top words can be structurally
   infeasible — feasible words are deeper) → three-pass certification.
4. N=15: same shape. Honest target: proven if witnessing cooperates, else a tight certified bracket
   with the residual named. Engine handles 8M-vector bands in hours; witness quality is the schedule
   driver, not the band sweep.

## 8. Verification / how to run

- Gates (after any solver change): `bash experiments/regress.sh` → ALL GATES GREEN.
- Re-check a certificate: `.venv/bin/python experiments/35_certify.py check certs/<name>/ledger.json`
- Build a certification: `.venv/bin/python experiments/35_certify.py build --board 11 --main <w>
  --turn <TURN_STR> --floor <F> [--center] --name <n> --procs 20 --wall 600 --wall-a 2
  --witness <witness.json>`  (resumable; UB-descending; refutations printed loudly).
- Build Rust: `cargo build --release --manifest-path experiments/xfill_rs/Cargo.toml`; then refresh
  the stable binary `cp target/release/xfill target/release/xfill_lev3` (the binary 35_certify uses).
  Do NOT touch frozen `xfill_frozen` / `xfill_ac3`.
- Witness check: `.venv/bin/python experiments/witness_check.py <witness.json>`.

## 9. Environment / process gotchas (IMPORTANT)

- Python venv: `.venv/bin/python`. Repo: `/home/bob/programming/scrabble4`.
- **No `rm`** — it drops the user out of auto-mode. Truncate with `: > file` or write fresh paths.
- A `while jobs -rp | wc -l` concurrency throttle does NOT work in a detached/non-interactive shell
  (job control off → launches everything at once, a real runaway). Use **`xargs -P`**.
- `for p in $(pgrep X); do ...` aborts the whole compound under errexit when pgrep matches nothing —
  guard with `|| true` or pipe `pgrep X | while read p`. Kill detached pools by process-GROUP
  (`kill -9 -<pgid>`); they're setsid so children reparent to init.
- The Bash safety classifier intermittently errors "claude-fable-5 temporarily unavailable" on
  scheduled/auto turns — read-only tools still work; retry, or the user runs commands via `! <cmd>`.
- A 4-hour heartbeat cron (`12e5c0f3`, session-only) checks health + continues; memory holds the
  NEXT-SHELL command queue so nothing is lost between turns.
- After rebuilding xfill, ALWAYS refresh `xfill_lev3` (the binary the certifier invokes) — a stale
  lev3 once silently lacked `--batchvec` and produced all-TO.
- bob's Julia jobs share the box (multipass.jl etc., ~35 cores when active); keep `--procs` modest
  when load is high.
