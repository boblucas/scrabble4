"""TRIPLET-HERRANGSCHIKKING OP HET GECORRIGEERDE BORD (2026-07-28).

Aanleiding: data/boards.toml miste 7 letterpremies in de rijen 11-14, o.a. de dubbele-letter-
velden (3,14) en (11,14).  Daardoor is de hele rij-14-rangschikking met verkeerde gewichten
gemaakt.  Dit script herberekent alles op het (nu correcte) bord:

  waarde(w, rij y) = PROD_x WM[y][x]  *  SOM_x LM[y][x] * v(w[x])

en levert een gerangschikte lijst bezorgbare, zak-haalbare tripletten (R0, R7, R14).

Drie filters, in volgorde van hardheid:
  (1) ZAK       : de 45 ankertegels moeten uit 100 letters + 2 blanco's komen; tekort > 2 = dood.
                  Tekort <= 2 wordt met blanco's gedegradeerd (blanco = letterwaarde 0 op die cel);
                  de blanco's worden op de GOEDKOOPSTE cellen gelegd (minimaal waardeverlies).
  (2) BEZORGING : rij 0 en rij 14 moeten in stukjes gelegd kunnen worden.  Harde check
                  (fragment-lemma, zie experiments/FRAME_CAMPAIGN.md + mg_delivery.solve_delivery):
                  bestaat een 8-kolom-pre-set uit {1..6,8..13} waarvan elke maximale run
                  ofwel lengte 1 is, ofwel als blokken (<=3) legbaar is met ELK tussenfragment
                  een geldig woord.  Dit is precies de check die gymjuffrouwtjes doodde.
  (3) R7-VENSTER: rij 7 wordt bezorgd via een 8-letter-deelwoord w[a:a+8] (het 'werkster'-venster).
                  Optioneel (STRICT=1, default) moet dat venster de beide x4-kolommen 4 en 10 dekken.

Env: K0 (pool rij 0/14, default 300), K7 (pool rij 7, default 800), STRICT (1/0),
     TOP (aantal tripletten in de uitvoer, default 10), OUT (jsonl).
"""
import sys, os, json, itertools
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
from functools import lru_cache
import numpy as np
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba
lk = MG.lk
LM = np.array(r.letter_multiplier).astype(int).tolist()   # [y][x]
WM = np.array(r.word_multiplier).astype(int).tolist()     # [y][x]
V = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
BAG = Counter({ch: r.counts[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'})
BLANKS = 2
ANCH = (0, 7, 14)
CUR = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')

# ---------------------------------------------------------------- bord-audit
RESTORED = [((7, 11), 2), ((6, 12), 2), ((8, 12), 2), ((3, 14), 2), ((11, 14), 2),
            ((5, 13), 3), ((9, 13), 3)]          # ((x,y), lm) die vandaag terug zijn
def board_audit():
    bad = [(xy, lm, LM[xy[1]][xy[0]]) for xy, lm in RESTORED if LM[xy[1]][xy[0]] != lm]
    if bad:
        raise SystemExit(f"BORD NIET GECORRIGEERD: {bad}")
    assert LM[0] == LM[14] == LM[7], "ankerrijen hebben niet hetzelfde letterprofiel"
    return True

def isw(s):
    return tuple(cba[c] for c in s) in lk

W15 = [w for w in r.words_str if len(w) == 15]

# ---------------------------------------------------------------- waardering
RWM = {y: int(np.prod([WM[y][x] for x in range(15)])) for y in ANCH}     # 27 / 18 / 27
# rij 7 in ONZE architectuur: het middenvak (7,7) ligt al (openingszet) -> x2 al verbruikt
ARCHWM = {0: RWM[0], 7: RWM[7] // 2, 14: RWM[14]}

def lsum(w, y):
    return sum(LM[y][x] * V[w[x]] for x in range(15))

def value(w, y, arch=False):
    return (ARCHWM if arch else RWM)[y] * lsum(w, y)

def cellw(y, x, arch=False):
    """gewicht van cel (x,y): wat kost het om daar een blanco te leggen, per letterpunt"""
    return (ARCHWM if arch else RWM)[y] * LM[y][x]

# ---------------------------------------------------------------- bezorging
COLS = [c for c in range(1, 14) if c != 7]

@lru_cache(maxsize=None)
def interval_orderable(w, i, j):
    """kan de aaneengesloten run w[i..j] (>=2 cellen) in blokken <=3 gelegd worden met
    elk tussenstadium-fragment een geldig woord?"""
    if j == i:
        return True
    cells = tuple(range(i, j + 1))
    seen = set()
    def runs_ok(pl):
        cs = sorted(pl); k = 0
        while k < len(cs):
            m = k
            while m + 1 < len(cs) and cs[m + 1] == cs[m] + 1:
                m += 1
            if m > k and not isw(w[cs[k]:cs[m] + 1]):
                return False
            k = m + 1
        return True
    def dfs(pl):
        if len(pl) == len(cells):
            return True
        key = frozenset(pl)
        if key in seen:
            return False
        seen.add(key)
        todo = [c for c in cells if c not in pl]
        for size in (1, 2, 3):
            for blk in itertools.combinations(todo, size):
                span = set(range(min(blk), max(blk) + 1))
                if not (span - set(blk)) <= pl:
                    continue
                if pl and not any((b - 1 in pl or b + 1 in pl) for b in blk):
                    continue
                np_ = pl | set(blk)
                if runs_ok(np_) and dfs(np_):
                    return True
        return False
    return dfs(frozenset())

def _preset_ok(w, cs):
    k = 0
    while k < len(cs):
        m = k
        while m + 1 < len(cs) and cs[m + 1] == cs[m] + 1:
            m += 1
        if m > k and not interval_orderable(w, cs[k], cs[m]):
            return False
        k = m + 1
    return True

@lru_cache(maxsize=None)
def deliverable(w):
    """bestaat een 8-kolom-pre-set met uitsluitend bezorgbare runs?  Geeft de set of None."""
    for S in itertools.combinations(COLS, 8):
        if _preset_ok(w, list(S)):
            return S
    return None

@lru_cache(maxsize=None)
def deliverable_bonus(w):
    """MASKER-BEWUSTE waardering.  Een DL op x=3/11 telt alleen mee onder de rij-wm als die cel
    in de SLOTZET ligt; ligt hij in de pre-set, dan scoort hij zijn dubbel in het kleine zetje.
    Geeft (beste bonus, pre-set) over alle geldige 8-pre-sets: bonus = v(w[3])*[3 vrij] +
    v(w[11])*[11 vrij]."""
    best = (-1, None)
    for S in itertools.combinations(COLS, 8):
        b = (V[w[3]] if 3 not in S else 0) + (V[w[11]] if 11 not in S else 0)
        if b <= best[0]:
            continue
        if _preset_ok(w, list(S)):
            best = (b, S)
    return best

@lru_cache(maxsize=None)
def frag_richness(w):
    """aantal geldige deelwoorden w[i:j] met 2<=len<=6 binnen kolommen 1..13 (fragment-rijkdom)"""
    n = 0
    for i in range(1, 13):
        for j in range(i + 2, min(i + 7, 14) + 1):
            if isw(w[i:j]):
                n += 1
    return n

@lru_cache(maxsize=None)
def windows(w):
    """8-letter-deelwoorden w[a:a+8], a in 1..6 -> lijst (a, a+7)"""
    return tuple((a, a + 7) for a in range(1, 7) if a + 7 <= 13 and isw(w[a:a + 8]))

def x4window(w):
    return any(a <= 4 and b >= 10 for a, b in windows(w))

def window_bonus(w, strict=True):
    """beste (bonus, venster) voor rij 7: DL op 3/11 telt alleen als die cel BUITEN het
    pre-gelegde 8-venster ligt."""
    best = (-1, None)
    for a, b in windows(w):
        if strict and not (a <= 4 and b >= 10):
            continue
        bo = (V[w[3]] if not (a <= 3 <= b) else 0) + (V[w[11]] if not (a <= 11 <= b) else 0)
        if bo > best[0]:
            best = (bo, (a, b))
    return best

def value_real(w, y, strict=True):
    """bezorgbare (masker-bewuste) waarde onder de architectuur-multipliers"""
    S = sum(V[ch] for ch in w)
    if y == 7:
        bo = window_bonus(w, strict)[0]
        return ARCHWM[7] * (S + max(bo, 0))
    bo = deliverable_bonus(w)[0]
    if bo < 0:
        return 0                      # niet bezorgbaar
    return ARCHWM[y] * (S + bo)

# ---------------------------------------------------------------- zak + blanco
def bag_eval(a, b, c, arch=False):
    """geeft (tekort, verlies, cellen) — tekort = aantal verplichte blanco's,
    verlies = waardeverlies als die blanco's op de goedkoopste cellen komen."""
    need = Counter(a) + Counter(b) + Counter(c)
    short = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
    deficit = sum(short.values())
    if deficit == 0:
        return 0, 0, []
    loss = 0; chosen = []
    for ch, k in short.items():
        cands = []
        for y, w in ((0, a), (7, b), (14, c)):
            for x in range(15):
                if w[x] == ch:
                    cands.append((cellw(y, x, arch) * V[ch], x, y))
        cands.sort()
        for cost, x, y in cands[:k]:
            loss += cost; chosen.append((ch, x, y, cost))
    return deficit, loss, chosen

# ---------------------------------------------------------------- main
def main():
    board_audit()
    print(f"BORD OK — de 7 herstelde premies staan er.  15-letterwoorden: {len(W15)}", flush=True)
    print(f"rij-multipliers (nominaal): {RWM}   (architectuur, midden al gelegd): {ARCHWM}")
    print(f"letterprofiel ankerrijen: DL op x=3 en x=11 (identiek voor rij 0, 7 en 14)\n")

    # ---- 1. top-20 per rij
    rank = {}
    report = {}
    for y in ANCH:
        top = sorted(W15, key=lambda w: -value(w, y))
        rank[y] = {w: i + 1 for i, w in enumerate(top)}
        report[y] = [(w, value(w, y)) for w in top[:20]]
        print(f"=== TOP-20 rij {y} (wm={RWM[y]}) ===")
        for i, (w, v) in enumerate(report[y]):
            print(f"  {i+1:2d}. {w:18s} {v:5d}")
        cw = CUR[ANCH.index(y)]
        print(f"  huidige keuze: {cw} = {value(cw, y)}  (rang {rank[y][cw]}, "
              f"gat naar #1 = {report[y][0][1] - value(cw, y)})\n", flush=True)

    # ---- oude (defecte) rij-14-waardering ter vergelijking
    OLDLM14 = [1] * 15                       # defect bord: geen letterpremies op rij 14
    oldval = lambda w: RWM[14] * sum(OLDLM14[x] * V[w[x]] for x in range(15))
    oldtop = sorted(W15, key=lambda w: -oldval(w))
    oldrank = {w: i + 1 for i, w in enumerate(oldtop)}
    print("=== rij 14: defect bord vs correct bord ===")
    print(f"  polymelkzuurtje: defect {oldval('polymelkzuurtje')} (rang {oldrank['polymelkzuurtje']})"
          f"  ->  correct {value('polymelkzuurtje', 14)} (rang {rank[14]['polymelkzuurtje']})")
    print(f"  defecte top-5: {[(w, oldval(w)) for w in oldtop[:5]]}")
    print(f"  correcte top-5: {report[14][:5]}\n", flush=True)

    # ---- 2. pools (volledig, met bewijsbare afkap-drempels — geen willekeurige top-K)
    STRICT = os.environ.get('STRICT', '1') == '1'
    TOP = int(os.environ.get('TOP', '10'))
    curn = sum(value(w, y) for w, y in zip(CUR, ANCH))
    cd, cl, _ = bag_eval(*CUR)
    curdeg = curn - cl

    MAXA = max(value(w, 0) for w in W15)
    B0 = [w for w in W15 if windows(w) and (not STRICT or x4window(w))]
    MAXB = max(value(w, 7) for w in B0)
    # elke triplet die het huidige kan evenaren heeft value(a) >= curdeg - MAXB - MAXA, idem c;
    # en value(b) >= curdeg - 2*MAXA.  Dat maakt de pools EINDIG EN VOLLEDIG.
    flA = curdeg - MAXB - MAXA
    flB = curdeg - 2 * MAXA
    A = [w for w in sorted(W15, key=lambda w: -value(w, 0)) if value(w, 0) >= flA]
    print(f"drempels: MAXA={MAXA} MAXB={MAXB} -> vloer rij0/14 {flA}, vloer rij7 {flB}")
    print(f"rij-0/14-kandidaten boven de vloer: {len(A)}", flush=True)
    A = [w for w in A if deliverable(w)]
    print(f"  waarvan bezorgbaar (harde fragment-check): {len(A)}", flush=True)
    B = sorted([w for w in B0 if value(w, 7) >= flB], key=lambda w: -value(w, 7))
    print(f"rij-7-kandidaten met venster{' over x4-kol 4+10' if STRICT else ''} boven de vloer: "
          f"{len(B)} (van {len(B0)} met venster)\n", flush=True)
    if CUR[1] not in B:
        print(f"  LET OP: {CUR[1]} valt buiten de rij-7-pool"); B.append(CUR[1])

    # ---- 3. tripletten (gesnoeid; rij 0 en rij 14 zijn waarde-identiek -> ongeordend paar)
    Aval = [value(w, 0) for w in A]
    Bval = [value(w, 7) for w in B]
    maxb = max(Bval) if Bval else 0
    out = []
    for i in range(len(A)):
        if Aval[i] + (Aval[i + 1] if i + 1 < len(A) else 0) + maxb < curdeg:
            break
        for j in range(i + 1, len(A)):
            base = Aval[i] + Aval[j]
            if base + maxb < curdeg:
                break
            for k in range(len(B)):
                nom = base + Bval[k]
                if nom < curdeg:
                    break
                b = B[k]
                if b == A[i] or b == A[j]:
                    continue
                deficit, loss, _ = bag_eval(A[i], b, A[j])
                if deficit > BLANKS:
                    continue
                if nom - loss < curdeg:
                    continue
                out.append((nom - loss, nom, deficit, loss, A[i], b, A[j]))
    out.sort(reverse=True)
    curpos = next((i for i, o in enumerate(out) if set((o[4], o[5], o[6])) == set(CUR)), None)
    print(f"tripletten met gedegradeerde waarde >= huidig ({curdeg}): {len(out)}", flush=True)
    print(f"HUIDIG {CUR}: nominaal {curn}, tekort {cd}, gedegradeerd {curdeg}, "
          f"rang {curpos + 1 if curpos is not None else 'NIET GEVONDEN'}", flush=True)
    curreal = (value_real(CUR[0], 0) + value_real(CUR[1], 7, STRICT) + value_real(CUR[2], 14)
               - bag_eval(*CUR, arch=True)[1])
    print(f"  bezorgbare (masker-bewuste) waarde huidig: {curreal}\n", flush=True)

    rows = []
    print("=== TOP-%d bezorgbare, zak-haalbare tripletten ===" % TOP)
    seen = set()
    shown = 0
    for (deg, nom, deficit, loss, a, b, c) in out:
        key = (frozenset((a, c)), b)
        if key in seen:
            continue
        seen.add(key)
        real = (value_real(a, 0) + value_real(b, 7, STRICT) + value_real(c, 14)
                - bag_eval(a, b, c, arch=True)[1])
        d = {'rang': shown + 1, 'anker_paar': [a, c], 'R7': b, 'nominaal': nom,
             'zaktekort': deficit, 'blancoverlies': loss, 'gedegradeerd': deg,
             'delta_vs_huidig': deg - curdeg, 'bezorgbaar_real': real,
             'delta_real': real - curreal,
             'frag': [frag_richness(a), frag_richness(c)],
             'preset': [list(deliverable_bonus(a)[1]), list(deliverable_bonus(c)[1])],
             'venster': window_bonus(b, STRICT)[1]}
        rows.append(d); shown += 1
        print(f" {shown:2d}. {a} / {b} / {c}")
        print(f"     nominaal {nom}  tekort {deficit}  blancoverlies {loss}  gedegradeerd {deg}"
              f"  delta {deg - curdeg:+d} | masker-bewust {real} ({real - curreal:+d})  frag {d['frag']}")
        if shown >= TOP:
            break
    # ---- 4. PASS 2: rangschikking op de MASKER-BEWUSTE (bezorgbare) waarde
    # bovengrens per woord = de nominale architectuur-waarde; die snoeit de pools volledig.
    ubA = lambda w: value(w, 0)
    ubB = lambda w: value(w, 7) // 2
    MAXAu = max(ubA(w) for w in W15); MAXBu = max(ubB(w) for w in B0)
    A2 = [w for w in sorted(W15, key=lambda w: -ubA(w)) if ubA(w) >= curreal - MAXBu - MAXAu]
    A2 = [w for w in A2 if deliverable(w)]
    A2 = sorted(A2, key=lambda w: -value_real(w, 0))
    B2 = [w for w in B0 if ubB(w) >= curreal - 2 * MAXAu]
    B2 = sorted(B2, key=lambda w: -value_real(w, 7, STRICT))
    rA = [value_real(w, 0) for w in A2]; rB = [value_real(w, 7, STRICT) for w in B2]
    maxrb = max(rB) if rB else 0
    print(f"\nPASS 2 (masker-bewust): pool rij0/14 = {len(A2)}, pool rij7 = {len(B2)}", flush=True)
    out2 = []
    for i in range(len(A2)):
        if rA[i] + (rA[i + 1] if i + 1 < len(A2) else 0) + maxrb < curreal:
            break
        for j in range(i + 1, len(A2)):
            base = rA[i] + rA[j]
            if base + maxrb < curreal:
                break
            for k in range(len(B2)):
                tot = base + rB[k]
                if tot < curreal:
                    break
                b = B2[k]
                if b == A2[i] or b == A2[j]:
                    continue
                deficit, loss, _ = bag_eval(A2[i], b, A2[j], arch=True)
                if deficit > BLANKS or tot - loss < curreal:
                    continue
                out2.append((tot - loss, tot, deficit, loss, A2[i], b, A2[j]))
    out2.sort(reverse=True)
    pos2 = next((i for i, o in enumerate(out2) if set((o[4], o[5], o[6])) == set(CUR)), None)
    print(f"tripletten met bezorgbare waarde >= huidig ({curreal}): {len(out2)}; "
          f"rang huidig = {pos2 + 1 if pos2 is not None else 'NIET GEVONDEN'}")
    rows2 = []
    seen2 = set(); shown = 0
    print(f"=== TOP-{TOP} op BEZORGBARE (masker-bewuste) waarde ===")
    for (deg, tot, deficit, loss, a, b, c) in out2:
        key = (frozenset((a, c)), b)
        if key in seen2:
            continue
        seen2.add(key)
        d = {'rang': shown + 1, 'anker_paar': [a, c], 'R7': b, 'bezorgbaar': deg,
             'zaktekort': deficit, 'blancoverlies': loss,
             'nominaal': value(a, 0) + value(b, 7) + value(c, 14),
             'delta_vs_huidig': deg - curreal,
             'frag': [frag_richness(a), frag_richness(c)],
             'preset': [list(deliverable_bonus(a)[1]), list(deliverable_bonus(c)[1])],
             'venster': window_bonus(b, STRICT)[1]}
        rows2.append(d); shown += 1
        print(f" {shown:2d}. {a} / {b} / {c}   bezorgbaar {deg} ({deg - curreal:+d})  "
              f"nominaal {d['nominaal']}  tekort {deficit}  frag {d['frag']}")
        if shown >= TOP:
            break

    outp = os.environ.get('OUT', 'experiments/results/triplet_rerank.jsonl')
    with open(outp, 'w') as f:
        f.write(json.dumps({'huidig': {'triplet': list(CUR), 'nominaal': curn, 'zaktekort': cd,
                                       'gedegradeerd': curdeg, 'bezorgbaar_real': curreal,
                                       'rang_nominaal': curpos + 1 if curpos is not None else None,
                                       'rang_bezorgbaar': pos2 + 1 if pos2 is not None else None,
                                       'n_beter_nominaal': len(out) - 1, 'n_beter_bezorgbaar': len(out2) - 1},
                            'strict': STRICT,
                            'top20': {str(y): report[y] for y in ANCH}}) + "\n")
        for d in rows:
            d = dict(d); d['tabel'] = 'nominaal'; f.write(json.dumps(d) + "\n")
        for d in rows2:
            d = dict(d); d['tabel'] = 'bezorgbaar'; f.write(json.dumps(d) + "\n")
    print(f"\ngeschreven: {outp}")

if __name__ == '__main__':
    main()
