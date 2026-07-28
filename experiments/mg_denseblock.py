"""DICHTE-BLOK-TOPOLOGIEEN: verticale woorden in AANGRENZENDE kolommen.

Diagnose die dit script uitbuit (zie CLASSBOUND.md sectie 4): op het record staan de verticale
woorden in de kolommen 2,4,5,7,10,11,12 -- te ver uit elkaar.  De middenrijen 1/3/5/6/9/10/11/12/13
bevatten daardoor losse, niet-aangrenzende tegels en vormen GEEN horizontaal woord; ze leveren
samen 0 punten terwijl de per-lijn-analyse 55-94 per rij mogelijk acht.  De hefboom is dat een
tegel die in een verticaal EN een horizontaal woord ligt twee keer wordt gescoord.

Dit script bouwt bezettingen waarin de verticale woorden in aangrenzende kolommen staan (een
"blok"), waardeert ze met de m-calculus (mg_mceiling) en filtert op woordbaarheid.  Alles wat
bewezen goed is blijft staan: hetzelfde triplet en dezelfde drie maskers.

Harde randvoorwaarde die elke blokvorm meteen tekent (BEZORGBAARHEID):
  De maskercellen van rij 0 / 7 / 14 worden pas in de slotzet gelegd.  Daardoor valt rij 0
  uiteen in pre-groepen {1,2} {4,5,6} {9,10} {12} en rij 14 in {4,5,6} {8,9,10,11,12}.  Elke
  pre-groep is tot de slotzet een EILAND op zijn rij en kan dus alleen door een kolom worden
  aangeraakt: er moet een tegel op (x,1) resp. (x,13) liggen met x in die groep.  Een blok dat
  die groepen niet raakt is onleverbaar -- dat is de eerste zeef.

CLI:
  .venv/bin/python experiments/mg_denseblock.py                # sweep + tabel
  FIT=<naam> TLIM=900 .venv/bin/python experiments/mg_denseblock.py   # CP-SAT + arbiter
"""
import os, sys, json, itertools, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG
import mg_mceiling as M
import mg_newtopo as T

CAP = 101
FIN = T._finals()            # rij 0 {0,3,7,8,11,13,14}, rij 7 {0,1,2,3,12,13,14}, rij 14 {0,1,2,3,7,13,14}
FIXED = T.FIXED
RES = '/home/bob/programming/scrabble4/experiments/results'


# ------------------------------------------------------------------ pre-groepen / bezorging
def pre_groups(y):
    """De aaneengesloten groepen van rij y die NIET in de slotzet zitten."""
    F = set(FIN[y]); out, cur = [], []
    for x in range(15):
        if x in F:
            if cur: out.append(cur)
            cur = []
        else:
            cur.append(x)
    if cur: out.append(cur)
    return out


PRE0, PRE7, PRE14 = pre_groups(0), pre_groups(7), pre_groups(14)


def support_gaps(up, lo):
    """Welke pre-groepen van rij 0 / rij 14 hebben geen dragende kolom?
    up/lo: {kolom: verzameling rijen}."""
    bad = []
    for g in PRE0:
        if not any(1 in up.get(x, ()) for x in g): bad.append(('rij0', tuple(g)))
    for g in PRE14:
        if not any(13 in lo.get(x, ()) for x in g): bad.append(('rij14', tuple(g)))
    return bad


def add_support(up, lo, hoogte=6):
    """Voeg stubs toe voor pre-groepen zonder drager.  Een stub moet niet alleen de pre-groep
    RAKEN maar ook zelf BEZORGBAAR zijn; de enige structuur waar een bovenkolom aan kan hangen is
    rij 7 (of een laan).  Volle stubs (rijen 1..6 resp. 8..13) hangen na de rij-7-slotzet altijd
    aan rij 7 en zijn dus altijd bezorgbaar -- daarom is 6 de default."""
    up = {k: set(v) for k, v in up.items()}
    lo = {k: set(v) for k, v in lo.items()}
    for g in PRE0:
        if any(1 in up.get(x, ()) for x in g): continue
        x = max(g, key=lambda c: TABLE_UP.get((c, 8 if hoogte >= 6 else hoogte + 1), 0))
        up.setdefault(x, set()).update(range(7 - hoogte, 7))
    for g in PRE14:
        if any(13 in lo.get(x, ()) for x in g): continue
        x = max(g, key=lambda c: TABLE_LO.get((c, 8 if hoogte >= 6 else hoogte + 1), 0))
        lo.setdefault(x, set()).update(range(8, 8 + hoogte))
    return up, lo


# ------------------------------------------------------------------ lexicale kolomtabellen
def _tables():
    """TABLE_UP[(x,L)] = #woorden van lengte L die op rij 0 beginnen met de ankerletter van
    kolom x (en op rij 7 eindigen als L == 8).  Idem TABLE_LO voor de onderhelft."""
    up, lo = {}, {}
    for x in range(15):
        a, b, c = FIXED[(x, 0)], FIXED[(x, 7)], FIXED[(x, 14)]
        for L in range(2, 9):
            if L == 8:
                up[(x, L)] = sum(1 for w in T.BYLEN[8] if w[0] == a and w[7] == b)
                lo[(x, L)] = sum(1 for w in T.BYLEN[8] if w[0] == b and w[7] == c)
            else:
                up[(x, L)] = sum(1 for w in T.BYLEN[L] if w[0] == a)
                lo[(x, L)] = sum(1 for w in T.BYLEN[L] if w[-1] == c)
    return up, lo


TABLE_UP, TABLE_LO = _tables()


def col_ok(up, lo, lanes=()):
    """Weiger bezettingen waarvan de MAXIMALE verticale run in een kolom geen enkel woord heeft
    dat op de vaste ankerletters past (noodzakelijke voorwaarde; zelfde test als
    mg_newtopo.table_nonempty, maar al vóór het schema)."""
    occ = set()
    for d in (up, lo):
        for x, ys in d.items(): occ |= {(x, y) for y in ys}
    for y, xs in dict(lanes).items(): occ |= {(x, y) for x in xs}
    for y in (0, 7, 14): occ |= {(x, y) for x in range(15)}
    bad = []
    for x in range(15):
        y = 0
        while y < 15:
            if (x, y) not in occ: y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (x, y1 + 1) in occ: y1 += 1
            run = [(x, yy) for yy in range(y, y1 + 1)]
            if len(run) >= 2 and not T.table_nonempty(run): bad.append((x, y, y1))
            y = y1 + 1
    return bad


# ------------------------------------------------------------------ VRIJE SCHEMABOUWER
# `mg_newtopo.auto_schedule` hangt de drie slotzetten ALTIJD achteraan.  Het record doet dat
# aantoonbaar niet: daar is de rij-7-slotzet zet 23 van de 33, en de tegels (2,8)/(2,9)/(2,10)
# hangen daarna aan de zojuist gelegde rij 7.  Dat is precies de vrijheid die een dicht blok
# nodig heeft: een kolom in de kolommen 0-3 / 12-14 kan aan geen enkele structuur hangen TOTDAT
# rij 7 er ligt.  Deze bouwer behandelt een slotzet daarom als gewone kandidaat, zodra de rest
# van zijn rij ligt (eerder mag niet: dan zou de slotzet geen 15-letterwoord voltooien).
def schedule(cells, finals=None, seed=0, bingobonus=60, rnd_k=0, boete=0):
    """boete: strafpunten per TIJDELIJKE run (een gescoorde run die geen maximale run van het
    EINDbord is).  Elke tijdelijke run is een extra woord dat moet bestaan bovenop de runs die
    het eindbord toch al eist; dat is precies de 'lexicale schuld' van een ladderschema.  Met
    boete=0 maximeert de bouwer alleen het m-plafond (en wordt hij vaak CP-SAT-infeasible)."""
    import random
    finals = finals or FIN
    eind = {tuple(r) for r in board_runs(cells)}
    rnd = random.Random(seed)
    fincells = {y: [(x, y) for x in finals[y]] for y in (0, 7, 14)}
    rest = set(cells) - {c for z in fincells.values() for c in z}
    todo = set((0, 7, 14))
    placed, out = set(), []
    while rest or todo:
        cands = T.cand_moves(rest, placed, first=not out)
        cands = [c for c in cands if T.move_words_ok(placed, c)]
        for y in sorted(todo):
            z = fincells[y]
            if any(c in placed for c in z): continue
            if any((x, y) not in placed for x in range(15) if (x, y) not in z): continue
            if not out and (7, 7) not in set(z): continue
            if out and not any((x + dx, y + dy) in placed for (x, y) in z for dx, dy in M.NB):
                continue
            if T.move_words_ok(placed, z): cands.append(z)
        if not cands:
            return None, sorted(rest) + [('final', y) for y in sorted(todo)]
        scored = []
        for c in cands:
            v = M.score_of(out + [c], FIXED)[0] + (bingobonus if len(c) == 7 else 0)
            if boete:
                v -= boete * sum(1 for r in T.move_runs(placed, c) if tuple(r) not in eind)
            scored.append((v, c))
        scored.sort(key=lambda t: -t[0])
        pick = scored[rnd.randrange(min(rnd_k, len(scored)))][1] if rnd_k > 1 else scored[0][1]
        out.append(pick); placed |= set(pick)
        rest -= set(pick)
        for y in list(todo):
            if set(fincells[y]) <= placed: todo.discard(y)
    return out, None


def build_free(up, lo, lanes=(), tries=1):
    cells = set()
    for d in (up, lo):
        for x, ys in d.items(): cells |= {(x, y) for y in ys}
    for y, xs in dict(lanes).items(): cells |= {(x, y) for x in xs}
    for y in (0, 7, 14): cells |= {(x, y) for x in range(15)}
    best, bstuck = None, None
    for s in range(tries):
        mv, stuck = schedule(cells, seed=s, rnd_k=1 if s == 0 else 3)
        if mv is None:
            bstuck = stuck; continue
        v = T.ceil_fixed(mv)
        if best is None or v > best[0]: best = (v, mv)
    return (best[1] if best else None), (bstuck if best is None else len(cells))


# ------------------------------------------------------------------ bouw + waardering
def spec_of(up, lo, lanes=(), brug=()):
    cols = {}
    for x, ys in up.items(): cols.setdefault(x, []).extend(sorted(ys))
    for x, ys in lo.items(): cols.setdefault(x, []).extend(sorted(ys))
    sp = {'cols': {x: sorted(set(ys)) for x, ys in cols.items() if ys},
          'rails': {y: list(xs) for y, xs in dict(lanes).items()},
          'final': FIN}
    if brug: sp['brug'] = [list(b) for b in brug]
    return sp


def tiles_of(up, lo, lanes=()):
    cells = set()
    for d in (up, lo):
        for x, ys in d.items(): cells |= {(x, y) for y in ys}
    for y, xs in dict(lanes).items(): cells |= {(x, y) for x in xs}
    cells = {c for c in cells if c[1] not in (0, 7, 14)}
    return 45 + len(cells)


def evaluate(naam, up, lo, lanes=(), brug=(), iters=1200, seeds=2, verbose=True, lex=0):
    gaps = support_gaps(up, lo)
    rec = {'naam': naam, 'tegels_ruw': tiles_of(up, lo, lanes),
           'up': {x: sorted(v) for x, v in up.items()}, 'lo': {x: sorted(v) for x, v in lo.items()},
           'lanes': {y: list(xs) for y, xs in dict(lanes).items()}}
    if gaps:
        rec['status'] = f'ONLEVERBAAR (pre-groep zonder drager: {gaps})'
        if verbose: print(f"{naam:32s} {rec['status']}", flush=True)
        return rec
    dun = col_ok(up, lo, lanes)
    if dun:
        rec['status'] = f'LEXICAAL DOOD (lege kolomtabel: {dun})'
        if verbose: print(f"{naam:32s} {rec['status']}", flush=True)
        return rec
    t0 = time.time()
    try:
        mv, n = build_free(up, lo, lanes, tries=int(os.environ.get('TRIES', '3')))
    except Exception as e:
        rec['status'] = f'bouwfout {e}'
        if verbose: print(f"{naam:32s} {rec['status']}", flush=True)
        return rec
    if mv is None:
        rec['status'] = f'schema vast: {n[:6]}'
        if verbose: print(f"{naam:32s} {rec['status']}", flush=True)
        return rec
    tiles = sum(len(z) for z in mv)
    if tiles > CAP:
        mv2, weg = T.trim_to_cap(mv)
        if mv2 is None:
            rec['status'] = f'OVER CAP {tiles}, niet trimbaar'
            if verbose: print(f"{naam:32s} {rec['status']}", flush=True)
            return rec
        rec['getrimd'] = [list(c) for c in weg]
        mv = mv2; tiles = sum(len(z) for z in mv)
    base = T.ceil_fixed(mv)
    best, bmv = base, mv
    for s in range(seeds):
        b, m = T.search(mv, iters=iters, seed=s)
        if b > best: best, bmv = b, m
    rec.update({'tegels': tiles, 'zetten': len(bmv),
                'bingos': sum(1 for z in bmv if len(z) == 7),
                'seed': base, 'plafond': best,
                'dood': [[list(k), L, nr, nt] for k, L, nr, nt in T.diagnose(bmv)],
                'moves': [[list(c) for c in z] for z in bmv],
                'sec': round(time.time() - t0, 1), 'status': 'ok'})
    if lex:
        # de lexicale test op het GREEDY-schema (dat heeft de minste tussenruns en is dus de
        # gunstigste kans die deze bezetting heeft); NEE = de bezetting is definitief weerlegd.
        v, st, runs = lex_feasible(mv, tlim=lex, nw=4)
        rec['lex'] = v; rec['nruns'] = len(runs)
    if verbose:
        print(f"{naam:32s} tegels {tiles:3d} zet {len(bmv):3d} bingo {rec['bingos']:2d} "
              f"seed {base:5d} plafond {best:5d} lex {rec.get('lex','-'):8s} "
              f"dood {rec['dood']}", flush=True)
    return rec


# ------------------------------------------------------------------ blokvormen
def blok(a, b, rows):
    return {x: set(rows) for x in range(a, b + 1)}


def RANGE(a, b): return list(range(a, b + 1))


def ref_record(pad=f'{RES}/maxgame_BEST.json'):
    """De EXACTE bezetting van het record als (up, lo, lanes) -- de enige eerlijke meetlat.
    (Een met de hand nagebouwde 'record-achtige' bezetting mist de zes vultegels en meet 100
    plafondpunten te laag.)"""
    D = json.load(open(pad))
    cells = {tuple(c) for z in D['moves'] for c in z}
    up, lo = {}, {}
    for (x, y) in cells:
        if y in (0, 7, 14): continue
        (up if y < 7 else lo).setdefault(x, set()).add(y)
    return up, lo, []


# ================================================================== SYSTEMATISCHE ZOEKRUIMTE
# De bezorgbaarheidszeef legt de bovenhelft bijna vast: elk van de rij-0-pre-groepen {1,2},
# {4,5,6}, {9,10} en {12} heeft een kolom nodig die tot rij 1 reikt.  Dat zijn VIER kolommen
# op vaste, uit elkaar liggende posities -- de recordtopologie.  De enige vrijheid voor een
# dicht blok is dus: rond zo'n verplichte drager EXTRA aangrenzende kolommen zetten.  Idem
# onder, waar de pre-groepen {4,5,6} en {8,9,10,11,12} elk een kolom tot rij 13 vragen.
#
# hoogte h: boven = rijen (7-h)..6, onder = rijen 8..(7+h).  h=6 raakt rij 1 resp. rij 13 en
# is dus de enige hoogte die als DRAGER kan dienen; kortere kolommen hangen aan rij 7.
G1 = {'g1-rec': {2: 6}, 'g1-paar': {1: 6, 2: 6}, 'g1-1kort': {1: 3, 2: 6},
      'g1-2kort': {1: 6, 2: 3}, 'g1-alt': {1: 6}}
G2 = {'g2-rec': {5: 6}, 'g2-45': {4: 6, 5: 6}, 'g2-56': {5: 6, 6: 6},
      'g2-456': {4: 6, 5: 6, 6: 6}, 'g2-5+6k': {5: 6, 6: 3}, 'g2-4k+5': {4: 3, 5: 6},
      'g2-alt6': {6: 6}, 'g2-6+5k': {5: 3, 6: 6}}
G3 = {'g3-rec': {10: 6}, 'g3-910': {9: 6, 10: 6}, 'g3-9k+10': {9: 3, 10: 6},
      'g3-9+10k': {9: 6, 10: 3}, 'g3-alt9': {9: 6}, 'g3-8910': {8: 6, 9: 6, 10: 6},
      'g3-10+11k': {10: 6, 11: 3}, 'g3-89k+10': {8: 3, 9: 3, 10: 6}}
G4 = {'g4-rec': {12: 6}, 'g4-11k+12': {11: 3, 12: 6}, 'g4-12+13k': {12: 6, 13: 3},
      'g4-1112': {11: 6, 12: 6}, 'g4-11k12+13k': {11: 3, 12: 6, 13: 3}}
L1 = {'l1-rec': {4: 6}, 'l1-45': {4: 6, 5: 6}, 'l1-4+5k': {4: 6, 5: 3},
      'l1-456': {4: 6, 5: 6, 6: 6}, 'l1-alt6': {6: 6}, 'l1-56': {5: 6, 6: 6},
      'l1-3k+4': {3: 3, 4: 6}, 'l1-4+5k6k': {4: 6, 5: 3, 6: 3}}
L2 = {'l2-rec': {11: 6}, 'l2-1112': {11: 6, 12: 6}, 'l2-10k+11': {10: 3, 11: 6},
      'l2-11+12k': {11: 6, 12: 3}, 'l2-alt12': {12: 6}, 'l2-101112': {10: 6, 11: 6, 12: 6},
      'l2-9k10k+11': {9: 3, 10: 3, 11: 6}, 'l2-8k9k10k+11': {8: 3, 9: 3, 10: 3, 11: 6},
      'l2-9k10k+11+12k': {9: 3, 10: 3, 11: 6, 12: 3}}
# PLANKEN: de woordrechthoek-meting (MODE RECT) laat zien dat een blok dat rij 1 of rij 13
# HAALT lexicaal muurvast zit (kolomwoord = 8 letters met twee vaste ankerletters: boven max
# breedte 4, onder max breedte 3), maar dat een blok dat alleen AAN RIJ 7 HANGT (rijen 4-6 of
# rijen 8-10, kolomwoord = 4 letters met een vaste letter) tot breedte 6 overal bestaat.
# Vandaar deze twee extra assen: brede, lage planken direct boven en onder rij 7.
P5 = {'p5-geen': (), 'p5-2t6': RANGE(2, 6), 'p5-4t10': RANGE(4, 10), 'p5-2t12': RANGE(2, 12),
      'p5-8t12': RANGE(8, 12), 'p5-1t6': RANGE(1, 6), 'p5-9t13': RANGE(9, 13),
      'p5-4t6': RANGE(4, 6), 'p5-5t9': RANGE(5, 9), 'p5-2t9': RANGE(2, 9)}
P8 = {'p8-geen': (), 'p8-2t6': RANGE(2, 6), 'p8-4t10': RANGE(4, 10), 'p8-2t12': RANGE(2, 12),
      'p8-8t12': RANGE(8, 12), 'p8-4t11': RANGE(4, 11), 'p8-9t13': RANGE(9, 13),
      'p8-4t6': RANGE(4, 6), 'p8-5t9': RANGE(5, 9), 'p8-2t9': RANGE(2, 9)}
AS = [G1, G2, G3, G4, L1, L2, P5, P8]
BASIS = ['g1-rec', 'g2-rec', 'g3-rec', 'g4-rec', 'l1-rec', 'l2-rec', 'p5-geen', 'p8-geen']
LANEN = {'laan4': [(4, RANGE(2, 14))], 'geen': [], 'laan4+10': [(4, RANGE(2, 14)),
                                                               (10, RANGE(3, 11))]}


def occ_of(keuze, laan='laan4', center=True):
    """keuze = acht sleutels (g1,g2,g3,g4,l1,l2,p5,p8).  Levert (up, lo, lanes)."""
    up, lo = {}, {}
    for k, D in zip(keuze[:4], AS[:4]):
        for x, h in D[k].items(): up[x] = max(up.get(x, 0), h)
    for k, D in zip(keuze[4:6], AS[4:6]):
        for x, h in D[k].items(): lo[x] = max(lo.get(x, 0), h)
    if center:                      # de centrumbingo van het record: kolom 7 rijen 4..10
        up[7] = max(up.get(7, 0), 2)
        lo[7] = max(lo.get(7, 0), 3)
    UP = {x: set(range(7 - h, 7)) for x, h in up.items()}
    LO = {x: set(range(8, 8 + h)) for x, h in lo.items()}
    if len(keuze) > 6:
        for x in P5[keuze[6]]: UP.setdefault(x, set()).update((5, 6))
        for x in P8[keuze[7]]: LO.setdefault(x, set()).update((8, 9))
    return UP, LO, LANEN[laan]


def coord_search(rondes=3, laan='laan4', verbose=True):
    """Coordinaatstijging over de zes groepskeuzes: begin bij de recordtopologie en verwissel
    steeds EEN groep tegen alle alternatieven.  Zo blijft het aantal evaluaties lineair in de
    grootte van de zoekruimte in plaats van multiplicatief."""
    cur = list(BASIS)
    hist, cache = [], {}

    def sc(keuze, naam):
        key = tuple(keuze) + (laan,)
        if key in cache: return cache[key]
        up, lo, lanes = occ_of(keuze, laan)
        r = evaluate(naam, up, lo, lanes, iters=int(os.environ.get('ITERS', '800')),
                     seeds=1, verbose=verbose, lex=int(os.environ.get('LEX', '0')))
        r['keuze'] = list(keuze); r['laan'] = laan
        cache[key] = r; hist.append(r)
        return r

    best = sc(cur, 'BASIS ' + '/'.join(cur))
    bestv = best.get('seed', -1) if (not best.get('dood')
                                     and best.get('lex', 'JA') != 'NEE') else -1
    for ronde in range(rondes):
        verbeterd = False
        for i, D in enumerate(AS):
            for k in D:
                if k == cur[i]: continue
                kand = list(cur); kand[i] = k
                r = sc(kand, f'r{ronde} {k}')
                v = r.get('seed', -1) if (r.get('status') == 'ok' and not r.get('dood')
                                          and r.get('lex', 'JA') != 'NEE') else -1
                if v > bestv and r.get('tegels', 999) <= CAP:
                    bestv, cur, verbeterd = v, kand, True
        if verbose: print(f'-- ronde {ronde}: {bestv} {cur}', flush=True)
        if not verbeterd: break
    return cur, bestv, hist


def kandidaten():
    """De blokvormen die we willen meten.  Naamgeving: U<a-b> = bovenblok kolommen a..b
    (rijen 1-6), L<a-b> = onderblok (rijen 8-13)."""
    K = []
    UP6 = RANGE(1, 6)
    LO6 = RANGE(8, 13)
    # --- referentie: de EXACTE recordbezetting (maxgame_BEST.json), zodat elke delta eerlijk is
    K.append(('REF record (exacte bezetting)', *ref_record(), []))
    # --- 1. bovenblok van 3/4 aangrenzende kolommen met goede kolomtabellen (7,8,9,10)
    for (a, b) in [(8, 10), (7, 10), (8, 11), (5, 7), (4, 6), (9, 12), (2, 5), (12, 14)]:
        up = blok(a, b, UP6)
        lo = {4: set(LO6), 11: set(LO6)}
        u2, l2 = add_support(up, lo)
        K.append((f'U{a}-{b} + record-onder', u2, l2, [(4, RANGE(2, 14))], []))
    # --- 2. onderblok van 3/4 aangrenzende kolommen (4,5,6,7 / 11,12)
    for (a, b) in [(4, 7), (5, 7), (4, 6), (11, 12), (10, 12), (11, 14), (5, 8)]:
        lo = blok(a, b, LO6)
        up = {2: set(UP6), 5: set(UP6), 10: set(UP6), 12: set(UP6)}
        u2, l2 = add_support(up, lo)
        K.append((f'L{a}-{b} + record-boven', u2, l2, [(4, RANGE(2, 14))], []))
    # --- 3. blok boven EN onder
    for (a, b), (c, d) in [((8, 10), (4, 7)), ((7, 10), (4, 7)), ((8, 10), (5, 7)),
                           ((8, 11), (4, 7)), ((5, 8), (4, 7)), ((8, 10), (11, 14))]:
        up, lo = blok(a, b, UP6), blok(c, d, LO6)
        u2, l2 = add_support(up, lo)
        K.append((f'U{a}-{b} + L{c}-{d}', u2, l2, [(4, RANGE(2, 14))], []))
        K.append((f'U{a}-{b} + L{c}-{d} zonder laan', u2, l2, [], []))
    # --- 4. blok met halve hoogte (rijen 1-3 / 11-13): goedkoper, korte kolomwoorden
    for (a, b) in [(8, 11), (7, 11), (4, 8)]:
        up = blok(a, b, RANGE(1, 3))
        lo = {4: set(LO6), 11: set(LO6)}
        u2, l2 = add_support(up, lo)
        K.append((f'U{a}-{b} halfhoog + record-onder', u2, l2, [(4, RANGE(2, 14))], []))
    # --- 5. twee smalle blokken (paren) i.p.v. een groot blok
    K.append(('U9-10 + U4-5 (twee paren)',
              *add_support({9: set(UP6), 10: set(UP6), 4: set(UP6), 5: set(UP6)},
                           {4: set(LO6), 11: set(LO6)}), [(4, RANGE(2, 14))], []))
    K.append(('U9-10+U1-2 + L11-12+L5-6',
              *add_support({9: set(UP6), 10: set(UP6), 1: set(UP6), 2: set(UP6)},
                           {11: set(LO6), 12: set(LO6), 5: set(LO6), 6: set(LO6)}),
              [(4, RANGE(2, 14))], []))
    return K


# ------------------------------------------------------------------ schema-verfijning
def refine(mv, iters=6000, seeds=6, eis_schoon=True, lex=0):
    """Ladderzoektocht over het zetschema, maar alleen schema's die OOK lijnconsistent blijven
    (`diagnose` leeg) worden geaccepteerd, en desgewenst ook lexicaal niet-weerlegd.  Zonder die
    eisen wint de zoeker 200-400 plafondpunten met tussenstappen die lexicaal niet bestaan (de
    'ladderillusie' uit NEWTOPO.md sectie 6.1)."""
    best, bmv = T.ceil_fixed(mv), mv
    for s in range(seeds):
        b, m = T.search(mv, iters=iters, seed=s)
        if b <= best: continue
        if eis_schoon and T.diagnose(m): continue
        if lex and lex_feasible(m, tlim=lex, nw=4)[0] == 'NEE': continue
        best, bmv = b, m
    return best, bmv


# ------------------------------------------------------------------ lexicale kern
def runs_of(mv):
    placed, runs = set(), []
    for cells in mv:
        for run in T.move_runs(placed, cells):
            if tuple(run) not in {tuple(q) for q in runs}: runs.append(run)
        placed |= set(cells)
    return runs


def _lexmodel(runs, occ, drop=()):
    from ortools.sat.python import cp_model
    m_ = cp_model.CpModel()
    L = {}
    for c in occ:
        L[c] = m_.new_constant(FIXED[c]) if c in FIXED else m_.new_int_var(1, 26, f'L{c}')
    for i, run in enumerate(runs):
        if i in drop: continue
        fx = {j: FIXED[c] for j, c in enumerate(run) if c in FIXED}
        tab = [w for w in T.BYLEN.get(len(run), []) if all(w[j] == v for j, v in fx.items())]
        if not tab: return None, None
        m_.add_allowed_assignments([L[c] for c in run], tab)
    return m_, L


def lex_feasible(mv, tlim=60, nw=4):
    """ZUIVER LEXICAAL: bestaat er UBERHAUPT een letterinvulling waarbij elke gescoorde run een
    woord is?  Geen zak, geen blanco's, geen doel -- alleen de kruiswoord-eisen.  Dit isoleert
    de vraag 'is dit blok woordbaar' van 'past het in de zak'.
    Geeft 'JA' / 'NEE' / 'ONBEKEND' terug; ONBEKEND is geen weerlegging."""
    from ortools.sat.python import cp_model
    runs = runs_of(mv)
    occ = sorted({c for z in mv for c in z})
    m_, L = _lexmodel(runs, occ)
    if m_ is None: return 'NEE', 'lege runtabel', runs
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tlim
    s.parameters.num_workers = nw
    st = s.solve(m_)
    v = {cp_model.OPTIMAL: 'JA', cp_model.FEASIBLE: 'JA',
         cp_model.INFEASIBLE: 'NEE'}.get(st, 'ONBEKEND')
    return v, st, runs


def lex_core(mv, tlim=30, nw=4):
    """Minimale onvervulbare kern: laat runs weg zolang het model onvervulbaar blijft.  Wat
    overblijft is precies de verzameling kruiswoord-eisen die elkaar uitsluiten."""
    from ortools.sat.python import cp_model
    runs = runs_of(mv)
    occ = sorted({c for z in mv for c in z})
    drop = set()

    def unsat(dr):
        m_, _ = _lexmodel(runs, occ, dr)
        if m_ is None: return True
        s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tlim
        s.parameters.num_workers = nw
        return s.solve(m_) == cp_model.INFEASIBLE

    if not unsat(drop): return None
    for i in range(len(runs)):
        if unsat(drop | {i}): drop.add(i)
    return [runs[i] for i in range(len(runs)) if i not in drop]


def board_runs(cells):
    """Alle maximale runs (>=2) van het EINDbord.  Deze moeten woorden zijn ongeacht welk
    zetschema je kiest -- dus een noodzakelijke voorwaarde voor de BEZETTING zelf."""
    occ = set(cells)
    out = []
    for h in (0, 1):
        for a in range(15):
            b = 0
            while b < 15:
                c = (b, a) if h else (a, b)
                if c not in occ: b += 1; continue
                b1 = b
                while b1 + 1 < 15 and ((b1 + 1, a) if h else (a, b1 + 1)) in occ: b1 += 1
                if b1 > b:
                    out.append([((k, a) if h else (a, k)) for k in range(b, b1 + 1)])
                b = b1 + 1
    return out


def static_feasible(cells, tlim=120, nw=6):
    """SCHEMA-ONAFHANKELIJKE zeef: bestaat er een letterinvulling waarbij ALLE maximale runs van
    het eindbord woorden zijn?  NEE hier weerlegt de BEZETTING (geen enkel zetschema kan hem
    redden); JA zegt nog niets over de tussenstanden."""
    from ortools.sat.python import cp_model
    runs = board_runs(cells)
    m_ = cp_model.CpModel()
    L = {c: (m_.new_constant(FIXED[c]) if c in FIXED else m_.new_int_var(1, 26, f'L{c}'))
         for c in sorted(cells)}
    for run in runs:
        fx = {j: FIXED[c] for j, c in enumerate(run) if c in FIXED}
        tab = [w for w in T.BYLEN.get(len(run), []) if all(w[j] == v for j, v in fx.items())]
        if not tab: return 'NEE', f'lege tabel {beschrijf_run(run)}', runs
        m_.add_allowed_assignments([L[c] for c in run], tab)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tlim
    s.parameters.num_workers = nw
    st = s.solve(m_)
    v = {cp_model.OPTIMAL: 'JA', cp_model.FEASIBLE: 'JA',
         cp_model.INFEASIBLE: 'NEE'}.get(st, 'ONBEKEND')
    return v, st, runs


def rect_feasible(cols, rows, tlim=60, nw=4, tussen=()):
    """WOORDRECHTHOEK: bestaat er een letterinvulling van het blok cols x rows waarbij
      * elke KOLOM een woord is over zijn volle verticale run (dus inclusief de vaste
        ankerletters op rij 0 / 7 / 14 waar de run daar tegenaan ligt), en
      * elke RIJ een woord is over de volle blokbreedte,
      * en optioneel elke TUSSENbreedte in `tussen` ook (de kolom-voor-kolom bouwvolgorde).
    Dit is de blokvraag zonder schema, zonder zak en zonder score: puur het lexicon."""
    from ortools.sat.python import cp_model
    rows = sorted(rows); cols = sorted(cols)
    occ = {(x, y) for x in cols for y in rows}
    for y in (0, 7, 14): occ |= {(x, y) for x in cols}
    m_ = cp_model.CpModel()
    L = {c: (m_.new_constant(FIXED[c]) if c in FIXED else m_.new_int_var(1, 26, f'L{c}'))
         for c in sorted(occ)}
    runs = []
    for x in cols:                                  # verticale runs
        y = 0
        while y < 15:
            if (x, y) not in occ: y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (x, y1 + 1) in occ: y1 += 1
            if y1 > y: runs.append([(x, yy) for yy in range(y, y1 + 1)])
            y = y1 + 1
    for y in rows:                                  # horizontale runs (volle breedte + tussen)
        for w in list(tussen) + [len(cols)]:
            if w < 2 or w > len(cols): continue
            runs.append([(x, y) for x in cols[:w]])
    for run in runs:
        fx = {j: FIXED[c] for j, c in enumerate(run) if c in FIXED}
        tab = [w for w in T.BYLEN.get(len(run), []) if all(w[j] == v for j, v in fx.items())]
        if not tab: return 'NEE', f'lege tabel {beschrijf_run(run)}'
        m_.add_allowed_assignments([L[c] for c in run], tab)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = tlim
    s.parameters.num_workers = nw
    st = s.solve(m_)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        g = {c: s.value(L[c]) for c in occ}
        A = '.abcdefghijklmnopqrstuvwxyz'
        beeld = [''.join(A[g[(x, y)]] for x in cols) for y in sorted(occ, key=lambda c: c[1])
                 and sorted({y for (x, y) in occ})]
        return 'JA', beeld
    return ('NEE' if st == cp_model.INFEASIBLE else 'ONBEKEND'), st


def main_rect():
    """De kernmeting van dit spoor: tot welke blokbreedte bestaat er nog een woordrechthoek?"""
    tl = float(os.environ.get('TLIM', '60'))
    for naam, rows in (('boven rijen 1-6 (kolomwoord rij 0-7)', RANGE(1, 6)),
                       ('boven rijen 4-6 (kolomwoord rij 4-7)', RANGE(4, 6)),
                       ('boven rijen 1-3 (kolomwoord rij 0-3)', RANGE(1, 3)),
                       ('onder rijen 8-13 (kolomwoord rij 7-14)', RANGE(8, 13)),
                       ('onder rijen 8-10 (kolomwoord rij 7-10)', RANGE(8, 10))):
        print(f'\n### {naam}')
        for w in range(2, 7):
            regel = []
            for a in range(0, 15 - w + 1):
                cols = RANGE(a, a + w - 1)
                if 7 in cols and rows[0] < 7 < rows[-1]: continue
                v, info = rect_feasible(cols, rows, tlim=tl)
                regel.append(f'{a}-{a+w-1}:{v[0]}')
            print(f'  breedte {w}: ' + ' '.join(regel), flush=True)


def beschrijf_run(run):
    x0, y0 = run[0]; x1, y1 = run[-1]
    k = 'rij' if y0 == y1 else 'kol'
    idx = y0 if y0 == y1 else x0
    fx = ''.join(('.abcdefghijklmnopqrstuvwxyz'[FIXED[c]] if c in FIXED else '?') for c in run)
    return f'{k} {idx} [{x0},{y0}]-[{x1},{y1}] len {len(run)} patroon {fx}'


# ------------------------------------------------------------------ CP-SAT + arbiter
def fit_and_check(naam, mv, tlim=900, nw=8, out=None):
    st, ob, g, bl = T.fit(mv, tlim=tlim, nw=nw)
    print(f'CP-SAT {naam}: {st} {ob}', flush=True)
    if st != 'ok':
        return None
    tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
    print(f'ARBITER {int(tot)} ok={ok} {"" if ok else msg[:160]}', flush=True)
    if ok:
        out = out or f'{RES}/denseblock_{naam.replace(" ", "_").replace("/", "-")}.json'
        json.dump({'grid': g, 'moves': [[list(c) for c in z] for z in mv],
                   'blanks': [list(b) for b in sorted(bl)], 'total': int(tot), 'ok': True,
                   'topologie': naam, 'triple': list(T.TRIPLET)}, open(out, 'w'))
        print('->', out, flush=True)
    return int(tot) if ok else None


def main():
    rows = []
    only = set(filter(None, os.environ.get('ONLY', '').split(',')))
    iters = int(os.environ.get('ITERS', '1200'))
    for naam, up, lo, lanes, brug in kandidaten():
        if only and not any(o in naam for o in only): continue
        rows.append(evaluate(naam, up, lo, lanes, brug, iters=iters,
                             lex=int(os.environ.get('LEX', '0'))))
    ok = [r for r in rows if r.get('status') == 'ok']
    ref = next((r for r in ok if r['naam'].startswith('REF')), None)
    print('\n== ranglijst (m-plafond, ankervast) ==')
    for r in sorted(ok, key=lambda q: -q['plafond']):
        d = f" d_ref {r['plafond']-ref['plafond']:+5d}" if ref else ''
        print(f"{r['naam']:34s} plafond {r['plafond']:5d}{d} eerlijk {r['seed']:5d} "
              f"tegels {r['tegels']:3d} bingo {r['bingos']:2d} lex {r.get('lex','-'):8s}"
              + ('  DOOD ' + str(r['dood']) if r['dood'] else '  lijn-OK'))
    out = os.environ.get('OUT', f'{RES}/denseblock.json')
    json.dump(rows, open(out, 'w'), indent=1)
    print('->', out)


def main_coord():
    laan = os.environ.get('LAAN', 'laan4')
    cur, bestv, hist = coord_search(rondes=int(os.environ.get('RONDES', '3')), laan=laan)
    ok = [r for r in hist if r.get('status') == 'ok']
    print('\n== alle geevalueerde bezettingen (eerlijk = greedy-schema, geen ladder) ==')
    for r in sorted(ok, key=lambda q: -q['seed']):
        print(f"{'/'.join(r['keuze']):46s} eerlijk {r['seed']:5d} ladder {r['plafond']:5d} "
              f"tegels {r['tegels']:3d} bingo {r['bingos']:2d}"
              + f"  lex {r.get('lex','-')}"
              + ('  DOOD ' + str(r['dood']) if r['dood'] else '  lijn-OK'))
    print(f'\nbeste diagnose-schone keuze: {cur} eerlijk {bestv}')
    out = os.environ.get('OUT', f'{RES}/denseblock_coord_{laan}.json')
    json.dump(hist, open(out, 'w'), indent=1)
    print('->', out)


def main_top():
    """Neem de N beste lijn-consistente bezettingen uit een coord-draai, verfijn hun schema en
    laat CP-SAT ze echt invullen; de arbiter (MG.score_game) beslist."""
    src = os.environ.get('IN', f'{RES}/denseblock_coord_laan4.json')
    D = [r for r in json.load(open(src)) if r.get('status') == 'ok' and not r.get('dood')
         and r.get('lex', 'JA') != 'NEE']
    D.sort(key=lambda r: -r['seed'])
    n = int(os.environ.get('N', '3'))
    tlim = float(os.environ.get('TLIM', '900'))
    for r in D[:n]:
        naam = '/'.join(r['keuze'])
        mv = [[tuple(c) for c in z] for z in r['moves']]
        b, bmv = refine(mv, iters=int(os.environ.get('ITERS', '6000')),
                        seeds=int(os.environ.get('SEEDS', '6')),
                        lex=int(os.environ.get('REFLEX', '20')))
        print(f'\n=== {naam}: plafond {r["seed"]} -> {b} (schoon), {len(bmv)} zetten, '
              f'{sum(1 for z in bmv if len(z)==7)} bingo', flush=True)
        fit_and_check(naam, bmv, tlim=tlim, nw=int(os.environ.get('NW', '6')))


if __name__ == '__main__':
    if os.environ.get('RECT'):
        main_rect()
    elif os.environ.get('TOP'):
        main_top()
    elif os.environ.get('COORD'):
        main_coord()
    elif os.environ.get('FIT'):
        D = json.load(open(os.environ.get('IN', f'{RES}/denseblock.json')))
        r = next(x for x in D if x['naam'] == os.environ['FIT'])
        mv = [[tuple(c) for c in z] for z in r['moves']]
        fit_and_check(r['naam'], mv, tlim=float(os.environ.get('TLIM', '900')),
                      nw=int(os.environ.get('NW', '8')), out=os.environ.get('FITOUT'))
    else:
        main()
