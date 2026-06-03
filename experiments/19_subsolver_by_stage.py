"""
Experiment 19: which subsolvers do the work in each pipeline stage?
Parses a full CP-SAT log (multiple concatenated solves) into blocks and, per block,
reports: presolved size, whether it's an OPTIMISATION (has objective) or FEASIBILITY
solve, status, and the top subsolvers that (a) found solutions and (b) improved the bound.

Stages: stage-1 = horizontal main-word (optimise), stage-2 = vertical+connectivity
(optimise), stage-3 = connectivity (feasibility, no objective).

Run: python experiments/19_subsolver_by_stage.py [logfile]
"""
import sys, re
from collections import Counter

LOG = sys.argv[1] if len(sys.argv) > 1 else "experiments/results/turns/dutch11_noblank.fulllog"
text = open(LOG, errors="ignore").read()
blocks = text.split("Starting CP-SAT solver")
print(f"{LOG}: {len(blocks)-1} solve blocks\n")

def tag(line):
    # subsolver name = token right after the "next:[...]" bracket (strip trailing "(...)")
    m = re.search(r"\]\s+([a-z0-9_]+)", line)
    return m.group(1) if m else "?"

for i, b in enumerate(blocks[1:], 1):
    if i > 8: break
    nvars = re.search(r"#Variables:\s*([\d']+)", b)
    nvars = nvars.group(1) if nvars else "?"
    has_obj = "objective:" in b and not re.search(r"objective:\s*NA", b)
    obj = re.search(r"\nobjective:\s*([\-\d.]+)", b)
    bound = re.search(r"\nbest_bound:\s*([\-\d.]+)", b)
    status = re.search(r"\nstatus:\s*(\w+)", b)
    sols = Counter(tag(l) for l in b.splitlines() if re.match(r"^#\d+\s", l))
    bounds = Counter(tag(l) for l in b.splitlines() if l.startswith("#Bound"))
    kind = "OPTIMISE" if has_obj else "FEASIBILITY"
    print(f"block {i}: {kind:11} vars={nvars:>8} status={status.group(1) if status else '?':12} "
          f"obj={obj.group(1) if obj else 'NA':>6} bound={bound.group(1) if bound else 'NA':>8}")
    if sols:
        print(f"   solutions found by : {dict(sols.most_common(5))}")
    if bounds:
        print(f"   bound improved by  : {dict(bounds.most_common(6))}")
    print()
