"""NIEUWE TOPOLOGIEEN: generator + m-calculus-waardering + woordbaarheidsfilter.

Waarom nog een topologie-script?  `mg_classceiling.py` vergelijkt klassen op het VRIJE plafond
(pure geometrie).  Dat getal is misleidend: het gat tussen vrij (5757) en ankervast (4867) is
bijna 900 punten, en de ankerletters liggen vast.  Hier wordt daarom alles gemeten op het
ANKERVASTE plafond -- SOM_c m(c)*waarde(c) met de echte tripletletters op rij 0/7/14 en de best
mogelijke resttegels op de vrije cellen -- en bovendien meteen gefilterd op WOORDBAARHEID
(voor elke gescoorde run moet er een woord van die lengte bestaan dat op de vaste ankerletters
past; dezelfde noodzakelijke voorwaarde als in `mg_schedsearch.py`).

Wat het script bijdraagt bovenop de bestaande motoren:

  * een generieke BOUWER (`build`): een topologie is een spec van verticale kolomstukken,
    horizontale lanen ("rails") en de drie slotzetten; de bouwer hakt alles in zetten van <=7
    tegels, ordent ze first-fit legaal en hangt de finals achteraan.  Zo kost een nieuw idee
    drie regels in plaats van een hand-geschreven zetschema.
  * een woordbaarheids-BEWUSTE schemazoeker (`search`), zodat het gerapporteerde plafond hoort
    bij een schema dat het lexicon niet meteen weerlegt.
  * de RAIL-familie: rij 1 en rij 13 als steunrail.  Nieuw idee: die rijen hebben elk twee DWS
    ((1,1)/(13,1) resp. (1,13)/(13,13)) EN ze liggen direct naast een x27-rij, dus een rail
    daar (a) scoort zelf x4 over 13-15 cellen en (b) draagt ALLE pre-cellen van de x27-rij,
    waardoor de vier klimkolommen van de recordtopologie overbodig worden.

CLI:  .venv/bin/python experiments/mg_newtopo.py [ITERS=..] [ONLY=naam,naam]
"""
import sys, os, json, random
from collections import Counter
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG
import mg_mceiling as M

CAP = 101
BEST = '/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json'
RESCHED = '/home/bob/programming/scrabble4/experiments/results/mg_lexresched.json'
TRIPLET = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')
ROWY = {0: 0, 1: 7, 2: 14}

r = MG.r
cba = r.alphabet.cba
BYLEN = {}
for w in r.words_str:
    BYLEN.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))

# vaste ankerletters (het bevestigd optimale triplet)
FIXED = {}
for w, y in zip(TRIPLET, (0, 7, 14)):
    for x, ch in enumerate(w):
        FIXED[(x, y)] = cba[ch]


# ------------------------------------------------------------------ woordbaarheid
_wcache = {}


def table_nonempty(run):
    """Bestaat er een woord van deze lengte dat op de vaste ankerletters van deze run past?
    Noodzakelijke voorwaarde voor elke gescoorde run (zie mg_schedsearch)."""
    key = (len(run),) + tuple((i, FIXED[c]) for i, c in enumerate(run) if c in FIXED)
    hit = _wcache.get(key)
    if hit is None:
        fx = key[1:]
        hit = any(all(w[i] == v for i, v in fx) for w in BYLEN.get(len(run), ()))
        _wcache[key] = hit
    return hit


def move_runs(placed, move):
    """De maximale runs (>=2) die deze zet raakt, gegeven de al liggende tegels."""
    pl = placed | set(move)
    cset = set(move)
    seen, out = set(), []
    for (x, y) in move:
        for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
            x0, y0 = x, y
            while x0 - dx >= 0 and y0 - dy >= 0 and (x0 - dx, y0 - dy) in pl:
                x0 -= dx; y0 -= dy
            x1, y1 = x, y
            while x1 + dx < 15 and y1 + dy < 15 and (x1 + dx, y1 + dy) in pl:
                x1 += dx; y1 += dy
            n = max(x1 - x0, y1 - y0) + 1
            if n < 2 or (tag, x0, y0) in seen:
                continue
            seen.add((tag, x0, y0))
            out.append([(x0 + i * dx, y0 + i * dy) for i in range(n)])
    return out


def move_words_ok(placed, move):
    return all(table_nonempty(run) for run in move_runs(placed, move))


def words_ok(moves, why=False):
    for run, _ in M.events_of(moves):
        if not table_nonempty(run):
            return (False, run) if why else False
    return (True, None) if why else True


# ------------------------------------------------------------------ legaliteit + zoeker
def legal(moves, why=False):
    placed = set()
    for i, mv in enumerate(moves):
        s = set(mv)
        if not mv or len(mv) > 7 or len(s) != len(mv) or (s & placed):
            return (False, f'zet {i}: grootte/overlap') if why else False
        if i == 0:
            if (7, 7) not in s:
                return (False, 'zet 0 dekt center niet') if why else False
        elif not any((x + dx, y + dy) in placed for (x, y) in mv for dx, dy in M.NB):
            return (False, f'zet {i}: raakt bord niet {sorted(s)}') if why else False
        if not M.shape_ok(s, placed):
            return (False, f'zet {i}: geen aaneengesloten lijn {sorted(s)}') if why else False
        placed |= s
    return (True, 'ok') if why else True


def ceil_fixed(moves):
    return M.score_of(moves, FIXED)[0]


def search(seed_moves, iters=6000, seed=0, need_words=True):
    """Lokale zoektocht over ZETSCHEMA's bij vaste bezetting, met woordbaarheidsfilter."""
    rnd = random.Random(seed)
    cur = [list(m) for m in seed_moves]
    best = ceil_fixed(cur)
    bestmv = [list(m) for m in cur]
    for _ in range(iters):
        cand = [list(m) for m in cur]
        op = rnd.random()
        idx = [i for i, m in enumerate(cand) if len(m) > 1]
        if op < 0.45 and idx:
            i = rnd.choice(idx)
            m = sorted(cand[i], key=lambda c: (c[1], c[0]))
            if rnd.random() < 0.5:
                m = m[::-1]
            k = rnd.randrange(1, len(m))
            cand[i:i + 1] = [m[:k], m[k:]]
        elif op < 0.85 and len(cand) > 2:
            i = rnd.randrange(len(cand)); j = rnd.randrange(len(cand))
            if i == j:
                continue
            mv = cand.pop(i); cand.insert(j, mv)
        else:
            i = rnd.randrange(max(1, len(cand) - 1))
            if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                cand[i:i + 2] = [cand[i] + cand[i + 1]]
        if not legal(cand):
            continue
        if need_words and not words_ok(cand):
            continue
        sc = ceil_fixed(cand)
        if sc >= best:
            if sc > best:
                bestmv = [list(m) for m in cand]
            best = sc
            cur = cand
    return best, bestmv


# ------------------------------------------------------------------ generieke bouwer
def chunks(cells, n=7):
    """Hak een lijnstuk in aaneengesloten zetten van <=n tegels (langs de lijn gesorteerd)."""
    cells = sorted(cells, key=lambda c: (c[1], c[0]))
    out, blok = [], []
    for c in cells:
        if blok and (abs(c[0] - blok[-1][0]) + abs(c[1] - blok[-1][1])) == 1 and len(blok) < n:
            blok.append(c)
        else:
            if blok:
                out.append(blok)
            blok = [c]
    if blok:
        out.append(blok)
    return out


def cand_moves(rest, placed, first=False):
    """Alle vorm-legale zetten die NU mogelijk zijn: per lijn elk interval [a,b] met 1..7 nieuwe
    cellen waarvan alle tussenliggende cellen al liggen of in de zet zitten, en dat het bord
    raakt (zet 0: het centrum dekt)."""
    out = []
    lines = [[(x, y) for x in range(15)] for y in range(15)]
    lines += [[(x, y) for y in range(15)] for x in range(15)]
    for line in lines:
        okset = {i for i, c in enumerate(line) if c in rest or c in placed}
        for a in sorted(okset):
            if line[a] not in rest:
                continue
            b, nnew = a, 0
            while b in okset:
                if line[b] in rest:
                    nnew += 1
                if nnew > 7:
                    break
                if line[b] in rest:
                    new = [c for c in line[a:b + 1] if c in rest]
                    s = set(new)
                    if first:
                        if (7, 7) in s:
                            out.append(new)
                    elif any((x + dx, y + dy) in placed
                             for (x, y) in new for dx, dy in M.NB):
                        out.append(new)
                b += 1
    return out


def auto_schedule(cells, brug, finals, finalorder=(7, 0, 14), minzet=False):
    """Bouw zelf een legaal zetschema voor een gegeven BEZETTING.

    Greedy op de m-calculus: kies bij elke stap de zet met het hoogste plafond-na-deze-zet, met
    een bonus voor 7-tegelzetten (een bingo is 50 punten waard).  `brug`-zetten (bv. de twee
    DWS-cellen van een x4-laan) worden ZO LAAT MOGELIJK gelegd -- pas als de rest van hun lijn
    ligt -- zodat de x4 over de volle run scoort; loopt het schema vast, dan mag de brug alsnog
    eerder (hij is soms zelf de enige verbinding naar de rest van de lijn).  De drie slotzetten
    hangen achteraan in `finalorder`."""
    finalcells = {(x, y) for y, xs in finals.items() for x in xs}
    brugcell = {c for b in brug for c in b}
    rest = set(cells) - finalcells - brugcell
    placed, out = set(), []

    def brugcands(force=False):
        got = []
        for b in brug:
            if set(b) & placed or not out:
                continue
            if not force:
                lijn = {c for c in cells
                        if (b[0][1] == b[-1][1] and c[1] == b[0][1])
                        or (b[0][0] == b[-1][0] and c[0] == b[0][0])}
                if lijn & rest:
                    continue
            if M.shape_ok(set(b), placed) and any((x + dx, y + dy) in placed
                                                  for (x, y) in b for dx, dy in M.NB):
                got.append(list(b))
        return got

    while rest or any(not (set(b) & placed) for b in brug):
        cands = cand_moves(rest, placed, first=not out) + brugcands()
        cands = [c for c in cands if move_words_ok(placed, c)]
        if not cands:
            cands = [c for c in brugcands(force=True) if move_words_ok(placed, c)]
        if not cands:
            return None, sorted(rest)
        best, bestv = None, None
        for c in cands:
            v = M.score_of(out + [c], FIXED)[0]
            # MINZET: zo min mogelijk zetten.  Elke extra tussenstap eist een EXTRA woord van
            # dezelfde lijn (elke tussenrun moet zelf een woord zijn); ladderschema's halen
            # daarom wel een hoog m-plafond maar zijn lexicaal vrijwel altijd infeasible.
            key = ((len(c), v) if minzet else (v + (60 if len(c) == 7 else 0), len(c)))
            if bestv is None or key > bestv:
                best, bestv = c, key
        out.append(best)
        placed |= set(best)
        rest -= set(best)
    for y in finalorder:
        z = [(x, y) for x in finals[y] if (x, y) not in placed]
        if z:
            out.append(z); placed |= set(z)
    return out, None


def build(spec):
    """spec: {'center': [cellen], 'cols': {x: [rijen]}, 'rails': {y: [kolommen]},
              'brug': [[cellen],..], 'final': {0:[xs],7:[xs],14:[xs]}, 'finalorder': (7,0,14)}
    Alle 15 cellen van rij 0/7/14 liggen altijd; wat niet in de final staat is pre-cel."""
    cellen = set(spec.get('center', ()))
    for x, ys in sorted(spec.get('cols', {}).items()):
        cellen |= {(x, y) for y in ys}
    for y, xs in sorted(spec.get('rails', {}).items()):
        cellen |= {(x, y) for x in xs}
    for y in (0, 7, 14):
        cellen |= {(x, y) for x in range(15)}
    brug = [list(b) for b in spec.get('brug', [])]
    mv, stuck = auto_schedule(cellen, brug, spec['final'],
                              spec.get('finalorder', (7, 0, 14)),
                              minzet=bool(os.environ.get('MINZET')))
    if mv is None:
        return None, stuck
    return mv, len(cellen)


# ------------------------------------------------------------------ DSL
def V(x, ys): return [(x, y) for y in ys]
def H(y, xs): return [(x, y) for x in xs]
def R(a, b): return list(range(a, b + 1))


# ================================================================== TOPOLOGIEEN
# LEXICALE RANDVOORWAARDEN (gemeten, zie NEWTOPO.md sectie 2).  Met dit triplet bestaat er
#   * GEEN 2-letterwoord dat met de 'q' van (11,0) begint  -> kolom 11 moet minstens 3 lang zijn
#   * GEEN 2-letterwoord dat op de 'y'/'z'/'j' van (3,14)/(8,14)/(13,14) eindigt
#                                                          -> die kolommen minstens 3 lang
#   * volle 15-letterkolommen bestaan alleen op x = 14 (600), 5 (104), 2 (27), 12 (3), 7 (2)
#     -- kolom 0 (g..f..p), 11 (q..r..r) en de rest hebben er NUL.
def t_record():
    """(ref) ons record 4777: 3 ankerrijen, 4 klimkolommen boven (2/5/10/12), 2 onder (4/11),
    rij-4-laan x4.  Referentiepunt voor alle delta's."""
    D = json.load(open(RESCHED))
    return [[tuple(c) for c in m] for m in D['moves']], 101


def _finals(f0=(0, 3, 7, 8, 11, 13, 14), f7=(0, 1, 2, 3, 12, 13, 14),
            f14=(0, 1, 2, 3, 7, 13, 14)):
    return {0: list(f0), 7: list(f7), 14: list(f14)}


# --- RAIL-familie: rij 1 en rij 13 als steunrail --------------------------------
# Kerngedachte (nieuw): rij 1 en rij 13 hebben elk twee DWS op afstand 12 ((1,1)/(13,1) resp.
# (1,13)/(13,13)) en twee TLS ((5,y)/(9,y)).  Een brugzet die BEIDE DWS nieuw dekt scoort de
# hele rail x4 -- over 13 tot 15 cellen, dus 52-60 m-eenheden.  Belangrijker nog: de rail ligt
# direct naast de x27-rij en draagt daardoor ALLE pre-cellen daarvan, zodat de vier
# klimkolommen van de recordtopologie (24-28 tegels) overbodig worden.  En hij maakt de
# randkolommen 0 en 14 bereikbaar, wat zonder rail onmogelijk is.
def t_rail1():
    """(rail1) alleen de bovenrail: rij 1 vol (kolom 11 krijgt een 3-letter q-woord),
    onderhelft blijft de recordconstructie (kolommen 4 en 11)."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 5: R(2, 6), 2: R(2, 6), 4: R(8, 13), 12: R(8, 13)},
        'rails': {1: R(0, 14), 4: R(2, 13), 10: R(4, 11)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)]],
        'final': _finals(),
    })


def t_rail13():
    """(rail13) alleen de onderrail: rij 13 vol; kolommen 3/8/13 krijgen een cel op rij 12
    (geen 2-letterwoord op y/z/j).  Boven blijft de recordconstructie."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 3: [12], 8: [12], 13: [12], 7: R(11, 12)},
        'rails': {4: R(2, 13), 13: R(0, 14)},
        'brug': [[(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail1_13():
    """(H-frame) beide rails: rijen 0,1,7,13,14 + een ruggengraat.  De klimkolommen zijn weg."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 5: R(2, 6) + R(8, 12), 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14), 4: R(2, 13)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)], [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail_col14():
    """(rail+kol14) DE COMBINATIE.  De rails maken kolom 14 bereikbaar -- zonder rail is die
    kolom alleen via (13,4) te bereiken en dat is de bekende blokkade.  Kolom 14 is de enige
    TWS-kolom met een volwaardig 15-letterwoord (s......e......e, 600 stuks) en wordt door
    ALLE DRIE de slotzetten x3 herscoord: 39 + 42 + 45 = 126 m-eenheden voor 12 tegels."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 14: R(2, 6) + R(8, 12), 5: R(2, 6) + R(8, 12),
                 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)], [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail1_col14():
    """(rail1+kol14) alleen de bovenrail + kolom 14: onderaan hangt kolom 14 aan de
    record-achtige kolom 13/12-structuur.  Goedkoper in tegels dan de dubbele rail."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 14: R(2, 6) + R(8, 13), 5: R(2, 6), 2: R(2, 6),
                 13: R(8, 13), 4: R(8, 13)},
        'rails': {1: R(0, 14), 4: R(2, 13)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)]],
        'final': _finals(),
    })


def t_rail13_col14():
    """(rail13+kol14) onderrail + kolom 14; boven de vier klimkolommen van het record."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 12: R(1, 6), 14: R(1, 6) + R(8, 12),
                 3: [12], 8: [12], 13: [12]},
        'rails': {4: R(2, 13), 13: R(0, 14)},
        'brug': [[(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail_col14_col5():
    """(rail+kol14+kol5) idem, maar de ruggengraat is kolom 5 EN kolom 2 (beide lexicaal vol
    mogelijk: e..e..e = 104 woorden, s..e..l = 27)."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 14: R(2, 6) + R(8, 12), 5: R(2, 6) + R(8, 12),
                 2: R(2, 6), 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)], [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail_col14_99():
    """(rail+kol14, 99 tegels) DE COMBINATIE, exact binnen budget.  Rijen 0,1,7,13,14 vol,
    ruggengraat kolom 5 (e..e..e, 104 woorden), kolom 14 vol (s..e..e, 600), kolom 11 drie lang
    voor het q-woord, kolommen 3/8/13 drie lang voor y/z/j.  99 tegels, 2 over."""
    return build({
        'cols': {5: R(2, 6) + R(8, 12), 14: R(2, 6) + R(8, 12), 11: [2],
                 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)],
                 [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail_col14_col2():
    """(rail+kol14+kol2) idem plus kolom 2 vol (s..e..l, 27 woorden) in plaats van de twee
    losse reservetegels: een tweede volle kolom die door alle drie de finals wordt herscoord."""
    return build({
        'cols': {5: R(2, 6) + R(8, 12), 14: R(2, 6) + R(8, 12), 2: R(2, 6) + R(8, 12),
                 11: [2], 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)],
                 [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_rail_col14_lane4():
    """(rail+kol14+laan4) idem plus de x4-laan in rij 4 (DWS (4,4)/(10,4)) als vierde lijn."""
    return build({
        'cols': {5: R(2, 6) + R(8, 12), 14: R(2, 6) + R(8, 12), 11: [2],
                 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 13: R(0, 14), 4: R(2, 12)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)],
                 [(0, 13), (1, 13), (13, 13), (14, 13)],
                 [(4, 4), (10, 4)]],
        'final': _finals(),
    })


def t_rail2_12():
    """(rail2+12) LEXICAAL VEILIGE RAIL-VARIANT: de rails liggen op rij 2 en rij 12 (DWS
    (2,2)/(12,2) resp. (2,12)/(12,12), x4 over 11 cellen) en raken de x27-rijen NIET.  De
    pre-cellen van rij 0/14 worden met losse stubcellen op rij 1/13 aangehaakt, zodat alleen
    daar een verticale 3-run ontstaat -- geen 15 verplichte 2-letterwoorden."""
    return build({
        'cols': {5: R(3, 6) + R(8, 11), 2: [1, 13], 6: [1, 13], 9: [1, 13], 12: [1, 13],
                 14: R(3, 11)},
        'rails': {2: R(2, 12), 12: R(2, 12), 4: R(2, 14)},
        'brug': [[(2, 2), (12, 2)], [(2, 12), (12, 12)]],
        'final': _finals(),
    })


# --- KOLOM-14-LADDER: de rail-familie is lexicaal dood (zie NEWTOPO.md), maar kolom 14 zelf
# leeft.  Het probleem was altijd de BEZORGING: kolom 14 raakt alleen kolom 13, en die is in de
# recordtopologie leeg.  Oplossing: de rij-4-laan tot (13,4) doortrekken (bovenhelft) en een
# stukje rij 13 tot (13,13) (onderhelft).  Kolom 14 wordt dan door alle drie de slotzetten x3
# herscoord: 13-run (rij-7-final) + 14-run (rij-0-final) + 15-run (rij-14-final) = 126 m.
def t_col14_ladder():
    """(kol14-ladder) volle kolom 14, bezorgd via (13,4) boven en (12,13)/(13,13) onder.
    Rij-0-final = {0,3,7,11,12,13,14} zodat er maar DRIE klimkolommen nodig zijn."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6) + R(8, 13), 9: R(1, 6),
                 14: R(1, 6) + R(8, 13), 11: R(8, 13)},
        'rails': {4: R(2, 13), 13: [12, 13]},
        'final': _finals(f0=(0, 3, 7, 11, 12, 13, 14)),
    })


def t_col14_ladder_b():
    """(kol14-ladder-b) idem met de recordachtige vier klimkolommen (2/5/10/12) en de
    rij-0-final van het record; duurder in tegels, maar bingorijker."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 14: R(1, 6) + R(8, 13), 11: R(8, 13), 4: R(8, 13)},
        'rails': {4: R(2, 13), 13: [12, 13]},
        'final': _finals(),
    })


def t_col14_boven():
    """(kol14-boven) alleen de BOVENhelft van kolom 14 (rijen 1..6): het woord is dan
    s......e (rijen 0..7, 1242 woorden) en er zijn twee x3-gebeurtenissen in plaats van drie.
    Goedkoop: 6 tegels, geen onderbezorging nodig."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 14: R(1, 6), 11: R(8, 13), 4: R(8, 13)},
        'rails': {4: R(2, 13), 10: R(4, 11)},
        'final': _finals(),
    })


def t_col14_onder():
    """(kol14-onder) alleen de ONDERhelft (rijen 8..13): woord e......e (rijen 7..14),
    bezorgd via (12,13)/(13,13).  Twee x3-gebeurtenissen (rij-7- en rij-14-final)."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 14: R(8, 13), 11: R(8, 13), 4: R(8, 13)},
        'rails': {4: R(2, 13), 13: [12, 13]},
        'final': _finals(),
        'finalorder': (7, 0, 14),
    })


# --- LANEN ZONDER RAIL: rijen 3/4/10/11 raken de x27-rijen niet, dus geen enkele verplichte
# verticale 2-letterwoord-keten.  Elke laan wordt met een DWS-brugzet x4 gesloten.
def t_twee_lanen():
    """(2 lanen) x4-lanen op rij 4 EN rij 10, beide met een DWS-brugzet gesloten."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 4: R(11, 13), 11: R(11, 13)},
        'rails': {4: R(2, 13), 10: R(2, 12)},
        'brug': [[(4, 4), (10, 4)], [(4, 10), (10, 10)]],
        'final': _finals(),
    })


def t_lanen_3_11():
    """(lanen 3+11) x4-lanen op rij 3 en rij 11 (DWS (3,y)/(11,y), spanwijdte 9) bovenop de
    rij-4-laan; de klimkolommen kruisen ze allemaal."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 12)},
        'rails': {4: R(2, 13), 3: R(3, 11), 11: R(3, 11)},
        'brug': [[(3, 3), (11, 3)], [(3, 11), (11, 11)]],
        'final': _finals(),
    })


def t_lanen_2_12():
    """(lanen 2+12) x4-lanen op rij 2 en rij 12 (DWS spanwijdte 11, DLS op (6,y)/(8,y))."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: R(3, 11), 2: R(2, 12), 12: R(2, 12)},
        'brug': [[(2, 2), (12, 2)], [(2, 12), (12, 12)]],
        'final': _finals(),
    })


def t_lanen_kol14():
    """(2 lanen + kol14) de twee x4-lanen plus de volle kolom 14; de rij-4-laan levert (14,4)
    en de rij-10-laan doorgetrokken tot (14,10) levert de onderhelft."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 12: R(1, 6),
                 14: R(1, 6) + R(8, 13), 11: R(11, 13)},
        'rails': {4: R(2, 14), 10: R(2, 14)},
        'brug': [[(4, 4), (10, 4)], [(4, 10), (10, 10)]],
        'final': _finals(),
    })


def t_kol7_boven():
    """(kol7-boven) kolom 7 rijen 1..3: de rij-0-final herscoort dan het kolomwoord rijen 0..10
    met x3 (11 cellen = 33 m voor 3 tegels).  Kolom 7 mag NIET helemaal vol (k..k..k = 2
    woorden, CP-SAT-infeasible), dus de onderhelft blijft leeg."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {7: R(1, 3), 2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: R(2, 13)},
        'final': _finals(),
    })


# --- overige nieuwe ideeen -------------------------------------------------------
def t_lane_late():
    """(laat-x4) de rij-4-laan wordt PAS gesloten als de rij vol is: de twee DWS (4,4)/(10,4)
    komen als laatste brugzet, zodat de x4 over 15 in plaats van 8 cellen loopt."""
    return build({
        'center': V(7, R(5, 10)),
        'cols': {2: R(1, 6), 5: R(1, 3) + R(5, 6), 10: R(1, 3) + R(5, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: [0, 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 14], 10: R(4, 11)},
        'brug': [[(4, 4), (10, 4)]],
        'final': _finals(),
    })


def t_weave():
    """(weefsel) HERSCORINGSDICHTHEID: twee volle lanen (rij 4 en rij 10) die daarna door
    vijf kolommen worden gekruist -- elke kruising herscoort de hele laan."""
    return build({
        'center': H(7, R(4, 10)),
        'rails': {4: R(0, 14), 10: R(0, 14)},
        'cols': {2: R(1, 3) + R(5, 6) + R(8, 9), 5: R(1, 3) + R(5, 6),
                 10: R(1, 3) + R(5, 6), 12: R(1, 3) + R(5, 6) + R(8, 9),
                 7: R(8, 9) + R(11, 13)},
        'final': _finals(),
    })


def t_x4stack():
    """(x4-stapel) vier x4-lanen: rijen 1, 4, 10 en 13, elk met een DWS-brugzet gesloten."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {11: [2], 5: R(2, 3) + R(11, 12), 3: [12], 8: [12], 13: [12]},
        'rails': {1: R(0, 14), 4: R(2, 12), 10: R(3, 11), 13: R(0, 14)},
        'brug': [[(0, 1), (1, 1), (13, 1), (14, 1)], [(4, 4), (10, 4)], [(4, 10), (10, 10)],
                 [(0, 13), (1, 13), (13, 13), (14, 13)]],
        'final': _finals(),
    })


def t_halfcol0():
    """(halfkol0) kolom 0 ONDERhelft (rijen 8..13): het woord is dan f......p (rijen 7..14,
    24 woorden), want de VOLLE kolom 0 (g..f..p) heeft er nul.  Twee x3-gebeurtenissen."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 0: R(8, 13), 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: R(2, 13), 13: R(0, 4)},
        'final': _finals(),
        'finalorder': (7, 14, 0),
    })


def t_col5():
    """(kol5) volle kolom 5 (e..e..e) met TLS op (5,1)/(5,5)/(5,9)/(5,13).  Kolom 5 heeft GEEN
    enkele WM -- test of een lexicaal makkelijke volle kolom zonder TWS iets oplevert."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {5: R(1, 6) + R(8, 13), 2: R(1, 6), 10: R(1, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: R(2, 13)},
        'final': _finals(),
        'finalorder': (7, 0, 14),
    })


def t_row0_smallfinal():
    """(kleine-final) rij-0-final met vijf tegels (0,3,7,11,14): alleen TWS+DLS in de final,
    grotere pre-groepen.  Test of minder final-cellen loont (het kost 27*waarde per cel)."""
    return build({
        'center': V(7, R(4, 10)),
        'cols': {2: R(1, 6), 5: R(1, 6), 9: R(1, 6), 12: R(1, 6),
                 4: R(8, 13), 11: R(8, 13)},
        'rails': {4: R(2, 13), 10: R(4, 11)},
        'final': _finals(f0=(0, 3, 7, 11, 14), f7=(0, 1, 2, 3, 12, 13, 14),
                         f14=(0, 3, 7, 11, 14)),
    })


TOPOS = [
    ('ref record 4777', t_record),
    ('rail1 (bovenrail)', t_rail1),
    ('rail13 (onderrail)', t_rail13),
    ('rail1+13 (H-frame)', t_rail1_13),
    ('rail1+13 + kol14', t_rail_col14),
    ('rail1 + kol14', t_rail1_col14),
    ('rail13 + kol14', t_rail13_col14),
    ('rail+kol14+kol5+kol2', t_rail_col14_col5),
    ('rail+kol14 (99 tegels)', t_rail_col14_99),
    ('rail+kol14+kol2', t_rail_col14_col2),
    ('rail+kol14+laan4', t_rail_col14_lane4),
    ('rail2+12 (lex-veilig)', t_rail2_12),
    ('kol14-ladder (3 klimmers)', t_col14_ladder),
    ('kol14-ladder-b (4 klimmers)', t_col14_ladder_b),
    ('kol14-boven (rijen 1..6)', t_col14_boven),
    ('kol14-onder (rijen 8..13)', t_col14_onder),
    ('2 lanen (rij 4+10)', t_twee_lanen),
    ('lanen rij 3+11', t_lanen_3_11),
    ('lanen rij 2+12', t_lanen_2_12),
    ('2 lanen + kol14', t_lanen_kol14),
    ('kol7-boven (rijen 1..3)', t_kol7_boven),
    ('laat-x4 (rij-4-brug laatst)', t_lane_late),
    ('weefsel (lanen eerst)', t_weave),
    ('x4-stapel (rij 1/4/10/13)', t_x4stack),
    ('halfkol0 (rijen 8..13)', t_halfcol0),
    ('kol5 vol (e..e..e)', t_col5),
    ('kleine rij-0-final', t_row0_smallfinal),
]


def trim_to_cap(moves, cap=CAP):
    """Het bord draagt hoogstens `cap` tegels (de tegenstander houdt er minstens een).  Gooi
    net zo lang de cel met de LAAGSTE m weg als het schema legaal EN woordbaar blijft, zodat
    alle topologieen op hetzelfde tegelbudget worden vergeleken."""
    cur = [list(z) for z in moves]
    weg = []
    while sum(len(z) for z in cur) > cap:
        m = M.multiplicity(cur)
        for _, c in sorted((v, c) for c, v in m.items()):
            if c[1] in (0, 7, 14):                      # ankerrijen blijven heel
                continue
            cand = [[q for q in z if q != c] for z in cur]
            cand = [z for z in cand if z]
            if legal(cand) and words_ok(cand):
                cur = cand; weg.append(c); break
        else:
            return None, weg
    return cur, weg


def analyse(naam, fn, iters):
    try:
        mv, n = fn()
    except Exception as e:                                     # bouwfout = topologie ongeldig
        return {'naam': naam, 'status': f'bouwfout: {e}'}
    if mv is None:
        return {'naam': naam, 'status': f'onleverbaar: {n[:6] if n else ""}'}
    tiles = sum(len(z) for z in mv)
    ok, msg = legal(mv, why=True)
    row = {'naam': naam, 'tegels': tiles, 'zetten': len(mv),
           'bingos': sum(1 for z in mv if len(z) == 7)}
    if not ok:
        row['status'] = f'illegaal: {msg}'
        return row
    if tiles > CAP:
        row['ruw'] = tiles
        mv, weg = trim_to_cap(mv)
        if mv is None:
            row['status'] = f'OVER CAP ({tiles}) en niet te trimmen'
            return row
        row['getrimd'] = [list(c) for c in weg]
        tiles = sum(len(z) for z in mv)
        row['tegels'] = tiles
        row['bingos'] = sum(1 for z in mv if len(z) == 7)
    wok, bad = words_ok(mv, why=True)
    row['woordbaar'] = wok
    row['woordbreuk'] = None if wok else [list(c) for c in bad]
    row['seed'] = ceil_fixed(mv)   # plafond van het greedy-schema (MINZET=1 => ladderloos)
    dg = diagnose(mv)
    row['dode_lijnen'] = [[list(k), n] for k, n, _a, _b in dg]
    base = ceil_fixed(mv)
    row['seed_plafond'] = base
    best, bmv = base, mv
    for s in range(3):
        b, m = search(mv, iters=iters, seed=s, need_words=wok)
        if b > best:
            best, bmv = b, m
    row['ankervast'] = best
    row['bingos_best'] = sum(1 for z in bmv if len(z) == 7)
    row['status'] = 'ok'
    row['moves'] = [[list(c) for c in z] for z in bmv]
    return row


# ------------------------------------------------------------------ diagnose per lijn
def diagnose(mv, topn=3):
    """Waarom is een geometrie lexicaal infeasible?  De woordbaarheidstest keurt elke run
    APART; in werkelijkheid moeten ALLE runs op dezelfde lijn door EEN letterrij worden
    waargemaakt.  Een lijn die stapsgewijs wordt gelegd eist dus dat elke tussenstand zelf een
    woord is.  Deze functie neemt per lijn de langste run, loopt haar woordtabel af en kijkt of
    er een woord is waarvan alle deelruns ook woorden zijn."""
    placed, runs = set(), set()
    for cells in mv:
        for run in move_runs(placed, cells):
            runs.add(tuple(run))
        placed |= set(cells)
    perline = {}
    for run in runs:
        key = ('H', run[0][1]) if run[0][1] == run[-1][1] else ('V', run[0][0])
        perline.setdefault(key, []).append(run)
    bad = []
    for key, rs in sorted(perline.items()):
        rs.sort(key=len)
        big = rs[-1]
        pos = {c: i for i, c in enumerate(big)}
        subs = [tuple(pos[c] for c in q) for q in rs[:-1] if all(c in pos for c in q)]
        fx = {i: FIXED[c] for i, c in enumerate(big) if c in FIXED}
        tab = [w for w in BYLEN.get(len(big), []) if all(w[i] == v for i, v in fx.items())]
        ok = 0
        for w in tab:
            if all(tuple(w[i] for i in sub) in _WSET.get(len(sub), ()) for sub in subs):
                ok += 1
                if ok >= topn:
                    break
        if ok == 0:
            bad.append((key, len(big), len(rs), len(tab)))
    return bad


_WSET = {}
for _L, _ws in BYLEN.items():
    _WSET[_L] = set(_ws)


# ------------------------------------------------------------------ CP-SAT-vulling
def fit(mv, tlim=600, nw=8, hint=None):
    """Vul een geometrie met echte woorden en maximaliseer de score.  Elke gescoorde run krijgt
    een add_allowed_assignments-tabel (de woorden van die lengte die op de vaste ankerletters
    passen), de zak is een telbeperking, en hoogstens twee cellen zijn blanco (waarde 0).
    Model identiek aan mg_insert.solve, maar voor een WILLEKEURIGE geometrie."""
    from ortools.sat.python import cp_model
    import numpy as np
    LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
    bag = Counter({c: r.counts[c] for c in r.counts})
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
        for run in move_runs(placed, cells):
            events.append((run, set(cells))); runs.add(tuple(run))
        placed |= set(cells)
    for run in sorted(runs, key=len):
        fx = {i: fixed[c] for i, c in enumerate(run) if c in fixed}
        tab = [w for w in BYLEN.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab:
            return 'nowords', list(run), None, None
        m_.add_allowed_assignments([L[c] for c in run], tab)
    BL = {c: m_.new_bool_var(f'bl{c}') for c in free}
    m_.add(sum(BL.values()) <= 2)
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
        m_.add(sum(cnt) + sum(1 for c, v in fixed.items() if v == ch) <= bag[ch])
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
    m_.maximize(sum(obj) + bingos)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = tlim
    sol.parameters.num_workers = nw
    sol.parameters.log_search_progress = True
    st = sol.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeasible' if st == cp_model.INFEASIBLE else 'unknown'), None, None, None
    g = [[0] * 15 for _ in range(15)]
    for c in occ:
        g[c[1]][c[0]] = sol.value(L[c])
    return 'ok', sol.objective_value, g, {c for c in free if sol.value(BL[c])}


def run_fit():
    naam = os.environ['FIT']
    fn = dict(TOPOS)[naam]
    mv, n = fn()
    if mv is None:
        print('onleverbaar', n); return
    if sum(len(z) for z in mv) > CAP:
        mv, weg = trim_to_cap(mv)
        print('getrimd', weg)
    best, bmv = ceil_fixed(mv), mv
    for sd in range(int(os.environ.get('SEEDS', '3')) if not os.environ.get('MINZET') else 0):
        b, m2 = search(mv, iters=int(os.environ.get('ITERS', '3000')), seed=sd)
        if b > best:
            best, bmv = b, m2
    print(f'{naam}: {sum(len(z) for z in bmv)} tegels, {len(bmv)} zetten, '
          f'{sum(1 for z in bmv if len(z)==7)} bingo, ankervast plafond {best}', flush=True)
    st, ob, g, bl = fit(bmv, tlim=float(os.environ.get('TLIM', '900')),
                        nw=int(os.environ.get('NW', '8')))
    print('CP-SAT:', st, ob, flush=True)
    if st == 'ok':
        tot, per, ok, msg = MG.score_game([row[:] for row in g], bmv, bl)
        print(f'ARBITER {int(tot)} ok={ok} {"" if ok else msg[:120]}', flush=True)
        out = os.environ.get('FITOUT', '/home/bob/programming/scrabble4/experiments/results/'
                             'newtopo_fit.json')
        json.dump({'grid': g, 'moves': [[list(c) for c in z] for z in bmv],
                   'blanks': [list(b) for b in sorted(bl)], 'total': int(tot),
                   'ok': bool(ok), 'topologie': naam, 'triple': list(TRIPLET)},
                  open(out, 'w'))
        print('->', out, flush=True)


def main():
    iters = int(os.environ.get('ITERS', '4000'))
    only = set(filter(None, os.environ.get('ONLY', '').split(',')))
    rows = []
    for naam, fn in TOPOS:
        if only and not any(o in naam for o in only):
            continue
        r_ = analyse(naam, fn, iters)
        rows.append(r_)
        s = r_.get('ankervast')
        print(f"{naam:30s} {r_['status'][:26]:26s} tegels {r_.get('tegels','-'):>4} "
              f"bingo {r_.get('bingos_best', r_.get('bingos','-')):>3} "
              f"seed {r_.get('seed','-'):>5} ladder {s if s else '-'} "
              f"dode-lijnen {r_.get('dode_lijnen','-')}", flush=True)
        if r_.get('woordbreuk'):
            print(f"{'':32s}   eerste onwoordbare run: {r_['woordbreuk']}", flush=True)
    ref = next((x for x in rows if x['naam'].startswith('ref')), None)
    if ref and ref.get('ankervast'):
        print(f"\nreferentie ankervast plafond (record) = {ref['ankervast']}; "
              f"gerealiseerd 4777 (realisatiegraad {4777/ref['ankervast']:.3f})")
        print(f"{'topologie':30s} {'seed':>7s} {'d_ref':>7s} {'ladder':>8s} {'schatting':>10s}")
        for x in sorted([q for q in rows if q.get('ankervast')], key=lambda q: -q['seed']):
            g = 4777 / ref['seed']
            print(f"{x['naam']:30s} {x['seed']:7d} {x['seed']-ref['seed']:+7d} "
                  f"{x['ankervast']:8d} {int(x['seed']*g):10d}"
                  + ('   DOOD: ' + str(x['dode_lijnen']) if x['dode_lijnen'] else ''))
    out = '/home/bob/programming/scrabble4/experiments/results/newtopo.json'
    json.dump(rows, open(out, 'w'), indent=1)
    print('->', out)


if __name__ == '__main__':
    if os.environ.get('FIT'):
        run_fit()
    else:
        main()
