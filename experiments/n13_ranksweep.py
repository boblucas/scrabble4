"""N=13 center-constrained RANKED witness sweep (smart, ratcheting).

Walk the analytic candidate ranking (experiments/results/n13/rank.txt, best optimistic-total first).
For each main word, place it left-block (scoring cols {0..6} => bingo) and run xfill --emit (via
n13_witness.py) with a length-vector that makes the two x3 columns (0 and center-6) long for high
vertical.  n13_witness now captures the TO incumbent too, so even hard configs yield a verified
board.  The VERTICAL floor passed to xfill = best_total - main(word): as best_total climbs, weak
candidates get a high floor and are rejected fast (xfill root-prunes infeasibles in nodes=1).

Pure compute (no LLM).  Run detached + niced.  Logs every verified improvement.

Usage:
  python experiments/n13_ranksweep.py --rank experiments/results/n13/rank.txt \
      --start-total 366 --wall 20 --max-words 1500 --out-prefix experiments/results/n13/rank_sweep
"""
import sys, os, json, subprocess, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NW = os.path.join(ROOT, 'experiments', 'n13_witness.py')
PY = sys.executable

# length-vectors to try per word (over scoring cols 0..6; col6=center must be >=7).
# x3 columns are 0 and 6 -> make them long for high vertical; keep variety modest to bound cost.
LVECS = ["8,2,2,2,2,2,8", "8,2,2,2,2,2,7", "8,3,2,2,2,3,8"]


def parse_rank(path):
    out = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        # format: opt_total main vert word
        try:
            opt, main, vert, word = int(parts[0]), int(parts[1]), int(parts[2]), parts[3]
        except Exception:
            continue
        if len(word) == 13:
            out.append((opt, main, word))
    return out


def left_block_turn(word):
    return ''.join(c.upper() if i < 7 else c.lower() for i, c in enumerate(word))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rank', default='experiments/results/n13/rank.txt')
    ap.add_argument('--start-total', type=int, default=366)
    ap.add_argument('--wall', type=float, default=20.0)
    ap.add_argument('--max-words', type=int, default=1500)
    ap.add_argument('--out-prefix', default='experiments/results/n13/rank_sweep')
    a = ap.parse_args()

    cands = parse_rank(a.rank)
    best_total = a.start_total
    best_file = None
    log = a.out_prefix + '.log'
    os.makedirs(os.path.dirname(log), exist_ok=True)

    def emit(msg):
        with open(log, 'a') as f:
            f.write(msg + '\n')
        print(msg, flush=True)

    emit(f"# N=13 ranked sweep: {len(cands)} candidates, start_total={best_total}, "
         f"wall={a.wall}, lvecs={LVECS}, max_words={a.max_words}")

    for n, (opt, main, word) in enumerate(cands[:a.max_words]):
        if opt <= best_total:
            emit(f"# STOP at #{n}: optimistic opt={opt} <= best_total={best_total} (rest can't beat it)")
            break
        turn = left_block_turn(word)
        floor = max(0, best_total - main)            # vertical needed to beat current best
        got = None
        for lvec in LVECS:
            cand = a.out_prefix + '_cand.json'
            cmd = [PY, NW, '--main', word, '--turn', turn, '--lvec', lvec,
                   '--floor', str(floor), '--wall', str(a.wall), '--out', cand, '--name', 'rk']
            try:
                p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=a.wall + 90)
            except subprocess.TimeoutExpired:
                continue
            txt = p.stdout + p.stderr
            if 'WITNESS OK' in txt:
                try:
                    d = json.load(open(cand)); tot = int(d.get('claimed_total', 0))
                except Exception:
                    continue
                if tot > best_total:
                    best_total = tot
                    keep = a.out_prefix + f'_best_{tot}.json'
                    json.dump(d, open(keep, 'w'), indent=1)
                    best_file = keep
                    got = (tot, lvec)
                    floor = max(0, best_total - main)   # raise floor for the remaining lvecs of this word
        if got:
            emit(f"NEWBEST #{n} word={word} main={main} -> TOTAL={got[0]} lvec={got[1]}  saved {best_file}")
        else:
            emit(f"  #{n} word={word} main={main} opt={opt} -> none (floor was {max(0,a.start_total-main)})")

    emit(f"# DONE best_total={best_total} file={best_file}")


if __name__ == '__main__':
    main()
