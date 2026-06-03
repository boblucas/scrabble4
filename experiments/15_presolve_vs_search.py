"""
Experiment 15: in the FULL merged board model, is add_automaton (presolve) the
bottleneck, or is it the SEARCH? Decomposes one large-N merged stage-2 solve into:
  - Python build time (create_board incl. add_automaton + minimisation, word mapping, scoring)
  - CP-SAT presolve time (where add_automaton is expanded)  -> "Starting search" marker
  - whether/when search actually starts within the time limit

Earlier I measured ONE width-12 line in ISOLATION at 406s presolve; this tests whether
that cost survives in context (fixed main letters + columns + connectivity prune the rows).

Run: python experiments/15_presolve_vs_search.py [board] [mainword]
"""
import sys, time, re
sys.path.insert(0, '/home/bob/programming/scrabble4')
from ortools.sat.python import cp_model
from scrabble import construct_rules
import importlib.util
def _load(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
exp11=_load("exp11","/home/bob/programming/scrabble4/experiments/11_merge_connectivity_into_stage2.py")

def run(board, mainword, time_limit=240):
    rules = construct_rules('dutch', board)
    W = rules.W
    if not mainword:
        mainword = rules.alphabet.to_str(next(w for w in rules.words if len(w)==W))
    print(f"\n=== board {board} (W={W}), main='{mainword}' ===", flush=True)
    sp = [(x,0) for x in range(W)]
    t=time.time()
    model, cells3 = exp11.build_stage2(rules, mainword, sp, all_rows=True, connectivity=True)
    t_build = time.time()-t
    print(f"  Python build (create_board+add_automaton+minimise+wordmap+score): {t_build:.1f}s", flush=True)

    logs=[]
    s=cp_model.CpSolver()
    s.parameters.log_search_progress=True
    s.parameters.log_to_stdout=False
    s.parameters.num_search_workers=8
    s.parameters.max_time_in_seconds=time_limit
    s.log_callback=lambda m: logs.append(m)
    t=time.time(); res=s.Solve(model); t_solve=time.time()-t
    txt="\n".join(logs)
    # parse phase markers from the CP-SAT log
    m_pre = re.search(r"Starting presolve at ([\d.]+)s", txt)
    m_search = re.search(r"Starting (?:search|Search) at ([\d.]+)s", txt)
    m_bool = re.search(r"'new_bool: automaton expansion' was applied ([\d']+) times", txt)
    pv = re.search(r"PresolvedNumVariables:\s*([\d']+)", txt)
    status={cp_model.OPTIMAL:'OPTIMAL',cp_model.FEASIBLE:'FEASIBLE',cp_model.INFEASIBLE:'INFEASIBLE',cp_model.UNKNOWN:'UNKNOWN(timeout)'}.get(res,str(res))
    print(f"  CP-SAT: presolve_starts_at={m_pre.group(1) if m_pre else '?'}s  "
          f"search_starts_at={m_search.group(1)+'s' if m_search else 'NOT REACHED within limit'}", flush=True)
    print(f"  automaton_expansion_bools={m_bool.group(1) if m_bool else '?'}  presolved_bools={pv.group(1) if pv else '?'}", flush=True)
    print(f"  total Solve() wall={t_solve:.1f}s (limit {time_limit}s)  status={status}", flush=True)
    if m_search:
        presolve_s=float(m_search.group(1))
        print(f"  => PRESOLVE took ~{presolve_s:.1f}s ; SEARCH got ~{t_solve-presolve_s:.1f}s -> "
              f"{'PRESOLVE-dominated (add_automaton)' if presolve_s > t_solve*0.5 else 'SEARCH-dominated'}", flush=True)
    else:
        print(f"  => search never started -> presolve (add_automaton) IS the bottleneck at this N", flush=True)

if __name__=='__main__':
    board = sys.argv[1] if len(sys.argv)>1 else '9'
    mw = sys.argv[2] if len(sys.argv)>2 else None
    run(board, mw)
