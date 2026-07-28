"""KLASSE-PLAFONDS: welke GEOMETRIE-KLASSE heeft genoeg bovengrens?

Gebruikt de m-motor (mg_mceiling): score = SOM_c m(c)*waarde(c) + 50*#bingo's, met m puur uit
geometrie + zetvolgorde.  Hier bouwen we per klasse een representatieve BEZETTING + ZETSCHEMA
(cellen, geen woorden) en rekenen het plafond uit.

Drie regimes per klasse (ladder-afhankelijkheid):
  vrij    - elke legale zet (ook 1-tegel-zetten): maximale ladder-vrijheid
  min2    - elke zet legt >=2 tegels
  minzet  - geen splitsingen: elke lijn in zo min mogelijk zetten (canoniek schema)

Alle regimes eisen ECHTE zet-vorm: een zet ligt op EEN lijn en de run tussen min en max moet
volledig gevuld zijn (mg_mceiling.legal_schedule checkt dat NIET -> zie --shapefree).

CLI:  .venv/bin/python experiments/mg_classceiling.py [ITERS=20000] [BOARD=repo|std]
"""
import sys, os, json, random
from multiprocessing import Pool
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import mg_mceiling as M

CAP = 101                      # bord <= 101 tegels (tegenstander houdt er minstens 1)

# ---------------------------------------------------------------- bord-varianten
# data/boards.toml mist in de ONDERSTE helft 7 letterpremies (asymmetrisch t.o.v. een
# standaard scrabblebord).  BOARD=std herstelt ze (spiegeling van de bovenhelft).
STD_LM = None


def use_board(kind):
    global STD_LM
    if kind == 'repo':
        return
    lm = [row[:] for row in M.LM]
    for y in range(8, 15):                     # spiegel rij 14-y
        lm[y] = M.LM[14 - y][:]
    STD_LM = lm
    M.LM = lm


def missing_premies():
    out = []
    for y in range(8, 15):
        for x in range(15):
            if M.LM[y][x] != M.LM[14 - y][x]:
                out.append(((x, y), M.LM[14 - y][x], M.LM[y][x]))
    return out


# ---------------------------------------------------------------- legaliteit (streng)
def shape_ok(mv, placed):
    """Zet ligt op EEN lijn en vormt met het bestaande bord een aaneengesloten run."""
    xs = {x for x, y in mv}; ys = {y for x, y in mv}
    if len(xs) > 1 and len(ys) > 1: return False
    if len(xs) == 1:
        x = next(iter(xs)); a, b = min(ys), max(ys)
        return all((x, y) in placed or (x, y) in mv for y in range(a, b + 1))
    y = next(iter(ys)); a, b = min(xs), max(xs)
    return all((x, y) in placed or (x, y) in mv for x in range(a, b + 1))


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
def search(seed_moves, iters=20000, minsize=1, allow_split=True, shape=True, seed=0, fixed=None):
    rnd = random.Random(seed)
    cur = [list(m) for m in seed_moves]
    best, _ = M.score_of(cur, fixed)
    bestmv = [list(m) for m in cur]
    for _ in range(iters):
        cand = [list(m) for m in cur]
        op = rnd.random()
        idx = [i for i, m in enumerate(cand) if len(m) > max(1, minsize)]
        if allow_split and op < 0.45 and idx:
            i = rnd.choice(idx); m = cand[i]
            k = rnd.randrange(1, len(m))
            rnd.shuffle(m)
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
        sc, _ = M.score_of(cand, fixed)
        if sc >= best:
            if sc > best: bestmv = [list(m) for m in cand]
            best = sc; cur = cand
    return best, bestmv


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
    return _anker3(kol7=False)


def _anker3(kol7=False):
    """Gedeelde bouwer voor (a) en (f).  kol7=True vult kolom 7 helemaal (rijen 1..13) zodat
    beide x27-finals het kolom-7-woord herscoren."""
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
    mv.append(V(4, R(11, 13)) if kol7 else V(4, [8, 9, 11, 12, 13]))
    mv.append(V(11, [8, 9, 11, 12, 13]))
    if not kol7:
        mv.append(V(9, R(11, 13)))
        mv.append(H(14, [9]))
    mv.append(H(7, [0, 1, 2, 3, 4, 13, 14]))        # FINAL rij 7  -> x9
    mv.append(H(14, [4]))
    mv.append(H(14, [11]))
    mv.append(H(14, [5, 6]))
    mv.append(H(14, [12]))
    mv.append(H(14, [8, 9, 10]) if kol7 else H(14, [10]))
    if not kol7: mv.append(H(14, [8]))
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
    """(a') hetzelfde, maar de ECHTE bezetting+zetvolgorde van ons 4531-record."""
    D = json.load(open('/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json'))
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
    """(f) GOEDKOOPSTE INGREEP op klasse (a): kolom 7 helemaal vol (rijen 1..13), zodat de
    rij-14-final EN de rij-0-final het kolom-7-woord elk x3 herscoren.  Kost 6 tegels."""
    return _anker3(kol7=True)


KLASSEN = [
    ('a  anker3 (synth)',       klasse_a),
    ('a2 anker3 (min2-lever)',  klasse_a_min2),
    ("a' anker3 (record 4531)", klasse_a_record),
    ('b  FRAME 0/7/14',         klasse_b),
    ('b2 FRAME 2/7/12',         klasse_b2),
    ('b3 FRAME 0/14 partieel',  klasse_b3),
    ('c  x4-lanen puur',        klasse_c),
    ('d  hybride',              klasse_d),
    ('e  herscoringszwaar',     klasse_e),
    ('f  anker3 + volle kol 7', klasse_f),
    ('f2 f in min2-uitvoering', klasse_f_min2),
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
    base, _ = M.score_of(moves)
    out['seed'] = base
    out['bingos_seed'] = sum(1 for mv in moves if len(mv) == 7)
    # regimes
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
    out['best_moves'] = mvrij
    return out


def _job(name, board, iters):
    use_board(board)
    fn = dict((n, f) for n, f in KLASSEN)[name]
    return analyse(name, fn(), iters, verbose=False)


def main():
    board = os.environ.get('BOARD', 'repo')
    iters = int(os.environ.get('ITERS', '20000'))
    use_board(board)
    print(f'BORD={board}  ITERS={iters}  CAP={CAP} tegels')
    if board == 'repo':
        mis = missing_premies()
        if mis:
            print(f'LET OP: data/boards.toml mist {len(mis)} letterpremies in de onderhelft: '
                  + ', '.join(f'{c}:{a}->{b}' for c, a, b in mis))
    # ijking op het record: vrij plafond (zonder letters) vs plafond met de ECHTE ankerletters
    D = json.load(open('/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json'))
    rmv = [[tuple(c) for c in m] for m in D['moves']]
    g = D['grid']
    fx = {(x, y): g[y][x] for y in (0, 7, 14) for x in range(15) if g[y][x]}
    c_fix, _ = M.score_of(rmv, fx)
    c_free, _ = M.score_of(rmv, None)
    shape_blind, sb_mv = M.best_schedule(rmv, fx, iters=4000)
    shape_aware, _ = search(rmv, iters=4000, fixed=fx)
    print(f'IJKING record 4531: plafond met echte ankerletters {c_fix}, zonder letters {c_free} '
          f'(letterverlies {c_free - c_fix}); gerealiseerd {D["total"]} '
          f'=> realisatiegraad {D["total"] / c_free:.3f}')
    print(f'  herschema met ankerletters: vormBLIND {shape_blind} '
          f'(legaal van vorm: {legal(sb_mv)}), vormBEWUST {shape_aware}')
    print(f'  => een klasse moet ~{int(4819 / (D["total"] / c_free))} vrij plafond halen om 4819 '
          f'te kunnen realiseren bij dezelfde realisatiegraad')
    with Pool(min(len(KLASSEN), 12)) as pool:
        rows = pool.starmap(_job, [(n, board, iters) for n, _ in KLASSEN])
    for r in rows:
        name = r['naam']
        if r['legaal']:
            print(f"{name:26s} tegels={r['tegels']:3d} seed={r['seed']:5d} "
                  f"vrij={r['vrij']:5d} min2={r['min2']:5d} (gedropt {r['min2_gedropte_cellen']:2d}) "
                  f"minzet={r['minzet']:5d} bingo={r['bingos_vrij']:2d} m-som={r['m_som']:5d}"
                  + ('  << OVER CAP' if r['over_cap'] else ''))
            print(f"{'':26s} m niet-anker: {r['m_nonanker']}")
    print()
    print('=== TABEL (gesorteerd op vrij plafond) ===')
    print(f"{'klasse':26s} {'tegels':>6s} {'vrij':>6s} {'min2':>6s} {'minzet':>7s} {'ladder':>7s}")
    for r in sorted([x for x in rows if x['legaal']], key=lambda x: -x['vrij']):
        print(f"{r['naam']:26s} {r['tegels']:6d} {r['vrij']:6d} {r['min2']:6d} "
              f"{r['minzet']:7d} {r['ladder_delta']:7d}")
    json.dump([{k: v for k, v in r.items() if k != 'best_moves'} for r in rows],
              open('/home/bob/programming/scrabble4/experiments/results/classceiling_%s.json' % board, 'w'),
              indent=1)


if __name__ == '__main__':
    main()
