"""KLASSE-PLAFONDS: welke GEOMETRIE-KLASSE heeft genoeg bovengrens?  (bord HERSTELD 2026-07-28)

Gebruikt de m-motor (mg_mceiling): score = SOM_c m(c)*waarde(c) + 50*#bingo's, met m puur uit
geometrie + zetvolgorde.  Hier bouwen we per klasse een representatieve BEZETTING + ZETSCHEMA
(cellen, geen woorden) en rekenen het plafond uit.

Drie regimes per klasse (ladder-afhankelijkheid):
  vrij    - elke legale zet (ook 1-tegel-zetten): maximale ladder-vrijheid
  min2    - elke zet legt >=2 tegels
  minzet  - geen splitsingen: elke lijn in zo min mogelijk zetten (canoniek schema)

Alle regimes eisen ECHTE zet-vorm (een lijn, aaneengesloten run).  Die check zit sinds
2026-07-28 in mg_mceiling.legal_schedule/shape_ok zelf; `legal()` hieronder voegt alleen de
min-grootte-eis en foutmeldingen toe.

CLI:  .venv/bin/python experiments/mg_classceiling.py [ITERS=20000] [SURGERY=1]
"""
import sys, os, json, random
from multiprocessing import Pool
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import mg_mceiling as M

CAP = 101                      # bord <= 101 tegels (tegenstander houdt er minstens 1)
BEST = '/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json'


# ---------------------------------------------------------------- bord-controle
def board_check():
    """Het bord MOET een echt scrabblebord zijn: 180-graden-symmetrisch, 24 DL, 12 TL,
    17 DW, 8 TW.  (Tot 2026-07-28 miste data/boards.toml 7 letterpremies in rijen 11-14;
    die fout is hersteld in commit 'BORD-DEFECT HERSTELD'.  Deze check bewaakt dat.)"""
    lm, wm = M.LM, M.WM
    sym = all(lm[y][x] == lm[14 - y][14 - x] and wm[y][x] == wm[14 - y][14 - x]
              for y in range(15) for x in range(15))
    cl = Counter(v for row in lm for v in row)
    cw = Counter(v for row in wm for v in row)
    ok = sym and cl[2] == 24 and cl[3] == 12 and cw[2] == 17 and cw[3] == 8
    return ok, {'symmetrisch': sym, 'DL': cl[2], 'TL': cl[3], 'DW': cw[2], 'TW': cw[3]}


# ---------------------------------------------------------------- legaliteit (streng)
shape_ok = M.shape_ok            # zet = EEN lijn + aaneengesloten run (nu in de motor zelf)


def legal(moves, minsize=1, shape=True, why=False):
    placed = set()
    for i, mv in enumerate(moves):
        s = set(mv)
        if not mv or len(mv) > 7 or len(s) != len(mv) or (s & placed):
            return (False, f'zet {i}: grootte/overlap') if why else False
        if len(mv) < minsize:
            return (False, f'zet {i}: < {minsize} tegels') if why else False
        if i == 0:
            if (7, 7) not in s:
                return (False, 'zet 0 dekt center niet') if why else False
        elif not any((x + dx, y + dy) in placed for (x, y) in mv for dx, dy in M.NB):
            return (False, f'zet {i}: raakt bord niet {sorted(s)}') if why else False
        if shape and not shape_ok(s, placed):
            return (False, f'zet {i}: geen aaneengesloten lijn {sorted(s)}') if why else False
        placed |= s
    return (True, 'ok') if why else True


# ---------------------------------------------------------------- schema-zoektocht
def search(seed_moves, iters=20000, minsize=1, allow_split=True, shape=True, seed=0,
           fixed=None, zero=None):
    """Lokale zoektocht over SCHEMA's bij vaste bezetting (splitsen/hersorteren/samenvoegen).
    Splitsingen gebeuren LANGS DE LIJN, zodat de deelzetten zelf weer vorm-legaal zijn."""
    rnd = random.Random(seed)
    cur = [list(m) for m in seed_moves]
    best, _ = M.score_of(cur, fixed, zero=zero)
    bestmv = [list(m) for m in cur]
    for _ in range(iters):
        cand = [list(m) for m in cur]
        op = rnd.random()
        idx = [i for i, m in enumerate(cand) if len(m) > max(1, minsize)]
        if allow_split and op < 0.45 and idx:
            i = rnd.choice(idx); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
            if rnd.random() < 0.5: m = m[::-1]
            k = rnd.randrange(1, len(m))
            cand[i:i + 1] = [m[:k], m[k:]]
        elif op < 0.85 and len(cand) > 2:
            i = rnd.randrange(len(cand)); j = rnd.randrange(len(cand))
            if i == j: continue
            mv = cand.pop(i); cand.insert(j, mv)
        else:
            i = rnd.randrange(max(1, len(cand) - 1))
            if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                cand[i:i + 2] = [cand[i] + cand[i + 1]]
        if not legal(cand, minsize=minsize, shape=shape): continue
        sc, _ = M.score_of(cand, fixed, zero=zero)
        if sc >= best:
            if sc > best: bestmv = [list(m) for m in cand]
            best = sc; cur = cand
    return best, bestmv


def multisearch(seed_moves, iters, seeds=4, **kw):
    best, bm = 0, seed_moves
    for s in range(seeds):
        b, m = search(seed_moves, iters=iters, seed=s, **kw)
        if b > best: best, bm = b, m
    return best, bm


def to_min2(moves):
    """Maak een schema waarin elke zet >=2 tegels legt: fuseer 1-tegel-zetten met een andere
    zet (zelfde lijn); lukt dat niet, dan is die cel niet leverbaar en valt hij weg."""
    cur = [list(m) for m in moves]
    gedropt = []
    while True:
        singles = [i for i, m in enumerate(cur) if len(m) < 2]
        if not singles: break
        i = singles[0]
        ok = False
        for j in range(len(cur)):
            if j == i or len(cur[j]) >= 7: continue
            cand = [list(m) for m in cur]
            cell = cand[i][0]
            cand[j] = cand[j] + [cell]
            cand.pop(i)
            if legal(cand, minsize=1):
                cur = cand; ok = True; break
        if not ok:
            gedropt.append(cur[i][0]); cur.pop(i)
    while cur and not legal(cur, minsize=2):        # herstel: gooi kapotte zetten weg
        for i in range(len(cur)):
            if not legal(cur[:i + 1], minsize=2):
                gedropt.extend(cur[i]); cur.pop(i); break
        else:
            break
    return cur, gedropt


def trim_to_cap(moves, cap=CAP):
    """Bord mag maar `cap` tegels dragen.  Gooi net zo lang de cel met de LAAGSTE m weg als
    het schema legaal blijft.  Zo vergelijken we alle klassen op hetzelfde tegelbudget."""
    cur = [list(m) for m in moves]
    weg = []
    while sum(len(m) for m in cur) > cap:
        m = M.multiplicity(cur)
        for _, c in sorted((v, c) for c, v in m.items()):
            cand = [[q for q in z if q != c] for z in cur]
            cand = [z for z in cand if z]
            if legal(cand):
                cur = cand; weg.append(c); break
        else:
            break
    return cur, weg


def profile(moves):
    m = M.multiplicity(moves)
    anchors = {(x, y) for y in (0, 7, 14) for x in range(15)}
    non = Counter(v for c, v in m.items() if c not in anchors)
    return m, non


# ---------------------------------------------------------------- DSL
def V(x, ys): return [(x, y) for y in ys]
def H(y, xs): return [(x, y) for x in xs]
def R(a, b): return list(range(a, b + 1))


# ================================================================ KLASSEN
def klasse_a():
    """(a) HUIDIGE KLASSE: 3 ankerrijen (0/7/14) x27/x9/x27 + verticale bingo's.
    Topologie van ons record: verticalen leveren de pre-cellen van de ankerrijen,
    de finals (7 tegels, incl. alle TWS) sluiten de rij af."""
    return _anker3()


def _anker3(kol7=False, onderlaan=None):
    """Gedeelde bouwer voor (a), (f) en de onderlaan-klassen (g/h/i).
    kol7=True vult kolom 7 helemaal (rijen 1..13) zodat beide x27-finals het kolom-7-woord
    herscoren.  onderlaan=y vervangt de onderste losse verticalen door een x4-laan in rij y
    (rij 11/12/13: de twee DWS worden door een 2-tegel-brugzet NIEUW gedekt -> wm 4)."""
    mv = []
    mv.append(V(7, R(4, 10)))                       # center-bingo
    if kol7:
        mv.append(V(7, R(1, 3)))
        mv.append(V(7, R(11, 13)))
    mv.append(H(4, [3, 4, 5, 6, 8, 9, 10]))         # x4-laan rij 4 ((4,4)+(10,4))
    mv.append(V(2, R(0, 6)))                        # bingo-klimmer, levert (2,0)
    mv.append(V(5, [0, 1, 2, 3, 5, 6, 7]))          # bingo-klimmer, levert (5,0)+(5,7)
    mv.append(V(9, [0, 1, 2, 3, 5, 6, 7]))          # bingo-klimmer, levert (9,0)+(9,7)
    mv.append(H(7, [6, 8]))                         # rij-7 pre-keten naar rechts
    mv.append(H(7, [10, 11, 12]))
    mv.append(V(12, R(0, 6)))                       # bingo-klimmer, levert (12,0)
    mv.append(H(0, [1]))                            # rij-0 pre-ketens
    mv.append(H(0, [4, 6]))
    mv.append(H(0, [10]))
    mv.append(H(10, [4, 5, 6, 8, 9, 10, 11]))       # x4-laan rij 10 + brug (11,10)
    drager = (4, 11)                                # kolommen die rij 14 aanhaken
    if onderlaan:
        y = onderlaan
        a, b = [x for x in range(15) if M.WM[y][x] == 2]     # de twee DWS van deze rij
        # de dalende kolommen mogen NIET op de DWS van de laan staan (die moeten NIEUW zijn
        # in de completeringszet) en niet op kolom 7 als die al vol is
        drager = tuple(c for c in (4, 11, 12, 3) if c not in (a, b) and not (kol7 and c == 7))[:2]
        bezet = {c for z in mv for c in z}
        for c in drager:
            mv.append([(c, yy) for yy in R(8, 13) if (c, yy) not in bezet])
        bezet |= {c for z in mv for c in z}
        pre = [x for x in R(a + 1, b - 1) if (x, y) not in bezet]
        blok = []                                   # aaneengesloten stukken van <=7 tegels
        for x in pre:
            if blok and x == blok[-1] + 1 and len(blok) < 7: blok.append(x)
            else:
                if blok: mv.append(H(y, blok))
                blok = [x]
        if blok: mv.append(H(y, blok))
        mv.append(H(y, [a, b]))                     # x4-completering (beide DWS nieuw)
    else:
        mv.append(V(4, R(11, 13)) if kol7 else V(4, [8, 9, 11, 12, 13]))
        mv.append(V(11, [8, 9, 11, 12, 13]))
        if not kol7:
            mv.append(V(9, R(11, 13)))
    mv.append(H(7, [0, 1, 2, 3, 4, 13, 14]))        # FINAL rij 7  -> x9
    # rij-14 pre-ketens: hangen aan de dalende kolommen en groeien naar elkaar toe
    pre14 = [x for x in R(1, 13) if x not in (7, 13)]
    dl, dr = min(drager), max(drager)
    mv.append(H(14, [dl])); mv.append(H(14, [dr]))
    keten, links = [], sorted(set(pre14) - {dl, dr} - {1, 2, 3})
    for x in links:
        if keten and x == keten[-1] + 1 and len(keten) < 7: keten.append(x)
        else:
            if keten: mv.append(H(14, keten))
            keten = [x]
    if keten: mv.append(H(14, keten))
    mv.append(H(14, [0, 1, 2, 3, 7, 13, 14]))       # FINAL rij 14 -> x27
    mv.append(H(0, [0, 3, 7, 8, 11, 13, 14]))       # FINAL rij 0  -> x27 (DLS 3/11 nieuw)
    return [m for m in mv if m]


def klasse_a_min2(kol7=False):
    """(a2) klasse (a) met MIN-2-LEVERING: klimkolommen stoppen op rij 1 (6 tegels, geen bingo)
    en de pre-cellen van de ankerrijen komen als PAREN.  Kost 4 bingo's, maar geen enkele
    1-tegel-zet -> dit is het eerlijke min2-getal voor de ankerklasse."""
    mv = []
    mv.append(V(7, R(4, 10)))
    mv.append(H(4, [3, 4, 5, 6, 8, 9, 10]))          # x4-laan rij 4
    mv.append(V(2, R(1, 6)))                         # klimkolom (6 tegels)
    mv.append(H(0, [1, 2]))                          # pre-paar
    mv.append(V(5, [1, 2, 3, 5, 6, 7]))
    mv.append(H(0, [4, 5]))
    mv.append(V(9, [1, 2, 3, 5, 6, 7]))
    mv.append(H(0, [9, 10]))
    mv.append(H(7, [6, 8]))
    mv.append(H(7, [10, 11, 12]))
    mv.append(V(12, R(1, 6)))
    mv.append(H(0, [12, 13]))
    mv.append(H(10, [4, 5, 6, 8, 9, 10, 11]))        # x4-laan rij 10
    if kol7:
        mv.append(V(7, R(11, 13)))                   # kolom 7 dicht tot rij 13
        mv.append(H(10, [3]))                        # 2 restant-tegels als kruisletters
        mv.append(H(10, [12]))
    else:
        mv.append(V(4, R(11, 13)))
    mv.append(V(11, R(11, 13)))
    mv.append(H(7, [0, 1, 2, 3, 4, 13, 14]))         # FINAL rij 7 x9
    mv.append(V(2, R(8, 13)))                        # hangt aan (2,7) uit de final
    mv.append(H(14, [1, 2]))
    mv.append(H(14, [3, 4]) if kol7 else H(14, [4, 5]))
    mv.append(H(14, [10, 11]))
    mv.append(H(14, [12, 13]))
    mv.append(H(14, [0, 5, 6, 7, 8, 9, 14]) if kol7 else
              H(14, [0, 3, 6, 7, 8, 9, 14]))         # FINAL rij 14 x27 (+ kolom 7 x3)
    mv.append(H(0, [0, 3, 6, 7, 8, 11, 14]))         # FINAL rij 0 x27 (DLS 3/11 nieuw)
    return mv


def klasse_a_record():
    """(a') hetzelfde, maar de ECHTE bezetting+zetvolgorde van ons record (4751)."""
    D = json.load(open(BEST))
    return [[tuple(c) for c in m] for m in D['moves']]


def klasse_b():
    """(b) FRAME: rijen 0/7/14 EN kolommen 0/7/14 alle 15 letters (81 cellen), snijdend in de
    9 TWS-cellen.  De kolommen worden TWEEMAAL x3 gecompleteerd (rij-14-final -> 14-run,
    rij-0-final -> 15-run).  KLIMKOLOM-LEMMA: elke ankerrij heeft 8 pre-cellen, gesplitst door
    de final-cel (7,rij); links en rechts daarvan is elk een klimkolom van 6 tegels nodig
    (afstand rij 7 -> rij 1) => 4 x 6 = 24 tegels bovenop de 81.  Totaal 105 > 101 = OVER CAP."""
    mv = []
    mv.append(V(7, R(4, 10)))                       # center
    mv.append(V(7, R(1, 3)))                        # kolom 7 boven ((7,0) blijft voor de final)
    mv.append(V(7, R(11, 13)))                      # kolom 7 onder
    mv.append(H(7, [4, 5, 6]))                      # rij-7 pre links
    mv.append(H(7, [8, 9, 10, 11]))                 # rij-7 pre rechts
    mv.append(H(7, [0, 1, 2, 3, 12, 13, 14]))       # FINAL rij 7 -> x9 ; opent kolom 0/14
    mv.append(V(0, R(1, 6)))                        # kolom-0 boven  (run 1..7)
    mv.append(V(0, R(8, 13)))                       # kolom-0 onder  (run 1..13)
    mv.append(V(14, R(1, 6)))
    mv.append(V(14, R(8, 13)))
    mv.append(V(2, R(0, 6)))                        # KLIMKOLOM linksboven (7 tegels = bingo)
    mv.append(V(12, R(0, 6)))                       # KLIMKOLOM rechtsboven
    mv.append(V(2, R(8, 14)))                       # KLIMKOLOM linksonder
    mv.append(V(12, R(8, 14)))                      # KLIMKOLOM rechtsonder
    mv.append(H(0, [1, 3, 4]))                      # rij-0 pre-keten rond (2,0)
    mv.append(H(0, [10, 11, 13]))                   # rond (12,0)
    mv.append(H(14, [1, 3, 4]))
    mv.append(H(14, [10, 11, 13]))
    mv.append(H(14, [0, 5, 6, 7, 8, 9, 14]))        # FINAL rij 14 x27 + kol 0/7/14 x3 (14-runs)
    mv.append(H(0, [0, 5, 6, 7, 8, 9, 14]))         # FINAL rij 0  x27 + kol 0/7/14 x3 (15-runs)
    return mv


def _frame(kols, klim, paren0, final0, paren14, final14, kort=()):
    """Gedeelde frame-bouwer: alles hangt aan de rij-7-final (die (0,7)..(14,7) opent).
    kols = kolommen die als VOLLE lijn worden gelegd; klim = klimkolommen die alleen de
    pre-cellen van rij 0/14 leveren; paren = volgorde van de pre-paren per ankerrij."""
    mv = []
    mv.append(V(7, R(4, 10)))                        # center
    mv.append(H(7, [6, 8]))                          # rij-7 pre
    mv.append(H(7, [3, 4, 5]))
    mv.append(H(7, [9, 10]))
    mv.append(H(7, [0, 1, 2, 11, 12, 13, 14]))       # FINAL rij 7 x9 -> opent alle kolommen
    if 7 in kols:
        mv.append(V(7, R(11, 13)))                   # kolom 7 = rijen 4..13
    for c in kols:
        if c == 7: continue
        mv.append(V(c, R(1, 6)))                     # hangt aan (c,7); (c,0)/(c,14) volgen later
        mv.append(V(c, R(8, 12 if c in kort else 13)))
    for c in klim:
        mv.append(V(c, R(0, 6)))                     # klimkolom = 7 tegels = BINGO
        mv.append(V(c, R(8, 14)))
    for p in paren0:
        mv.append(H(0, p))
    for p in paren14:
        mv.append(H(14, p))
    mv.append(H(14, final14))                        # FINAL rij 14 x27 (completeert kolommen)
    mv.append(H(0, final0))                          # FINAL rij 0  x27 (completeert kolommen)
    return mv


def klasse_b2():
    """(b2) FRAME met verschoven kolommen 2/7/12 + klimkolommen 5/9: geen TWS maar DWS-paren
    ((2,2)/(2,12)/(12,2)/(12,12)) -> x2 per kolomhelft.  101 tegels."""
    return _frame(kols=(2, 7, 12), klim=(5, 9), kort=(2,),
                  paren0=([4, 6], [8, 10], [2, 3]),
                  final0=[0, 1, 7, 11, 12, 13, 14],
                  paren14=([4, 6], [8, 10], [2, 3]),
                  final14=[0, 1, 7, 11, 12, 13, 14])


def klasse_b3():
    """(b3) PARTIEEL TWS-FRAME: kolommen 0 en 14 volledig (x3-completering door BEIDE
    x27-finals), kolom 7 alleen het centrumstuk.  De grootste legale variant van het
    TWS-frame (99 tegels).  Let op: de DLS-cellen (3,0)/(11,0) moeten hier PRE zijn."""
    return _frame(kols=(0, 14), klim=(2, 12),
                  paren0=([1, 3], [11, 13], [4, 5]),
                  final0=[0, 6, 7, 8, 9, 10, 14],
                  paren14=([1, 3], [11, 13], [4, 5]),
                  final14=[0, 6, 7, 8, 9, 10, 14])


def klasse_c():
    """(c) x4-LANEN puur: rijen 1,2,3,4,10,11,12,13 als lange woorden die BEIDE DWS-cellen
    nieuw dekken (x4).  Geen ankerrijen, dus geen enkele TWS."""
    mv = []
    mv.append(V(7, R(4, 10)))                       # center-bingo
    mv.append(V(7, R(1, 3)))                        # verticale brug naar de bovenlanen
    mv.append(V(7, R(11, 13)))
    for y, a, b in ((4, 4, 10), (3, 3, 11), (2, 2, 12), (1, 1, 13),
                    (10, 4, 10), (11, 3, 11), (12, 2, 12), (13, 1, 13)):
        inner = [x for x in R(a + 1, b - 1) if x != 7]
        for k in range(0, len(inner), 7):
            mv.append(H(y, inner[k:k + 7]))         # pre-cellen
        mv.append(H(y, [a, b]))                     # x4-completering (beide DWS nieuw)
    mv.append(V(4, [5, 6, 7, 8, 9]))                # kolom 4 dicht -> 13-run rows 1..13
    mv.append(V(10, [5, 6, 7, 8, 9]))
    return mv


def klasse_d():
    """(d) HYBRIDE: 3 ankerrijen + volle kolom 7 + 2 x4-rijlanen (rij 4 en 10) + klimkolommen."""
    mv = []
    mv.append(V(7, R(4, 10)))                       # center
    mv.append(V(7, R(1, 3)))                        # kolom 7 volledig (behalve de finals)
    mv.append(V(7, R(11, 13)))
    mv.append(H(4, [5, 6, 8, 9]))                   # rij-4 laan-pre (binnenkant)
    mv.append(H(4, [4, 10]))                        # x4: beide DWS nieuw (run 4..10)
    mv.append(H(4, [3, 11]))                        # laan-verlenging (herscoring x1)
    mv.append(H(10, [5, 6, 8, 9]))
    mv.append(H(10, [4, 10]))                       # x4
    mv.append(H(10, [3, 11]))
    mv.append(V(2, R(0, 6)))                        # klimkolom linksboven (bingo)
    mv.append(V(12, R(0, 6)))                       # klimkolom rechtsboven
    mv.append(V(2, R(8, 14)))                       # klimkolom linksonder
    mv.append(V(12, R(8, 14)))                      # klimkolom rechtsonder
    mv.append(H(0, [1, 3, 4]))
    mv.append(H(0, [10, 11, 13]))
    mv.append(H(14, [1, 3, 4]))
    mv.append(H(14, [10, 11, 13]))
    mv.append(H(7, [5, 6, 8, 9]))                   # rij-7 pre
    mv.append(H(7, [4, 10, 11]))
    mv.append(H(7, [0, 1, 2, 3, 12, 13, 14]))       # FINAL rij 7  x9
    mv.append(H(14, [0, 5, 6, 7, 8, 9, 14]))        # FINAL rij 14 x27 (+ kolom 7 x3)
    mv.append(H(0, [0, 5, 6, 7, 8, 9, 14]))         # FINAL rij 0  x27 (+ kolom 7 x3)
    return mv


def klasse_e():
    """(e) HERSCORINGSZWAAR: dezelfde ankerrijen, maar elke verticaal wordt STAPSGEWIJS
    verlengd (elke tussenstand herscoort de hele run) + post-finale extensies."""
    mv = []
    mv.append(V(7, R(4, 10)))
    mv.append(H(4, [3, 4, 5, 6, 8, 9, 10]))
    mv.append([(11, 4)])
    for c, ys in ((2, R(0, 6)), (5, [0, 1, 2, 3, 5, 6, 7]),
                  (10, [0, 1, 2, 3, 5, 6, 7]), (12, R(0, 6))):
        mv.append(V(c, ys[-3:]))                    # onderste stuk eerst (raakt rij 4/7)
        mv.append(V(c, ys[:-3]))                    # verlenging omhoog -> herscoort de run
    mv.append(H(0, [1]))
    mv.append(H(0, [4, 6]))
    mv.append(H(0, [9]))
    mv.append(H(10, [4, 5, 6, 8, 9, 10]))
    mv.append([(11, 10)])
    for c in (4, 11):
        ys = [y for y in R(8, 13) if (c, y) not in {(4, 10), (11, 10)}]
        mv.append(V(c, ys[:2]))                     # rijen 8,9
        mv.append(V(c, ys[2:]))                     # rijen 11..13 -> herscoort
    mv.append(V(9, R(11, 13)))
    mv.append(H(7, [4, 6, 8, 9, 11]))
    mv.append(H(7, [0, 1, 2, 3, 12, 13, 14]))       # FINAL rij 7
    mv.append(H(14, [4]))
    mv.append(H(14, [11]))
    mv.append(H(14, [5, 6]))
    mv.append(H(14, [8, 9, 10]))
    mv.append(H(14, [12]))
    mv.append(H(14, [0, 1, 2, 3, 7, 13, 14]))       # FINAL rij 14
    mv.append(H(0, [0, 3, 7, 8, 11, 13, 14]))       # FINAL rij 0
    return mv


def klasse_f_min2():
    """(f2) klasse (f) in min2-uitvoering: min-2-levering + kolom 7 dicht tot rij 13, zodat de
    rij-14-final het kolom-7-woord (rijen 4..14) x3 herscoort."""
    return klasse_a_min2(kol7=True)


def klasse_f():
    """(f) kolom 7 helemaal vol (rijen 1..13), zodat de rij-14-final EN de rij-0-final het
    kolom-7-woord elk x3 herscoren.  Kost 6 tegels."""
    return _anker3(kol7=True)


# --- NIEUW (bord-correctie): de onderhelft is weer premie-rijk -------------------
def klasse_g():
    """(g) ONDERLAAN RIJ 13: rij 13 heeft DWS (1,13)+(13,13) en - NIEUW NA DE BORDCORRECTIE -
    TLS (5,13)+(9,13).  De laan wordt met een brugzet gecompleteerd die beide DWS NIEUW dekt
    (x4 over de 13-run).  Vervangt de onderste losse verticalen van klasse (a)."""
    return _anker3(onderlaan=13)


def klasse_h():
    """(h) ONDERLAAN RIJ 12: DWS (2,12)+(12,12), DLS (6,12)+(8,12) (beide hersteld)."""
    return _anker3(onderlaan=12)


def klasse_i():
    """(i) ONDERLAAN RIJ 11: DWS (3,11)+(11,11), DLS (0,11)/(7,11)/(14,11) ((7,11) hersteld)."""
    return _anker3(onderlaan=11)


def klasse_j():
    """(j) kolom 7 vol + onderlaan rij 12 (de twee beste losse ingrepen gecombineerd)."""
    return _anker3(kol7=True, onderlaan=12)


KLASSEN = [
    ('a  anker3 (synth)',       klasse_a),
    ('a2 anker3 (min2-lever)',  klasse_a_min2),
    ("a' anker3 (record 4751)", klasse_a_record),
    ('b  FRAME 0/7/14',         klasse_b),
    ('b2 FRAME 2/7/12',         klasse_b2),
    ('b3 FRAME 0/14 partieel',  klasse_b3),
    ('c  x4-lanen puur',        klasse_c),
    ('d  hybride',              klasse_d),
    ('e  herscoringszwaar',     klasse_e),
    ('f  anker3 + volle kol 7', klasse_f),
    ('f2 f in min2-uitvoering', klasse_f_min2),
    ('g  anker3 + laan rij 13', klasse_g),
    ('h  anker3 + laan rij 12', klasse_h),
    ('i  anker3 + laan rij 11', klasse_i),
    ('j  kol 7 vol + laan 12',  klasse_j),
]


def analyse(name, moves, iters, verbose=True):
    cells = [c for mv in moves for c in mv]
    n = len(cells)
    ok, msg = legal(moves, why=True)
    out = {'naam': name, 'tegels': n, 'uniek': len(set(cells)), 'legaal': ok, 'msg': msg,
           'over_cap': max(0, n - CAP)}
    if not ok:
        if verbose: print(f'  !! {name}: ILLEGAAL SCHEMA -> {msg}')
        return out
    out['getrimd'] = 0
    if n > CAP:                                  # eerlijk vergelijken: zelfde tegelbudget
        moves, weg = trim_to_cap(moves)
        out['getrimd'] = len(weg)
        out['tegels_ruw'] = n
        out['tegels'] = n = sum(len(z) for z in moves)
    base, _ = M.score_of(moves)
    out['seed'] = base
    out['bingos_seed'] = sum(1 for mv in moves if len(mv) == 7)
    minzet, _ = search(moves, iters=iters, minsize=1, allow_split=False)
    m2seed, gedropt = to_min2(moves)
    out['min2_gedropte_cellen'] = len(gedropt)
    min2, _ = search(m2seed, iters=iters, minsize=2, allow_split=True) if m2seed else (0, [])
    vrij, mvrij = search(moves, iters=iters, minsize=1, allow_split=True)
    if minzet > vrij: vrij, mvrij = minzet, moves     # minzet-schema is ook vrij toegestaan
    out['vrij'], out['min2'], out['minzet'] = vrij, min2, minzet
    out['bingos_vrij'] = sum(1 for mv in mvrij if len(mv) == 7)
    m, non = profile(mvrij)
    out['m_som'] = sum(m.values())
    out['m_nonanker'] = sorted(non.items())
    out['ladder_delta'] = vrij - min2
    return out


def _job(name, iters):
    fn = dict((n, f) for n, f in KLASSEN)[name]
    return analyse(name, fn(), iters, verbose=False)


# ================================================================ CHIRURGIE OP HET RECORD
def drop_cells(moves, k, protect=()):
    """Offer k tegels op: steeds de cel met de LAAGSTE m waarvan het weghalen het schema
    legaal laat (ankerrijen en beschermde cellen blijven staan)."""
    cur = [list(m) for m in moves]
    weg = []
    prot = set(protect)
    while len(weg) < k:
        m = M.multiplicity(cur)
        for _, c in sorted((v, c) for c, v in m.items()):
            if c[1] in (0, 7, 14) or c in prot or c in weg: continue
            cand = [[q for q in z if q != c] for z in cur]
            cand = [z for z in cand if z]
            if legal(cand):
                cur = cand; weg.append(c); break
        else:
            return None, weg
    return cur, weg


def resect(moves, cel):
    """Snijd `cel` uit de zet die hem legt: die zet valt uiteen in een KOP (het stuk voor de
    cel, langs de lijn) en een STAART die pas gelegd kan worden nadat de cel er weer ligt.
    Nodig om een al bezette premiecel opnieuw als NIEUWE cel in een andere zet te gebruiken."""
    out, staart = [], []
    for z in moves:
        if cel in z:
            zz = sorted(z, key=lambda c: (c[1], c[0]))
            i = zz.index(cel)
            kop, staart = zz[:i], zz[i + 1:]
            if kop: out.append(kop)
        else:
            out.append(list(z))
    return out, staart


def reorder(moves):
    """Herorden een verzameling zetten tot een legale volgorde (first-fit): pak steeds de
    eerste zet die NU legaal is.  Nodig na een resectie: de staart van een doorgesneden
    zet moet naar achteren, en alles wat aan die staart hangt schuift mee."""
    rest = [list(m) for m in moves]
    out, placed = [], set()
    while rest:
        for i, z in enumerate(rest):
            s = set(z)
            if s & placed: continue
            if not out:
                if (7, 7) not in s: continue
            elif not any((x + dx, y + dy) in placed for (x, y) in z for dx, dy in M.NB):
                continue
            if not shape_ok(s, placed): continue
            out.append(z); placed |= s; rest.pop(i); break
        else:
            return None
    return out


def _apply(moves, nieuw):
    """Voeg de zetten `nieuw` toe en herorden tot een legaal schema."""
    return reorder([list(m) for m in moves] + [list(z) for z in nieuw])


def lex_reschedule(rec, grid, blanks, iters=20000, seeds=4):
    """Herordenen met de ECHTE arbiter: elke tussenstand moet woordenboek-legaal zijn.
    Dit meet hoeveel van de m-motor-speling (die het lexicon negeert) echt bestaat."""
    import maxgame_score as MG

    def sc(moves):
        tot, _, ok, _ = MG.score_game([r[:] for r in grid], [list(z) for z in moves], blanks)
        return int(tot) if ok else -1

    best, bestmv = sc(rec), [list(z) for z in rec]
    for s in range(seeds):
        rnd = random.Random(s)
        cur, curv = [list(z) for z in rec], best
        for _ in range(iters):
            cand = [list(z) for z in cur]
            op = rnd.random()
            idx = [i for i, m in enumerate(cand) if len(m) > 1]
            if op < 0.45 and idx:
                i = rnd.choice(idx); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
                if rnd.random() < 0.5: m = m[::-1]
                k = rnd.randrange(1, len(m))
                cand[i:i + 1] = [m[:k], m[k:]]
            elif op < 0.85 and len(cand) > 2:
                i = rnd.randrange(len(cand)); j = rnd.randrange(len(cand))
                if i == j: continue
                mv = cand.pop(i); cand.insert(j, mv)
            else:
                i = rnd.randrange(max(1, len(cand) - 1))
                if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                    cand[i:i + 2] = [cand[i] + cand[i + 1]]
            if not legal(cand): continue
            v = sc(cand)
            if v >= curv:
                if v > best: best, bestmv = v, [list(z) for z in cand]
                curv = v; cur = cand
    return best, bestmv


def surgery(iters=20000):
    """Concrete ingrepen op ons 4751-bord.  Het bord zit vol (101 tegels), dus elke toevoeging
    moet even veel tegels vrijmaken: we offeren steeds de cellen met de LAAGSTE m."""
    D = json.load(open(BEST))
    rec = [[tuple(c) for c in m] for m in D['moves']]
    g = D['grid']; blanks = set(tuple(b) for b in D['blanks'])
    fx_anker = {(x, y): g[y][x] for y in (0, 7, 14) for x in range(15) if g[y][x]}
    fx_all = {(x, y): g[y][x] for y in range(15) for x in range(15) if g[y][x]}
    occ = {c for mv in rec for c in mv}

    base_free, _ = M.score_of(rec, None)
    base_fix, _ = M.score_of(rec, fx_anker)
    base_exact, _ = M.score_of(rec, fx_all, zero=blanks)
    res = {'basis': {'vrij': base_free, 'ankervast': base_fix, 'exact': base_exact}}

    # (0) SCHEMA-ONLY: zelfde tegels, zelfde letters, andere zetvolgorde
    ex, exmv = multisearch(rec, iters, seeds=4, fixed=fx_all, zero=blanks)
    fr, _ = multisearch(rec, iters, seeds=4)
    fi, _ = multisearch(rec, iters, seeds=4, fixed=fx_anker)
    lexbest, lexmv = lex_reschedule(rec, g, blanks, iters=min(iters, 4000), seeds=3)
    res['schema-only'] = {'vrij': fr, 'ankervast': fi, 'exact': ex, 'lexicaal_geldig': lexbest,
                          'zetten': len(exmv), 'bingos': sum(1 for z in exmv if len(z) == 7)}
    res['schema-only_moves'] = [[list(c) for c in z] for z in exmv]
    res['lex_moves'] = [[list(c) for c in z] for z in lexmv]

    # (1..n) structurele ingrepen: (naam, toegevoegde cellen, nieuwe zetten, beschermd, resect)
    ingrepen = []
    # rij-10 x4-laan: (4,10) uit de kolom-4-zet SNIJDEN en samen met (10,10) NIEUW leggen,
    # zodat die zet beide DWS van rij 10 nieuw dekt -> x4 over de run x=4..10
    lane10 = [(x, 10) for x in (5, 6, 8, 9, 10) if (x, 10) not in occ]
    ingrepen.append(('rij-10 x4-laan', lane10,
                     [[c for c in lane10 if c != (10, 10)], [(4, 10), (10, 10)]],
                     {(4, 10)}, (4, 10)))
    # onderlanen: vul rij y tussen de DWS en completeer met de 2 DWS-cellen (x4 over de run)
    for y in (11, 12, 13):
        dws = [x for x in range(15) if M.WM[y][x] == 2]
        pre = [x for x in R(dws[0] + 1, dws[1] - 1) if (x, y) not in occ]
        add = [(x, y) for x in pre] + [(x, y) for x in dws if (x, y) not in occ]
        zetten = [[(x, y) for x in pre[k:k + 7]] for k in range(0, len(pre), 7)]
        zetten.append([(x, y) for x in dws if (x, y) not in occ])
        ingrepen.append((f'onderlaan rij {y}', add, zetten, set(), None))
    # kolom 7 vol (klasse f op ons bord)
    k7 = [(7, y) for y in list(R(1, 3)) + list(R(11, 13)) if (7, y) not in occ]
    ingrepen.append(('kolom 7 vol (1..13)', k7, [[(7, y) for y in R(1, 3)],
                                                 [(7, y) for y in R(11, 13)]], set(), None))
    ingrepen.append(('kolom 7 onder (11..13)', [(7, y) for y in R(11, 13)],
                     [[(7, y) for y in R(11, 13)]], set(), None))
    # kolom-x4: de kolommen 3 en 11 hebben DWS op rij 3 EN rij 11.  Als één zet ze allebei
    # NIEUW dekt (brugzet over de al liggende tegels) scoort de hele kolomrun x4.
    for c in (11, 3):
        gat = [(c, y) for y in R(4, 10) if (c, y) not in occ]
        add = gat + [(c, 3)] + ([(c, 11)] if (c, 11) not in occ else [])
        zet = ([gat[k:k + 7] for k in range(0, len(gat), 7)] if gat else []) + [[(c, 3), (c, 11)]]
        ingrepen.append((f'kolom {c} x4 (DWS 3+11)', add, zet, {(c, 11)},
                         (c, 11) if (c, 11) in occ else None))
    # combinaties
    dws13 = [(1, 13), (13, 13)]
    pre13 = [(x, 13) for x in R(2, 12) if (x, 13) not in occ and (x, 13) not in k7]
    ingrepen.append(('kolom 7 vol + onderlaan 13', k7 + pre13 + dws13,
                     [[(7, y) for y in R(1, 3)], [(7, y) for y in R(11, 13)]]
                     + [pre13[k:k + 7] for k in range(0, len(pre13), 7)] + [dws13],
                     set(), None))
    ingrepen.append(('kolom 7 vol + rij-10-laan', k7 + lane10,
                     [[(7, y) for y in R(1, 3)],
                      [c for c in lane10 if c != (10, 10)], [(4, 10), (10, 10)],
                      [(7, y) for y in R(11, 13)]], {(4, 10)}, (4, 10)))

    # de centrumkolom (openingsbingo) is de ruggengraat waar alle nieuwe structuur aan hangt
    ruggengraat = {(7, y) for y in R(4, 10)} | {(4, 10), (11, 10), (4, 14), (11, 7)}
    for naam, add, zetten, prot, snij in ingrepen:
        k = len([c for c in add if c not in occ])
        kaal, weg = drop_cells(rec, k, protect=prot | set(add) | ruggengraat)
        if kaal and snij:
            kaal, staart = resect(kaal, snij)
            zetten = list(zetten) + ([staart] if staart else [])
        mv = _apply(kaal, [z for z in zetten if z]) if kaal else None
        row = {'nieuwe_tegels': k, 'geofferd': sorted(weg)}
        if mv is None:
            row['status'] = 'niet legaal in te passen'
        else:
            n = sum(len(z) for z in mv)
            fr, frm = multisearch(mv, iters, seeds=3)
            fi, _ = multisearch(mv, iters, seeds=3, fixed=fx_anker)
            row.update({'status': 'ok', 'tegels': n, 'vrij': fr, 'ankervast': fi,
                        'd_vrij': fr - res['schema-only']['vrij'],
                        'd_ankervast': fi - res['schema-only']['ankervast'],
                        'bingos': sum(1 for z in frm if len(z) == 7)})
        res[naam] = row
    return res


def main():
    iters = int(os.environ.get('ITERS', '20000'))
    ok, info = board_check()
    print(f'BORD-CHECK: {info}  -> {"ECHT SCRABBLEBORD" if ok else "AFWIJKEND BORD!"}')
    assert ok, 'data/boards.toml is geen standaard scrabblebord meer'
    print(f'ITERS={iters}  CAP={CAP} tegels')

    D = json.load(open(BEST))
    rmv = [[tuple(c) for c in m] for m in D['moves']]
    g = D['grid']; blanks = set(tuple(b) for b in D['blanks'])
    fx = {(x, y): g[y][x] for y in (0, 7, 14) for x in range(15) if g[y][x]}
    fx_all = {(x, y): g[y][x] for y in range(15) for x in range(15) if g[y][x]}
    c_fix, _ = M.score_of(rmv, fx)
    c_free, _ = M.score_of(rmv, None)
    c_exact, _ = M.score_of(rmv, fx_all, zero=blanks)
    tot = D['total']
    print(f'IJKING record {tot}: m-calculus exact {c_exact} (moet {tot} zijn), '
          f'plafond met ankerletters {c_fix}, vrij plafond {c_free}')
    gr_free, gr_fix = tot / c_free, tot / c_fix
    print(f'  realisatiegraad t.o.v. vrij plafond {gr_free:.3f}, t.o.v. ankervast {gr_fix:.3f}')
    for doel in (4819, 5000):
        print(f'  => voor {doel} is ~{int(doel / gr_free)} vrij plafond nodig '
              f'(of {int(doel / gr_fix)} ankervast plafond)')

    with Pool(min(len(KLASSEN), 12)) as pool:
        rows = pool.starmap(_job, [(n, iters) for n, _ in KLASSEN])
    print()
    print('=== TABEL (gesorteerd op vrij plafond) ===')
    print(f"{'klasse':26s} {'tegels':>6s} {'vrij':>6s} {'min2':>6s} {'minzet':>7s} {'ladder':>7s}"
          f" {'m-som':>6s}")
    for r in sorted([x for x in rows if x['legaal']], key=lambda x: -x['vrij']):
        print(f"{r['naam']:26s} {r['tegels']:6d} {r['vrij']:6d} {r['min2']:6d} "
              f"{r['minzet']:7d} {r['ladder_delta']:7d} {r['m_som']:6d}"
              + (f"  (getrimd -{r['getrimd']} van {r['tegels_ruw']})" if r.get('getrimd') else ''))
    for r in rows:
        if not r['legaal']:
            print(f"  !! {r['naam']}: ILLEGAAL -> {r['msg']}")
    json.dump(rows, open('/home/bob/programming/scrabble4/experiments/results/'
                         'classceiling.json', 'w'), indent=1)

    if os.environ.get('SURGERY'):
        print()
        print('=== CHIRURGIE OP HET 4751-BORD (101 tegels vol: elke toevoeging offert m-arme cellen) ===')
        s = surgery(iters)
        print(f"basis      : {s['basis']}")
        so = s['schema-only']
        print(f"schema-only: vrij {so['vrij']} ankervast {so['ankervast']} EXACT {so['exact']} "
              f"(+{so['exact'] - s['basis']['exact']} met dezelfde letters, maar het lexicon "
              f"negerend) zetten {so['zetten']} bingo's {so['bingos']}")
        print(f"  met woordenboekcontrole (score_game als arbiter): {so['lexicaal_geldig']} "
              f"({so['lexicaal_geldig'] - s['basis']['exact']:+d})")
        for k, v in s.items():
            if k in ('basis', 'schema-only', 'schema-only_moves', 'lex_moves'): continue
            if v['status'] != 'ok':
                print(f"{k:24s} {v['status']}")
            else:
                print(f"{k:24s} +{v['nieuwe_tegels']:2d} tegels, tegels={v['tegels']:3d} "
                      f"vrij {v['vrij']:5d} ({v['d_vrij']:+5d})  ankervast {v['ankervast']:5d} "
                      f"({v['d_ankervast']:+5d})  bingo {v['bingos']}")
                print(f"{'':24s}   geofferd: {v['geofferd']}")
        json.dump(s, open('/home/bob/programming/scrabble4/experiments/results/'
                          'classceiling_surgery.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
