"""ANKERKETEN VOOR RIJ 0 EN RIJ 14: masker en woord GEZAMENLIJK optimaliseren.

Vervolg op ROW7.md.  Daar bleek: de waarde van een ankerwoord is niet multiplier*(S+DL-bonus)
maar multiplier*(S+DL-bonus) + KETEN(w, masker), want elke bezorgzet herscoort elke maximale
run die hij raakt.  Voor rij 7 was de keten 45 punten.  Hier voor rij 0 en rij 14, waar de
multiplier 27 is in plaats van 9 en het masker VIER vrije binnencellen heeft.

GEOMETRIE (rij 0 en rij 14 zijn identiek: WM 3/1../3/1../3, DL op x=3 en x=11):
  * de slotzet legt 7 cellen en moet (0,y),(7,y),(14,y) bevatten -> x27; er blijven dus
    4 vrije maskerplekken over uit de 12 binnenkolommen {1..6, 8..13}, en de PRE-SET is
    de overige 8.
  * (7,y) is ALTIJD een maskercel => de pre-set valt uiteen in twee EILANDEN, kolommen 1-6
    en 8-13, die elkaar nooit raken.  Een zet kan nooit over kolom 7 heen reiken (de span
    zou een lege cel bevatten).  Daarom DECOMPONEERT de keten exact:
        keten(w, P) = keten_eiland(w, P n {1..6}) + keten_eiland(w, P n {8..13})
        wortels(P)  = #runs links + #runs rechts        (>= 2, want 8 > 6)
  * anders dan rij 7 is er GEEN gratis wortel: rij 7 had het centrum uit zet 1.  Elke run
    op rij 0/14 heeft een verticale stub nodig ((c,1) resp. (c,13)).

VOLLEDIGE MAAT:   F(w, masker) = 27*(S(w) + v(w[3])*[3 in masker] + v(w[11])*[11 in masker])
                                 + keten(w, pre-set)
Op ons record: rij 0 keten 19, rij 14 keten 53, rij 7 keten 45 (empirisch nagemeten).

CLI:  .venv/bin/python experiments/mg_anchorchain.py
Env:  MAXROOTS (default 4), MB (basisbord), TOP, OUT, PART=0,1,2,3
"""
import sys, os, json, itertools, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import numpy as np
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba
LM = np.array(r.letter_multiplier).astype(int).tolist()
WM = np.array(r.word_multiplier).astype(int).tolist()
V = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
BAG = Counter({ch: r.counts[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'})
BLANKS = 2
W15 = [w for w in r.words_str if len(w) == 15]
SETS = {}
for w in r.words_str:
    SETS.setdefault(len(w), set()).add(w)
def isw(s):
    return s in SETS.get(len(s), ())
S = lambda w: sum(V[c] for c in w)
lsum = lambda w: S(w) + V[w[3]] + V[w[11]]

CUR = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')
LEFT = tuple(range(1, 7))            # kolommen 1..6
RIGHT = tuple(range(8, 14))          # kolommen 8..13
TOP = int(os.environ.get('TOP', '15'))
MAXROOTS = int(os.environ.get('MAXROOTS', '4'))
PARTS = set(os.environ.get('PART', '0,1,2,3').split(','))
RESULT = {}

def hdr(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78, flush=True)

# ---------------------------------------------------------------- eiland-DP
def _build_trans(n=6):
    tr = {}
    for st in range(1 << n):
        outs = []
        rem = [i for i in range(n) if not (st >> i) & 1]
        for k in range(1, len(rem) + 1):
            for blk in itertools.combinations(rem, k):
                span = set(range(blk[0], blk[-1] + 1)) - set(blk)
                if not all((st >> i) & 1 for i in span):
                    continue                       # zetvorm: gat niet gevuld
                ns = st
                for b in blk:
                    ns |= 1 << b
                touch = any(((b - 1 >= 0 and (st >> (b - 1)) & 1) or
                             (b + 1 < n and (st >> (b + 1)) & 1)) for b in blk)
                outs.append((ns, blk, 0 if touch else 1))
        tr[st] = outs
    return tr

def _runs_mask(st, n=6):
    out = []; i = 0
    while i < n:
        if (st >> i) & 1:
            j = i
            while j + 1 < n and (st >> (j + 1)) & 1:
                j += 1
            out.append((i, j)); i = j + 1
        else:
            i += 1
    return out

TR6 = _build_trans(6)
RUNS6 = {st: _runs_mask(st) for st in range(64)}
NRUNS6 = {st: len(RUNS6[st]) for st in range(64)}

def island_table(w, cols, maxroots):
    """Voor ELKE deelverzameling van dit eiland: de maximale ketenwaarde bij <= maxroots
    wortels.  Geeft {subset: {roots: waarde}}; ontbrekende subsets zijn niet legbaar."""
    n = len(cols)
    val = [V[w[c]] for c in cols]
    lm = [LM[0][c] for c in cols]                  # LM identiek voor rij 0/7/14
    okm = [all(isw(w[cols[i]:cols[j] + 1]) for i, j in RUNS6[st] if j > i) for st in range(1 << n)]
    best = {(0, 0): 0}
    for st in sorted(range(1 << n), key=lambda s: bin(s).count('1')):
        for rt in range(maxroots + 1):
            cv = best.get((st, rt))
            if cv is None:
                continue
            for ns, blk, nr in TR6[st]:
                if not okm[ns] or rt + nr > maxroots:
                    continue
                g = 0
                for (i, j) in RUNS6[ns]:
                    if j == i or not any(i <= b <= j for b in blk):
                        continue
                    for x in range(i, j + 1):
                        g += lm[x] * val[x] if x in blk else val[x]
                k = (ns, rt + nr)
                if cv + g > best.get(k, -1):
                    best[k] = cv + g
    out = {}
    for (st, rt), v in best.items():
        d = out.setdefault(st, {})
        if v > d.get(rt, -1):
            d[rt] = v
    # monotoon maken in het wortelbudget
    for st, d in out.items():
        run = -1
        for rt in range(maxroots + 1):
            run = max(run, d.get(rt, -1))
            if run >= 0:
                d[rt] = run
    return out

def full_measure(w, maxroots=MAXROOTS, want_mask=False):
    """max over alle maskers van 27*(S+DL-bonus) + keten, bij <= maxroots wortels."""
    L = island_table(w, LEFT, maxroots)
    R_ = island_table(w, RIGHT, maxroots)
    Sw = S(w); best = None
    for sl, dl in L.items():
        kl = bin(sl).count('1')
        if kl > 6:
            continue
        kr = 8 - kl
        if not (2 <= kr <= 6):
            continue
        pre_l = {LEFT[i] for i in range(6) if (sl >> i) & 1}
        b3 = 0 if 3 in pre_l else V[w[3]]
        for sr, dr in R_.items():
            if bin(sr).count('1') != kr:
                continue
            pre_r = {RIGHT[i] for i in range(6) if (sr >> i) & 1}
            b11 = 0 if 11 in pre_r else V[w[11]]
            for rl, vl in dl.items():
                for rr, vr in dr.items():
                    if rl + rr > maxroots:
                        continue
                    tot = 27 * (Sw + b3 + b11) + vl + vr
                    if best is None or tot > best[0]:
                        best = (tot, vl + vr, rl + rr, tuple(sorted(pre_l | pre_r)))
    if best is None:
        return None
    return best if want_mask else best[0]

def chain_bound(w):
    """geldige bovengrens op de keten: <=6 gebeurtenissen per eiland, elke gebeurtenis
    herscoort hoogstens het hele eiland op maximale multiplier."""
    return sum(V[w[c]] * (LM[0][c] + 5) for c in LEFT + RIGHT)

# ---------------------------------------------------------------- 0. ijking
def part0():
    hdr("0. IJKING — reproduceert de DP de gemeten ketens van het record?")
    D = json.load(open(os.environ.get('MB', 'experiments/results/maxgame_BEST.json')))
    grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
    inv = {v: k for k, v in cba.items()}
    print(f"  basisbord {os.environ.get('MB','experiments/results/maxgame_BEST.json')}: "
          f"{D.get('total')}, {len(moves)} zetten")
    for y, w in ((0, CUR[0]), (14, CUR[2])):
        fin = [i for i, m in enumerate(moves) if (0, y) in m and (14, y) in m][0]
        mask = sorted(x for x, yy in moves[fin] if yy == y)
        pre = tuple(sorted(set(range(1, 14)) - set(mask)))
        pl = tuple(c for c in pre if c < 7); pr = tuple(c for c in pre if c > 7)
        sl = sum(1 << LEFT.index(c) for c in pl); sr = sum(1 << RIGHT.index(c) for c in pr)
        L = island_table(w, LEFT, 6); R_ = island_table(w, RIGHT, 6)
        dl = L.get(sl, {}); dr = R_.get(sr, {})
        nroots = NRUNS6[sl] + NRUNS6[sr]
        ch = (max(dl.values()) if dl else None, max(dr.values()) if dr else None)
        tot = (ch[0] or 0) + (ch[1] or 0)
        b3 = 0 if 3 in pre else V[w[3]]; b11 = 0 if 11 in pre else V[w[11]]
        print(f"  rij {y:2d} {w}: masker {mask}, pre-set {list(pre)}, wortels {nroots}")
        print(f"      DP-keten links {ch[0]} + rechts {ch[1]} = {tot}   "
              f"DL-bonus {b3}+{b11}={b3+b11}   volledige maat {27*(S(w)+b3+b11)+tot}")
        RESULT.setdefault('ijking', {})[str(y)] = {'masker': mask, 'pre': list(pre),
                                                   'keten': tot, 'wortels': nroots}
    print("  (gemeten op het bord: rij 0 = 19, rij 14 = 53, rij 7 = 45)")

# ---------------------------------------------------------------- 1. ranglijst
def part1(floor=None):
    hdr(f"1. VOLLEDIGE MAAT voor rij 0 / rij 14 (identieke geometrie), wortelbudget "
        f"<= {MAXROOTS}")
    cur_full = {w: full_measure(w, MAXROOTS, True) for w in (CUR[0], CUR[2])}
    print("  huidige woorden, masker+woord GEZAMENLIJK geoptimaliseerd:")
    for w in (CUR[0], CUR[2]):
        f = cur_full[w]
        print(f"    {w:18s} nominaal 27*lsum={27*lsum(w):5d}  ->  BESTE maat {f[0]:5d} "
              f"(keten {f[1]}, wortels {f[2]}, pre-set {list(f[3])})")
    if floor is None:
        floor = min(f[0] for f in cur_full.values())
    pool = [w for w in W15 if 27 * lsum(w) + chain_bound(w) >= floor]
    print(f"\n  snoeivloer {floor} (27*lsum + geldige ketengrens) -> pool {len(pool)} "
          f"van {len(W15)}")
    t0 = time.time(); rows = []
    for i, w in enumerate(pool):
        f = full_measure(w, MAXROOTS, True)
        if f:
            rows.append((f[0], f[1], f[2], f[3], w))
        if (i + 1) % 2000 == 0:
            print(f"    .. {i+1}/{len(pool)} ({time.time()-t0:.0f}s)", flush=True)
    rows.sort(reverse=True)
    print(f"  {len(rows)} woorden hebben een legbaar masker ({time.time()-t0:.0f}s)\n")
    print(f"  {'#':>3}  {'woord':<18} {'maat':>6} {'27*lsum':>8} {'keten':>6} {'wtl':>4}  pre-set")
    for i, (tot, ch, rt, pre, w) in enumerate(rows[:TOP]):
        print(f"  {i+1:>3}. {w:<18} {tot:>6} {27*lsum(w):>8} {ch:>6} {rt:>4}  {list(pre)}")
    for w in (CUR[0], CUR[2]):
        k = next(i for i, x in enumerate(rows) if x[4] == w)
        print(f"  huidig: {w} maat {rows[k][0]} -> rang {k+1} van {len(rows)}")
    RESULT['ranglijst'] = [{'w': w, 'maat': t, 'keten': c, 'wortels': rt, 'pre': list(p)}
                           for t, c, rt, p, w in rows[:200]]
    return rows

# ---------------------------------------------------------------- 2. tripletten
def part2(rows):
    hdr("2. TRIPLET op de volledige maat (rij 0/14 met keten, rij 7 met keten), zak-bewust")
    import importlib.util as iu
    sp = iu.spec_from_file_location("r7", "/home/bob/programming/scrabble4/experiments/mg_row7.py")
    os.environ['PART'] = ''            # geen deel uitvoeren bij import
    r7 = iu.module_from_spec(sp); sp.loader.exec_module(r7)

    def row7_measure(w):
        best = None
        for a in range(1, 7):
            if not isw(w[a:a + 8]):
                continue
            ch = r7.chain_value(w, a, 2)
            if ch is None:
                continue
            b = (V[w[3]] if not (a <= 3 <= a + 7) else 0) + (V[w[11]] if not (a <= 11 <= a + 7) else 0)
            v = 9 * (S(w) + b) + ch
            if best is None or v > best:
                best = v
        return best
    A = {w: t for t, c, rt, p, w in rows}
    t0 = time.time()
    B = {}
    for w in W15:
        m = row7_measure(w)
        if m is not None:
            B[w] = m
    print(f"  rij-7-pool {len(B)} ({time.time()-t0:.0f}s); rij-0/14-pool {len(A)}")
    def bagev(a, b, c):
        need = Counter(a) + Counter(b) + Counter(c)
        sh = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
        d = sum(sh.values())
        if d == 0:
            return 0, 0
        if d > BLANKS:
            return d, None
        loss = 0
        for ch, k in sh.items():
            cands = sorted(mult * LM[0][x] * V[ch] for w, mult in ((a, 27), (b, 9), (c, 27))
                           for x in range(15) if w[x] == ch)
            loss += sum(cands[:k])
        return d, loss
    curv = A[CUR[0]] + B[CUR[1]] + A[CUR[2]]
    print(f"  HUIDIG triplet volledige maat: {A[CUR[0]]} + {B[CUR[1]]} + {A[CUR[2]]} = {curv}")
    As = sorted(A.items(), key=lambda kv: -kv[1])
    Bs = sorted(B.items(), key=lambda kv: -kv[1])
    mb = Bs[0][1]
    out = []
    for i in range(len(As)):
        if As[i][1] + (As[i + 1][1] if i + 1 < len(As) else 0) + mb < curv:
            break
        for j in range(i + 1, len(As)):
            if As[i][1] + As[j][1] + mb < curv:
                break
            for bw, bv in Bs:
                tot = As[i][1] + As[j][1] + bv
                if tot < curv:
                    break
                if bw == As[i][0] or bw == As[j][0]:
                    continue
                d, loss = bagev(As[i][0], bw, As[j][0])
                if loss is None or tot - loss < curv:
                    continue
                out.append((tot - loss, As[i][0], bw, As[j][0], d))
    out.sort(reverse=True)
    pos = next((k for k, o in enumerate(out) if set(o[1:4]) == set(CUR)), None)
    print(f"  {len(out)} tripletten halen de huidige maat; rang huidig = "
          f"{pos+1 if pos is not None else '?'}")
    seen = set(); n = 0
    for o in out:
        k = (frozenset((o[1], o[3])), o[2])
        if k in seen:
            continue
        seen.add(k); n += 1
        print(f"   {n:2d}. {o[0]:5d} ({o[0]-curv:+4d})  {o[1]} / {o[2]} / {o[3]}  blanco {o[4]}")
        if n >= TOP:
            break
    RESULT['triplet'] = {'huidig': curv, 'n': len(out),
                         'top': [{'maat': o[0], 'r0': o[1], 'r7': o[2], 'r14': o[3]}
                                 for o in out[:TOP]]}
    return out

# ---------------------------------------------------------------- 3. kolomcensus
def part3(out):
    hdr("3. KOLOMTABEL-FILTER (dode kolommen) op de tripletten die de maat halen")
    W8 = [w for w in r.words_str if len(w) == 8]
    def census(a, b, c):
        top = [sum(1 for w in W8 if w[0] == a[i] and w[7] == b[i]) for i in range(15)]
        bot = [sum(1 for w in W8 if w[0] == b[i] and w[7] == c[i]) for i in range(15)]
        dt = [i for i in range(1, 14) if i != 7 and top[i] == 0]
        db = [i for i in range(1, 14) if i != 7 and bot[i] == 0]
        return top, bot, dt, db
    cands = [CUR] + [(o[1], o[2], o[3]) for o in out[:12] if set(o[1:4]) != set(CUR)]
    rows = []
    for tri in cands:
        top, bot, dt, db = census(*tri)
        rows.append((len(dt) + len(db), sum(top[1:14]), sum(bot[1:14]), tri, dt, db))
        tag = '  <-- HUIDIG' if tri == CUR else ''
        print(f"  {tri[0]}/{tri[1]}/{tri[2]}{tag}")
        print(f"     som top {sum(top[1:14]):5d}  som bodem {sum(bot[1:14]):5d}  "
              f"DOOD {len(dt)+len(db)}  (top {dt}, bodem {db})")
    RESULT['census'] = [{'triplet': list(t), 'dood': d, 'top': tp, 'bodem': bo}
                        for d, tp, bo, t, _, _ in rows]


if __name__ == '__main__':
    if '0' in PARTS:
        part0()
    rows = []
    if '1' in PARTS:
        rows = part1()                       # pas 1: levert maxA exact
        if '2' in PARTS:
            maxA = rows[0][0]
            maxB = int(os.environ.get('MAXB', '567'))     # max rij-7-maat (deel 7 van mg_row7)
            curv = (dict((x[4], x[0]) for x in rows)[CUR[0]] +
                    dict((x[4], x[0]) for x in rows)[CUR[2]] +
                    int(os.environ.get('CUR7', '486')))
            fl = curv - maxA - maxB
            print(f"\n  JOINT-VLOER: huidig {curv} - maxA {maxA} - maxB {maxB} = {fl} "
                  f"-> pas 2 met die vloer (bewijsbaar volledig)")
            rows = part1(fl)
    out = part2(rows) if '2' in PARTS and rows else []
    if '3' in PARTS and out:
        part3(out)
    o = os.environ.get('OUT', 'experiments/results/anchorchain.json')
    json.dump(RESULT, open(o, 'w'), indent=1)
    print(f"\ngeschreven: {o}")
