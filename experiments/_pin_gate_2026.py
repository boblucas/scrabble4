"""Pin-gate v3: validate `xfill --pinbatch` against the CP-SAT oracle under dutch2026 + HMAX=15
(new lexicon + long verticals => NOTHING carries from the v2 gate; fresh A/B evidence required).

GATE:
  1. CANARY (mask (0,3,7,8,11,12,14)): the 2100 board's combo at floor 2099 -- pinbatch must NOT
     return LE (MAX must witness > 2099; TO is sound).
  2. A/B per mask (geschenkcheques (0,3,7,8,11,12,14) + flauwekulexcuus (0,3,6,7,11,13,14)):
     ~60 band combos (top 30 by gross + 30 random) double-solved: CP-SAT oracle_beats_lb verdict
     must match pinbatch (LE<->UNSAT, MAX->SAT-witnessed, TO excused, any conflict = FAIL).
  3. Timing report for both engines under the new regime.
Env: N15_LANG=dutch2026 N15_HMAX=15 (set in-script); bases from bases_2026/ (hmax 15 baked in).
"""
import sys, os, json, time, random, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
os.environ.setdefault('N15_HMAX', '15')
os.environ['CPSAT_WORKERS'] = '4'
import n15_twolevel as T

ROOT = '/home/bob/programming/scrabble4'
BIN = f'{ROOT}/experiments/xfill_rs/target/release/xfill'
BASES = f'{ROOT}/experiments/results/oracle_parallel/bases_2026'
LB = 2100
random.seed(11)


class Pin:
    def __init__(self, basefile):
        self.p = subprocess.Popen([BIN, '--pinbatch', basefile, '--emit'],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def decide(self, key, floor, toks):
        self.p.stdin.write(f"{key} {floor} {' '.join(toks)}\n"); self.p.stdin.flush()
        res = None; board = None
        while True:
            line = self.p.stdout.readline()
            if not line:
                return 'DEAD', None
            if line.startswith('RES '):
                res = line.split(None, 2)[2].strip()
                if res.startswith('MAX'):
                    nxt = self.p.stdout.readline()
                    if nxt.startswith('BOARD'):
                        board = [int(x) for x in nxt.split()[2:]]
                return res, board


def toks_for(combo, bcols):
    return ['-' if not combo.get(c) or len(combo[c]) <= 1
            else ','.join(str(x) for x in combo[c][1:]) for c in bcols]


def gate_mask(word, mask, canary_spec=None):
    tag = '_'.join(str(c) for c in mask)
    base = f'{BASES}/{word}/base_{tag}.txt'
    if not os.path.exists(base):
        from n15_varmax_certify import build_unit_base
        os.environ['XDICT'] = 'experiments/xtests/dict_2026_15.txt'
        os.environ['XHMAX'] = '15'
        base, _, _ = build_unit_base(word, mask, BASES)
    bcols = [int(l.split()[1]) for l in open(base) if l.startswith('BCOL')]
    mc = T.main_const(word, mask)
    vfloor = LB - mc
    pin = Pin(base)
    fails = []

    if canary_spec:
        grid = json.load(open(canary_spec))['grid']
        combo = {}
        for c in mask:
            col = [grid[y][c] for y in range(15)]
            L = 0
            while L < 15 and col[L] != 0:
                L += 1
            combo[c] = tuple(col[:L]) if L > 1 else None
        res, board = pin.decide('CANARY', 2099 - mc, toks_for(combo, bcols))
        ok = not res.startswith('LE') and res != 'DEAD' and not res.startswith('NOCAND')
        if res.startswith('MAX') and board:
            from n15_varmax_certify import reconstruct_board
            g = reconstruct_board(word, board)
            wok, vt, rep = T.verify_board(word, mask, g)
            ok = wok and vt > 2099
            print(f"  canary: {res.split(' nodes')[0]} witness={vt if wok else rep.get('fail')}",
                  flush=True)
        else:
            print(f"  canary: {res.split(' nodes')[0]} ({'sound' if ok else 'FAIL'})", flush=True)
        if not ok:
            fails.append(('canary', word, mask))

    avail, _ = T.build_avail(word, mask, 1)
    res = T.enumerate_above_blanks(word, mask, avail, vfloor, collect_top=50_000, node_budget=100_000_000)
    band = res['top']
    print(f"  band sample: count={res['count']} capped={res['capped']} collected={len(band)}", flush=True)
    picks = list(range(min(30, len(band)))) + random.sample(range(len(band)),
                                                            min(30, len(band)))
    picks = sorted(set(picks))
    mism = []
    tp, tc = [], []
    for i in picks:
        gross, combo = band[i]
        key = f'g{i}'
        t0 = time.time(); pres, pboard = pin.decide(key, vfloor, toks_for(combo, bcols))
        t1 = time.time(); cres, cgrid = T.oracle_beats_lb(word, mask, combo, vfloor, cap=300.0)
        t2 = time.time()
        tp.append(t1 - t0); tc.append(t2 - t1)
        ok = ((pres.startswith('LE') and cres == 'UNSAT')
              or (pres.startswith('MAX') and cres == 'SAT')
              or pres.startswith('TO') or cres == 'UNKNOWN')
        if not ok:
            mism.append((i, pres.split(' nodes')[0], cres))
            print(f"  !!! MISMATCH band[{i}] gross={gross}: pin={pres.split(' nodes')[0]} "
                  f"cpsat={cres}", flush=True)
    tp.sort(); tc.sort()
    print(f"  A/B {len(picks)} combos: mism={len(mism)}; pin median={tp[len(tp)//2]*1000:.1f}ms "
          f"cpsat median={tc[len(tc)//2]:.1f}s", flush=True)
    if mism:
        fails.append(('mismatch', word, mask, mism))
    pin.p.terminate()
    return fails


allf = []
print("=== geschenkcheques (0,3,7,8,11,12,14) ===", flush=True)
allf += gate_mask('geschenkcheques', (0, 3, 7, 8, 11, 12, 14),
                  canary_spec=f'{ROOT}/experiments/results/turns/N15_best_2100.json')
print("=== flauwekulexcuus (0,3,6,7,11,13,14) ===", flush=True)
allf += gate_mask('flauwekulexcuus', (0, 3, 6, 7, 11, 13, 14))
print("\n=== GATE v3 REPORT ===")
if allf:
    print(f"*** GATE FAIL *** {allf}"); sys.exit(1)
print("*** GATE PASS ***")
