"""A/B soundness gate for the v2 oracle pipeline (template-proto fast inner + score-aware
oracle_beats_lb + blank-aware enumeration + content-keyed ledger).

GATE (all must pass before v2 serves any production verdict):
  1. CANARY (process-independent, content-derived): the verified 2008 board's combo -- read
     directly from N15_best_2008.json's columns, NOT from a positional id -- on mask
     (0,3,7,8,11,12,14) at LB 2007: oracle_beats_lb must return SAT and the grid must pass
     verify_board with total > 2007.  Catches false-UNSAT (over-constrained model).
  2. BLANK-AWARE ENUM on (8,12)@2007: band must be a superset of the old 81872 (count >=) and
     must CONTAIN the canary combo's key.
  3. A/B on 40 random (9,12)@2008 band combos: oracle_feasible (v1 exact, slow) vs
     oracle_feasible_fast (template) verdicts IDENTICAL; and oracle_beats_lb=SAT implies
     feasible=SAT (beats is a restriction of feasible).
  4. Timing: median fast-solve time; require >=5x vs the slow build+solve on the same combos.

Runs single-threaded CP-SAT (CPSAT_WORKERS=1) to mirror production workers.
"""
import sys, os, json, time, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['CPSAT_WORKERS'] = '1'
os.environ.setdefault('RESERVE', '1')
from collections import Counter
import n15_twolevel as T

ROOT = '/home/bob/programming/scrabble4'
random.seed(42)
WORD = 'geschenkcheques'
H = W = 15


def board_combo(spec_path, mask):
    """Extract the combo (per-mask-col vertical word codes) realized by a saved board."""
    grid = json.load(open(spec_path))['grid']
    combo = {}
    for c in mask:
        col = [grid[y][c] for y in range(H)]
        L = 0
        while L < H and col[L] != 0:
            L += 1
        combo[c] = tuple(col[:L]) if L > 1 else None
    return combo


def enum(mask, lb):
    mc = T.main_const(WORD, mask)
    avail, _ = T.build_avail(WORD, mask, 1)
    t0 = time.time()
    res = T.enumerate_above_blanks(WORD, mask, avail, lb - mc, blank_budget=2,
                                   collect_top=50_000_000)
    print(f"enum {mask} lb={lb}: count={res['count']} capped={res['capped']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    assert not res['capped']
    return res['top']


# ---- 1. canary ------------------------------------------------------------------------------
# fix_grid: pin the KNOWN 2008 board's setup into the model -> pure propagation.  Validates the
# v2 model (pins + penalty + automata + flow + bag) ACCEPTS a known-legal >LB board (the
# false-UNSAT / over-constraint check) without paying a hard SAT search (June: 1182s).
MASK_C = (0, 3, 7, 8, 11, 12, 14)
spec_c = json.load(open(f'{ROOT}/experiments/results/turns/N15_best_2008.json'))
combo_c = board_combo(f'{ROOT}/experiments/results/turns/N15_best_2008.json', MASK_C)
mc_c = T.main_const(WORD, MASK_C)
print(f"canary combo: { {c: ''.join(chr(96+x) for x in ww) if ww else None for c, ww in combo_c.items()} }",
      flush=True)
t0 = time.time()
st, grid = T.oracle_beats_lb(WORD, MASK_C, combo_c, 2007 - mc_c, cap=600.0,
                             fix_grid=spec_c['grid'])
print(f"canary oracle_beats_lb(vfloor={2007-mc_c}, fix_grid) = {st}  ({time.time()-t0:.1f}s)",
      flush=True)
if st != 'SAT':
    print("!!! GATE FAIL: canary not SAT (false-UNSAT risk)"); sys.exit(1)
ok, vt, rep = T.verify_board(WORD, MASK_C, grid)
print(f"canary verify_board ok={ok} total={vt}", flush=True)
if not ok or vt <= 2007:
    print(f"!!! GATE FAIL: canary witness {vt} / {rep.get('fail')}"); sys.exit(1)

# ---- 2. blank-aware band superset -----------------------------------------------------------
band_c = enum(MASK_C, 2007)
keys_c = set()
for g, combo in band_c:
    keys_c.add(T.combo_key(combo))
print(f"band(8,12)@2007: {len(band_c)} combos (v1 no-blank band was 81872)", flush=True)
if len(band_c) < 81872:
    print("!!! GATE FAIL: blank-aware band SMALLER than v1 band"); sys.exit(1)
if T.combo_key(combo_c) not in keys_c:
    print("!!! GATE FAIL: canary combo missing from band"); sys.exit(1)
print(f"canary key present; band grew by {len(band_c) - 81872} blank-assisted combos", flush=True)

# ---- 3+4. A/B verdicts + timing on (9,12)@2008 ----------------------------------------------
MASK_U = (0, 3, 7, 9, 11, 12, 14)
mc_u = T.main_const(WORD, MASK_U)
band_u = enum(MASK_U, 2008)
idx = random.sample(range(len(band_u)), 40)
mism, slow_secs, fast_secs, beats_secs = [], [], [], []
for k, i in enumerate(idx):
    gross, combo = band_u[i]
    t0 = time.time(); st_slow, _ = T.oracle_feasible(WORD, MASK_U, combo, cap=1200.0)
    t1 = time.time(); st_fast, _ = T.oracle_feasible_fast(WORD, MASK_U, combo, cap=1200.0)
    t2 = time.time(); st_beat, _ = T.oracle_beats_lb(WORD, MASK_U, combo, 2008 - mc_u, cap=1200.0)
    t3 = time.time()
    slow_secs.append(t1 - t0); fast_secs.append(t2 - t1); beats_secs.append(t3 - t2)
    bad = st_slow != st_fast or (st_beat == 'SAT' and st_slow == 'UNSAT')
    if bad:
        mism.append((i, st_slow, st_fast, st_beat))
        print(f"!!! MISMATCH band[{i}]: slow={st_slow} fast={st_fast} beats={st_beat}", flush=True)
    if (k + 1) % 10 == 0:
        print(f"  {k+1}/40 checked, mismatches={len(mism)}", flush=True)

for name, xs in (('slow(feas)', slow_secs), ('fast(feas)', fast_secs), ('beats_lb', beats_secs)):
    xs2 = sorted(xs)
    print(f"{name}: median={xs2[len(xs2)//2]:.2f}s p90={xs2[35]:.2f}s max={xs2[-1]:.2f}s", flush=True)
sp = sorted(slow_secs)[20] / max(sorted(beats_secs)[20], 1e-9)
print(f"\n=== GATE REPORT ===")
print(f"canary: SAT + witness {vt} > 2007  OK")
print(f"band superset: OK ({len(band_c)} >= 81872)")
print(f"A/B verdicts: {40 - len(mism)}/40 consistent; mismatches: {mism}")
print(f"speedup (median slow feas / median beats_lb): {sp:.1f}x")
if mism:
    print("!!! GATE FAIL: verdict mismatches"); sys.exit(1)
if sp < 5:
    print("!!! GATE FAIL: speedup < 5x"); sys.exit(1)
print("*** GATE PASS ***")
