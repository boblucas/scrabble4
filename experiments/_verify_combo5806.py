"""Reconstruct geschenkcheques mask (0,3,7,8,11,12,14) combo id 5806 (the oracle's surviving SAT,
gross 286 -> total 2010) and run the FIXED witness_check. If it passes -> a real new LB 2010.
If it fails -> the oracle's feasibility model is an over-permissive relaxation (spurious SAT)."""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
from collections import Counter
import n15_twolevel as T
from scrabble import construct_rules

W = 'geschenkcheques'; MASK = (0, 3, 7, 8, 11, 12, 14)
r = construct_rules('dutch', '15')
mc = T.main_const(W, MASK)
vfloor = 2007 - mc
mt = r.alphabet.to_tup(W)
avail = Counter({code: r.counts[code] - Counter(mt[c] for c in MASK)[code] for code in r.counts})
print(f"main_const={mc} vfloor={vfloor}")
res = T.enumerate_above_fast(W, MASK, avail, vfloor, collect_top=50_000_000)
combos = res['top']
print(f"combos>vfloor = {res['count']} (capped={res['capped']}), collected={len(combos)}")
cid = 5806
if cid >= len(combos):
    print(f"!! id {cid} out of range ({len(combos)})"); sys.exit(1)
gross, combo = combos[cid]
total = mc + gross
print(f"combo id {cid}: gross={gross} -> total={total}")
print("re-running oracle_feasible (exact CP-SAT, long cap)...")
st, grid = T.oracle_feasible(W, MASK, combo, cap=1200.0)
print(f"oracle verdict = {st}")
if st != 'SAT' or grid is None:
    print("NOT SAT on re-run (was a timeout-race or nondeterministic) -> not a board"); sys.exit(0)
ok, vt, rep = T.verify_board(W, MASK, grid)
print(f"FIXED witness_check: ok={ok} verified_total={vt}")
if ok:
    print(f"*** REAL NEW LB = {vt} (combo 5806) ***")
    import json
    spec = {'board': '15', 'main_word': W,
            'turn_str': ''.join(c.upper() if i in MASK else c.lower() for i, c in enumerate(W)),
            'require_center': True, 'claimed_total': vt, 'grid': grid}
    p = f'/home/bob/programming/scrabble4/experiments/results/turns/N15_best_{vt}.json'
    json.dump(spec, open(p, 'w')); print(f"saved {p}")
else:
    print(f"!!! SPURIOUS SAT -- witness_check REJECTS: {rep.get('fail', rep)}")
    print("=> the oracle feasibility model is an OVER-PERMISSIVE RELAXATION.")
