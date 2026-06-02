# Scrabble Solver — Research Directions

A complete map of improvement directions, from incremental to radical. Grounded in the
empirical findings in `experiments/` (OR-Tools CP-SAT 9.12).

## The core finding that frames everything
The model is a CP-SAT problem where every board row/column is constrained by `add_automaton`
to be a sequence of dictionary words. Experiments showed:
- CP-SAT **canonicalizes** the automaton in presolve, so the *representation* you feed it
  doesn't change model size — only **true DFA minimization** does (verified **6–8× smaller**
  model, and language-correct).
- But minimization is **expensive to compute** (naive ~O(n²); 40s for a 15k-word toy), which is
  why "minimized DAWGs didn't work" historically.
- Even minimized, **one** width-15 line over a small dict is ~38k booleans; a full board ×
  big dictionary makes the monolithic model fundamentally huge.

So: automaton tricks have a ceiling. Below, directions are grouped by how far they move from the
current design. The honest answer to "can we extend CP-SAT with a subsolver/primitive" is in
**Axis D**.

---

## Axis A — Keep CP-SAT, attack the dictionary primitive
**A1. Minimal-DFA via linear-time Revuz (highest-value, VERIFIED cheap).** The 6–8× model shrink
is real, correct, AND cheap: exp 05 builds the minimal row DFA for the **full 196k-word English
dictionary in 0.86s** in pure Python (Revuz: bucket trie nodes by height, merge equal signatures
bottom-up) — ~1000× faster than naive Moore for the identical result. No GPU / fast-language
rewrite / 24h needed. Action: replace `dawg.py:create_scrabble_automaton`'s positional-encoding
builder with the Revuz construction (keep the `(start, finals, edges)` return), cache per
dictionary. `dawg.py`'s existing `DAWG` is NOT minimal (its `FSANode.__eq__` keys children by raw
`id`) — either fix it or drop it for the Revuz path.

**A2. MDD-based dictionary constraint.** The modern primitive for "this sequence ∈ a huge set"
is a **Multi-valued Decision Diagram** with MDD propagation (Hadžić/Hoda/van Hoeve). It's the
minimal layered automaton *with* a stronger incremental propagator. CP-SAT has no native MDD
propagation; IBM **CP Optimizer** and research CP solvers do. Flag as "the right primitive,
wrong solver."

**A3. Length-bucketed / anchored automata.** Most real plays touch few cells. Build small
automata specialized to the actual open slots/anchors rather than the full-width line language.

## Axis B — Keep CP-SAT, attack the connectivity primitive
The depth/spanning-tree `single_component` (`solve.py:114`) is the stage-3 bottleneck.
**B1.** Use CP-SAT's native **`add_circuit`** (well-propagated) as a connected-subgraph gadget,
or **single-commodity flow** from the center (totally-unimodular ⇒ strong LP relaxation).
**B2.** **Lazy connectivity**: solve without it, flood-fill the solution, add a separator/no-good
cut, re-solve — reusing the existing `do_solve` generator. CP-SAT has no in-solve lazy
constraints, so this is an outer loop (loses warm starts) — see Axis D for solvers that don't.

## Axis C — Reformulate the model: slot-and-word + column generation
Drop "each line is a valid word-sequence via automaton." Use **placement variables** `(word w in
slot s)` — the classic crossword-as-ILP model. Intersections force shared cells to agree; tile
supply and scoring are linear. Then:
- **Column generation**: a pricing subproblem generates only high-value placements (a DAWG/GADDAG
  query), so you never materialize the whole dictionary as constraints.
- The **LP relaxation yields strong upper bounds** — directly serving goal B's "near-optimal +
  bounds" target.
- Board layout (which slots exist) becomes a branching decision. This is the OR-native radical
  pivot and sidesteps the per-line automaton wall entirely.

## Axis D — Extend the solver with a custom subsolver / primitive (your explicit question)
**Honest answer for OR-Tools CP-SAT: you cannot.** CP-SAT exposes **no user-defined propagators,
no lazy-clause hooks, and no in-solve constraint callbacks** in any of its APIs. Its internal
"subsolvers" (LNS workers, LP, feasibility pump, max-SAT core, etc.) are **configurable, not
authorable**. The only extension points are: choose among built-in globals (`automaton`, `table`,
`circuit`, `cumulative`…), `add_hint`, tune the worker portfolio, and the solve→add→re-solve loop.

To get a genuine **custom theory/propagator for the dictionary + connectivity**, move to a solver
that exposes the hook. Concrete options, roughly easiest→deepest:

- **MiniZinc front-end.** Free access to `regular`, `table`, and crucially the `tree` /
  `connected` / `subgraph` **globals** that natively handle the connectivity now hand-rolled as a
  depth encoding. Multiple backends (Chuffed, Gecode, CP-SAT, Gurobi) from one model — a fast way
  to bake off the connectivity primitive.
- **clingo (ASP).** Has a **Python `Propagator` API** (theory propagation) — implement a
  "valid-word-sequence" and/or connectivity propagator as a real subsolver, with native
  optimization. Crosswords are very natural in ASP.
- **Lazy Clause Generation CP — Chuffed / Geas / Gecode.** Author a custom global constraint
  (a DAWG-backed "regular-with-cost", or `connected`) *with explanations*. LCG is state-of-the-art
  for exactly this kind of structured combinatorial optimization.
- **SAT + IPASIR-UP (CaDiCaL).** The literal "extend a SAT solver with a subsolver": IPASIR-UP is
  a **user-propagator interface**. Implement a DPLL(T)-style **Scrabble theory solver** — given
  partial cell assignments, propagate dictionary/crossword consequences and return conflict
  clauses. Maximum control, most work.
- **ILP with lazy callbacks — Gurobi / SCIP.** Native **lazy constraints & callbacks** ⇒
  connectivity as TSP-style subtour-elimination cuts *inside* the search tree (the textbook
  scalable approach), plus strong LP bounds for goal B. A pragmatic, powerful pivot.
- **SMT — Z3.** Sequence/string theory + optimization (νZ); express dictionary membership via
  regex. More experimental for this scale.

## Axis E — Drop the general solver for the single move
The **max single move** is nearly enumerable: candidate main words are few, and a **GADDAG**
move-generator + Scrabble-specific score **upper bounds** in a domain-specific branch-and-bound
likely beats any general solver by orders of magnitude. (This is how recreational-math max-move
records were computed.) Use CP only to optimize residual choices, if at all. Probably the fastest
route to "bigger dictionary, single move."

## Axis F — The solitaire game: bilevel decomposition + bounds (matches "near-optimal + bounds")
A full game is too big monolithically. Decompose:
- **Outer**: choose the final board *fill* (a crossword construction using ≤ bag tiles) that
  maximizes scoring potential.
- **Inner**: given a fixed fill, find the optimal **play-order** — a sequencing problem where word
  multipliers score in the turn a covering tile is first placed, bingos reward 7-tile turns, and
  connectivity imposes precedence. This inner problem is its own ILP/DP.
- **Lower bound**: beam search / large-neighborhood search over plays (a strong solitaire
  heuristic). **Upper bound**: relax order+connectivity to an assignment/transportation problem
  (assign tiles to cells maximizing Σ tile-score × best-reachable-multiplier s.t. supply + each
  line valid) or Lagrangian relaxation. **Report the gap.**
- **Milestone**: full 7×7 small-dict game first (reuses the cheap automaton + cheap connectivity),
  then scale with bounds.

## Axis G — Learning-augmented (speculative)
ML-guided branching/value ordering; a GNN over the board graph to guide connectivity; RL/imitation
to propose strong plays as warm-start lower bounds. High-risk, potentially high-reward for the game.

---

## Recommended portfolio (what to actually try, ordered)
1. **POSINDEP construction** — adopt now; cheap, unblocks "can't build at width 15", zero model risk. *(verified)*
2. **Revuz minimal row DFA** — the verified 6–8× model shrink, linear-time (<1s for full English). Implement in `dawg.py`. *(verified win, verified cheap)*
3. **Slot-and-word + column-generation UPPER BOUND** — directly serves goal B and yields bounds; sidesteps the per-line wall.
4. **Connectivity bake-off** — MiniZinc `connected`/`tree` global OR Gurobi lazy cuts vs the CP-SAT depth encoding (Axis B/D).
5. **Domain-specific B&B for the single move** (Axis E) — likely the fastest path to the bigger-dictionary single move.
6. Longer horizon: a custom dictionary propagator (clingo / IPASIR-UP / Chuffed) if the general formulations plateau.
