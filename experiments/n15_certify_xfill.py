"""N=15 SOUND certification of a threat word's true single-turn max <= LB, via the xfill engine.

For each LEGAL mask of the word (n15_greedy_lb.candidate_masks; mask contains {0,7,14}, pre-placed
row-0 runs spell dict words), invoke 35_certify.py build with the per-mask VERTICAL floor

    vfloor(word, mask) = LB - main_const(word, mask)

under --center --no-scale (full Dutch bag + 2 blanks).  reserve is OMITTED (reserve=0): a looser
bag than the true reserve=1, so an LE here is a SOUND over-approximation (LE under reserve=0 =>
LE under reserve=1; fewer tiles can only lower the max).  35_certify enumerates the full band of
length-vectors whose optimistic per-column-best-gross UB exceeds vfloor, discharges each via
GEOM (Steiner bridge LB > budget) / KNAP (tile-aware CP-SAT bound) / LE (natural xfill completion),
and refuses to certify on any TO.  We then run `check` on each mask's ledger.

VERDICT per word:
  CERTIFIED <= LB   -- every legal mask's ledger checks CERTIFIED (all band vectors sound LE/GEOM/KNAP)
  NEW-LB            -- some mask's build printed REFUTED (a board > LB) -> re-witness, raise LB
  OPEN             -- some mask's band has a TO hole (xfill could not close a slice in the wall)

Single sequential process (process-kill safety: NO parallelism beyond 35_certify's internal procs;
no group kills / setsid).  Each mask is one 35_certify subprocess run sequentially.
"""
import sys, os, json, time, subprocess, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from n15_greedy_lb import candidate_masks
import n15_xfill_push as P

ROOT = '/home/bob/programming/scrabble4'
CERT35 = f'{ROOT}/experiments/35_certify.py'


def turn_str(w, mask):
    return ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(w))


def certify_mask(w, mask, lb, wall, wall_a, procs):
    """Build + check one mask's ledger.  Returns (status, info) where status in
    {CERTIFIED, OPEN, REFUTED, NOBAND}."""
    mc = P.main_const(w, mask)
    vfloor = lb - mc
    if vfloor < 0:
        # main alone exceeds LB?  impossible for these words (main <= 1724 < 1952) but guard anyway.
        return ('REFUTED', {'reason': f'main_const {mc} > LB {lb}'})
    name = f'n15cert_{w}_{"_".join(map(str, mask))}'
    turn = turn_str(w, mask)
    env = dict(os.environ); env.pop('MAXNODES', None)
    bcmd = ['python', CERT35, 'build', '--board', '15', '--main', w, '--turn', turn,
            '--floor', str(vfloor), '--center', '--no-scale', '--name', name,
            '--wall', str(wall), '--wall-a', str(wall_a), '--procs', str(procs)]
    t0 = time.time()
    bp = subprocess.run(bcmd, capture_output=True, text=True, env=env, cwd=ROOT,
                        timeout=wall * 50 + 3600)
    out = bp.stdout + bp.stderr
    if 'REFUTED' in out:
        # surface the best witnessed value
        best = None
        for line in out.splitlines():
            if 'best witnessed' in line:
                best = line.strip()
        return ('REFUTED', {'vfloor': vfloor, 'mc': mc, 'detail': best or out[-400:]})
    ledger = f'{ROOT}/experiments/results/certs/{name}/ledger.json'
    if not os.path.exists(ledger):
        return ('OPEN', {'reason': 'no ledger', 'tail': out[-400:]})
    cp = subprocess.run(['python', CERT35, 'check', ledger, '--rerun-sample', '2'],
                        capture_output=True, text=True, env=env, cwd=ROOT, timeout=4000)
    cout = cp.stdout + cp.stderr
    band = next((l for l in out.splitlines() if l.startswith('band=')), '')
    dt = time.time() - t0
    if 'CERTIFIED' in cout.splitlines()[-1] if cout.splitlines() else False:
        return ('CERTIFIED', {'vfloor': vfloor, 'mc': mc, 'band': band, 'dt': f'{dt:.0f}s'})
    return ('OPEN', {'vfloor': vfloor, 'mc': mc, 'band': band, 'dt': f'{dt:.0f}s',
                     'check_tail': cout[-500:]})


def certify_word(w, lb, wall, wall_a, procs, masks_limit):
    masks = candidate_masks(w, limit=masks_limit)
    print(f"## {w}: {len(masks)} legal masks (limit {masks_limit}), LB={lb}", flush=True)
    results = []
    word_status = 'CERTIFIED'
    for i, mask in enumerate(masks):
        st, info = certify_mask(w, mask, lb, wall, wall_a, procs)
        print(f"  [{i+1}/{len(masks)}] mask={mask} -> {st} {info}", flush=True)
        results.append((mask, st, info))
        if st == 'REFUTED':
            word_status = 'NEW-LB'
            print(f"  !!! {w} mask={mask} REFUTES LB {lb}: {info}", flush=True)
            break
        if st == 'OPEN':
            word_status = 'OPEN'    # keep going to learn which masks are open, but word is OPEN
    print(f"## {w}: WORD VERDICT = {word_status}", flush=True)
    return word_status, results


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lb', type=int, default=1952)
    ap.add_argument('--wall', type=int, default=120)
    ap.add_argument('--wall-a', type=float, default=2.0)
    ap.add_argument('--procs', type=int, default=6)
    ap.add_argument('--masks', type=int, default=30)
    ap.add_argument('--words', type=str, required=True, help='comma-separated threat words')
    a = ap.parse_args()
    summary = {}
    for w in a.words.split(','):
        st, _ = certify_word(w, a.lb, a.wall, a.wall_a, a.procs, a.masks)
        summary[w] = st
    print("=== SUMMARY ===", flush=True)
    for w, st in summary.items():
        print(f"  {w}: {st}", flush=True)
