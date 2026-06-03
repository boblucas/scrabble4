"""
Experiment 18: does extra_subsolvers=["probing_max_lp"]*N actually spawn N diversified
bound-provers, and does it help close the objective bound faster?

Builds the board-9 rugbyclub merged model once, then solves it with cores=24 and
extra_probing in {0,4,8}, time-limited. Reports: how many probing_max_lp workers were
launched (from the CP-SAT worker list), final status/obj/bound, and time-to-OPTIMAL.

Run: python experiments/18_extra_probing.py
"""
import sys, time, re
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules
import importlib.util
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp16 = _load("exp16", "/home/bob/programming/scrabble4/experiments/16_flow_vs_depth_connectivity.py")

def run(model, cores, extra_probing, tl):
    logs = []
    s = cp_model.CpSolver()
    s.parameters.log_search_progress = True
    s.parameters.log_to_stdout = False
    s.parameters.num_search_workers = cores
    s.parameters.optimize_with_core = False
    s.parameters.max_presolve_iterations = 1
    if extra_probing:
        s.parameters.extra_subsolvers.extend(["probing_max_lp"] * extra_probing)
    s.parameters.max_time_in_seconds = tl
    t = time.time(); res = s.Solve(model); wall = time.time() - t
    txt = "\n".join(logs := getattr(s, "_logs", logs))
    return s, res, wall

def run2(model, cores, extra_probing, tl):
    logs = []
    s = cp_model.CpSolver()
    s.parameters.log_search_progress = True
    s.parameters.log_to_stdout = False
    s.parameters.num_search_workers = cores
    s.parameters.optimize_with_core = False
    s.parameters.max_presolve_iterations = 1
    if extra_probing:
        s.parameters.extra_subsolvers.extend(["probing_max_lp"] * extra_probing)
    s.parameters.max_time_in_seconds = tl
    s.log_callback = lambda m: logs.append(m)
    t = time.time(); res = s.Solve(model); wall = time.time() - t
    txt = "\n".join(logs)
    # count probing_max_lp workers from the subsolver list line(s)
    m = re.search(r"(\d+)\s+full subsolvers:\s*\[([^\]]*)\]", txt)
    n_probe = txt.count("'probing_max_lp")  # appears once per launched worker in the list
    full_list = m.group(2) if m else "?"
    # time the objective bound was first proven OPTIMAL
    opt_time = None
    mm = re.search(r"#Done\s+([\d.]+)s", txt)
    st = {cp_model.OPTIMAL:'OPTIMAL', cp_model.FEASIBLE:'FEASIBLE', cp_model.INFEASIBLE:'INFEASIBLE',
          cp_model.UNKNOWN:'timeout'}.get(res, str(res))
    obj = s.objective_value if res in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    print(f"  extra_probing={extra_probing}: status={st} wall={wall:.1f}s obj={obj} "
          f"bound={s.best_objective_bound:.0f} probing_max_lp_in_list~={n_probe}")
    print(f"      full subsolver list: [{full_list}]")
    return st, obj, s.best_objective_bound, wall

if __name__ == '__main__':
    TL = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    rules = construct_rules('dutch', '9')
    sp = [(x, 0) for x in range(rules.W)]
    print("building board-9 rugbyclub merged model...", flush=True)
    model, _ = exp16.build_merged(rules, 'rugbyclub', sp, 'depth')
    print(f"solving with cores=24, time_limit={TL}s each:\n", flush=True)
    for ep in [0, 4, 8]:
        run2(model, 24, ep, TL)
