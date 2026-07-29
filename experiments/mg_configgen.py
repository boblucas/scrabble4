"""CONFIGURATIE-GENERATOR: systematische opsomming van STRUCTUURPARAMETERS.

De LNS-vloot muteert celverzamelingen en blijft daardoor in hetzelfde dal (gemeten: 0 van 24
mutaties haalt de arbiter).  Deze module somt in plaats daarvan de PARAMETERS op waaruit ons
bord in werkelijkheid is opgebouwd, en laat een filterketen van goedkoop naar duur beslissen.

DE PARAMETERISERING (onderbouwing in experiments/CONFIGGEN.md)
-------------------------------------------------------------
Vast (bewezen optimaal, zie LETTERBUDGET.md / MASKGEOM.md):
  * triplet geschenkcheques / flexwerkstertje / polymelkzuurtje op rij 0 / 7 / 14
  * de drie slotmaskers REC (rij 0 {0,3,7,8,11,13,14}, rij 7 {0,1,2,3,12,13,14},
    rij 14 {0,1,2,3,7,13,14})
Vrij:
  * per rij-0-eiland ({1,2} {4,5,6} {9,10} {12}) een DRAGENDE kolom die rij 1 haalt   (eiland-lemma)
  * per rij-14-eiland ({4,5,6} {8..12}) een dragende kolom die rij 13 haalt
  * de DIEPTE van elke dragende kolom (waar zijn verticaal ophoudt), incl. doorlopen door rij 7
  * de CENTRUMKOLOM 7 (moet (7,7) in zet 1 leggen): boven- en ondergrens
  * nul, een of twee horizontale LANEN (rij + spanwijdte) in de banden 1..6 en 8..13
  * losse ROW7-HANGERS: extra kolommen die aan rij 7 hangen
  * LAANHANGERS: kolommetjes van 1-2 cellen aan een laan
  * de PEEL: hoeveel bladcellen post-final een voor een worden gelegd (de extensieketen)

Alles samen ligt in de orde 10^6-10^7 punten; het RECORD is er een van (calibratie: MODE=calib).

DE FILTERKETEN (oplopende kosten; de zak vroeg)
-----------------------------------------------
  F1 vorm/tegelcap        : <=101 tegels, elke run >=2, geen zwevende cellen        (us)
  F2 eiland/bezorging     : elk pre-eiland van rij 0/7/14 heeft een drager;
                            elke cel is bereikbaar (component raakt rij 7 of een laan) (us)
  F3 zak-lexicaal per run : bestaat er een woord op de vaste ankerletters DAT OOK
                            uit de restzak te bouwen is?  (gecachet, us)               <-- ZAK VROEG
  F4 schema               : deterministische bouwer + peel-varianten                  (ms)
  F5 m-plafond            : exacte zak-bovengrens; < record+1 => weg                  (0,3 ms)
  F6 lijnconsistentie     : mg_newtopo.diagnose (alle runs op een lijn door EEN woord) (ms)
  F7 CP-SAT beslissing    : fit_decide(schema, target=record+1); NEE = bewijs          (minuten)
  F8 arbiter              : MG.score_game, alleen ok=True telt

BELANGRIJKE MEETUITKOMST (zie CONFIGGEN.md 3): het m-plafond discrimineert in dit stadium
nauwelijks meer -- 192 buren van het record liggen binnen 30 plafondpunten van elkaar terwijl het
record 110 punten onder zijn eigen plafond realiseert.  De selectie voor F7 gebeurt daarom op
STRUCTURELE SPREIDING (pick_diverse) in plaats van puur op plafond.

CLI (zie ook experiments/mg_configgen_run.sh)
--------------------------------------------
  MODE=calib                                     # record reproduceren + ijking
  MODE=enum   SHARD=k NSHARD=10 TMIN=56 TMAX=56  # fase 1: skeletten
  MODE=expand IN=<dir> TOPN=4000                 # fase 2: extra kolommen + laanhangers
  MODE=refine IN=<dir> TOPN=2000                 # fase 3: vol schema + lijnconsistentie
  MODE=decide IN=<dir> TOPN=300 TARGET=4794      # fase 4: CP-SAT beslissingsvorm
  MODE=fit    IN=<dir> TOPN=40 TLIM=900          # fase 4b: CP-SAT maximaliseren
  MODE=stats  IN=<dir>                           # filtertellingen + plafond-histogram
"""
import os, sys, json, time, itertools, random
from collections import Counter

sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG
import mg_mceiling as mc
import mg_newtopo as T

r = MG.r
cba = r.alphabet.cba
INV = {v: k for k, v in cba.items()}
BAG = Counter({c: r.counts[c] for c in r.counts})
NBLANK = r.blank_count
FIXED = T.FIXED
BYLEN = T.BYLEN
CAP = 101
RES = '/home/bob/programming/scrabble4/experiments/results'
SCRATCH = ('/tmp/claude-1000/-home-bob-programming-scrabble4/'
           'da7ed622-7493-428d-96da-a3b3144f633e/scratchpad')

MASKS = {0: (0, 3, 7, 8, 11, 13, 14), 7: (0, 1, 2, 3, 12, 13, 14),
         14: (0, 1, 2, 3, 7, 13, 14)}
ANCHOR_ROWS = (0, 7, 14)


def _islands(pre):
    out, cur = [], []
    for x in range(15):
        if x in pre:
            cur.append(x)
        elif cur:
            out.append(tuple(cur)); cur = []
    if cur: out.append(tuple(cur))
    return out


PRE = {y: tuple(x for x in range(15) if x not in MASKS[y]) for y in ANCHOR_ROWS}
ISL = {y: _islands(PRE[y]) for y in ANCHOR_ROWS}
# rij 0: [(1,2),(4,5,6),(9,10),(12)] ; rij 7: [(4..11)] ; rij 14: [(4,5,6),(8..12)]
ISL0, ISL14 = ISL[0], ISL[14]

# ------------------------------------------------------------------ RESTZAK (de zak-toets)
# De 45 ankercellen liggen vast; wat overblijft is alles wat de 56 vrije cellen mogen gebruiken.
ANCHOR_LETTERS = Counter(FIXED[(x, y)] for y in ANCHOR_ROWS for x in range(15))
REST = Counter({ch: BAG[ch] - ANCHOR_LETTERS.get(ch, 0) for ch in BAG})
REST_TOT = sum(REST.values())            # 55 lettertegels
REST_SET = {ch for ch, n in REST.items() if n > 0}


# ------------------------------------------------------------------ F3: zak-lexicale runtoets
_RUNCACHE = {}


def run_bag_ok(run):
    """Bestaat er een woord van deze lengte dat (a) op de vaste ankerletters van deze run past
    EN (b) waarvan de VRIJE posities uit de restzak te bouwen zijn (met <=2 blanco's)?

    Dit is strikt sterker dan `table_nonempty` en kost hetzelfde: het is de zaktoets op run-
    niveau, en juist die was in eerder werk de gemiste zeef (m-plafond is zak-BEWUST maar niet
    zak-LEXICAAL).  Cache-sleutel = (lengte, vaste posities) -- er zijn er maar enkele honderden.
    """
    key = (len(run),) + tuple((i, FIXED[c]) for i, c in enumerate(run) if c in FIXED)
    hit = _RUNCACHE.get(key)
    if hit is not None:
        return hit
    L, fx = key[0], key[1:]
    free_idx = [i for i in range(L) if i not in {j for j, _ in fx}]
    hit = False
    for w in BYLEN.get(L, ()):
        if not all(w[i] == v for i, v in fx):
            continue
        need = Counter(w[i] for i in free_idx)
        short = sum(max(0, n - REST[ch]) for ch, n in need.items())
        if short <= NBLANK:
            hit = True
            break
    _RUNCACHE[key] = hit
    return hit


# ------------------------------------------------------------------ geometrie
def cells_of(cfg):
    """cfg: {'cols': {x: [(a,b), ...]}, 'lanes': [(y, x0, x1), ...]}.  Rijen 0/7/14 altijd vol."""
    occ = {(x, y) for y in ANCHOR_ROWS for x in range(15)}
    for x, ivs in cfg['cols'].items():
        for (a, b) in ivs:
            occ |= {(x, y) for y in range(a, b + 1)}
    for (y, x0, x1) in cfg['lanes']:
        occ |= {(x, y) for x in range(x0, x1 + 1)}
    return occ


def vruns(occ):
    """maximale verticale runs (>=2)"""
    out = []
    for x in range(15):
        y = 0
        while y < 15:
            if (x, y) not in occ:
                y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (x, y1 + 1) in occ:
                y1 += 1
            if y1 > y:
                out.append([(x, k) for k in range(y, y1 + 1)])
            y = y1 + 1
    return out


def hruns(occ):
    out = []
    for y in range(15):
        x = 0
        while x < 15:
            if (x, y) not in occ:
                x += 1; continue
            x1 = x
            while x1 + 1 < 15 and (x1 + 1, y) in occ:
                x1 += 1
            if x1 > x:
                out.append([(k, y) for k in range(x, x1 + 1)])
            x = x1 + 1
    return out


def f1_shape(occ):
    """tegelcap en geen losse (niet-aangrenzende) cel buiten de ankerrijen"""
    if len(occ) > CAP:
        return 'cap'
    for c in occ:
        x, y = c
        if y in ANCHOR_ROWS:
            continue
        if not any((x + dx, y + dy) in occ for dx, dy in mc.NB):
            return 'zwevend'
    return None


def f2_delivery(occ):
    """eiland-lemma + bereikbaarheid.

    (a) elk pre-eiland van rij 0 heeft een kolom met (x,1) bezet; idem rij 14 met (x,13).
    (b) elke vrije cel hangt (via vrije cellen) aan rij 7 of aan een cel die zelf aan rij 7 hangt
        -- de enige structuur die er tijdens de bouw al ligt.  Cellen in rij 1..6 die alleen aan
        rij 0 hangen zijn ONBEZORGBAAR: rij 0 komt pas in de slotzet.
    """
    for g in ISL0:
        if not any((x, 1) in occ for x in g):
            return 'rij0-eiland'
    for g in ISL14:
        if not any((x, 13) in occ for x in g):
            return 'rij14-eiland'
    # bereikbaarheid: floodfill door de VRIJE cellen, startend bij de buren van rij 7
    free = {c for c in occ if c[1] not in ANCHOR_ROWS}
    seed = [c for c in free if c[1] in (6, 8)]
    seen = set(seed); stack = list(seed)
    while stack:
        x, y = stack.pop()
        for dx, dy in mc.NB:
            n = (x + dx, y + dy)
            if n in free and n not in seen:
                seen.add(n); stack.append(n)
    if len(seen) != len(free):
        return 'onbereikbaar'
    return None


VOW = {cba[c] for c in 'aeiouy'}
REST_VOW = sum(n for ch, n in REST.items() if ch in VOW and n > 0)
_VCACHE = {}


def run_min_vowels(run):
    """Het MINIMALE aantal klinkers dat deze run op zijn VRIJE posities nodig heeft, over alle
    woorden die op de vaste ankerletters passen.  Verticale runs zijn onderling disjunct, dus de
    som over alle verticale runs is een geldige ondergrens op het klinkerverbruik."""
    key = (len(run),) + tuple((i, FIXED[c]) for i, c in enumerate(run) if c in FIXED)
    hit = _VCACHE.get(key)
    if hit is not None:
        return hit
    L, fx = key[0], key[1:]
    free_idx = [i for i in range(L) if i not in {j for j, _ in fx}]
    best = None
    for w in BYLEN.get(L, ()):
        if not all(w[i] == v for i, v in fx):
            continue
        n = sum(1 for i in free_idx if w[i] in VOW)
        if best is None or n < best:
            best = n
            if best == 0:
                break
    hit = 999 if best is None else best
    _VCACHE[key] = hit
    return hit


def f3b_vowels(occ):
    """GLOBALE zakzeef: de verticale runs zijn disjunct, dus hun minimale klinkerbehoefte telt
    op.  De restzak heeft er maar 23 (plus 2 blanco's) -- bij zeven lange verticalen zit dat
    tegen de grens aan.  NEE hier weerlegt de bezetting zonder een schema te bouwen."""
    need = sum(run_min_vowels(run) for run in vruns(occ))
    return need > REST_VOW + NBLANK


_WSET = {L: set(ws) for L, ws in BYLEN.items()}
_CHAINCACHE = {}


def chain_len(run, side='tail', maxL=8):
    """De LEXICAAL ondersteunde ketenlengte van een run.

    Een verlengketen levert per tegel meer op dan een bingo (gemeten op het record: de
    kolom-2-keten 'smarots' -> 'smarotsenden' geeft 176 punten voor 11 tegels = 16,0/tegel,
    tegen 12,8/tegel voor de zeven gewone bingo's), MAAR hij eist dat ELKE tussenstand zelf een
    woord is.  Deze functie telt hoe ver dat lexicaal kan: het grootste L waarvoor er een woord
    bestaat dat op de ankerletters past en waarvan de L opeenvolgende afkappingen (aan de
    staart- of kopkant) ook allemaal woorden zijn die op HUN ankerletters passen.

    Gecachet op (lengte, ankerpatroon, kant); er zijn maar enkele honderden patronen."""
    n = len(run)
    fx = tuple((i, FIXED[c]) for i, c in enumerate(run) if c in FIXED)
    key = (n, fx, side, maxL)
    hit = _CHAINCACHE.get(key)
    if hit is not None:
        return hit
    fxd = dict(fx)
    best = 0
    for w in BYLEN.get(n, ()):
        if not all(w[i] == v for i, v in fx):
            continue
        L = 0
        for k in range(1, min(maxL, n - 2) + 1):
            sub = w[:n - k] if side == 'tail' else w[k:]
            if sub not in _WSET.get(len(sub), ()):
                break
            off = 0 if side == 'tail' else k
            if not all(sub[i - off] == v for i, v in fx if off <= i < off + len(sub)):
                break
            L = k
        if L > best:
            best = L
            if best >= min(maxL, n - 2):
                break
    _CHAINCACHE[key] = best
    return best


def ext_potential(occ, maxL=8):
    """Hoeveel bladcellen kan deze bezetting ECHT verlengen: per verticale run het minimum van
    (a) het aantal cellen dat er aan die kant afgepeld kan worden en (b) de lexicaal
    ondersteunde ketenlengte.  Dit is de as die de rangschikking hoort te sturen -- niet het
    aantal bingo's."""
    o = set(occ)
    tot, det = 0, []
    for run in vruns(occ):
        x = run[0][0]
        y0, y1 = run[0][1], run[-1][1]
        for side, ycell in (('tail', y1), ('head', y0)):
            # hoeveel cellen aan deze kant zijn vrije (niet-anker) cellen met een vrije buiten-buur
            k = 0
            step = -1 if side == 'tail' else 1
            y = ycell
            while 0 <= y < 15 and (x, y) in o and y not in ANCHOR_ROWS and len(run) - k > 2:
                nb = (x, y - step)
                if nb in o and nb[1] not in ANCHOR_ROWS:
                    pass
                k += 1
                y += step
                if k >= maxL:
                    break
            if k == 0:
                continue
            L = min(k, chain_len(run, side, maxL))
            if L > 0:
                tot += L; det.append((x, y0, y1, side, L))
    return tot, det


_SUBCACHE = {}


def sub_ok(final_run, i, j):
    """Bestaat er EEN woord voor de eindrun dat op de ankerletters past en waarvan het stuk
    [i:j] zelf ook een woord is dat op ZIJN ankerletters past?

    Dit is de paarsgewijze versie van `mg_newtopo.diagnose` en de goedkoopste manier om de
    ladderillusie al tijdens het bouwen te vermijden: elke TIJDELIJKE run die een zet maakt is
    een deelstuk van de uiteindelijke run op die lijn, en moet zelf een woord zijn.  Gemeten
    zonder deze test: 0 van 60 bezettingen levert een lijnconsistent schema."""
    n = len(final_run)
    fx = tuple((k, FIXED[c]) for k, c in enumerate(final_run) if c in FIXED)
    key = (n, fx, i, j)
    hit = _SUBCACHE.get(key)
    if hit is not None:
        return hit
    sub_fx = [(k - i, v) for k, v in fx if i <= k < j]
    hit = False
    for w in BYLEN.get(n, ()):
        if not all(w[k] == v for k, v in fx):
            continue
        s = w[i:j]
        if s in _WSET.get(len(s), ()) and all(s[k] == v for k, v in sub_fx):
            hit = True
            break
    _SUBCACHE[key] = hit
    return hit


def _final_run_of(c, horiz, finmap):
    return finmap.get(('H' if horiz else 'V', c))


def move_bag_ok(placed, move, finmap=None):
    """elke run die deze zet raakt moet (a) een zak-bouwbaar woord toelaten en (b), als hij nog
    niet de EINDrun van zijn lijn is, een deelstuk zijn dat samen met die eindrun bestaat"""
    for run in T.move_runs(placed, move):
        if not run_bag_ok(run):
            return False
        if finmap is None:
            continue
        horiz = run[0][1] == run[-1][1]
        fr = finmap.get(('H' if horiz else 'V', run[0]))
        if fr is None:
            fr = finmap.get(('H' if horiz else 'V', run[0]), None)
        if fr is None or len(fr) == len(run):
            continue
        pos = fr.index(run[0])
        if not sub_ok(fr, pos, pos + len(run)):
            return False
    return True


def f3_bagwords(occ):
    """elke maximale run van het EINDbord moet een zak-bouwbaar woord toelaten"""
    for run in vruns(occ):
        if not run_bag_ok(run):
            return ('V', run[0][0], len(run))
    for run in hruns(occ):
        if not run_bag_ok(run):
            return ('H', run[0][1], len(run))
    return None


# ------------------------------------------------------------------ F4: schemabouwer
def _segments(occ):
    """alle maximale lijnsegmenten (rij en kolom) van het bord, als lijst van cellen"""
    return vruns(occ) + hruns(occ)


def _cands(placed, segs, first, barrier, frontier):
    """Alle vorm-legale zetten binnen de EINDbezetting: per lijnsegment elk interval [i..j]
    waarvan de uiteinden nieuw zijn, dat 1..7 nieuwe cellen bevat, dat geen barriere-cel
    (= nog niet toegestane slotzetcel) bevat, en dat het bord raakt.  Intervallen mogen
    al gelegde cellen OVERSPANNEN -- precies wat de 7-tegelbingo's van het record doen
    (kolom 10 rijen 0..7 met rij 4 al gelegd = 7 nieuwe tegels).

    `frontier` = de lege cellen die aan een gelegde cel grenzen; de aanraaktoets is daarmee een
    lidmaatschapstest in plaats van vier buurtoetsen per cel (dat was 60% van de bouwtijd)."""
    out = []
    for seg in segs:
        n = len(seg)
        ok = [0] * n            # 1 = beschikbaar (nieuw of al gelegd), 0 = barriere
        new = [0] * n
        for i, c in enumerate(seg):
            if c in placed:
                ok[i] = 1
            elif c in barrier:
                ok[i] = 0
            else:
                ok[i] = 1; new[i] = 1
        for i in range(n):
            if not new[i]:
                continue
            cnt = 0
            touch = False
            cells = []
            for j in range(i, n):
                if not ok[j]:
                    break
                if new[j]:
                    cnt += 1
                    if cnt > 7:
                        break
                    cells.append(seg[j])
                    if not touch and seg[j] in frontier:
                        touch = True
                else:
                    touch = True          # het interval overspant een gelegde cel
                    continue
                if first:
                    if (7, 7) in cells:
                        out.append(list(cells))
                elif touch:
                    out.append(list(cells))
    seen, uniq = set(), []
    for mvc in out:
        k = tuple(sorted(mvc))
        if k in seen: continue
        seen.add(k); uniq.append(mvc)
    return uniq


PREM = None


def _prem():
    global PREM
    if PREM is None:
        import numpy as np
        LM = np.array(r.letter_multiplier).astype(int)
        WM = np.array(r.word_multiplier).astype(int)
        PREM = {(x, y): int(LM[y][x]) * int(WM[y][x]) for y in range(15) for x in range(15)}
    return PREM


def build_schedule(occ, ext=(), rnd=None, rnd_k=1, words=True, small=True):
    """Deterministische greedy bouwer.  `ext` = cellen die pas NA de slotzetten een voor een
    worden gelegd (de extensieketen; elke zo'n zet herscoort de hele run).

    Prioriteit: bingo's (7 tegels) eerst, dan grootste zet, dan hoogste premiewaarde.  De drie
    slotzetten zijn gewone kandidaten zodra de rest van hun rij ligt (net als in
    mg_denseblock.schedule; mg_newtopo.auto_schedule hangt ze altijd achteraan en verwerpt
    daardoor bezettingen die bestaan -- waaronder ons eigen record)."""
    P = _prem()
    extset = set(ext)
    core = occ - extset
    segs = _segments(core)
    # kaart van cel -> de EINDrun van zijn lijn, zodat elke tijdelijke run als deelstuk
    # getoetst kan worden (sub_ok).  De eindruns zijn die van de VOLLEDIGE bezetting.
    finmap = {}
    for run in vruns(occ):
        for c in run:
            finmap[('V', c)] = run
    for run in hruns(occ):
        for c in run:
            finmap[('H', c)] = run
    fincells = {y: [(x, y) for x in MASKS[y]] for y in ANCHOR_ROWS}
    finset = {c for z in fincells.values() for c in z}
    todo_fin = set(ANCHOR_ROWS)
    placed, out = set(), []
    frontier = set()
    rest = core - finset
    guard = 0
    while rest or todo_fin:
        guard += 1
        if guard > 200:
            return None
        cands = _cands(placed, segs, first=not out, barrier=finset, frontier=frontier)
        for y in sorted(todo_fin):
            z = fincells[y]
            if any(c in placed for c in z):
                continue
            if any((x, y) not in placed for x in range(15) if (x, y) not in set(z)):
                continue
            if not out and (7, 7) not in set(z):
                continue
            if out and not any((x + dx, y + dy) in placed
                               for (x, y) in z for dx, dy in mc.NB):
                continue
            cands.append(z)
        if not cands:
            return None
        # bingo's eerst (50 punten).  Daarna twee tegengestelde regimes:
        #  small=True  -> de KLEINSTE zet: elke extra tussenstap herscoort de hele run nog een
        #                 keer (het ladder-mechanisme van de kolom-2-keten van het record), maar
        #                 elke tussenstand moet dan ook een woord zijn;
        #  small=False -> de GROOTSTE zet: zo min mogelijk tijdelijke runs, dus lexicaal het
        #                 makkelijkst.  Gemeten: met small=True is vrijwel elk schema
        #                 lijn-inconsistent (0 van 2400 schoon), met small=False niet.
        sg = -1 if small else 1
        scored = sorted(cands, key=lambda c: (1 if len(c) == 7 else 0, sg * len(c),
                                              sum(P[q] for q in c)), reverse=True)
        pool = []
        for c in scored:                       # woordtoets pas op de gerangschikte lijst: dat
            if not words or move_bag_ok(placed, c, finmap):   # scheelt ~30 dure runtoetsen per stap
                pool.append(c)
                if len(pool) >= (rnd_k if rnd else 1):
                    break
        if not pool:
            return None
        best = pool[rnd.randrange(len(pool))] if (rnd and len(pool) > 1) else pool[0]
        out.append(list(best)); placed |= set(best)
        for (x, y) in best:
            frontier.discard((x, y))
            for dx, dy in mc.NB:
                n = (x + dx, y + dy)
                if 0 <= n[0] < 15 and 0 <= n[1] < 15 and n not in placed:
                    frontier.add(n)
        rest -= set(best)
        for y in list(todo_fin):
            if set(fincells[y]) <= placed:
                todo_fin.discard(y)
    # extensieketen: een voor een, altijd de cel die nu aan het bord raakt
    todo = list(extset)
    while todo:
        pick = None
        for c in todo:
            if c in frontier and (not words or move_bag_ok(placed, [c], finmap)):
                pick = c; break
        if pick is None:
            return None
        out.append([pick]); placed.add(pick); todo.remove(pick)
        frontier.discard(pick)
        for dx, dy in mc.NB:
            n = (pick[0] + dx, pick[1] + dy)
            if 0 <= n[0] < 15 and 0 <= n[1] < 15 and n not in placed:
                frontier.add(n)
    return out


def peel_order(occ):
    """Bladcellen in afpel-volgorde.  Een bladcel heeft precies EEN bezette buur; die post-final
    leggen herscoort de hele run (het mechanisme achter de kolom-2-keten van het record).
    Dragende cellen (x,1)/(x,13) van een eiland zonder alternatief worden nooit afgepeld."""
    o = set(occ)
    prot = set()
    for g in ISL0:
        s = [x for x in g if (x, 1) in o]
        if len(s) == 1: prot.add((s[0], 1))
    for g in ISL14:
        s = [x for x in g if (x, 13) in o]
        if len(s) == 1: prot.add((s[0], 13))
    P = _prem()
    order = []
    while True:
        leaves = []
        for c in o:
            if c[1] in ANCHOR_ROWS or c in prot:
                continue
            d = sum(1 for dx, dy in mc.NB if (c[0] + dx, c[1] + dy) in o)
            if d == 1:
                leaves.append(c)
        if not leaves:
            break
        # verst van rij 7 eerst (dat is de kop van een keten), dan laagste premie
        leaves.sort(key=lambda c: (-abs(c[1] - 7), P[c], c))
        c = leaves[0]
        order.append(c); o.discard(c)
    return order


def schedule_variants(occ, peels=(0, 4, 8), seeds=1, clean=False, words=True):
    """Bouw schema's voor verschillende peel-dieptes en geef de beste (plafond, schema, peel).
    clean=True eist bovendien lijnconsistentie (mg_newtopo.diagnose leeg) -- dat is de rem op de
    'ladderillusie': zonder die eis wint de bouwer honderden plafondpunten met tussenstanden die
    lexicaal niet bestaan."""
    po = peel_order(occ)
    best = None
    for small in (True, False):
        for k in peels:
            if k > len(po):
                continue
            for s in range(seeds):
                mv = build_schedule(occ, ext=po[:k],
                                    rnd=random.Random(s) if s else None, rnd_k=4 if s else 1,
                                    words=words, small=small)
                if mv is None or not mc.legal_schedule(mv):
                    continue
                cap = mc.score_of(mv, FIXED)[0]
                if best is not None and cap <= best[0]:
                    continue
                if clean and T.diagnose(mv):
                    continue
                best = (cap, mv, k)
    return best


def screen_ceiling(occ, peels=(0, 5, 9)):
    """SNELLE zeef-plafond: greedy schema zonder woordtoets, drie peel-dieptes.  Op de
    recordbezetting geeft dit 4870 tegen 4889 voor het echte recordschema -- een systematische
    onderschatting van ~20 punten, ruim genoeg voor RANGSCHIKKEN."""
    po = peel_order(occ)
    best = 0
    for k in peels:
        if k > len(po):
            continue
        mv = build_schedule(occ, ext=po[:k], words=False)
        if mv is None:
            continue
        c = mc.score_of(mv, FIXED)[0]
        if c > best:
            best = c
    return best


# ================================================================== ENUMERATOR
# Bezetting als bitmaskers per kolom (bit y = rij y).  Kosten zijn dan INCREMENTEEL te houden:
# elke laag van de opsomming raakt maar 1-4 kolommen, dus een niveau kost enkele popcounts.
FREEB = sum(1 << y for y in range(15) if y not in ANCHOR_ROWS)


def _pc(v):
    return bin(v).count('1')


def _iv(a, b):
    return sum(1 << y for y in range(a, b + 1))


LANE_X0 = tuple(int(v) for v in os.environ.get('LX0', '0,2,4').split(','))
LANE_X1 = tuple(int(v) for v in os.environ.get('LX1', '10,12,14').split(','))


LANEROWS = ({int(v) for v in os.environ['LANEROWS'].split(',')}
            if os.environ.get('LANEROWS') else None)
C7ROWS = ({int(v) for v in os.environ['C7ROWS'].split(',')}
          if os.environ.get('C7ROWS') else None)


def lane_menu(rows):
    out = [None]
    for r in rows:
        if LANEROWS is not None and r not in LANEROWS:
            continue
        for x0 in LANE_X0:
            for x1 in LANE_X1:
                if x1 - x0 >= 4:
                    out.append((r, x0, x1))
    return out


def col7_menu():
    """kolom 7 draagt zet 1 (die (7,7) moet dekken) -> (7,6) of (7,8) moet bezet zijn"""
    out = []
    for t in [None] + [(a, 6) for a in range(1, 7)]:
        if C7ROWS is not None and t is not None and t[0] not in C7ROWS:
            continue
        for b in [None] + [(8, e) for e in range(8, 14)]:
            if C7ROWS is not None and b is not None and b[1] not in C7ROWS:
                continue
            if t is None and b is None:
                continue
            ivs = tuple(q for q in (t, b) if q is not None)
            out.append((ivs, sum(_iv(*q) for q in ivs)))
    return out


def sup_top_menu(lane_t):
    """DRAGENDE kolom van rij 0: bezet (x,1).  full = rijen 1..6 (hangt aan rij 7),
    stub = rijen 1..r-1 (hangt aan de laan), thru = full + doorlopen tot rij d."""
    out = [('full', _iv(1, 6))]
    if lane_t is not None and lane_t[0] >= 3:
        out.append((f'stub{lane_t[0]}', _iv(1, lane_t[0] - 1)))
    for d in range(8, 14):
        out.append((f'thru{d}', _iv(1, 6) | _iv(8, d)))
    return out


def sup_bot_menu(lane_b):
    out = [('full', _iv(8, 13))]
    if lane_b is not None and lane_b[0] <= 11:
        out.append((f'stub{lane_b[0]}', _iv(lane_b[0] + 1, 13)))
    for a in range(1, 7):
        out.append((f'thru{a}', _iv(a, 6) | _iv(8, 13)))
    return out


SUP0 = [(a, b, c, 12) for a in (1, 2) for b in (4, 5, 6) for c in (9, 10)]
SUP14 = [(a, b) for a in (4, 5, 6) for b in (8, 9, 10, 11, 12)]
FREE_CELLS = CAP - 45           # 56 vrije cellen naast de 45 ankercellen
EXTRA_OPTS = ([(f't{a}', _iv(a, 6)) for a in range(2, 7)] +
              [(f'b{b}', _iv(8, b)) for b in range(8, 13)])


def _combos(menu, n, maxnonfull):
    """alle n-tupels uit `menu` met hoogstens `maxnonfull` niet-'full' keuzes (het budget laat
    er zelden meer toe: elke afwijking van 'full' kost of levert tegels)"""
    idx = range(len(menu))
    out = []
    for combo in itertools.product(idx, repeat=n):
        if sum(1 for i in combo if menu[i][0] != 'full') > maxnonfull:
            continue
        out.append(tuple(menu[i] for i in combo))
    return out


def all_lanes(nlane=1):
    """de laan-as: hoogstens EEN laan per band (twee lanen kosten ~16 tegels en passen bij zes
    volle dragers nooit binnen de 56; de laan-sweep in MASKGEOM.md vond bovendien alleen rij
    1/3/4/6 positief).  nlane=2 zet de gecombineerde as aan voor een gerichte deelsweep."""
    LT, LB = lane_menu(range(1, 7)), lane_menu(range(8, 14))
    if nlane < 2:
        return [(None, None)] + [(a, None) for a in LT if a] + [(None, b) for b in LB if b]
    return [(a, b) for a in LT for b in LB]


def skeletons(lt, lb, tmin, tmax, maxnonfull=1, cnt=None, menu='all'):
    """SKELET = laan(en) + kolom 7 + de vier rij-0-dragers met hun dieptes + de twee
    rij-14-dragers met hun dieptes.  Yield: (mask, cost, beschrijving)."""
    cnt = cnt if cnt is not None else Counter()
    lanes = tuple(q for q in (lt, lb) if q is not None)
    lanebit = [0] * 15
    for (y, x0, x1) in lanes:
        for x in range(x0, x1 + 1):
            lanebit[x] |= 1 << y
    lane_cost = sum(_pc(v & FREEB) for v in lanebit)
    if lane_cost > tmax:
        return
    mt, mb = sup_top_menu(lt), sup_bot_menu(lb)
    if menu == 'stub':
        # gerichte deelsweep: alleen 'full' en 'stub'.  Korte (laan-gewortelde) dragers ruilen
        # VERTICALE structuur in voor HORIZONTALE bij gelijk tegelaantal -- precies de zet die
        # de campagne nooit geprobeerd heeft (alle laan-pogingen waren TOEVOEGINGEN op volle
        # dragers en dus zak-infeasible; dit is een RUIL).
        mt = [e for e in mt if e[0] == 'full' or e[0].startswith('stub')]
        mb = [e for e in mb if e[0] == 'full' or e[0].startswith('stub')]
        maxnonfull = 4
    TOPC = _combos(mt, 4, maxnonfull)
    BOTC = _combos(mb, 2, maxnonfull)
    for (c7ivs, c7mask) in col7_menu():
        base = list(lanebit)
        base[7] |= c7mask
        cost0 = lane_cost + _pc(base[7] & FREEB) - _pc(lanebit[7] & FREEB)
        if cost0 + 8 > tmax:
            continue
        for s0 in SUP0:
            for tc in TOPC:
                m1 = list(base); c1 = cost0
                for x, (nm, msk) in zip(s0, tc):
                    c1 -= _pc(m1[x] & FREEB)
                    m1[x] |= msk
                    c1 += _pc(m1[x] & FREEB)
                if c1 > tmax:
                    continue
                for s14 in SUP14:
                    for bc in BOTC:
                        m2 = list(m1); c2 = c1
                        for x, (nm, msk) in zip(s14, bc):
                            c2 -= _pc(m2[x] & FREEB)
                            m2[x] |= msk
                            c2 += _pc(m2[x] & FREEB)
                        cnt['knopen'] += 1
                        if not (tmin <= c2 <= tmax):
                            cnt['F0 budget'] += 1
                            continue
                        yield (tuple(m2), c2,
                               {'lanes': lanes, 'c7': c7ivs, 'sup0': s0, 'sup14': s14,
                                'top': tuple(q[0] for q in tc),
                                'bot': tuple(q[0] for q in bc)})


def expansions(mask, lanes, budget, nextra=1, nhang=3):
    """UITBREIDINGEN op een skelet binnen het resterende tegelbudget: extra kolommen die aan
    rij 7 hangen, en 1-cel-hangertjes aan een laan (het (11,3)-mechanisme van het record)."""
    m0 = list(mask)
    used = {x for x in range(15) if m0[x] & FREEB}
    exopts = [(x, nm, msk) for x in range(1, 14) if x != 7 and x not in used
              for (nm, msk) in EXTRA_OPTS]
    hopts = []
    for (y, x0, x1) in lanes:
        for x in range(x0, x1 + 1):
            for yy in (y - 1, y + 1):
                if yy in ANCHOR_ROWS or not (0 <= yy < 15) or (m0[x] >> yy & 1):
                    continue
                hopts.append((x, yy))
    hopts = sorted(set(hopts))
    exsets = [()]
    for n in range(1, nextra + 1):
        for combo in itertools.combinations(exopts, n):
            if len({q[0] for q in combo}) == n:
                exsets.append(combo)
    for ex in exsets:
        m1 = list(m0); c1 = 0
        for (x, nm, msk) in ex:
            c1 -= _pc(m1[x] & FREEB)
            m1[x] |= msk
            c1 += _pc(m1[x] & FREEB)
        if c1 > budget:
            continue
        hh = [h for h in hopts if not (m1[h[0]] >> h[1] & 1)]
        for n in range(0, min(nhang, budget - c1) + 1):
            for hg in itertools.combinations(hh, n):
                m2 = list(m1); c2 = c1
                for (x, y) in hg:
                    c2 -= _pc(m2[x] & FREEB)
                    m2[x] |= 1 << y
                    c2 += _pc(m2[x] & FREEB)
                if c2 > budget:
                    continue
                yield tuple(m2), c2, ex, hg


def mask_to_cells(mask):
    occ = {(x, y) for y in ANCHOR_ROWS for x in range(15)}
    for x in range(15):
        v = mask[x]
        for y in range(15):
            if v >> y & 1:
                occ.add((x, y))
    return occ


def cells_to_mask(occ):
    m = [0] * 15
    for (x, y) in occ:
        m[x] |= 1 << y
    return tuple(v & FREEB for v in m)


# ================================================================== DRIJVER
PEELS = tuple(int(v) for v in os.environ.get('PEELS', '0,6').split(','))
# F3b (klinkerbudget) staat standaard UIT: gemeten kill-rate 0 op 1581 configuraties.  De
# restzak heeft 23 klinkers + 2 blanco's en de recordbezetting heeft er maar 10 nodig -- het
# klinkerbudget is dus niet bindend.  De code blijft staan als vastgelegde meting.
VOWELCHECK = int(os.environ.get('VOWEL', '0'))


def evaluate(mask, cnt, floor, peels=PEELS):
    """De filterketen op EEN configuratie.  Geeft (cap, occ) of None, en telt waar hij afvalt."""
    occ = mask_to_cells(mask)
    why = f1_shape(occ)
    if why:
        cnt['F1 vorm/cap'] += 1; return None
    why = f2_delivery(occ)
    if why:
        cnt['F2 ' + why] += 1; return None
    if f3_bagwords(occ):
        cnt['F3 zak-lexicaal'] += 1; return None
    if VOWELCHECK and f3b_vowels(occ):
        cnt['F3b klinkerbudget'] += 1; return None
    cap = screen_ceiling(occ, peels)
    if cap == 0:
        cnt['F4 schema vast'] += 1; return None
    cnt['F4 schema ok'] += 1
    if cap < floor:
        cnt['F5 plafond te laag'] += 1; return None
    cnt['F5 door'] += 1
    return cap, occ


def rank_value(occ, cap):
    """Rangschikwaarde.  Het kale m-plafond discrimineert binnen een familie nauwelijks (zie
    CONFIGGEN.md 3), en de per-tegel-meting op het record laat zien dat VERLENGKETENS per tegel
    meer opleveren dan een extra bingo (16,0 tegen 12,8 punt/tegel).  Daarom telt het lexicaal
    ondersteunde verlengpotentieel expliciet mee."""
    ep, _ = ext_potential(occ)
    return cap + RANKW * ep, ep


RANKW = int(os.environ.get('RANKW', '0'))


def _emit(fh, rec):
    fh.write(json.dumps(rec) + '\n')


def _dump_top(out, heap):
    """de top-K atomisch naar <out>.top; een herstart leest hem terug in de heap"""
    tmp = out + '.top.tmp'
    with open(tmp, 'w') as g:
        for (cap, mask, cost, dj) in sorted(heap, reverse=True):
            g.write(json.dumps({'t': 'S', 'mask': list(mask), 'cap': cap,
                                'tiles': cost, 'desc': json.loads(dj)}) + '\n')
    os.replace(tmp, out + '.top')


def main_enum():
    """Fase 1: skeletten.  Gesharded over de laan-as en hervatbaar (elke laan die af is wordt
    als DONE-regel weggeschreven; een herstart slaat die over).  Alleen de TOPK beste
    configuraties worden bewaard -- de rest telt alleen mee in de histogram."""
    import heapq
    shard = int(os.environ.get('SHARD', '0'))
    nshard = int(os.environ.get('NSHARD', '1'))
    tmin = int(os.environ.get('TMIN', '56'))
    tmax = int(os.environ.get('TMAX', str(FREE_CELLS)))
    floor = int(os.environ.get('FLOOR', '4800'))
    maxnf = int(os.environ.get('MAXNF', '1'))
    nlane = int(os.environ.get('NLANE', '1'))
    topk = int(os.environ.get('TOPK', '12000'))
    ceilmax = int(os.environ.get('CEILMAX', '999999'))
    sample = int(os.environ.get('SAMPLE', '0'))
    nseen = 0
    rnd = random.Random(1234 + shard)
    out = os.environ.get('OUT', f'{RES}/configgen/skel_{shard}.jsonl')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    done = set()
    heap = []
    if os.path.exists(out):
        for line in open(out):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('t') == 'DONE':
                done.add(tuple(map(_tup, d['lane'])))
    if os.path.exists(out + '.top'):
        for line in open(out + '.top'):
            d = json.loads(line)
            heapq.heappush(heap, (d['cap'], tuple(d['mask']), d['tiles'],
                                  json.dumps(d['desc'])))
    lanes = all_lanes(nlane)
    mine = [lanes[i] for i in range(len(lanes)) if i % nshard == shard]
    cnt = Counter()
    hist = Counter()
    t0 = time.time()
    fh = open(out, 'a')
    for (lt, lb) in mine:
        key = tuple(map(_tup, (lt, lb)))
        if key in done:
            continue
        c0 = time.time(); nyield = 0; nnew = 0
        for (mask, cost, desc) in skeletons(lt, lb, tmin, tmax, maxnf, cnt,
                                            os.environ.get('MENU', 'all')):
            nyield += 1
            got = evaluate(mask, cnt, floor)
            if got is None:
                continue
            cap, occ = got
            hist[cap // 20 * 20] += 1
            if RANKW:
                cap2, ep = rank_value(occ, cap)
                desc = dict(desc); desc['ep'] = ep; cap = cap2
            if cap > ceilmax:
                cnt['F5 boven band'] += 1
                continue
            item = (cap, mask, cost, json.dumps({k: _js(v) for k, v in desc.items()}))
            if sample:
                # RESERVOIRSTEEKPROEF binnen de plafondband.  Top-K op zeef-plafond levert
                # systematisch de ladderillusie-staart op (gemeten: de 120.000 bewaarde
                # configuraties van fase A liggen allemaal in 5050-5316 terwijl het record op
                # 4868 zit).  Een reservoir geeft een ONVERTEKENDE steekproef van de band.
                nseen += 1
                if len(heap) < topk:
                    heap.append(item); nnew += 1
                else:
                    j = rnd.randrange(nseen)
                    if j < topk:
                        heap[j] = item; nnew += 1
            elif len(heap) < topk:
                heapq.heappush(heap, item); nnew += 1
            elif cap > heap[0][0]:
                heapq.heapreplace(heap, item); nnew += 1
        _emit(fh, {'t': 'DONE', 'lane': [_js(lt), _js(lb)], 'n': nyield,
                   'sec': round(time.time() - c0, 1)})
        fh.flush()
        _dump_top(out, heap)          # hervatbaar: de heap na ELKE laan wegschrijven
        print(f'[{shard}] laan {lt}/{lb}: {nyield} skeletten binnen budget, '
              f'{cnt["F5 door"]} boven vloer, heap {len(heap)} (+{nnew}), '
              f'{time.time()-c0:.1f}s', flush=True)
    _dump_top(out, heap)
    for (cap, mask, cost, dj) in sorted(heap, reverse=True):
        _emit(fh, {'t': 'S', 'mask': list(mask), 'cap': cap, 'tiles': cost,
                   'desc': json.loads(dj)})
    _emit(fh, {'t': 'CNT', 'cnt': dict(cnt), 'hist': dict(hist),
               'sec': round(time.time() - t0, 1)})
    fh.close()
    print(f'[{shard}] KLAAR in {time.time()-t0:.0f}s')
    for k, v in cnt.most_common():
        print(f'   {k:22s} {v}')


def _js(v):
    if v is None: return None
    if isinstance(v, (list, tuple)): return [_js(q) for q in v]
    return v


def _tup(v):
    if isinstance(v, list): return tuple(_tup(q) for q in v)
    return v


def main_expand():
    """Fase 2: uitbreidingen (extra kolommen + laanhangers) op de beste skeletten."""
    src = os.environ.get('IN', f'{RES}/configgen')
    topn = int(os.environ.get('TOPN', '4000'))
    floor = int(os.environ.get('FLOOR', '4830'))
    tmax = int(os.environ.get('TMAX', str(FREE_CELLS)))
    nextra = int(os.environ.get('NEXTRA', '1'))
    nhang = int(os.environ.get('NHANG', '3'))
    shard = int(os.environ.get('SHARD', '0'))
    nshard = int(os.environ.get('NSHARD', '1'))
    rows = []
    files = ([src] if src.endswith('.jsonl') else
             [os.path.join(src, f) for f in sorted(os.listdir(src)) if f.startswith('skel_')])
    for p in files:
        for line in open(p):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('t') == 'S':
                rows.append(d)
    per = int(os.environ.get('PER', '4'))
    rows = pick_diverse(rows, topn, per) if per else sorted(
        rows, key=lambda d: -d['cap'])[:topn]
    rows = [rows[i] for i in range(len(rows)) if i % nshard == shard]
    out = os.environ.get('OUT', f'{RES}/configgen/exp_{shard}.jsonl')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    seen = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('t') == 'DONESK':
                seen.add(d['i'])
    fh = open(out, 'a')
    cnt = Counter(); t0 = time.time()
    for i, d in enumerate(rows):
        if i in seen:
            continue
        mask = tuple(d['mask'])
        lanes = tuple(tuple(q) for q in d['desc']['lanes'])
        budget = tmax - d['tiles']
        n = 0
        for (m2, extra, ex, hg) in expansions(mask, lanes, budget, nextra, nhang):
            n += 1
            cnt['uitbreidingen'] += 1
            got = evaluate(m2, cnt, floor)
            if got is None:
                continue
            cap, occ = got
            _emit(fh, {'t': 'E', 'mask': list(m2), 'cap': cap,
                       'tiles': d['tiles'] + extra, 'base': d['desc'],
                       'extra': _js(ex), 'hang': _js(hg)})
        _emit(fh, {'t': 'DONESK', 'i': i, 'n': n})
        if i % 50 == 0:
            fh.flush()
            print(f'[{shard}] skelet {i}/{len(rows)} ({n} uitbreidingen), '
                  f'{cnt.get("F5 door", 0)} door, {time.time()-t0:.0f}s', flush=True)
    _emit(fh, {'t': 'CNT', 'cnt': dict(cnt), 'sec': round(time.time() - t0, 1)})
    fh.close()
    for k, v in cnt.most_common():
        print(f'   {k:22s} {v}')


def pick_diverse(rows, topn, per=3):
    """Kies de top-N maar met STRUCTURELE SPREIDING: hoogstens `per` configuraties per
    (laan, rij-0-dragers, rij-14-dragers).  Het m-plafond discrimineert in dit stadium
    nauwelijks (gemeten correlatie zeef-plafond ~ verfijnd plafond = 0,47, en 192
    record-buren liggen allemaal binnen 30 plafondpunten van elkaar terwijl het record
    er 110 onder realiseert), dus spreiding is meer waard dan de laatste plafondpunten."""
    rows = sorted(rows, key=lambda d: -d['cap'])
    grp, out = Counter(), []
    for d in rows:
        b = d.get('desc') or d.get('base') or {}
        k = (json.dumps(b.get('lanes')), json.dumps(b.get('sup0')),
             json.dumps(b.get('sup14')))
        if grp[k] >= per:
            continue
        grp[k] += 1
        out.append(d)
        if len(out) >= topn:
            break
    return out


def load_cands(src=f'{RES}/configgen', kinds=('S', 'E')):
    rows, seen = [], set()
    files = ([src] if src.endswith('.jsonl') else
             [os.path.join(src, f) for f in sorted(os.listdir(src))
              if f.endswith('.jsonl') or f.endswith('.top')])
    for p in files:
        for line in open(p):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('t') in kinds:
                k = tuple(d['mask'])
                if k in seen:
                    continue
                seen.add(k); rows.append(d)
    rows.sort(key=lambda d: -d['cap'])
    return rows


def main_refine():
    """Fase 3: op de beste configuraties het VOLLE schema-onderzoek (woordtoets aan, meer
    peel-dieptes, meer restarts) plus de lijnconsistentietoets (mg_newtopo.diagnose)."""
    src = os.environ.get('IN', f'{RES}/configgen')
    topn = int(os.environ.get('TOPN', '3000'))
    shard = int(os.environ.get('SHARD', '0'))
    nshard = int(os.environ.get('NSHARD', '1'))
    per = int(os.environ.get('PER', '3'))
    # PLAFONDBAND.  Gemeten: alle 2400 configuraties met het HOOGSTE zeef-plafond (5210-5316)
    # zijn lijn-inconsistent -- dat zijn precies de ladderillusies.  Het realistische venster ligt
    # rond het record (zeef-plafond 4868).  Zonder deze band selecteert de rangschikking
    # systematisch de onbruikbare staart.
    cmin = int(os.environ.get('CAPMIN', '0'))
    cmax = int(os.environ.get('CAPMAX', '99999'))
    cands = [d for d in load_cands(src) if cmin <= d['cap'] <= cmax]
    print(f'[{shard}] {len(cands)} kandidaten in band [{cmin},{cmax}]', flush=True)
    rows = pick_diverse(cands, topn, per) if per else cands[:topn]
    rows = [(i, rows[i]) for i in range(len(rows)) if i % nshard == shard]
    out = os.environ.get('OUT', f'{RES}/configgen/ref_{shard}.jsonl')
    done = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                done.add(json.loads(line)['i'])
            except Exception:
                pass
    fh = open(out, 'a')
    cnt = Counter(); t0 = time.time()
    for (i, d) in rows:
        if i in done:
            continue
        occ = mask_to_cells(tuple(d['mask']))
        got = schedule_variants(occ, peels=(0, 2, 4, 6, 8, 10, 12), seeds=3, words=True)
        if got is None:
            cnt['geen schema'] += 1
            _emit(fh, {'i': i, 'ok': False, 'why': 'geen schema'}); continue
        cap, mv, k = got
        diag = T.diagnose(mv)
        # LADDERZOEK: lokale zoektocht over het zetschema bij VASTE bezetting, maar alleen
        # schema's die lijnconsistent blijven.  Zonder die eis wint de zoeker honderden
        # plafondpunten met tussenstanden die lexicaal niet bestaan (NEWTOPO.md 6.1).
        best, bmv = (cap, mv) if not diag else (0, None)
        for s in range(int(os.environ.get('SEEDS', '2'))):
            b, m2 = T.search(mv, iters=int(os.environ.get('ITERS', '800')), seed=s,
                             need_words=True)
            if b > best and not T.diagnose(m2):
                best, bmv = b, m2
        cnt['schoon' if bmv is not None else 'lijn-vuil'] += 1
        _emit(fh, {'i': i, 'ok': True, 'mask': d['mask'], 'cap_screen': d['cap'],
                   'cap': best if bmv is not None else cap, 'cap_greedy': cap, 'peel': k,
                   'diag': len(diag), 'schoon': bmv is not None,
                   'bingos': sum(1 for z in mv if len(z) == 7),
                   'moves': [[list(c) for c in z] for z in (bmv or mv)],
                   'moves0': [[list(c) for c in z] for z in mv]})
        if len(done) % 25 == 0:
            fh.flush()
        done.add(i)
    _emit(fh, {'i': -1, 'cnt': dict(cnt), 'sec': round(time.time() - t0, 1)})
    fh.close()
    for k, v in cnt.most_common():
        print(f'   {k:22s} {v}')


def fit_decide(mv, target, tlim=180, nw=2, hintgrid=None):
    """BESLISSINGSVORM van de invulling: bestaat er een lettering waarbij dit schema >= target
    scoort?  Veel sneller dan maximaliseren -- we hoeven het optimum niet te kennen, alleen of
    het boven het record uitkomt.  INFEASIBLE is bovendien een BEWIJS dat deze bezetting met dit
    schema het record niet kan halen (zelfde redenering als exact_fill in mg_letterbudget).

    Geeft ('JA', grid, blanks, score) / ('NEE', ...) / ('ONBEKEND', ...)."""
    from ortools.sat.python import cp_model
    import numpy as np
    LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
    val = {i: r.scores[i] for i in range(1, 27)}
    occ = sorted({c for z in mv for c in z})
    fixed = {c: FIXED[c] for c in occ if c in FIXED}
    free = [c for c in occ if c not in fixed]
    m_ = cp_model.CpModel()
    L = {c: m_.new_int_var(1, 26, f'L{c}') for c in free}
    for c, v in fixed.items():
        L[c] = m_.new_constant(v)
    placed, events, runs = set(), [], set()
    for cells in mv:
        for run in T.move_runs(placed, cells):
            events.append((run, set(cells))); runs.add(tuple(run))
        placed |= set(cells)
    for run in sorted(runs, key=len):
        fx = {i: fixed[c] for i, c in enumerate(run) if c in fixed}
        tab = [w for w in BYLEN.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab:
            return 'NEE', None, None, 0
        m_.add_allowed_assignments([L[c] for c in run], tab)
    BL = {c: m_.new_bool_var(f'bl{c}') for c in free}
    m_.add(sum(BL.values()) <= NBLANK)
    for ch in range(1, 27):
        cnt = []
        for c in free:
            b = m_.new_bool_var(f'i{c}_{ch}')
            m_.add(L[c] == ch).only_enforce_if(b)
            m_.add(L[c] != ch).only_enforce_if(b.negated())
            nb = m_.new_bool_var(f'nb{c}_{ch}')
            m_.add_bool_and([b, BL[c].negated()]).only_enforce_if(nb)
            m_.add_bool_or([b.negated(), BL[c]]).only_enforce_if(nb.negated())
            cnt.append(nb)
        m_.add(sum(cnt) + sum(1 for c, v in fixed.items() if v == ch) <= BAG[ch])
    VV = [0] + [val[i] for i in range(1, 27)]
    vv = {}
    for c in occ:
        v = m_.new_int_var(0, 10, f'v{c}')
        m_.add_element(L[c], VV, v)
        if c in BL:
            ve = m_.new_int_var(0, 10, f've{c}')
            m_.add(ve == v).only_enforce_if(BL[c].negated())
            m_.add(ve == 0).only_enforce_if(BL[c])
            vv[c] = ve
        else:
            vv[c] = v
    obj, bingos = [], sum(50 for z in mv if len(z) == 7)
    for run, cset in events:
        wm = 1
        for (x, y) in run:
            if (x, y) in cset:
                wm *= int(WM[y][x])
        obj.append(sum(vv[(x, y)] * (int(LM[y][x]) if (x, y) in cset else 1)
                       for (x, y) in run) * wm)
    m_.add(sum(obj) + bingos >= target)
    # WARME START.  Gemeten: zonder hint komt zelfs het EIGEN schema van het record met
    # target=4793 (waarvan we weten dat het haalbaar is) in 150 s niet verder dan ONBEKEND.
    # Elke cel die ook op het referentiebord ligt krijgt daarom diens letter als hint.
    if hintgrid:
        for c in free:
            g = hintgrid[c[1]][c[0]]
            if g:
                m_.add_hint(L[c], g)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = tlim
    sol.parameters.num_workers = nw
    st = sol.solve(m_)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        g = [[0] * 15 for _ in range(15)]
        for c in occ:
            g[c[1]][c[0]] = sol.value(L[c])
        return 'JA', g, {c for c in free if sol.value(BL[c])}, target
    return ('NEE' if st == cp_model.INFEASIBLE else 'ONBEKEND'), None, None, 0


def main_decide():
    """Fase 4a: de snelle beslissingstoets op alle verfijnde configuraties.
    NEE = bewezen dat deze bezetting+schema het record niet haalt; JA = beter bord."""
    src = os.environ.get('IN', f'{RES}/configgen')
    tlim = float(os.environ.get('TLIM', '150'))
    nw = int(os.environ.get('NW', '2'))
    topn = int(os.environ.get('TOPN', '400'))
    shard = int(os.environ.get('SHARD', '0'))
    nshard = int(os.environ.get('NSHARD', '1'))
    target = int(os.environ.get('TARGET', '4794'))
    rows = []
    for f in sorted(os.listdir(src)):
        if not f.startswith('ref'):
            continue
        for line in open(os.path.join(src, f)):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('ok') and d.get('moves'):
                rows.append(d)
    seen, uniq = set(), []
    for d in rows:
        k = tuple(d.get('mask', []))
        if k in seen:
            continue
        seen.add(k); uniq.append(d)
    uniq.sort(key=lambda d: (0 if d.get('schoon') else 1, -d['cap']))
    uniq = uniq[:topn]
    mine = [uniq[i] for i in range(len(uniq)) if i % nshard == shard]
    out = os.environ.get('OUT', f'{RES}/configgen/dec_{shard}.jsonl')
    done = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                done.add(json.loads(line)['i'])
            except Exception:
                pass
    fh = open(out, 'a')
    cnt = Counter()
    hintgrid = json.load(open(os.environ.get('HINT', f'{RES}/maxgame_BEST.json')))['grid']
    print(f'[{shard}] {len(mine)} configuraties te beslissen (target {target})', flush=True)
    for d in mine:
        if d['i'] in done:
            continue
        for tag in ('moves', 'moves0'):
            if tag not in d or (tag == 'moves0' and d['moves0'] == d['moves']):
                continue
            mv = [[tuple(c) for c in z] for z in d[tag]]
            t0 = time.time()
            v, g, bl, sc = fit_decide(mv, target, tlim=tlim, nw=nw, hintgrid=hintgrid)
            cnt[v] += 1
            _emit(fh, {'i': d['i'], 'tag': tag, 'v': v, 'cap': d['cap'],
                       'sec': round(time.time() - t0, 1)})
            fh.flush()
            if v == 'JA':
                tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
                print(f'[{shard}] #{d["i"]} {tag}: JA -> arbiter {int(tot)} ok={ok}',
                      flush=True)
                if ok and int(tot) >= target:
                    pad = f'{RES}/configgen/configgen_board_{int(tot)}.json'
                    json.dump({'grid': g, 'moves': [[list(c) for c in z] for z in mv],
                               'blanks': [list(b) for b in sorted(bl)], 'total': int(tot),
                               'ok': True, 'triple': list(T.TRIPLET),
                               'bron': f'mg_configgen decide #{d["i"]} {tag}'},
                              open(pad, 'w'))
                    print(f'*** BOVEN HET RECORD: {int(tot)} -> {pad} ***', flush=True)
                break
        if sum(cnt.values()) % 10 == 0:
            print(f'[{shard}] {dict(cnt)}', flush=True)
    _emit(fh, {'i': -1, 'cnt': dict(cnt)})
    fh.close()
    print(f'[{shard}] KLAAR {dict(cnt)}')


def main_fit():
    """Fase 4: CP-SAT-invulling + arbiter.  Alleen ok=True telt, en alleen boven het record."""
    src = os.environ.get('IN', f'{RES}/configgen')
    tlim = float(os.environ.get('TLIM', '600'))
    nw = int(os.environ.get('NW', '4'))
    topn = int(os.environ.get('TOPN', '40'))
    shard = int(os.environ.get('SHARD', '0'))
    nshard = int(os.environ.get('NSHARD', '1'))
    lb = int(os.environ.get('LB', '4793'))
    rows = []
    files = [os.path.join(src, f) for f in sorted(os.listdir(src)) if f.startswith('ref_')]
    for p in files:
        for line in open(p):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('ok') and d.get('moves'):
                rows.append(d)
    rows.sort(key=lambda d: (0 if d.get('schoon') else 1, -d['cap']))
    rows = rows[:topn]
    rows = [rows[i] for i in range(len(rows)) if i % nshard == shard]
    print(f'[{shard}] {len(rows)} configuraties te vullen', flush=True)
    outdir = f'{RES}/configgen'
    best = lb
    for j, d in enumerate(rows):
        # twee schema's per bezetting: het GELADDERDE (hoogste plafond) en het GREEDY
        # (minste tussenruns, dus lexicaal het makkelijkst).  Welke van de twee CP-SAT
        # aankan is vooraf niet te zeggen -- op het record was het de gelagderde.
        for tag in ('ladder', 'greedy'):
            key = 'moves' if tag == 'ladder' else 'moves0'
            if key not in d:
                continue
            mv = [[tuple(c) for c in z] for z in d[key]]
            t0 = time.time()
            st, ob, g, bl = T.fit(mv, tlim=tlim, nw=nw)
            if st != 'ok':
                print(f'[{shard}] #{d["i"]} {tag} plafond {d["cap"]}: CP-SAT {st} '
                      f'({time.time()-t0:.0f}s)', flush=True)
                continue
            tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
            print(f'[{shard}] #{d["i"]} {tag} plafond {d["cap"]}: CP-SAT {int(ob)} -> '
                  f'ARBITER {int(tot)} ok={ok} ({time.time()-t0:.0f}s)', flush=True)
            if not ok:
                continue
            D = {'grid': g, 'moves': [[list(c) for c in z] for z in mv],
                 'blanks': [list(b) for b in sorted(bl)], 'total': int(tot),
                 'ok': True, 'triple': list(T.TRIPLET),
                 'bron': f'mg_configgen {tag} #{d["i"]}'}
            if int(tot) > best:
                best = int(tot)
                pad = f'{outdir}/configgen_board_{int(tot)}.json'
                json.dump(D, open(pad, 'w'))
                print(f'*** BOVEN DE VLOER: {int(tot)} -> {pad} ***', flush=True)
            else:
                json.dump(D, open(f'{outdir}/cg_{int(tot)}_{d["i"]}_{tag}.json', 'w'))


# ------------------------------------------------------------------ referentie / calibratie
def record_cfg(path=f'{RES}/maxgame_BEST.json'):
    """De bezetting van het record, terug vertaald naar de parameterisering."""
    D = json.load(open(path))
    occ = {tuple(c) for z in D['moves'] for c in z}
    cols = {}
    for x in range(15):
        ys = sorted(y for y in range(1, 14) if y != 7 and (x, y) in occ)
        ivs, cur = [], []
        for y in ys:
            if cur and y == cur[-1] + 1 and not (cur[-1] < 7 < y):
                cur.append(y)
            else:
                if cur: ivs.append((cur[0], cur[-1]))
                cur = [y]
        if cur: ivs.append((cur[0], cur[-1]))
        if ivs: cols[x] = ivs
    return {'cols': cols, 'lanes': [], 'naam': 'RECORD'}, occ, D


def main_calib():
    cfg, occ_rec, D = record_cfg()
    occ = cells_of(cfg)
    print(f"record: {len(occ_rec)} tegels; parameterisering geeft {len(occ)} "
          f"({'IDENTIEK' if occ == occ_rec else 'AFWIJKEND'})")
    if occ != occ_rec:
        print('  verschil:', sorted(occ ^ occ_rec))
    print('  kolommen:', {x: v for x, v in sorted(cfg['cols'].items())})
    for nm, fn in (('F1', f1_shape), ('F2', f2_delivery), ('F3', f3_bagwords)):
        print(f'  {nm}: {fn(occ) or "OK"}')
    mv0 = [[tuple(c) for c in z] for z in D['moves']]
    print(f"  plafond van het ECHTE recordschema : {mc.score_of(mv0, FIXED)[0]} "
          f"(gerealiseerd {D['total']})")
    t0 = time.time()
    po = peel_order(occ)
    print(f"  peel-volgorde (eerste 12): {po[:12]}")
    got = schedule_variants(occ)
    if got is None:
        print('  BOUWER FAALT op de recordbezetting -- generator is niet geijkt!')
        return
    cap, mv, k = got
    print(f"  plafond van het GEBOUWDE schema    : {cap}  (peel={k}, {len(mv)} zetten, "
          f"{sum(1 for z in mv if len(z) == 7)} bingo's, {time.time()-t0:.2f}s)")
    print(f"  diagnose (lijnconsistentie): {T.diagnose(mv) or 'schoon'}")
    json.dump({'moves': [[list(c) for c in z] for z in mv], 'ceiling': cap, 'peel': k},
              open(f'{SCRATCH}/configgen_calib.json', 'w'))
    # IJKING: het record moet een PUNT van de opsomming zijn
    rm = cells_to_mask(occ_rec)
    skel = list(rm)
    skel[11] &= ~(1 << 3); skel[13] &= ~(1 << 5)
    skel = tuple(skel)
    cnt = Counter(); hit = None
    for (mask, cost, desc) in skeletons((4, 2, 14), None, 50, 56, 1, cnt):
        if mask == skel:
            hit = (cost, desc); break
    print(f"  IJKING skelet in de opsomming: {'JA' if hit else 'NEE'} {hit[1] if hit else ''}")
    if hit:
        ok = any(m2 == rm for (m2, _e, _x, _h)
                 in expansions(skel, ((4, 2, 14),), 56 - hit[0], 1, 3))
        print(f"  IJKING record volledig (skelet + hangers): {'JA' if ok else 'NEE'}")


def main_stats():
    """Filtertellingen en plafond-histogram over alle shards -- de landschapsinformatie."""
    src = os.environ.get('IN', f'{RES}/configgen')
    pat = os.environ.get('PAT', 'skel')
    cnt, hist, lanes = Counter(), Counter(), []
    tops = []
    for f in sorted(os.listdir(src)):
        if not f.startswith(pat):
            continue
        for line in open(os.path.join(src, f)):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('t') == 'CNT':
                cnt.update(d['cnt']); hist.update({int(k): v for k, v in d['hist'].items()})
            elif d.get('t') == 'DONE':
                lanes.append((d['lane'], d['n'], d['sec']))
            elif d.get('t') in ('S', 'E'):
                tops.append(d['cap'])
    print(f'{len(lanes)} laan-opties afgewerkt, {sum(q[2] for q in lanes)/3600:.2f} CPU-uur')
    tot = sum(cnt.values())
    print(f'\n== filtertellingen ==')
    order = ['knopen', 'F0 budget', 'F1 vorm/cap', 'F2 rij0-eiland', 'F2 rij14-eiland',
             'F2 onbereikbaar', 'F3 zak-lexicaal', 'F4 schema vast', 'F4 schema ok',
             'F5 plafond te laag', 'F5 door', 'uitbreidingen']
    for k in order + [k for k in cnt if k not in order]:
        if k in cnt:
            print(f'  {k:22s} {cnt[k]:>12,}')
    if hist:
        print('\n== plafond-histogram (zeef-plafond, bins van 20) ==')
        for k in sorted(hist):
            print(f'  {k:5d} {hist[k]:>10,}  ' + '#' * min(60, hist[k] * 60 //
                                                           max(hist.values())))
    if tops:
        tops.sort(reverse=True)
        print(f'\nbewaarde kandidaten: {len(tops)}, top {tops[:8]}')


if __name__ == '__main__':
    MODE = os.environ.get('MODE', 'calib')
    {'calib': main_calib, 'enum': main_enum, 'expand': main_expand,
     'refine': main_refine, 'fit': main_fit, 'stats': main_stats,
     'decide': main_decide}[MODE]()
