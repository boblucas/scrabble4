"""N=13 SPREAD feasibility survey -- ROBUST (subprocess-per-config, hard OS wall).

The decisive 'is 586 optimal?' test.  Because capturing the three x3 word-columns stacks the main-word
multiplier to x27, almost ANY feasible 3-x3 board scores > 586 (27*sum+50 > 586 needs letter-sum > 20,
which nearly every 13-letter word clears).  So the optimum question reduces to: does ANY feasible
3-x3 board exist?  -> a pure feasibility hunt with CP-SAT (the global-connectivity reasoner).

xfill explodes on spreads; CP-SAT decides many in ~3s but STALLS (model construction) on some, past
any solver cap.  So each (word,mask) is decided in its OWN subprocess with a hard wall: a stuck one
is killed -> TIMEOUT, never blocking the survey.

  worker:  python n13_spread_survey.py --one WORD MASKCSV         -> prints 'VERDICT SAT|UNSAT|UNKNOWN'
  driver:  python n13_spread_survey.py [--top N] [--wall 75] [--out ...]

A SAT hit => total >= 27*letter_sum+50 >> 586 => the optimum is a spread board (pivot to finding the
best one).  All UNSAT/TIMEOUT over a broad sample => strong evidence the left-block region (~586) is
optimal; the TIMEOUTs are the residual hard set to settle separately.
"""
import sys, os, time, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'experiments'))

# 3-x3 masks: 7 scoring cols all including {0,6,12} (col6 = center). x3 cols long for big verticals.
MASKS = [
    (0, 1, 2, 6, 10, 11, 12),
    (0, 1, 3, 6, 9, 11, 12),
    (0, 1, 5, 6, 7, 11, 12),
]


def lvec_for(mask):
    return {x: (8 if x in (0, 12) else 7 if x == 6 else 2) for x in mask}


def run_one(word, mask):
    import xtest
    Lvec = lvec_for(mask)
    turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(word))
    inst, meta = xtest.build_instance('13', word, turn, Lvec, scale=True, reserve=1)
    if inst is None:
        print("VERDICT NOCAND"); return
    st = xtest.cpsat_decide(meta, cap=10 ** 9)   # OS wall (subprocess timeout) is the real bound
    print("VERDICT " + str(st))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--one', nargs=2, metavar=('WORD', 'MASKCSV'))
    ap.add_argument('--rank', default='experiments/results/n13/rank_feas.txt')
    ap.add_argument('--top', type=int, default=80)
    ap.add_argument('--skip', type=int, default=0, help='skip the first N ranked words (sample a deeper band)')
    ap.add_argument('--wall', type=float, default=75.0)
    ap.add_argument('--out', default='experiments/results/n13/spread_survey.log')
    a = ap.parse_args()

    if a.one:
        word, maskcsv = a.one
        run_one(word, tuple(int(x) for x in maskcsv.split(',')))
        return

    words = []
    allw = []
    for line in open(os.path.join(ROOT, a.rank)):
        p = line.split()
        if len(p) == 4 and p[0].isdigit():
            allw.append((int(p[1]), p[3]))   # (main-proxy from rank, word)
    words = allw[a.skip:a.skip + a.top]

    logf = open(os.path.join(ROOT, a.out), 'w')
    def emit(m):
        logf.write(m + '\n'); logf.flush(); print(m, flush=True)

    emit(f"# N=13 spread survey (subprocess, hard wall {a.wall}s): {len(words)} words x {len(MASKS)} "
         f"3-x3 masks. Any SAT => optimum > 586.")
    hits = []
    for _mp, word in words:
        for mask in MASKS:
            maskcsv = ','.join(map(str, mask))
            t0 = time.time()
            try:
                r = subprocess.run([sys.executable, os.path.abspath(__file__), '--one', word, maskcsv],
                                   cwd=ROOT, capture_output=True, text=True, timeout=a.wall,
                                   env={**os.environ, 'CPSAT_WORKERS': os.environ.get('CPSAT_WORKERS', '8')})
                out = (r.stdout + r.stderr)
                v = next((l.split()[1] for l in out.splitlines() if l.startswith('VERDICT')), 'NOVERDICT')
            except subprocess.TimeoutExpired:
                v = 'TIMEOUT'
            dt = time.time() - t0
            line = f"{v:9s} {word} mask={mask} ({dt:.0f}s)"
            if v == 'SAT':
                hits.append((word, mask)); emit("SAT-HIT  " + line)
            else:
                emit("  " + line)
    emit(f"# DONE. SAT hits: {len(hits)}")
    for word, mask in hits:
        emit(f"#   FEASIBLE SPREAD: {word} mask={mask}  => total > 586, optimum is a spread board")
    if not hits:
        emit("# NO feasible 3-x3 spread in sample => strong evidence left-block region (~586) is optimal "
             "(residual = any TIMEOUT configs).")


if __name__ == '__main__':
    main()
