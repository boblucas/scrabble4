#!/usr/bin/env python3
"""STRETCH: one real geschenkcheques mask under --varmax + the varmax-aware knap UB.

Builds ONE mask base (scale=False, reserve=1 -- the real N=15 rules) in a FRESH scratch dir and runs
`xfill --varmax BASE --maxscore VFLOOR` once, vs the per-vector sweep size it replaces.  Does NOT
touch the running proof job's dir.  Reports the varmax verdict + nodes/time at a chosen KNAPCOLS cap."""
import sys, os, time, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'experiments'))
import xtest
from n15_greedy_lb import candidate_masks
import n15_xfill_push as P
BIN = os.path.join(ROOT, 'experiments/xfill_rs/target/release/xfill')
SCR = os.path.join(ROOT, 'experiments/xfill_varmax_knap_scratch')
os.makedirs(SCR, exist_ok=True)

W = 'geschenkcheques'
LB = int(sys.argv[sys.argv.index('--lb') + 1]) if '--lb' in sys.argv else 1955
wall = float(sys.argv[sys.argv.index('--wall') + 1]) if '--wall' in sys.argv else 60.0
mi = int(sys.argv[sys.argv.index('--mask') + 1]) if '--mask' in sys.argv else 0
knapcols = sys.argv[sys.argv.index('--knapcols') + 1] if '--knapcols' in sys.argv else None

masks = candidate_masks(W, limit=200)
mask = masks[mi]
mc = P.main_const(W, mask)
vfloor = LB - mc
turn = ''.join(c.upper() if i in mask else c.lower() for i, c in enumerate(W))
base = xtest.build_base('15', W, turn, scale=False, reserve=1)
bpath = os.path.join(SCR, f'geschenk_mask{mi}.txt')
xtest.dump_base(base, bpath)

# how many length-vectors the fixed sweep would enumerate for this mask (product of #lengths/col)
prod = 1
for col in base['cols']:
    prod *= max(1, len(col['bylen']))
print(f"mask#{mi}={mask}  main_const={mc}  vfloor={vfloor}  scoring_cols={[c['col'] for c in base['cols']]}")
print(f"lengths/col={[sorted(c['bylen']) for c in base['cols']]}")
print(f"fixed sweep would enumerate ~{prod} length-vectors; varmax = ONE search")

e = dict(os.environ)
e['WALL'] = str(wall)
if knapcols is not None:
    e['KNAPCOLS'] = knapcols
t0 = time.time()
r = subprocess.run([BIN, '--varmax', bpath, '--maxscore', str(vfloor)],
                   capture_output=True, text=True, env=e)
dt = time.time() - t0
verd = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
knap = [l for l in r.stderr.splitlines() if l.startswith('knap-ub:')]
print(f"varmax (KNAPCOLS={knapcols or 'all'}): {verd}   {knap[0] if knap else ''}   real_wall={dt:.1f}s")
