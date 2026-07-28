"""RIJ 7: HERWEGING (x9 i.p.v. x18) + BEZORGSTRUCTUUR-ONDERZOEK.

Twee vragen:

 (1) HERWEGING.  Rij 7 haalt x9, niet x18: de dubbel-woordcel (7,7) telt alleen als die cel
     NIEUW in de slotzet ligt, en het centrum ligt er al vanaf zet 1 (spelregel).  Alle eerdere
     rij-7-waarderingen (TRIPLET_RERANK.md) zijn dus een factor 2 te zwaar.  Hier: de
     gecorrigeerde ranglijsten, volledig (bewijsbare vloeren), zak- en blanco-bewust.

 (2) IS DE RIJ-7-EIS ZELFMOORD OF NOODZAAK?  flexwerkstertje staat op waarde-rang 431; het is
     gekozen omdat het het 8-letter-deelwoord 'werkster' bevat waarmee de 8 pre-cellen van rij 7
     als EEN aaneengesloten blok bezorgd kunnen worden.  Dat is geen spelregel maar een
     architectuureis.  Hier wordt de bezorging van rij 7 volledig gemodelleerd en geenumereerd.

BEZORGLEMMA VOOR RIJ 7 (afgeleid uit de spelregels + score_game):
  * Rij 7 is een 15-letterwoord; de slotzet legt er 7 cellen van, waaronder (0,7) en (14,7)
    (de twee TWS) => wm 3*3 = 9.  De overige 8 cellen (de PRE-SET P) liggen er al, en 7 in P
    (het centrum) is er vanaf zet 1.
  * Een zet legt <= 7 tegels en de nieuwe cellen mogen aan BEIDE kanten van een bestaand blok
    liggen (score_game/shape: de span tussen min en max moet gevuld zijn).  Een maximale run
    van P van lengte L is dus in EEN zet te leggen zodra hij ergens contact met het bord heeft:
      - de run die kolom 7 bevat groeit vanuit het centrum (L-1 <= 7 nieuw, altijd waar);
      - elke andere run heeft een WORTEL nodig: een kolom c in die run met een tegel op (c,6)
        of (c,8) (een verticaal/stub), zodat de zet het bord raakt.
  * Enige woordenboekeis: elke maximale run van P met lengte >= 2 moet een geldig woord zijn.
    (Tussenstadia zijn vrij te vermijden door de run in EEN zet te leggen.)
  => bezorgkosten van rij 7 = het AANTAL WORTELS = (#runs van P) - 1.

Gevolg: de 'werkster'-eis is het R=0-geval (P = een aaneengesloten 8-blok om kolom 7).  Met
R >= 1 wortels vervalt hij, en bovendien kunnen dan BEIDE dubbel-letter-kolommen (3 en 11)
in de x9-slotzet gehouden worden - wat met een 8-blok bewijsbaar onmogelijk is.

CLI:  .venv/bin/python experiments/mg_row7.py
Env:  PART=0,1,2,3,4,5 (default alles), TOP, OUT (jsonl), MBASE (basisbord).
"""
import sys, os, json, itertools, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
from functools import lru_cache
import importlib.util
import numpy as np
import maxgame_score as MG

spec = importlib.util.spec_from_file_location(
    "mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)

r = MG.r
cba = r.alphabet.cba
lk = MG.lk
LM = np.array(r.letter_multiplier).astype(int).tolist()
WM = np.array(r.word_multiplier).astype(int).tolist()
V = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
BAG = Counter({ch: r.counts[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'})
BLANKS = 2
ANCH = (0, 7, 14)
CUR = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')
W15 = [w for w in r.words_str if len(w) == 15]
BYLEN = {}
for w in r.words_str:
    BYLEN.setdefault(len(w), []).append(w)
SET = {}
for w in r.words_str:
    SET.setdefault(len(w), set()).add(w)

def isw(s):
    return s in SET.get(len(s), ())

S = lambda w: sum(V[c] for c in w)

# ---- multipliers -----------------------------------------------------------
# nominaal (hele rij in een zet, fictief): 27 / 18 / 27
RWM = {y: int(np.prod([WM[y][x] for x in range(15)])) for y in ANCH}
# ARCHITECTUUR (echt): de slotzet legt 7 cellen; (7,7) ligt al => rij 7 = 3*3 = 9
ARCHWM = {0: 27, 7: 9, 14: 27}
OLDWM = {0: 27, 7: 18, 14: 27}          # de foutieve weging uit TRIPLET_RERANK.md

def lsum(w, y):
    return sum(LM[y][x] * V[w[x]] for x in range(15))

def value(w, y, wm=None):
    return (wm or ARCHWM)[y] * lsum(w, y)

TOP = int(os.environ.get('TOP', '12'))
PARTS = set(os.environ.get('PART', '0,1,2,3,4,5,6,7').split(','))
RESULT = {}

def hdr(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78, flush=True)


# ============================================================ 0. AUDIT
def part0():
    hdr("0. AUDIT — rij 7 haalt x9 (empirisch op het record)")
    D = json.load(open(os.environ.get('MBASE', 'experiments/results/maxgame_BEST.json')))
    grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    tot, per, ok, msg = MG.score_game([row[:] for row in grid], moves, blanks)
    print(f"basisbord: score {int(tot)}  arbiter ok={ok} ({msg})  tegels="
          f"{sum(len(m) for m in moves)}  zetten={len(moves)}  bingo's="
          f"{sum(1 for m in moves if len(m) == 7)}")
    # de rij-7-slotzet opsporen: de zet die (0,7) en (14,7) legt
    fin = {}
    for y in ANCH:
        for i, mv in enumerate(moves):
            if (0, y) in mv and (14, y) in mv:
                fin[y] = (i, mv)
    for y in ANCH:
        i, mv = fin[y]
        prod = 1
        for (x, yy) in mv:
            prod *= WM[yy][x]
        pre = sorted(set(range(15)) - {x for x, _ in mv})
        print(f"  rij {y:2d}: slotzet = zet {i:2d}, {len(mv)} cellen {sorted(x for x,_ in mv)}"
              f"  -> woordmultiplier PRODUCT = x{prod}   (pre-set {pre})")
    print(f"\n  => rij 0 en rij 14 halen x27 (drie TWS nieuw); rij 7 haalt x{fin[7] and 9}: "
          f"(7,7) is de DWS maar ligt al sinds zet 1, dus alleen (0,7)x3 en (14,7)x3 tellen.")
    print(f"  nominale (fictieve) rijmultipliers als de hele rij in EEN zet zou gaan: {RWM}")
    print(f"  ARCHITECTUUR-multipliers (echt): {ARCHWM}   —  TRIPLET_RERANK gebruikte {OLDWM}")

    m = mc.multiplicity(moves)
    prof = {y: [m[(x, y)] for x in range(15)] for y in ANCH}
    inv = {v: k for k, v in cba.items()}
    print("\n  m-profielen (multipliciteit per cel, uit de m-calculus):")
    for y in ANCH:
        w = ''.join(inv[grid[y][x]] for x in range(15))
        print(f"   rij {y:2d} {w}  m={prof[y]}  som m={sum(prof[y])}  "
              f"waarde={sum(prof[y][x]*V[w[x]] for x in range(15))}")
    nonanch = sum(v for c, v in m.items() if c[1] not in ANCH)
    tot_anch = sum(sum(prof[y][x] * V[''.join(inv[grid[y][x2]] for x2 in range(15))[x]]
                       for x in range(15)) for y in ANCH)
    print(f"  ankers samen {tot_anch} van {int(tot)}  ({100*tot_anch/tot:.1f}%);"
          f" m-massa ankers {sum(sum(prof[y]) for y in ANCH)} van {sum(m.values())}")
    RESULT['prof'] = prof
    RESULT['score'] = int(tot)
    return prof


# ============================================================ 1. HERWEGING
def part1(prof):
    hdr("1. HERWEGING MET x9 — gecorrigeerde ranglijsten")
    print("waarde(w,y) = ARCHWM[y] * SOM_x LM[y][x]*v(w[x]);  ankerrijen 0/7/14 hebben een "
          "identiek letterprofiel (DL op x=3 en x=11), dus de volgorde per rij is identiek "
          "en alleen de SCHAAL verschilt: rij 7 telt half zo zwaar als vroeger gedacht.\n")
    top = sorted(W15, key=lambda w: -lsum(w, 0))
    rank = {w: i + 1 for i, w in enumerate(top)}
    print(" top-20 (lsum = S(w)+v(w[3])+v(w[11]); x27 voor rij 0/14, x9 voor rij 7):")
    for i, w in enumerate(top[:20]):
        print(f"  {i+1:2d}. {w:18s} lsum {lsum(w,0):3d}   x27={27*lsum(w,0):5d}  x9={9*lsum(w,0):4d}")
    for w, y in zip(CUR, ANCH):
        print(f"  huidig rij {y:2d}: {w:18s} lsum {lsum(w,0):3d} rang {rank[w]:6d}/{len(W15)}"
              f"   waarde x{ARCHWM[y]} = {value(w,y):5d}   (oude weging x{OLDWM[y]} = {value(w,y,OLDWM)})")
    d = 9 * lsum(CUR[1], 0)
    print(f"\n  KOSTEN VAN DE FOUT: rij 7 werd op {OLDWM[7]*lsum(CUR[1],0)} gewaardeerd, is "
          f"{d}.  Elke rij-7-waardering is exact gehalveerd; rij 0/14 wegen dus relatief "
          f"2x zo zwaar in elke tripletafweging.")

    # volledige tripletenumeratie, zak- en blanco-bewust, onder BEIDE wegingen
    def bag_eval(ws, wm):
        need = Counter(ws[0]) + Counter(ws[1]) + Counter(ws[2])
        short = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
        d = sum(short.values())
        if d == 0:
            return 0, 0
        if d > BLANKS:
            return d, None
        loss = 0
        for ch, k in short.items():
            cands = sorted(wm[y] * LM[y][x] * V[ch]
                           for w, y in zip(ws, ANCH) for x in range(15) if w[x] == ch)
            loss += sum(cands[:k])
        return d, loss

    for label, wm in (("GECORRIGEERD 27/9/27", ARCHWM), ("OUD (fout) 27/18/27", OLDWM)):
        cur = sum(value(w, y, wm) for w, y in zip(CUR, ANCH))
        cd, cl = bag_eval(CUR, wm)
        curdeg = cur - cl
        MAXA = wm[0] * max(lsum(w, 0) for w in W15)
        MAXB = wm[7] * max(lsum(w, 0) for w in W15)
        flA = curdeg - MAXB - MAXA
        flB = curdeg - 2 * MAXA
        A = [w for w in top if wm[0] * lsum(w, 0) >= flA]
        B = [w for w in top if wm[7] * lsum(w, 0) >= flB]
        vA = [wm[0] * lsum(w, 0) for w in A]; vB = [wm[7] * lsum(w, 0) for w in B]
        out = []
        mb = vB[0] if vB else 0
        for i in range(len(A)):
            if vA[i] + (vA[i + 1] if i + 1 < len(A) else 0) + mb < curdeg:
                break
            for j in range(i + 1, len(A)):
                if vA[i] + vA[j] + mb < curdeg:
                    break
                for k in range(len(B)):
                    nom = vA[i] + vA[j] + vB[k]
                    if nom < curdeg:
                        break
                    b = B[k]
                    if b == A[i] or b == A[j]:
                        continue
                    d, loss = bag_eval((A[i], b, A[j]), wm)
                    if loss is None or nom - loss < curdeg:
                        continue
                    out.append((nom - loss, nom, d, A[i], b, A[j]))
        out.sort(reverse=True)
        pos = next((i for i, o in enumerate(out) if set(o[3:6]) == set(CUR)), None)
        print(f"\n  --- {label}: pool rij0/14 {len(A)}, pool rij7 {len(B)};  huidig triplet "
              f"gedegradeerd {curdeg}, rang {pos+1 if pos is not None else '?'} van {len(out)}")
        for o in out[:6]:
            print(f"      {o[0]:5d} (+{o[0]-curdeg:3d}) {o[3]} / {o[4]} / {o[5]}"
                  f"  [blanco {o[2]}]")
        RESULT['nominaal_' + ('x9' if wm is ARCHWM else 'x18')] = {
            'huidig': curdeg, 'n_beter': len(out) - 1,
            'top': [{'som': o[0], 'r0': o[3], 'r7': o[4], 'r14': o[5], 'blanco': o[2]}
                    for o in out[:TOP]]}
    print("\n  LET OP: deze nominale lijst waardeert elke pre-cel alsof hij alleen zijn "
          "slotzet-bijdrage heeft.  De echte waardering staat in deel 4 (ware m-calculus).")


# ============================================================ 2. BEZORGMODEL RIJ 7
INTERVALS = [(i, j) for i in range(1, 14) for j in range(i + 1, 14)]
IIDX = {iv: k for k, iv in enumerate(INTERVALS)}

def presets():
    """alle pre-sets van rij 7: 8 kolommen uit 1..13 met kolom 7 erbij (het centrum)."""
    for c in itertools.combinations([c for c in range(1, 14) if c != 7], 7):
        yield tuple(sorted(c + (7,)))

def runs_of(P):
    out = []; cs = sorted(P); i = 0
    while i < len(cs):
        j = i
        while j + 1 < len(cs) and cs[j + 1] == cs[j] + 1:
            j += 1
        out.append((cs[i], cs[j])); i = j + 1
    return out

def preset_info(P):
    """(#wortels, vereiste woord-intervallen, bonus-vrijheid) van een pre-set."""
    rs = runs_of(P)
    roots = sum(1 for a, b in rs if not (a <= 7 <= b))
    need = tuple(IIDX[(a, b)] for a, b in rs if b > a)
    return roots, need, (3 not in P, 11 not in P)

def part2():
    hdr("2. HET BEZORGMODEL VAN RIJ 7 — hoeveel kost de 'werkster'-eis?")
    print(__doc__.split('BEZORGLEMMA VOOR RIJ 7')[1].split('CLI:')[0].strip())

    t = time.time()
    N = len(W15)
    OKI = np.zeros((N, len(INTERVALS)), dtype=bool)
    for wi, w in enumerate(W15):
        for k, (a, b) in enumerate(INTERVALS):
            if isw(w[a:b + 1]):
                OKI[wi, k] = True
    print(f"\n  fragmenttabel gebouwd ({N} woorden x {len(INTERVALS)} intervallen) "
          f"in {time.time()-t:.1f}s")

    # pre-sets groeperen op (wortels, vereiste intervallen, bonusvrijheid)
    groups = {}
    for P in presets():
        roots, need, free = preset_info(P)
        groups.setdefault((roots, need, free), P)
    print(f"  {sum(1 for _ in presets())} pre-sets -> {len(groups)} unieke "
          f"(wortels, fragment-eis, DL-vrijheid)-klassen")

    v3 = np.array([V[w[3]] for w in W15]); v11 = np.array([V[w[11]] for w in W15])
    Sv = np.array([S(w) for w in W15])
    NEG = -10 ** 9
    # per wortelbudget R: beste bonus en beste waarde per woord
    best_bonus = {}; minroot_both = np.full(N, 99, dtype=np.int8)
    cum = np.full(N, NEG, dtype=np.int64)
    for R in range(0, 8):
        bb = np.full(N, NEG, dtype=np.int64)
        for (roots, need, free), P in groups.items():
            if roots != R:
                continue
            ok = np.ones(N, dtype=bool) if not need else OKI[:, list(need)].all(axis=1)
            b = (v3 * free[0] + v11 * free[1]).astype(np.int64)
            bb = np.where(ok, np.maximum(bb, b), bb)
            if free[0] and free[1]:
                minroot_both = np.where(ok & (minroot_both > R), R, minroot_both)
        cum = np.maximum(cum, bb)
        best_bonus[R] = cum.copy()

    ci = W15.index(CUR[1])
    print("\n  Per WORTELBUDGET R (= aantal verticale stubs die rij-7-cellen aanleveren):")
    print(f"  {'R':>2} {'#toegelaten woorden':>20} {'beste rij-7-waarde':>19} "
          f"{'woord':<18} {'flexwerkstertje':>16} {'rang':>7}")
    rows = []
    for R in range(0, 8):
        val = np.where(best_bonus[R] > NEG // 2, 9 * (Sv + best_bonus[R]), NEG)
        n = int((val > NEG // 2).sum())
        if n == 0:
            print(f"  {R:>2} {0:>20}")
            continue
        bi = int(val.argmax())
        cv = int(val[ci])
        rank = int((val > cv).sum()) + 1
        print(f"  {R:>2} {n:>20} {int(val[bi]):>19} {W15[bi]:<18} {cv:>16} {rank:>7}")
        rows.append({'R': R, 'n': n, 'best': int(val[bi]), 'word': W15[bi],
                     'flex': cv, 'rang_flex': rank})
    RESULT['bezorgmodel'] = rows

    # de speciale gevallen
    print("\n  Structurele feiten:")
    okw = {}
    for a in range(1, 7):
        okw[a] = [w for w in W15 if isw(w[a:a + 8])]
    print(f"   * R=0 betekent: P is EEN aaneengesloten 8-blok [a,a+7] om kolom 7, a in 1..6, "
          f"en w[a:a+8] moet een woord zijn ('werkster'-eis).")
    for a in range(1, 7):
        print(f"       venster [{a},{a+7}]: {len(okw[a]):5d} woorden"
              f"{'   <-- ons venster' if a == 4 else ''}")
    print(f"     Zo'n blok bevat altijd kolom 7 en heeft breedte 8, dus 3 en 11 kunnen "
          f"NOOIT allebei buiten P vallen  ({sorted(set(range(3,12)) & set(range(1,7)))}"
          f" -> a<=3 vrijwaart 11 niet en a>=4 vrijwaart 3 wel maar 11 niet).")
    both = int((minroot_both < 99).sum())
    print(f"   * BEIDE DL-kolommen (3 en 11) vrij in de x9-slotzet: minimaal benodigde wortels")
    for R in range(0, 8):
        c = int((minroot_both == R).sum())
        if c:
            print(f"       R={R}: {c:6d} woorden (cumulatief {int((minroot_both<=R).sum()):6d})")
    print(f"     -> met R=0 onmogelijk voor ELK woord; vanaf R=1 haalbaar voor {both} van {N}.")
    print(f"     flexwerkstertje: min. wortels voor beide DL's vrij = {int(minroot_both[ci])}")
    RESULT['minroot_both_flex'] = int(minroot_both[ci])
    RESULT['minroot_hist'] = {int(R): int((minroot_both == R).sum()) for R in range(0, 8)}
    return best_bonus, minroot_both, OKI


# ============================================================ 3. JOINT TRIPLET
def part3(best_bonus, minroot_both):
    hdr("3. JOINT: welk triplet wint per bezorgmodel (x9, zak- en blancobewust)")
    N = len(W15)
    Sv = np.array([S(w) for w in W15])
    # rij 0/14: masker-bewust met de bestaande harde fragmentcheck uit mg_triplet_rerank
    import importlib.util as iu
    sp = iu.spec_from_file_location("tr", "/home/bob/programming/scrabble4/experiments/mg_triplet_rerank.py")
    tr = iu.module_from_spec(sp); sp.loader.exec_module(tr)

    def bag_eval(ws):
        need = Counter(ws[0]) + Counter(ws[1]) + Counter(ws[2])
        short = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
        d = sum(short.values())
        if d == 0:
            return 0, 0
        if d > BLANKS:
            return d, None
        loss = 0
        for ch, k in short.items():
            cands = sorted(ARCHWM[y] * LM[y][x] * V[ch]
                           for w, y in zip(ws, ANCH) for x in range(15) if w[x] == ch)
            loss += sum(cands[:k])
        return d, loss

    # rij 0/14 masker-bewuste waarde (hergebruik: harde bezorgcheck + beste DL-vrijhouding)
    hi = sorted(W15, key=lambda w: -lsum(w, 0))[:400]
    A = []
    for w in hi:
        b, P = tr.deliverable_bonus(w)
        if b >= 0:
            A.append((27 * (S(w) + b), w))
    A.sort(reverse=True)
    print(f"  rij-0/14-pool (top-400 op lsum, harde fragment-bezorgcheck): {len(A)}")

    for R in (0, 1, 2, 3):
        val7 = np.where(best_bonus[R] > -10 ** 8, 9 * (Sv + best_bonus[R]), -10 ** 9)
        order = np.argsort(-val7)
        B = [(int(val7[i]), W15[i]) for i in order[:1500] if val7[i] > -10 ** 8]
        if not B:
            continue
        curv = (27 * (S(CUR[0]) + tr.deliverable_bonus(CUR[0])[0]) +
                27 * (S(CUR[2]) + tr.deliverable_bonus(CUR[2])[0]) + int(val7[W15.index(CUR[1])]))
        curv -= bag_eval(CUR)[1]
        out = []
        for i in range(len(A)):
            if A[i][0] + (A[i + 1][0] if i + 1 < len(A) else 0) + B[0][0] < curv:
                break
            for j in range(i + 1, len(A)):
                if A[i][0] + A[j][0] + B[0][0] < curv:
                    break
                for bv, bw in B:
                    tot = A[i][0] + A[j][0] + bv
                    if tot < curv:
                        break
                    if bw == A[i][1] or bw == A[j][1]:
                        continue
                    d, loss = bag_eval((A[i][1], bw, A[j][1]))
                    if loss is None or tot - loss < curv:
                        continue
                    out.append((tot - loss, A[i][1], bw, A[j][1], d))
        out.sort(reverse=True)
        pos = next((k for k, o in enumerate(out) if set(o[1:4]) == set(CUR)), None)
        print(f"\n  --- wortelbudget R={R}: huidig triplet {curv}, rang "
              f"{pos+1 if pos is not None else '?'} van {len(out)} boven de vloer")
        seen = set(); n = 0
        for o in out:
            k = (frozenset((o[1], o[3])), o[2])
            if k in seen:
                continue
            seen.add(k); n += 1
            print(f"    {n:2d}. {o[0]:5d} ({o[0]-curv:+4d})  {o[1]} / {o[2]} / {o[3]}"
                  f"  blanco {o[4]}")
            if n >= 6:
                break
        RESULT[f'joint_R{R}'] = {'huidig': curv, 'n': len(out),
                                 'top': [{'som': o[0], 'r0': o[1], 'r7': o[2], 'r14': o[3]}
                                         for o in out[:TOP]]}


# ============================================================ 4. WARE m-CALCULUS
def part4(prof, minroot_both):
    hdr("4. DE EERLIJKE TOETS — ware m-calculus op de recordgeometrie")
    print("  De nominale waardering (deel 1/3) doet alsof een pre-cel niets verdient buiten de "
          "slotzet.  Fout: hij scoort ook in de bezorgzet en in elk kruiswoord.  De m-calculus "
          "meet dat exact.  Op het record: m(3,7)=18 (slotzet+DL) maar m(11,7)=17 (pre+DL+"
          "verticaal) — het verschil tussen 'DL vrij' en 'DL in de pre-set' is dus ~1-7 per "
          "letterpunt, niet 9.\n")
    m7 = prof[7]; m0 = prof[0]; m14 = prof[14]
    f = lambda w, p: sum(p[i] * V[w[i]] for i in range(15))
    print(f"  rij-7-profiel {m7}  (som {sum(m7)});  rij 0 {sum(m0)}, rij 14 {sum(m14)}")

    # (a) rijen 0/14 VAST: welk rij-7-woord is optimaal in de restzak?
    rest = Counter(BAG); rest.subtract(Counter(CUR[0])); rest.subtract(Counter(CUR[2]))
    cand = []
    for w in W15:
        c = Counter(w)
        sh = {ch: n - rest[ch] for ch, n in c.items() if n > rest[ch]}
        d = sum(sh.values())
        if d > BLANKS:
            continue
        loss = 0
        for ch, k in sh.items():
            loss += sum(sorted(m7[i] * V[ch] for i in range(15) if w[i] == ch)[:k])
        cand.append((f(w, m7) - loss, d, w))
    cand.sort(reverse=True)
    cur7 = f(CUR[1], m7)
    print(f"  (a) rijen 0/14 VAST (geschenkcheques/polymelkzuurtje), rij 7 vrij, restzak-bewust:")
    print(f"      {len(cand)} kandidaten passen; huidig flexwerkstertje = {cur7}")
    for v, d, w in cand[:10]:
        tag = '  <-- HUIDIG' if w == CUR[1] else ''
        print(f"        {w:18s} {v:5d} ({v-cur7:+4d}) blanco {d}  wortels-voor-beide-DL "
              f"{int(minroot_both[W15.index(w)])}{tag}")
    rank = sum(1 for v, d, w in cand if v > cur7) + 1
    print(f"      => rang van flexwerkstertje in de RESTZAK: {rank} van {len(cand)}")
    RESULT['restzak_rang_flex'] = rank
    RESULT['restzak_top'] = [{'w': w, 'v': int(v), 'blanco': d} for v, d, w in cand[:TOP]]

    # (b) alle drie vrij (bovengrens op de tripletwinst, geometrie vastgehouden)
    srt = {y: sorted(range(len(W15)), key=lambda i: -f(W15[i], prof[y])) for y in ANCH}
    MX = {y: f(W15[srt[y][0]], prof[y]) for y in ANCH}
    FL = sum(f(w, prof[y]) for w, y in zip(CUR, ANCH))
    pools = {}
    for y in ANCH:
        other = sum(MX[z] for z in ANCH if z != y)
        pools[y] = [W15[i] for i in srt[y] if f(W15[i], prof[y]) >= FL - other]
    print(f"\n  (b) alle drie vrij (zelfde geometrie): huidig ankertotaal {FL}; "
          f"pools {[len(pools[y]) for y in ANCH]}")
    C = {w: Counter(w) for w in set(pools[0]) | set(pools[7]) | set(pools[14])}
    def bagpen(a, b, c):
        need = C[a] + C[b] + C[c]
        sh = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
        d = sum(sh.values())
        if d == 0:
            return 0, 0
        if d > BLANKS:
            return d, None
        loss = 0
        for ch, k in sh.items():
            loss += sum(sorted(prof[y][i] * V[ch] for w, y in ((a, 0), (b, 7), (c, 14))
                               for i in range(15) if w[i] == ch)[:k])
        return d, loss
    v0 = [f(w, m0) for w in pools[0]]; v7 = [f(w, m7) for w in pools[7]]
    v14 = [f(w, m14) for w in pools[14]]
    m7max = max(v7); best = []
    for i, a in enumerate(pools[0]):
        if v0[i] + m7max + max(v14) < FL:
            break
        for k, c in enumerate(pools[14]):
            if v0[i] + v14[k] + m7max < FL:
                break
            if c == a:
                continue
            for j, b in enumerate(pools[7]):
                tot = v0[i] + v7[j] + v14[k]
                if tot < FL:
                    break
                if b == a or b == c:
                    continue
                d, loss = bagpen(a, b, c)
                if loss is None or tot - loss < FL:
                    continue
                best.append((tot - loss, a, b, c, d))
    best.sort(reverse=True)
    print(f"      {len(best)} tripletten halen de huidige waarde; top:")
    for o in best[:8]:
        print(f"        {o[0]:5d} ({o[0]-FL:+4d})  {o[1]} / {o[2]} / {o[3]}  blanco {o[4]}"
              f"  R7-wortels {int(minroot_both[W15.index(o[2])])}")
    print(f"      => de HELE tripletruimte is op deze geometrie hooguit "
          f"{(best[0][0]-FL) if best else 0} punten beter dan wat we hebben.")
    RESULT['warem'] = {'huidig': FL, 'n': len(best),
                       'top': [{'som': o[0], 'r0': o[1], 'r7': o[2], 'r14': o[3]} for o in best[:TOP]]}
    return best


# ============================================================ 5. KOLOMCENSUS
def part5(best):
    hdr("5. KOLOMTABELLEN — kan een alternatief rij-7-woord uberhaupt gekruist worden?")
    print("  Elke verticaal die rij 7 kruist heeft de rij-7-letter op zijn positie vast.  Voor de "
          "architectuur (top-verticalen rij 0-7, bodem-verticalen rij 7-14) telt per kolom c het "
          "aantal 8-letterwoorden met R0[c] .. R7[c] resp. R7[c] .. R14[c].\n")
    W8 = BYLEN.get(8, [])
    def census(a, b, c):
        top = [sum(1 for w in W8 if w[0] == a[i] and w[7] == b[i]) for i in range(15)]
        bot = [sum(1 for w in W8 if w[0] == b[i] and w[7] == c[i]) for i in range(15)]
        return top, bot
    cands = [CUR] + [ (o[1], o[2], o[3]) for o in best[:5] ]
    for tri in cands:
        top, bot = census(*tri)
        dead_t = [i for i in range(1, 14) if i != 7 and top[i] == 0]
        dead_b = [i for i in range(1, 14) if i != 7 and bot[i] == 0]
        tag = ' <-- HUIDIG' if tri == CUR else ''
        print(f"  {tri[0]}/{tri[1]}/{tri[2]}{tag}")
        print(f"     top  {[top[i] for i in range(15)]}  dode kolommen {dead_t}")
        print(f"     bodem{[bot[i] for i in range(15)]}  dode kolommen {dead_b}")
        print(f"     som top {sum(top[1:14])}  som bodem {sum(bot[1:14])}  "
              f"dood {len(dead_t)+len(dead_b)}")


# ============================================================ 6. EMPIRIE
def part6():
    hdr("6. EMPIRIE — de bezorgrelaxatie ECHT gebouwd op het recordbord (arbiter)")
    D = json.load(open(os.environ.get('MBASE', 'experiments/results/maxgame_BEST.json')))
    grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    alle = {(x, y): grid[y][x] for y in range(15) for x in range(15) if grid[y][x]}
    inv = {v: k for k, v in cba.items()}
    base = int(MG.score_game([r_[:] for r_ in grid], moves, blanks)[0])
    print(f"  basis {base}")

    print("\n  (a) DL-KOLOM 11 VRIJMAKEN.  Volgens het masker-bewuste model levert dat "
          f"9*v(r) = 18 op.  Constructie (zelfde letters, 11 bingo's behouden):")
    print("      pre-set rij 7 {4..11} -> {2,4,5,6,7,9,10,12};  slotzet {0,1,2,3,12,13,14} ->"
          " {0,1,3,8,11,13,14}")
    print("      (2,7) en (12,7) als gewortelde losse tegels ((2,6)='s' / (12,6)='g');")
    print("      de kolom-11-bingo verhuist van rijen 7-13 ('raspige') naar rijen 8-14 en wordt")
    print("      NA de rij-7-slotzet gelegd, zodat de verticale run rijen 7-14 = 'raspiger' is.")
    M = [list(m) for m in moves]
    FIN7 = [i for i, m in enumerate(M) if (0, 7) in m and (14, 7) in m][0]
    C11 = [i for i, m in enumerate(M) if (11, 7) in m and (11, 13) in m][0]
    I18 = [i for i, m in enumerate(M) if (11, 14) in m][0]
    I21 = [i for i, m in enumerate(M) if m == [(8, 7)]][0]
    FIN0 = [i for i, m in enumerate(M) if (0, 0) in m and (14, 0) in m][0]
    FIN14 = [i for i, m in enumerate(M) if (0, 14) in m and (14, 14) in m][0]
    I19 = [i for i, m in enumerate(M) if m == [(8, 14)]][0]
    I20 = [i for i, m in enumerate(M) if m == [(12, 14)]][0]
    drop = {C11, I18, I19, I20, I21, FIN7, FIN0, FIN14}
    new = [list(m) for i, m in enumerate(M) if i not in drop and i < FIN7]
    new += [[(2, 7)], [(12, 7)],
            [(0, 7), (1, 7), (3, 7), (8, 7), (11, 7), (13, 7), (14, 7)],
            [(11, y) for y in range(8, 15)],
            [(9, 14), (10, 14)], [(8, 14)], [(12, 14)],
            list(M[FIN0]), list(M[FIN14])]
    new += [list(m) for i, m in enumerate(M) if i not in drop and i > FIN7]
    tot, per, ok, msg = MG.score_game([r_[:] for r_ in grid], new, blanks)
    print(f"      -> zetten {len(new)}, tegels {sum(len(m) for m in new)}, bingo's "
          f"{sum(1 for m in new if len(m)==7)}, vorm-legaal {mc.legal_schedule(new)}")
    print(f"      -> ARBITER: {int(tot)}  ok={ok} ({msg})   verschil {int(tot)-base:+d}")
    mo = mc.multiplicity(moves); mn = mc.multiplicity(new)
    print("      m-verschillen (cel: oud -> nieuw, letter, delta):")
    tt = 0
    for c in sorted(set(mo) | set(mn), key=lambda c: (c[1], c[0])):
        if mo.get(c, 0) != mn.get(c, 0):
            d = (mn.get(c, 0) - mo.get(c, 0)) * (0 if c in blanks else r.scores[alle[c]])
            tt += d
            print(f"        {c} {mo.get(c,0):3d}->{mn.get(c,0):3d}  {inv[alle[c]]}  {d:+4d}")
    print(f"      som {tt:+d}")
    print("      DUIDING: (11,7) wint +6 (m 17->20) en (11,14) +2, maar de kolommen 4-10 van "
          "rij 7 verliezen samen 19 omdat de GENESTE PRE-RUN wegvalt: 'we'->'werk' en "
          "'te'->'ter'->'werkster' herscoren elke pre-cel meerdere keren.  De 'werkster'-eis "
          "is dus geen kostenpost maar een HERSCORINGSMOTOR.")
    RESULT['chirurgie_dl11'] = {'score': int(tot), 'ok': bool(ok), 'delta': int(tot) - base}

    print("\n  (b) EXACTE-SCORE SCHEMAZOEKER op het vaste bord (letters onveranderd, arbiter "
          "als poort; splits/verplaats/samenvoeg, plateau-wandeling).")
    ITERS = int(os.environ.get('SCHEDITERS', '200000'))
    import random as _rnd
    rnd = _rnd.Random(int(os.environ.get('SEED', '7')))
    def val(mv):
        if not mc.legal_schedule(mv):
            return None
        t_, p_, o_, m_ = MG.score_game([r_[:] for r_ in grid], mv, blanks)
        return int(t_) if o_ else None
    cur = [list(m) for m in moves]; curv = base; best = base
    for it in range(ITERS):
        cand = [list(m) for m in cur]
        op = rnd.random()
        multi = [i for i, m in enumerate(cand) if len(m) > 1]
        if op < 0.45 and multi:
            i = rnd.choice(multi); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
            if rnd.random() < 0.5:
                m = m[::-1]
            k = rnd.randrange(1, len(m)); cand[i:i + 1] = [m[:k], m[k:]]
        elif op < 0.85 and len(cand) > 2:
            i = rnd.randrange(len(cand) - 1); j = rnd.randrange(i + 1, len(cand))
            mv = cand.pop(i); cand.insert(j, mv)
        else:
            i = rnd.randrange(max(1, len(cand) - 1))
            if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                cand[i:i + 2] = [cand[i] + cand[i + 1]]
        v = val(cand)
        if v is None or v < curv:
            continue
        cur, curv = cand, v
        if v > best:
            best = v
            print(f"      it {it}: NIEUW {v}", flush=True)
    print(f"      {ITERS} iteraties; beste {best} (basis {base}) -> "
          f"{'VERBETERING' if best > base else 'geen verbetering: het schema is lokaal optimaal'}")
    RESULT['schedsearch'] = {'iters': ITERS, 'best': best, 'base': base}


# ============================================================ 7. HERSCORING
_TR = None; _RUNS = None
def _build_trans(n=8):
    """Woord-ONAFHANKELIJKE overgangen op een 8-cel-blok: welke groepen cellen mogen in
    EEN zet bij, en levert dat een nieuw (te wortelen) eiland op?"""
    tr = {}
    for st in range(1 << n):
        outs = []
        rem = [i for i in range(n) if not (st >> i) & 1]
        for k in range(1, min(len(rem), 7) + 1):
            for blk in itertools.combinations(rem, k):
                span = set(range(blk[0], blk[-1] + 1)) - set(blk)
                if not all((st >> i) & 1 for i in span):
                    continue                      # zetvorm: gat in de span
                ns = st
                for b in blk:
                    ns |= 1 << b
                touch = any(((b - 1 >= 0 and (st >> (b - 1)) & 1) or
                             (b + 1 < n and (st >> (b + 1)) & 1)) for b in blk)
                outs.append((ns, blk, 0 if touch else 1))
        tr[st] = outs
    return tr

def _runs_mask(st, n=8):
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

def chain_value(w, a, maxroots=2):
    """Maximale waarde van de BEZORGKETEN van de pre-run [a,a+7] (a<=7<=a+7).

    De 8 pre-cellen worden in zetten gelegd; elke zet HERSCOORT elke maximale run die hij
    raakt (nieuwe cellen tellen LM[7][x], oude 1; runs van lengte 1 scoren niets).  Elke
    tussenstand moet woordgeldig zijn.  Eilanden los van het centrum kosten een WORTEL
    (verticale stub); maxroots begrenst dat.  Dit is precies de motor achter
    'we'->'werk'->'te'->'ter'->'werkster' = 45 punten op ons record.
    Geeft None als het blok niet legbaar is."""
    global _TR, _RUNS
    if _TR is None:
        _TR = _build_trans(8); _RUNS = {st: _runs_mask(st) for st in range(256)}
    n = 8; c = 7 - a
    val = [V[w[a + i]] for i in range(n)]; lm = [LM[7][a + i] for i in range(n)]
    okm = [all(isw(w[a + i:a + j + 1]) for i, j in _RUNS[st] if j > i) for st in range(256)]
    start = 1 << c; full = (1 << n) - 1
    best = {(start, 0): 0}
    for st in sorted(range(256), key=lambda s: bin(s).count('1')):
        for rt in range(maxroots + 1):
            cv = best.get((st, rt))
            if cv is None:
                continue
            for ns, blk, nr in _TR[st]:
                if not okm[ns] or rt + nr > maxroots:
                    continue
                g = 0
                for (i, j) in _RUNS[ns]:
                    if j == i or not any(i <= b <= j for b in blk):
                        continue
                    for x in range(i, j + 1):
                        g += lm[x] * val[x] if x in blk else val[x]
                k = (ns, rt + nr)
                if cv + g > best.get(k, -1):
                    best[k] = cv + g
    return max((v for (s, rt), v in best.items() if s == full), default=None)

def part7():
    hdr("7. HERSCORINGS-BEWUSTE RIJ-7-WAARDERING — de eerlijke ranglijst")
    print("  Elke eerdere ranglijst waardeerde rij 7 als 9*(S+DL-bonus).  Dat mist de "
          "BEZORGKETEN: 'we'->'werk' en 'te'->'ter'->'werkster' herscoren de pre-cellen keer op "
          "keer.  Op het record is die keten 59 punten waard (523 werkelijk vs 441 nominaal, "
          "de rest komt van de kruisende verticalen).  Hier: 9*(S+DL-bonus) + max-keten, over "
          "alle vensters [a,a+7].  De DP reproduceert de recordketen EXACT (45).\n")
    MAXROOTS = int(os.environ.get("MAXROOTS", "2"))
    print(f"  wortelbudget in de keten-DP: {MAXROOTS} (onze architectuur heeft er 2: kolom-5/10-verticalen)")
    rows = []
    t0 = time.time()
    for w in W15:
        Sw = S(w)
        bestv = None; bestwin = None; bestch = 0
        for a in range(1, 7):
            b = a + 7
            if not isw(w[a:b + 1]):
                continue
            ch = chain_value(w, a, MAXROOTS)
            if ch is None:
                continue
            bonus = (V[w[3]] if not (a <= 3 <= b) else 0) + (V[w[11]] if not (a <= 11 <= b) else 0)
            v = 9 * (Sw + bonus) + ch
            if bestv is None or v > bestv:
                bestv, bestwin, bestch = v, (a, b), ch
        if bestv is not None:
            rows.append((bestv, bestch, bestwin, w))
    rows.sort(reverse=True)
    print(f"  {len(rows)} woorden hebben een legbare 8-blok-pre-set ({time.time()-t0:.0f}s)")
    cur = next((x for x in rows if x[3] == CUR[1]), None)
    rank = sum(1 for x in rows if x[0] > cur[0]) + 1 if cur else None
    print(f"  {'#':>3}  {'woord':<18} {'totaal':>7} {'keten':>6} {'venster':>9}")
    for i, (v, ch, win, w) in enumerate(rows[:15]):
        print(f"  {i+1:>3}. {w:<18} {v:>7} {ch:>6} {str(win):>9}")
    if cur:
        print(f"  huidig: {CUR[1]} totaal {cur[0]} (keten {cur[1]}, venster {cur[2]}) "
              f"-> RANG {rank} van {len(rows)}")
    # en nu met de zak erbij: rijen 0/14 vast
    rest = Counter(BAG); rest.subtract(Counter(CUR[0])); rest.subtract(Counter(CUR[2]))
    fits = []
    for v, ch, win, w in rows:
        c = Counter(w)
        sh = {x: n - rest[x] for x, n in c.items() if n > rest[x]}
        d = sum(sh.values())
        if d > BLANKS:
            continue
        loss = 0
        for x, k in sh.items():
            loss += sum(sorted(9 * LM[7][i] * V[x] for i in range(15) if w[i] == x)[:k])
        fits.append((v - loss, d, w, ch))
    fits.sort(reverse=True)
    ci = next((i for i, f in enumerate(fits) if f[2] == CUR[1]), None)
    print(f"\n  MET DE RESTZAK (rijen 0/14 = geschenkcheques/polymelkzuurtje vast): "
          f"{len(fits)} kandidaten")
    for i, (v, d, w, ch) in enumerate(fits[:10]):
        tag = '  <-- HUIDIG' if w == CUR[1] else ''
        print(f"    {i+1:>3}. {w:<18} {v:>7} (keten {ch:>4}, blanco {d}){tag}")
    print(f"  => rang van flexwerkstertje: {ci+1 if ci is not None else '?'} van {len(fits)}")
    RESULT['herscoring'] = {'rang_flex_zonder_zak': rank, 'n': len(rows),
                            'rang_flex_met_zak': (ci + 1) if ci is not None else None,
                            'top': [{'w': w, 'v': int(v), 'keten': int(ch), 'venster': list(win)}
                                    for v, ch, win, w in rows[:TOP]],
                            'top_zak': [{'w': w, 'v': int(v), 'keten': int(ch)}
                                        for v, d, w, ch in fits[:TOP]]}


if __name__ == '__main__':
    prof = part0() if '0' in PARTS else {0: [27,28,35,54,29,31,28,27,27,28,30,54,30,27,27],
                                         7: [9,9,14,18,14,14,11,13,10,12,14,17,10,9,9],
                                         14: [27,27,27,54,31,29,28,27,29,30,30,33,28,27,27]}
    if '1' in PARTS:
        part1(prof)
    bb = mrb = None
    if '2' in PARTS:
        bb, mrb, _ = part2()
    if '3' in PARTS and bb is not None:
        part3(bb, mrb)
    best = None
    if '4' in PARTS and mrb is not None:
        best = part4(prof, mrb)
    if '5' in PARTS and best:
        part5(best)
    if '6' in PARTS:
        part6()
    if '7' in PARTS:
        part7()
    out = os.environ.get('OUT', 'experiments/results/row7.json')
    json.dump(RESULT, open(out, 'w'), indent=1)
    print(f"\ngeschreven: {out}")
