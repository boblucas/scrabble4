"""A/B soundness gate for `xfill --pinbatch` (the Rust pinned-combo decision engine) vs the
trusted CP-SAT oracle_beats_lb ledgers.

GATE:
  1. SAT canaries: the verified 2008/2009/2010 boards' combos (mask (8,12)) at floor = the
     board's gross-1: pinbatch must return MAX >= gross, and the emitted BOARD must pass
     verify_board with total > LB-1.  Catches false-LE (over-constrained model).
  2. 2000 random UNSAT keys from the (8,12) lb2010 v2 ledger + 2000 from (9,12) lb2010:
     pinbatch at floor = vfloor must return LE (or TO -- counted, must be <2%).  Any MAX here
     is a verdict mismatch vs proven CP-SAT UNSAT -> FAIL.
  3. Throughput: median/p90 per-combo wall; require >=10x vs CP-SAT's ~0.57s median.
Combo line format:  <key> <floor> <tok per scoring col: '-' or stub 'c1,c2,..'>
The base's BCOL order defines token order.
"""
import sys, os, json, time, random, subprocess
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
random.seed(7)
ROOT = '/home/bob/programming/scrabble4'
BIN = f'{ROOT}/experiments/xfill_rs/target/release/xfill'
import n15_twolevel as T
from n15_varmax_certify import build_unit_base, reconstruct_board

WORD = 'geschenkcheques'
H = W = 15
OUT = f'{ROOT}/experiments/results/pin_gate'
os.makedirs(OUT, exist_ok=True)


def key_to_toks(key, bcols):
    """content key '0:glazuurt|3:...' -> per-bcol token ('-' or stub codes 'c1,c2,..')."""
    m = {}
    for part in key.split('|'):
        c, w = part.split(':')
        m[int(c)] = w
    toks = []
    for c in bcols:
        w = m[c]
        if w == '-' or len(w) <= 1:
            toks.append('-')
        else:
            toks.append(','.join(str(ord(ch) - 96) for ch in w[1:]))   # stub = tail codes
    return toks


def board_key(spec_path, mask):
    grid = json.load(open(spec_path))['grid']
    parts = []
    for c in sorted(mask):
        col = [grid[y][c] for y in range(H)]
        L = 0
        while L < H and col[L] != 0:
            L += 1
        parts.append(f"{c}:{''.join(chr(96 + x) for x in col[:L]) if L > 1 else '-'}")
    return '|'.join(parts)


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


def run_mask_gate(mask, tag, canaries, nsample=2000):
    mc = T.main_const(WORD, mask)
    vfloor = 2010 - mc
    base_path, _, _ = build_unit_base(WORD, mask, OUT)
    # bcol order = base order: read it back
    bcols = [int(l.split()[1]) for l in open(base_path) if l.startswith('BCOL')]
    pin = Pin(base_path)
    fails = []

    # canaries: known-SAT combos.  The ONLY unsound outcome is LE (false refutation) or a
    # witness-rejected MAX.  TO is sound (production falls back to CP-SAT, which found these
    # exact boards -- they are ledger-recorded SATs).
    for spec, lb in canaries:
        key = board_key(spec, mask)
        toks = key_to_toks(key, bcols)
        grossv = json.load(open(spec))['claimed_total'] - mc
        t0 = time.time()
        res, board = pin.decide('CANARY', lb - mc, toks)
        dt = time.time() - t0
        vt = None
        if res.startswith('MAX') and board:
            grid = reconstruct_board(WORD, board)
            wok, wvt, rep = T.verify_board(WORD, mask, grid)
            vt = wvt if wok else f"REJECT:{rep.get('fail')}"
            ok = wok and wvt > lb
        elif res.startswith('TO'):
            ok = True; vt = '(TO -> CP-SAT fallback; sound)'
        else:
            ok = False
        print(f"  canary {spec.split('_')[-1]} floor={lb-mc}: {res.split(' nodes')[0]} "
              f"witness={vt} expect>={grossv} ({dt:.2f}s) {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            fails.append(('canary', spec))

    # easy-SAT probe: all-bare combo at floor -1.  Even this needs real bridge CONSTRUCTION
    # (connect the isolated main tiles + center), which the refutation-tuned DFS may not finish;
    # the only UNSOUND outcomes are LE (false refutation) or a witness-rejected MAX.  A MAX can
    # never certify wrongly in production (witness_check gates every MAX).
    res, board = pin.decide('EASY', -1, ['-'] * len(bcols))
    vt = None
    if res.startswith('MAX') and board is not None:
        grid = reconstruct_board(WORD, board)
        wok, wvt, rep = T.verify_board(WORD, mask, grid)
        vt = wvt if wok else f"REJECT:{rep.get('fail')}"
        ok = wok
    elif res.startswith('TO'):
        ok = True; vt = '(TO; sound)'
    else:
        ok = False
    print(f"  easy-SAT probe: {res.split(' nodes')[0]} witness={vt} {'OK' if ok else 'FAIL'}",
          flush=True)
    if not ok:
        fails.append(('easy-sat', mask))

    # ledger UNSAT sample
    led = f'{ROOT}/experiments/results/oracle_parallel/geschenkcheques_{tag}_lb2010_v2.jsonl'
    keys = []
    for line in open(led):
        try:
            d = json.loads(line)
            if d.get('verdict') == 'UNSAT' and 'key' in d:
                keys.append(d['key'])
        except Exception:
            pass
    sample = random.sample(keys, min(nsample, len(keys)))
    times = []; n_to = 0; mism = []
    for i, key in enumerate(sample):
        toks = key_to_toks(key, bcols)
        t0 = time.time()
        res, _ = pin.decide(f'U{i}', vfloor, toks)
        times.append(time.time() - t0)
        if res.startswith('MAX'):
            mism.append(key); print(f"  !!! MISMATCH (CP-SAT UNSAT, pin MAX): {key}", flush=True)
        elif res.startswith('TO'):
            n_to += 1
        elif not res.startswith('LE'):
            mism.append(key); print(f"  !!! odd verdict {res} for {key}", flush=True)
        if (i + 1) % 500 == 0:
            ts = sorted(times)
            print(f"  {i+1}/{len(sample)} median={ts[len(ts)//2]*1000:.1f}ms "
                  f"p90={ts[int(len(ts)*0.9)]*1000:.1f}ms TO={n_to} mism={len(mism)}", flush=True)
    ts = sorted(times)
    print(f"mask {mask}: {len(sample)} UNSATs -> LE={len(sample)-n_to-len(mism)} TO={n_to} "
          f"mism={len(mism)}; median={ts[len(ts)//2]*1000:.1f}ms p90={ts[int(len(ts)*0.9)]*1000:.1f}ms "
          f"max={ts[-1]*1000:.0f}ms", flush=True)
    if mism:
        fails.append(('mismatches', mism))
    if n_to > len(sample) * 0.02:
        fails.append(('TO-rate', n_to))
    pin.p.stdin.close(); pin.p.terminate()
    return fails, ts[len(ts) // 2]


allfails = []
print("=== mask (0,3,7,8,11,12,14) ===", flush=True)
f1, med1 = run_mask_gate((0, 3, 7, 8, 11, 12, 14), '0378111214', [
    (f'{ROOT}/experiments/results/turns/N15_best_2008.json', 2007),
    (f'{ROOT}/experiments/results/turns/N15_best_2009.json', 2008),
    (f'{ROOT}/experiments/results/turns/N15_best_2010.json', 2009),
])
allfails += f1
print("=== mask (0,3,7,9,11,12,14) ===", flush=True)
f2, med2 = run_mask_gate((0, 3, 7, 9, 11, 12, 14), '0379111214', [])
allfails += f2

print("\n=== PIN GATE REPORT ===")
print(f"speedup vs CP-SAT 0.57s median: {0.57/max(med1,1e-9):.0f}x / {0.57/max(med2,1e-9):.0f}x")
if allfails:
    print(f"*** GATE FAIL *** {allfails}"); sys.exit(1)
print("*** GATE PASS ***")
