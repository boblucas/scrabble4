# Automaton ↔ CP-SAT verification experiments

Goal: before planning an automaton rewrite, empirically settle whether a
position-independent and/or **minimized** DFA actually works with OR-Tools CP-SAT
`add_automaton`, and what it does to model size — because minimized DAWGs were
remembered as "not working." OR-Tools version: **9.12.4544**. Run with `./.venv/bin/python`.

## Constructions compared
- **CURRENT**  — `create_scrabble_automaton(automaton_words_from_list(words, n))`, the
  positional-encoding DAWG in `dawg.py` (known-good baseline). Acyclic, fixed length `n`.
- **POSINDEP** — a small position-INDEPENDENT row DFA built from a plain trie. Cyclic
  (`(word (0+ word)*)?`), accepts any length. (`experiments/01_…:posindep_automaton`)
- **POSINDEP_dawg** — same, but built from `dawg.py`'s `DAWG` class instead of a trie.
- **MINIMIZED** — POSINDEP put through Moore DFA minimization (`experiments/01_…:minimize_dfa`).

## Experiments
| file | question | how |
|---|---|---|
| `01_verify_add_automaton.py` | Does `add_automaton` accept EXACTLY the intended language? | tiny dict, full enumeration of all accepted strings vs brute-force ground truth |
| `02_model_expansion.py` | How big is the CP-SAT model AFTER `add_automaton` unrolls it? | parse presolve log (`stop_after_presolve`), report `automaton_expansion` bools |
| `03_dawg_based_minimal.py` | Can we get the minimal model CHEAPLY from `dawg.py`'s DAWG? | build from DAWG, measure size + CP-SAT model; toy exact + all-strings product equiv |
| `04_minimization_is_correct.py` | Is the 6–8× reduction REAL or a lossy-minimization artifact? | exact deterministic-DFA equivalence (product+BFS) base vs minimized, at scale |

Results artifact: `experiments/results/02_model_expansion.txt`.

## Findings (verified)

1. **`add_automaton` works fine with position-independent AND minimized DFAs.** Exp 01:
   all three constructions accept exactly the ground-truth language on the toy dict.
   The remembered failure is **not** a CP-SAT correctness/determinism problem.

2. **CP-SAT canonicalizes during presolve — input representation does NOT change model size.**
   Exp 02 (english≤5): CURRENT (69k–232k states) and POSINDEP (20k states) expand to the
   *identical* `automaton_expansion` bool count at every width (e.g. **237,627** at N=15).
   So feeding CP-SAT a smaller (but non-minimal) automaton buys nothing at solve time.

3. **POSINDEP only wins on BUILD cost — but massively.** Build time 0.07s vs CURRENT's
   4.9s (N=7) → 25.5s (N=15), and CURRENT does not finish building at N=15 for full English.
   So POSINDEP is a safe, strict win for the *construction* bottleneck ("can't build at width
   15"), with zero effect on the resulting model.

4. **A truly MINIMIZED row DFA gives a ~6–8× smaller CP-SAT model — and it is CORRECT.**
   Exp 02/04 (english≤5, N=15): 237,627 → **38,007** expansion bools; minimal DFA = 2,653
   states vs 20,349 trie states. Exp 04 proves language-equivalence via exact all-strings
   product+BFS (`EQUIVALENT` for toy, english≤4, english≤5). CP-SAT's presolve does NOT
   reach this itself — pre-minimization is genuinely additive.

5. **The catch = the real reason minimized DAWGs "didn't work": minimization SPEED.**
   Naive Moore minimization is ~O(n²): 3.7s for english≤4 (6.7k states), **40s** for english≤5
   (20k states). It would never scale to 197k / 1.1M-word dictionaries. Building the row DFA
   from `dawg.py`'s `DAWG` does NOT help (exp 03: same 20,349 states, same 237k model) because
   that DAWG isn't truly minimal — its `FSANode.__eq__` keys children by `id`, not by minimized
   representative, so suffix-merging mostly fails.

6. **The deeper wall:** even the best case is ~38k booleans for ONE width-15 line over a small
   15k-word dict. A full 15×15 board has 30 such lines (+ intersections + scoring + connectivity),
   and per-line expansion grows with dictionary size. The monolithic CP-SAT model is therefore
   fundamentally large for big dictionaries regardless of automaton cleverness.

## Implication
- POSINDEP construction → adopt (cheap, unblocks build, zero risk).
- Fast minimal-DFA (proper **Hopcroft O(n log n)** or **Brzozowski**, not naive Moore) → chase
  the verified 6–8× model reduction; the only open question is whether minimization can be made
  cheap enough on real dictionaries (one-time, cacheable).
- For big dictionaries / full boards, the per-line wall motivates changing the *primitive*,
  *formulation*, or *solver* — see `../RESEARCH_DIRECTIONS.md`.
