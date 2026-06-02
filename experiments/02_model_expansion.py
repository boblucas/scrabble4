"""
Experiment 02: How big is the CP-SAT model AFTER add_automaton unrolls it?

The hypothesis (explaining why position-independent / minimized DAWGs "don't work"):
add_automaton unrolls the automaton across N+1 phases. The CURRENT layered automaton
has position-specific states (state s only live at one phase -> presolve prunes the rest),
whereas a POSITION-INDEPENDENT automaton has every state live at every phase, so the
expanded model can be N x larger even though the automaton itself is smaller.

We measure, per (construction, dict, width):
  - automaton build time, #states, #edges
  - CP-SAT presolved model size (#Booleans / #constraints) parsed from the solver log

Run: python experiments/02_model_expansion.py
"""
import sys, time, re
sys.path.insert(0, '/home/bob/programming/scrabble4')
import numpy as np
from ortools.sat.python import cp_model
from dawg import create_scrabble_automaton, automaton_words_from_list

import importlib.util
spec = importlib.util.spec_from_file_location("exp01", "/home/bob/programming/scrabble4/experiments/01_verify_add_automaton.py")
exp01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(exp01)
posindep_automaton = exp01.posindep_automaton


def load_english(max_len):
    words = open('/home/bob/programming/scrabble4/data/words/english').read().lower().split('\n')
    abc = 'abcdefghijklmnopqrstuvwxyz'
    cba = {c: i + 1 for i, c in enumerate(abc)}
    out = []
    for w in words:
        if w and 1 <= len(w) <= max_len and all(c in cba for c in w):
            out.append(tuple(cba[c] for c in w))
    # single letters count as words in this solver (scrabble.py adds set(abc))
    out += [(cba[c],) for c in abc]
    return sorted(set(out)), 26


def automaton_size(auto):
    start, finals, edges = auto
    states = {int(a) for a, _, _ in edges} | {int(b) for _, _, b in edges} | {int(start)} | {int(f) for f in finals}
    return len(states), len(edges)


def presolve_stats(auto, n, K, time_limit=10.0):
    start, finals, edges = auto
    edges = [(int(a), int(c), int(b)) for a, c, b in edges]
    finals = [int(f) for f in finals]
    model = cp_model.CpModel()
    xs = [model.new_int_var(0, K, f'x{i}') for i in range(n)]
    try:
        model.add_automaton(xs, int(start), finals, edges)
    except Exception as e:
        return None, {"error": f"{type(e).__name__}: {e}"}
    logs = []
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False          # capture via callback only
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = time_limit
    try:
        solver.parameters.stop_after_presolve = True  # we only want expansion size
    except Exception:
        pass
    solver.log_callback = lambda s: logs.append(s)
    t0 = time.time()
    solver.Solve(model)
    dt = time.time() - t0
    text = '\n'.join(logs)
    stats = {"presolve_s": round(dt, 2)}
    m = re.search(r"PresolvedNumVariables:\s*([\d']+)", text)
    if m: stats["presolved_vars"] = int(m.group(1).replace("'", ""))
    m = re.search(r"PresolvedNumConstraints:\s*([\d']+)", text)
    if m: stats["presolved_constraints"] = int(m.group(1).replace("'", ""))
    m = re.search(r"PresolvedNumTerms:\s*([\d']+)", text)
    if m: stats["presolved_terms"] = int(m.group(1).replace("'", ""))
    m = re.search(r"'new_bool: automaton expansion' was applied ([\d']+) times", text)
    if m: stats["automaton_expansion_bools"] = int(m.group(1).replace("'", ""))
    return text, stats


CASES = [
    ("english<=5", lambda: load_english(5)),
    ("english<=7", lambda: load_english(7)),
]
WIDTHS = [7, 11, 15]


def emit(msg, fh):
    print(msg, flush=True)
    fh.write(msg + "\n"); fh.flush()

def one(label, build_fn, n, K, fh, build_budget=120):
    t0 = time.time()
    try:
        auto = build_fn()
    except Exception as ex:
        emit(f"  {label:9}: BUILD FAILED: {type(ex).__name__}: {ex}", fh); return
    tb = time.time() - t0
    s, e = automaton_size(auto)
    text, stats = presolve_stats(auto, n, K)
    if "error" in stats:
        emit(f"  {label:9}: build={tb:6.1f}s states={s:>8} edges={e:>8}  add_automaton {stats['error']}", fh); return
    pv = stats.get("presolved_vars", "?"); pc = stats.get("presolved_constraints", "?")
    pt = stats.get("presolved_terms", "?"); ax = stats.get("automaton_expansion_bools", "?")
    emit(f"  {label:9}: build={tb:6.1f}s states={s:>8} edges={e:>8}  =>  presolved_bools={pv} "
         f"constraints={pc} terms={pt} (automaton_expansion_bools={ax}, presolve={stats.get('presolve_s')}s)", fh)

def run_case(name, words, K, fh):
    emit(f"\n========== dict={name} ({len(words)} words) ==========", fh)
    for n in WIDTHS:
        emit(f"--- width N={n} ---", fh)
        one("CURRENT",  lambda: create_scrabble_automaton(automaton_words_from_list(words, n)), n, K, fh)
        one("POSINDEP", lambda: posindep_automaton(words, minimize=False), n, K, fh)
        one("MINIMIZED",lambda: posindep_automaton(words, minimize=True),  n, K, fh)


if __name__ == '__main__':
    import os
    os.makedirs('/home/bob/programming/scrabble4/experiments/results', exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    with open('/home/bob/programming/scrabble4/experiments/results/02_model_expansion.txt', 'w') as fh:
        emit("Experiment 02: CP-SAT model size after add_automaton unrolling (OR-Tools 9.12)", fh)
        for name, loader in CASES:
            if only and only not in name:
                continue
            words, K = loader()
            run_case(name, words, K, fh)
