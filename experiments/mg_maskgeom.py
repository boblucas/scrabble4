"""MASKER x GEOMETRIE GEZAMENLIJK: welke slotzet-maskers laten AANGRENZENDE dragers toe?

Achtergrond.  `ANCHORCHAIN.md` optimaliseerde het masker uitsluitend op wat het voor de
ANKERRIJ ZELF oplevert: `mult*(S + DL-bonus) + keten(w, pre-set)`.  Op die maat is ons masker
optimaal.  `DENSEBLOCK.md` liet daarna zien dat datzelfde masker de rest van het bord vastzet:

    de maskercellen worden pas in de slotzet gelegd -> de pre-set valt uiteen in EILANDEN ->
    elk eiland heeft een eigen DRAGENDE kolom nodig (een tegel op (c,1) resp. (c,13)) ->
    het aantal en de LIGGING van de volle kolommen is een gevolg van de MASKERKEUZE.

Rij 0 heeft met ons masker vier eilanden ({1,2} {4,5,6} {9,10} {12}) en dus vier gedwongen
uit-elkaar-liggende dragers; rij 14 twee.  Elke drager is een kolomwoord van 8 letters met TWEE
vaste ankerletters -- precies de lexicale muur die DENSEBLOCK mat.  Dit script maakt die
koppeling expliciet en zoekt maskers die MINDER of DICHTER-BIJ-ELKAAR liggende dragers eisen,
en weegt de winst in de middenrijen af tegen het verlies op de ankerrij.

Formalisering (deel 1):
  islands(mask)        -> de maximale runs van de pre-set = de eilanden
  min_supports(mask)   -> = #eilanden (bewijs: zie MASKGEOM.md, eiland-lemma)
  support_domains      -> per eiland de toegestane kolommen (= het eiland zelf)
  mask_value(w,y,mask) -> mult*(S + LM-bonus op maskercellen) + keten(w, pre-set)
                          met de keten uit een exacte deelverzameling-DP per eiland

CLI (alles via env-variabelen; NW = aantal processen):
  MODE=formal   # deel 1: eiland-lemma, dragers, ijking op het record
  MODE=sweep    # deel 2: ALLE legbare maskers per ankerrij met maat, eilanden en dragers
  MODE=geo      # ijking van de geometrie-evaluator op de recordbezetting
  MODE=comb     # deel 3: coordinaatstijging over bouwblokken EN maskers tegelijk
  MODE=sa       # vrije simulated annealing over maskers EN bezetting
  MODE=probe    # gerichte probes (hanger/drager/aangrenzing)
  MODE=laan     # deel 4: welke LAAN levert het meeste op als je hem in het BESTAANDE
                #         recordschema invoegt en met losse tegels betaalt?  (de winnaar)
  MODE=laanfit  # CP-SAT-invulling + MG.score_game van de laan-kandidaten (fit_hint)
  MODE=lokaalfit # LOKALE invulling: alleen de omgeving van de nieuwe cellen vrij (fit_local)
  MODE=fit/fit2/deep  # oudere fit-varianten (portfolio van zetschema's)

Schrijft uitsluitend naar experiments/results/maskgeom_*.json; `maxgame_BEST.json`,
`lns_best.json` en `data/boards.toml` worden nooit aangeraakt.
"""
import os, sys, json, itertools, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import numpy as np
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba
inv = {v: k for k, v in cba.items()}
LM = np.array(r.letter_multiplier).astype(int).tolist()
WM = np.array(r.word_multiplier).astype(int).tolist()
VAL = {i: r.scores[i] for i in range(1, 27)}
RES = '/home/bob/programming/scrabble4/experiments/results'

TRIPLET = tuple(os.environ.get('TRIPLET',
                'geschenkcheques,flexwerkstertje,polymelkzuurtje').split(','))
WORD = {0: TRIPLET[0], 7: TRIPLET[1], 14: TRIPLET[2]}

BYLEN, WSET = {}, {}
for w in r.words_str:
    BYLEN.setdefault(len(w), []).append(w)
for L, ws in BYLEN.items():
    WSET[L] = set(ws)


def isword(s):
    return s in WSET.get(len(s), ())


# het masker van het record
REC = {0: (0, 3, 7, 8, 11, 13, 14), 7: (0, 1, 2, 3, 12, 13, 14), 14: (0, 1, 2, 3, 7, 13, 14)}
# rij 0/14: (7,y) moet in het masker (x27); rij 7: (7,7) is het centrum en ligt in zet 1, dus PRE
FORCED_IN = {0: (0, 7, 14), 7: (0, 14), 14: (0, 7, 14)}
FORCED_OUT = {0: (), 7: (7,), 14: ()}
MULT = {0: 27, 7: 9, 14: 27}
# de rij waarlangs een eiland van rij y gedragen wordt
CARRY = {0: 1, 7: None, 14: 13}


# =============================================================== DEEL 1: FORMALISERING
def islands(mask):
    """De maximale aaneengesloten groepen van de PRE-set (= alles buiten het masker).
    Dit zijn de eilanden uit het eiland-lemma."""
    F = set(mask); out, cur = [], []
    for x in range(15):
        if x in F:
            if cur:
                out.append(tuple(cur))
            cur = []
        else:
            cur.append(x)
    if cur:
        out.append(tuple(cur))
    return out


def min_supports(mask, y):
    """Minimaal aantal dragende kolommen dat dit masker afdwingt.

    EILAND-LEMMA.  Elke pre-cel (c,y) moet liggen VOOR de slotzet.  De eerste zet die een cel
    van eiland I raakt, raakt geen enkele andere tegel op rij y (de buren buiten I zijn
    maskercellen, dus leeg).  Die zet moet het bord raken, dus via de buurrij: er is een c in I
    met een tegel op (c, y+-1).  Elk eiland eist dus >= 1 dragende kolom, en die ligt IN het
    eiland.  Voor rij 7 is het eiland dat kolom 7 bevat gratis gedragen (de centrumzet)."""
    isl = islands(mask)
    if y == 7:
        return sum(1 for g in isl if 7 not in g)
    return len(isl)


def support_domains(mask, y):
    """Per eiland de toegestane dragerkolommen (= het eiland zelf)."""
    return [g for g in islands(mask) if not (y == 7 and 7 in g)]


def pre_ok(w, mask):
    """Noodzakelijke voorwaarde: elk eiland van lengte >= 2 staat als woord op het bord
    op het moment vlak voor de slotzet."""
    return all(len(g) < 2 or isword(w[g[0]:g[-1] + 1]) for g in islands(mask))


# ---------------------------------------------------------------- keten-DP per eiland
def _blocks(n):
    """alle (start,eind) blokken binnen een eiland van n cellen"""
    return [(i, j) for i in range(n) for j in range(i, n)]


def chain_island(w, y, cols, maxroots, free_root=False):
    """Exacte DP over deelverzamelingen van EEN eiland.

    Toestand = bitmasker van al gelegde cellen van het eiland.  Een zet legt een aaneengesloten
    blok lege cellen waarvan de span verder al gevuld is (zetvorm).  Hij kost een WORTEL (een
    verticale stub, dus een dragende kolom) als hij geen enkele al liggende cel van dit eiland
    raakt.  De opbrengst is de m-calculus van alle horizontale runs (>=2) die de zet raakt.

    Geeft {roots: beste ketenwaarde} voor roots <= maxroots.  free_root=True (rij 7, het
    eiland met het centrum) maakt de eerste wortel gratis."""
    n = len(cols)
    val = [VAL[cba[w[c]]] for c in cols]
    lm = [LM[y][c] for c in cols]
    wm = [WM[y][c] for c in cols]
    full = (1 << n) - 1

    def runs(st):
        out, i = [], 0
        while i < n:
            if (st >> i) & 1:
                j = i
                while j + 1 < n and (st >> (j + 1)) & 1:
                    j += 1
                out.append((i, j)); i = j + 1
            else:
                i += 1
        return out

    # legaliteit van een tussenstand: elke run van lengte >= 2 moet een woord zijn
    okm = [all(j == i or isword(w[cols[i]:cols[j] + 1]) for i, j in runs(st))
           for st in range(1 << n)]
    BLK = _blocks(n)
    best = {(0, 0): 0}
    order = sorted(range(1 << n), key=lambda s: bin(s).count('1'))
    for st in order:
        cur = {rt: v for (s2, rt), v in best.items() if s2 == st}
        if not cur:
            continue
        for (i, j) in BLK:
            bm = ((1 << (j - i + 1)) - 1) << i
            if st & bm:
                continue                                   # blok moet leeg zijn
            ns = st | bm
            if not okm[ns]:
                continue
            touch = ((i > 0 and (st >> (i - 1)) & 1) or (j + 1 < n and (st >> (j + 1)) & 1))
            nr = 0 if touch else 1
            # opbrengst
            g = 0
            mult = 1
            for x in range(i, j + 1):
                mult *= wm[x]
            for (a, b) in runs(ns):
                if b == a or not (a <= j and i <= b):
                    continue
                if not (a <= i and j <= b):
                    continue
                gg = 0
                for x in range(a, b + 1):
                    gg += lm[x] * val[x] if i <= x <= j else val[x]
                g += gg * mult
            for rt, v in cur.items():
                nrt = rt + nr
                if free_root and rt == 0 and nr == 1:
                    nrt = 0                                 # centrumzet levert de eerste gratis
                if nrt > maxroots:
                    continue
                k = (ns, nrt)
                if v + g > best.get(k, -1):
                    best[k] = v + g
    out = {}
    for (st, rt), v in best.items():
        if st != full:
            continue
        if v > out.get(rt, -1):
            out[rt] = v
    run = -1
    for rt in range(maxroots + 1):                          # monotoon in het wortelbudget
        if rt in out:
            run = max(run, out[rt])
        if run >= 0:
            out[rt] = run
    return out


def mask_value(w, y, mask, maxroots=6):
    """De volledige ankerrij-maat van dit masker:
        mult * (S(w) + SOM_{x in masker} (LM-1)*v(x))  +  keten(w, pre-set)
    Geeft (maat, slotzet_deel, keten, min_roots) of None als het masker niet legbaar is."""
    mult = 1
    for x in mask:
        mult *= WM[y][x]
    base = sum(VAL[cba[c]] for c in w) + sum((LM[y][x] - 1) * VAL[cba[w[x]]] for x in mask)
    slot = mult * base
    tot, roots = 0, 0
    for g in islands(mask):
        fr = (y == 7 and 7 in g)
        d = chain_island(w, y, g, maxroots, free_root=fr)
        if not d:
            return None
        need = min(d)
        tot += d[maxroots]
        roots += need
    return slot + tot, slot, tot, roots


def all_masks(y):
    """Alle legbare maskers van rij y: 7 cellen, met de gedwongen TWS erin."""
    fin = set(FORCED_IN[y]); fout = set(FORCED_OUT[y])
    pool = [x for x in range(15) if x not in fin and x not in fout]
    k = 7 - len(fin)
    for extra in itertools.combinations(pool, k):
        yield tuple(sorted(fin | set(extra)))


# ---------------------------------------------------------------- geometrische vrijheid
def geo_freedom(mask, y):
    """Hoeveel AANGRENZENDE dragers laat dit masker toe, en hoeveel volle (8-letter,
    dubbel-verankerde) kolommen dwingt het af?

    Elke drager is een kolom die rij 1 (resp. 13) haalt en dus een verticale run rij 0..7
    (resp 7..14) van 8 letters met twee vaste ankerletters vormt -- de lexicale muur uit
    DENSEBLOCK sec.2.  Kolommen die die rij NIET halen mogen kort zijn (rijen 4-6 / 8-10,
    4 letters, EEN vaste letter) en zijn lexicaal ruim; die kunnen dus wel dicht bij elkaar.

    Geeft (n_dragers, max_aangrenzend, keuzes) met max_aangrenzend = de grootste groep dragers
    die je aaneengesloten kunt kiezen (dragers uit VERSCHILLENDE eilanden zijn per definitie
    door minstens een maskerkolom gescheiden, dus dit is 1 zodra er >1 eiland is)."""
    dom = support_domains(mask, y)
    n = len(dom)
    # dragers uit verschillende eilanden zijn altijd gescheiden door een maskercel:
    # aangrenzende dragers kunnen dus alleen BINNEN een eiland.  Binnen een eiland is er
    # maar EEN drager nodig; extra dragers zijn vrijwillig en mogen naast elkaar.
    ruim = max((len(g) for g in dom), default=0)
    return n, ruim, dom


# =============================================================== rapportage deel 1
def fmt_mask(mask):
    return ''.join('X' if x in mask else '.' for x in range(15))


def main_formal():
    print("=" * 100)
    print("DEEL 1  FORMALISERING masker -> eilanden -> dragers  (ijking op het record)")
    print("=" * 100)
    for y in (0, 7, 14):
        w = WORD[y]
        m = REC[y]
        isl = islands(m)
        v = mask_value(w, y, m)
        print(f"\nrij {y:2d}  {w}   masker {sorted(m)}  {fmt_mask(m)}")
        print(f"   eilanden      {[''.join(w[c] for c in g) + str(list(g)) for g in isl]}")
        print(f"   min dragers   {min_supports(m, y)}   domeinen {support_domains(m, y)}")
        print(f"   maat {v[0]}  = slotzet {v[1]} + keten {v[2]}   (min wortels {v[3]})")


# =============================================================== DEEL 2: MASKERSWEEP
def sweep_row(y, maxroots=6):
    """Alle maskers van rij y met hun ankerrij-maat en hun geometrische gevolgen."""
    w = WORD[y]
    out = []
    for m in all_masks(y):
        if not pre_ok(w, m):
            continue
        v = mask_value(w, y, m, maxroots)
        if v is None:
            continue
        isl = islands(m)
        dom = support_domains(m, y)
        out.append({'mask': list(m), 'maat': v[0], 'slot': v[1], 'keten': v[2],
                    'roots': v[3], 'islands': [list(g) for g in isl],
                    'ndrag': len(dom), 'domeinen': [list(g) for g in dom],
                    'ruimte': max((len(g) for g in dom), default=0)})
    out.sort(key=lambda d: -d['maat'])
    return out


def main_sweep():
    alles = {}
    for y in (0, 14, 7):
        w = WORD[y]
        rows = sweep_row(y)
        alles[y] = rows
        ref = next(d for d in rows if tuple(d['mask']) == REC[y])
        print("=" * 108)
        print(f"RIJ {y}  {w}   ({len(rows)} legbare maskers)   record-maat {ref['maat']} "
              f"({ref['ndrag']} dragers)")
        print("=" * 108)
        print(f"{'masker':17s} {'maat':>5s} {'d_rec':>6s} {'slot':>5s} {'ket':>4s} "
              f"{'#dr':>3s}  eilanden")
        # de beste maskers per aantal gedwongen dragers
        for nd in range(0, 5):
            sel = [d for d in rows if d['ndrag'] == nd]
            if not sel:
                continue
            print(f"--- {nd} gedwongen drager(s): {len(sel)} maskers")
            for d in sel[:6]:
                mk = '*' if tuple(d['mask']) == REC[y] else ' '
                print(f"{mk}{fmt_mask(d['mask']):16s} {d['maat']:5d} {d['maat']-ref['maat']:+6d} "
                      f"{d['slot']:5d} {d['keten']:4d} {d['ndrag']:3d}  "
                      + ' '.join(''.join(w[c] for c in g) for g in d['islands']))
        print()
    json.dump({str(k): v for k, v in alles.items()}, open(f'{RES}/maskgeom_sweep.json', 'w'))
    print('->', f'{RES}/maskgeom_sweep.json')


# =============================================================== DEEL 3: GEOMETRIE
import mg_mceiling as M
import mg_newtopo as T
import mg_denseblock as DB

CAP = 101


def cells_of(cols, lanes=()):
    """cols: {x: verzameling rijen (zonder 0/7/14)}; lanes: {y: lijst kolommen}."""
    cells = set()
    for x, ys in cols.items():
        cells |= {(x, y) for y in ys}
    for y, xs in dict(lanes).items():
        cells |= {(x, y) for x in xs}
    cells = {c for c in cells if c[1] not in (0, 7, 14)}
    for y in (0, 7, 14):
        cells |= {(x, y) for x in range(15)}
    return cells


def gaps_of(cells, masks):
    """Welke eilanden hebben geen dragende kolom?  Dit is de bezorgbaarheidszeef, nu
    parametrisch in het masker."""
    bad = []
    for y, adj in ((0, 1), (14, 13)):
        for g in islands(masks[y]):
            if not any((x, adj) in cells for x in g):
                bad.append((y, g))
    for g in islands(masks[7]):
        if 7 in g:
            continue
        if not any((x, 6) in cells or (x, 8) in cells for x in g):
            bad.append((7, g))
    return bad


def col_tables_ok(cells):
    """Elke maximale verticale run moet minstens EEN woord toelaten dat op de ankerletters
    past (noodzakelijke voorwaarde, dezelfde als mg_newtopo.table_nonempty)."""
    bad = []
    for x in range(15):
        y = 0
        while y < 15:
            if (x, y) not in cells:
                y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (x, y1 + 1) in cells:
                y1 += 1
            if y1 > y and not T.table_nonempty([(x, k) for k in range(y, y1 + 1)]):
                bad.append((x, y, y1))
            y = y1 + 1
    return bad


def evaluate(naam, cols, lanes=(), masks=None, iters=1500, seeds=2, tries=3,
             lex=0, verbose=True):
    masks = masks or {y: list(REC[y]) for y in (0, 7, 14)}
    fin = {y: list(masks[y]) for y in (0, 7, 14)}
    cells = cells_of(cols, lanes)
    rec = {'naam': naam, 'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
           'cols': {str(x): sorted(ys) for x, ys in cols.items()},
           'lanes': {str(y): list(xs) for y, xs in dict(lanes).items()},
           'tegels_ruw': len(cells)}
    g = gaps_of(cells, masks)
    if g:
        rec['status'] = f'ONLEVERBAAR {g}'
        if verbose: print(f'{naam:38s} {rec["status"]}', flush=True)
        return rec
    b = col_tables_ok(cells)
    if b:
        rec['status'] = f'LEXICAAL DOOD (lege kolomtabel {b})'
        if verbose: print(f'{naam:38s} {rec["status"]}', flush=True)
        return rec
    best = None
    for s in range(tries):
        mv, stuck = DB.schedule(cells, finals=fin, seed=s, rnd_k=1 if s == 0 else 3)
        if mv is None:
            rec.setdefault('stuck', stuck[:6]); continue
        v = T.ceil_fixed(mv)
        if best is None or v > best[0]:
            best = (v, mv)
    if best is None:
        rec['status'] = f'schema vast {rec.get("stuck")}'
        if verbose: print(f'{naam:38s} {rec["status"]}', flush=True)
        return rec
    mv = best[1]
    tiles = sum(len(z) for z in mv)
    if tiles > CAP:
        mv2, weg = T.trim_to_cap(mv)
        if mv2 is None:
            rec['status'] = f'OVER CAP {tiles}'
            if verbose: print(f'{naam:38s} {rec["status"]}', flush=True)
            return rec
        mv = mv2; tiles = sum(len(z) for z in mv)
    base = T.ceil_fixed(mv)
    top, tmv = base, mv
    for s in range(seeds):
        b2, m2 = T.search(mv, iters=iters, seed=s)
        if b2 > top: top, tmv = b2, m2
    rec.update({'tegels': tiles, 'zetten': len(tmv),
                'bingos': sum(1 for z in tmv if len(z) == 7),
                'eerlijk': base, 'plafond': top,
                'dood': [[list(k), L, nr, nt] for k, L, nr, nt in T.diagnose(tmv)],
                'moves': [[list(c) for c in z] for z in mv],
                'moves_ladder': [[list(c) for c in z] for z in tmv],
                'status': 'ok'})
    if lex:
        v, st, runs = DB.lex_feasible(mv, tlim=lex, nw=4)
        rec['lex'] = v; rec['nruns'] = len(runs)
    if verbose:
        print(f'{naam:38s} tegels {tiles:3d} zet {len(tmv):3d} bingo {rec["bingos"]:2d} '
              f'eerlijk {base:5d} plafond {top:5d} lex {rec.get("lex","-"):8s}'
              + ('  DOOD ' + str(rec['dood']) if rec['dood'] else '  lijn-OK'), flush=True)
    return rec


def record_cols():
    """De EXACTE kolom/laan-bezetting van het record (de enige eerlijke meetlat)."""
    D = json.load(open(f'{RES}/maxgame_BEST.json'))
    cells = {tuple(c) for z in D['moves'] for c in z}
    cols = {}
    for (x, y) in cells:
        if y in (0, 7, 14):
            continue
        cols.setdefault(x, set()).add(y)
    return cols


def main_geo():
    cols = record_cols()
    print('record-kolommen:', {x: sorted(v) for x, v in sorted(cols.items())})
    r0 = evaluate('REF record (recordmaskers)', cols, (), None, lex=int(os.environ.get('LEX', '0')))
    print(json.dumps({k: r0[k] for k in ('tegels', 'zetten', 'bingos', 'eerlijk', 'plafond')
                      if k in r0}))


# =============================================================== DEEL 4: GEZAMENLIJKE ZOEKER
# De ankerrij-maat van een masker is exact bekend (deel 2).  De rest van het bord meten we met
# het m-plafond van een greedy zetschema (dezelfde bouwer op elke kandidaat, zoals DENSEBLOCK).
# Het TOTALE doel is dus:  plafond(bezetting, maskers)  --  de ankerrij-kosten zitten er al in,
# want het plafond rekent de slotzetten met hun echte multiplier mee.
MASKPOOL = {}


def maskpool(y, top=None):
    """De legbare maskers van rij y, gesorteerd op ankerrij-maat."""
    if y not in MASKPOOL:
        MASKPOOL[y] = [tuple(d['mask']) for d in sweep_row(y)]
    return MASKPOOL[y][:top] if top else MASKPOOL[y]


def quick_ceiling(cells, masks, seeds=2, penalty=True):
    """Greedy m-plafond van deze (bezetting, masker)-combinatie; None als hij niet bestaat."""
    fin = {y: list(masks[y]) for y in (0, 7, 14)}
    best, bmv = None, None
    for s in range(max(seeds, 4) if seeds > 1 else seeds):
        mv, _ = DB.schedule(cells, finals=fin, seed=s, rnd_k=1 if s == 0 else 3)
        if mv is None:
            continue
        v = T.ceil_fixed(mv)
        if best is None or v > best:
            best, bmv = v, mv
        if s + 1 >= seeds and best is not None:
            break
    if best is None:
        return None, None
    if penalty:
        best -= 250 * len(T.diagnose(bmv))
    return best, bmv


def feasible(cells, masks):
    return not gaps_of(cells, masks) and not col_tables_ok(cells)


# hoeveel 8-letterwoorden bestaan er per kolom met de twee vaste ankerletters?  Dit is de
# lexicale muur uit DENSEBLOCK sec.2 en meteen de rangschikking voor dragerkeuze.
def _coltab():
    up, lo = {}, {}
    for x in range(15):
        for L in range(2, 9):
            run_u = [(x, y) for y in range(8 - L, 8)]
            run_l = [(x, y) for y in range(7, 7 + L)]
            up[(x, L)] = T.table_nonempty(run_u)
            lo[(x, L)] = T.table_nonempty(run_l)
    n_up, n_lo = {}, {}
    for x in range(15):
        pu = WORD[0][x] + '?' * 6 + WORD[7][x]
        pl = WORD[7][x] + '?' * 6 + WORD[14][x]
        n_up[x] = sum(1 for w in BYLEN.get(8, []) if w[0] == pu[0] and w[7] == pu[7])
        n_lo[x] = sum(1 for w in BYLEN.get(8, []) if w[0] == pl[0] and w[7] == pl[7])
    return up, lo, n_up, n_lo


OKUP, OKLO, NUP, NLO = _coltab()


def repair_supports(cells, masks, rnd=None):
    """Voeg voor elk drager-loos eiland een volle kolom toe, bij voorkeur op de kolom met de
    rijkste 8-letter-tabel (de lexicale muur)."""
    cells = set(cells)

    def pick(g, tab):
        cand = [c for c in g if tab[c] > 0]
        if not cand:
            cand = list(g)
        if rnd is None:
            return max(cand, key=lambda c: tab[c])
        return rnd.choices(cand, weights=[1 + tab[c] for c in cand])[0]

    for g in islands(masks[0]):
        if any((x, 1) in cells for x in g):
            continue
        x = pick(g, NUP)
        cells |= {(x, y) for y in range(1, 7)}
    for g in islands(masks[14]):
        if any((x, 13) in cells for x in g):
            continue
        x = pick(g, NLO)
        cells |= {(x, y) for y in range(8, 14)}
    for g in islands(masks[7]):
        if 7 in g or any((x, 6) in cells or (x, 8) in cells for x in g):
            continue
        x = pick(g, NUP)
        cells |= {(x, y) for y in range(4, 7)}
    return cells


def trim_cells(cells, masks, rnd=None):
    """Breng een bezetting terug naar de tegel-cap door steeds de cel met de LAAGSTE m weg te
    gooien die de bezorgbaarheid niet breekt (zelfde idee als mg_newtopo.trim_to_cap, maar op
    celniveau en masker-bewust)."""
    cells = set(cells)
    while len(cells) > CAP:
        _, mv = quick_ceiling(cells, masks, seeds=1, penalty=False)
        m = M.multiplicity(mv) if mv else {}
        vrij = [c for c in cells if c[1] not in (0, 7, 14)]
        vrij.sort(key=lambda c: (m.get(c, 0), c))
        for c in vrij[:25]:
            rest = cells - {c}
            # niet alleen de dragers moeten heel blijven: een cel weghalen mag ook midden in
            # een kolom geen GAT slaan (dan is de rest van die kolom onbereikbaar).  De enige
            # betrouwbare test daarvoor is: bestaat er nog een zetschema?
            if gaps_of(rest, masks) or col_tables_ok(rest):
                continue
            if quick_ceiling(rest, masks, seeds=1, penalty=False)[0] is None:
                continue
            cells = rest; break
        else:
            break
    return cells


def joint_search(seed=0, iters=1200, start=None, tmax=None, log=None, fixmask=False,
                 poolsize=10):
    """Simulated annealing over (maskers, bezetting) tegelijk.

    Zetten:  (a) verwissel het masker van rij 0/7/14, (b) voeg een kolomsegment toe of haal er
    een weg, (c) voeg een losse cel toe of haal hem weg, (d) verplaats een drager binnen zijn
    eiland.  Harde eisen: elk eiland heeft een drager, elke kolomtabel is niet leeg, <= 101
    tegels, en er bestaat een legaal zetschema."""
    import random, math
    rnd = random.Random(seed)
    P = {y: maskpool(y, poolsize) for y in (0, 7, 14)}
    if start is None:
        cols = record_cols()
        masks = {y: tuple(REC[y]) for y in (0, 7, 14)}
        cur = cells_of(cols)
    elif isinstance(start[0], dict):
        cols, masks = start
        cur = cells_of(cols)
    else:
        cur, masks = set(map(tuple, start[0])), start[1]
    cur = repair_supports(cur, masks)
    cur = trim_cells(cur, masks, rnd)
    curv, curmv = quick_ceiling(cur, masks)
    if curv is None:                              # startbezetting heeft geen zetschema
        return {'plafond': -1, 'status': 'geen startschema', 'seed': seed,
                'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
                'cells': sorted(map(list, cur)), 'tegels': len(cur), 'moves': None, 'hist': []}
    best, bestmv, bestm, bestc = curv, curmv, dict(masks), set(cur)
    t0 = time.time()
    hist = []
    for it in range(iters):
        if tmax and time.time() - t0 > tmax:
            break
        T_ = 40 * (1 - it / iters) + 3
        ncells, nmasks = set(cur), dict(masks)
        op = rnd.random() if not fixmask else 0.12 + 0.88 * rnd.random()
        if op < 0.12:                                    # (a) masker verwisselen
            y = rnd.choice((0, 7, 14))
            nmasks[y] = rnd.choice(P[y])
            ncells = repair_supports(ncells, nmasks, rnd)
        elif op < 0.55:                                  # (b) kolomsegment
            x = rnd.randrange(15)
            boven = rnd.random() < 0.5
            h = rnd.choice((0, 1, 2, 3, 4, 5, 6))
            rows = set(range(7 - h, 7)) if boven else set(range(8, 8 + h))
            span = set(range(1, 7)) if boven else set(range(8, 14))
            ncells = {c for c in ncells if not (c[0] == x and c[1] in span)}
            ncells |= {(x, y2) for y2 in rows}
        elif op < 0.8:                                   # (c) losse cel
            x = rnd.randrange(15); y2 = rnd.choice([1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13])
            if (x, y2) in ncells and rnd.random() < 0.5:
                ncells.discard((x, y2))
            else:
                ncells.add((x, y2))
        else:                                            # (d) laanstuk
            y2 = rnd.choice([1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13])
            a = rnd.randrange(15); b = min(14, a + rnd.randrange(2, 10))
            if rnd.random() < 0.35:
                ncells -= {(x, y2) for x in range(a, b + 1)}
            else:
                ncells |= {(x, y2) for x in range(a, b + 1)}
        for y2 in (0, 7, 14):
            ncells |= {(x, y2) for x in range(15)}
        if gaps_of(ncells, nmasks):
            ncells = repair_supports(ncells, nmasks, rnd)
        # REPARATIE: het bord zit op de tegel-cap, dus elke toevoeging moet elders betaald
        # worden.  Haal willekeurige vrije cellen weg zolang de bezorgbaarheid intact blijft.
        tries = 0
        while len(ncells) > CAP and tries < 60:
            tries += 1
            c = rnd.choice([c for c in ncells if c[1] not in (0, 7, 14)])
            rest = ncells - {c}
            if not gaps_of(rest, nmasks):
                ncells = rest
        if len(ncells) > CAP or not feasible(ncells, nmasks):
            continue
        v, mv = quick_ceiling(ncells, nmasks)
        if v is None:
            continue
        if v > curv or rnd.random() < math.exp((v - curv) / T_):
            cur, masks, curv, curmv = ncells, nmasks, v, mv
            if v > best:
                best, bestmv, bestm, bestc = v, mv, dict(masks), set(cur)
                hist.append((it, v))
                if log:
                    print(f'  [{log}] it {it:5d} plafond {v} tegels {len(cur)} '
                          f'm0 {sorted(masks[0])} m7 {sorted(masks[7])} m14 {sorted(masks[14])}',
                          flush=True)
    return {'plafond': best, 'masks': {str(y): list(bestm[y]) for y in (0, 7, 14)},
            'cells': sorted(map(list, bestc)),
            'moves': [[list(c) for c in z] for z in bestmv] if bestmv else None,
            'tegels': len(bestc), 'seed': seed, 'hist': hist}


def _worker(args):
    seed, iters, tmax = args
    return joint_search(seed=seed, iters=iters, tmax=tmax, log=f's{seed}')


# ---------------------------------------------------------------- familie-modus
def _famworker(args):
    naam, masks, seed, iters, tmax = args
    cells = repair_supports(cells_of(record_cols()), masks)
    # de recordkolommen die door dit masker zinloos zijn geworden mogen weg; de SA regelt dat
    r = joint_search(seed=seed, iters=iters, tmax=tmax, log=None, fixmask=True,
                     start=(sorted(cells), masks))
    r['naam'] = naam
    r['ankermaat'] = sum(mask_value(WORD[y], y, masks[y])[0] for y in (0, 7, 14))
    print(f"{naam:34s} plafond {r['plafond']:5d} tegels {r['tegels']:3d} "
          f"ankermaat {r['ankermaat']:5d}", flush=True)
    return r


def fam_list():
    """De kandidaat-maskercombinaties: rij 0 varieert (daar zit de enige echte vrijheid),
    rij 7 en rij 14 blijven op hun optimum of op de goedkoopste alternatieven."""
    S0 = {tuple(d['mask']): d for d in sweep_row(0)}
    S7 = {tuple(d['mask']): d for d in sweep_row(7)}
    S14 = {tuple(d['mask']): d for d in sweep_row(14)}
    out = []
    # (1) rij 0 varieert over alle maskerklassen met maat >= 1400, rij 7/14 op record
    for m0, d in sorted(S0.items(), key=lambda kv: -kv[1]['maat']):
        if d['maat'] < 1400:
            continue
        naam = f"r0:{fmt_mask(m0)} d{d['ndrag']}"
        out.append((naam, {0: m0, 7: tuple(REC[7]), 14: tuple(REC[14])}))
    # (2) rij 14 varieert, rij 0/7 op record
    for m14, d in sorted(S14.items(), key=lambda kv: -kv[1]['maat'])[:6]:
        if tuple(m14) == tuple(REC[14]):
            continue
        out.append((f"r14:{fmt_mask(m14)} d{d['ndrag']}",
                    {0: tuple(REC[0]), 7: tuple(REC[7]), 14: tuple(m14)}))
    # (3) rij 7 varieert
    for m7, d in sorted(S7.items(), key=lambda kv: -kv[1]['maat'])[:6]:
        if tuple(m7) == tuple(REC[7]):
            continue
        out.append((f"r7:{fmt_mask(m7)} d{d['ndrag']}",
                    {0: tuple(REC[0]), 7: tuple(m7), 14: tuple(REC[14])}))
    return out


# ---------------------------------------------------------------- gerichte probes
# Wat de maskerkeuze BUITEN de ankerrij doet, zit in drie mechanismen:
#  (H) HANGER: staat er een kolom onder een MASKERcel, dan herscoort de slotzet de hele
#      verticale run.  Op x = 0, 7 en 14 is dat zelfs x3 (WM van de TWS), en die drie kolommen
#      liggen in ELK masker, dus die hanger is gratis beschikbaar -- maar hij kan geen drager
#      zijn en zijn segment is 6 in plaats van 7 tegels (dus geen eigen bingo).
#  (D) DRAGER: een eiland eist een kolom die rij 1 / rij 13 haalt = een 8-letterwoord met TWEE
#      vaste ankerletters (de lexicale muur).
#  (A) AANGRENZING: twee kolommen naast elkaar maken in elke tussenrij een horizontaal woord.
COL = {
    'k0t': [(0, y) for y in range(1, 7)],
    'k0b': [(0, y) for y in range(8, 14)],
    'k1t': [(1, y) for y in range(1, 7)],
    'k1b': [(1, y) for y in range(8, 14)],
    'k13t': [(13, y) for y in (1, 2, 3, 5, 6)],
    'k13b': [(13, y) for y in range(8, 14)],
    'k14t': [(14, y) for y in (1, 2, 3, 5, 6)],
    'k14b': [(14, y) for y in range(8, 14)],
    'k9t': [(9, y) for y in (1, 2, 3, 5, 6)],
    'k8t': [(8, y) for y in (1, 2, 3, 5, 6)],
    'k11t': [(11, y) for y in (1, 3, 5, 6)],
    'k6b': [(6, y) for y in range(8, 14)],
    'k12b': [(12, y) for y in range(8, 14)],
    'k5b': [(5, y) for y in range(9, 14)],
    'k2b': [(2, y) for y in (11, 12, 13)],
}
PROBES = [
    ('BASIS record', [], None),
    ('+k14t (hanger x3 x3)', ['k14t'], None),
    ('+k0t (hanger x3 x3)', ['k0t'], None),
    ('+k14b (hanger x3 x3)', ['k14b'], None),
    ('+k0b (hanger x3 x3)', ['k0b'], None),
    ('+k14t+k0t', ['k14t', 'k0t'], None),
    ('+k14t+k14b', ['k14t', 'k14b'], None),
    ('+k14t+k13t (paar)', ['k14t', 'k13t'], None),
    ('+k0t+k1t (paar)', ['k0t', 'k1t'], None),
    ('+k12b (kol 12 door)', ['k12b'], None),
    ('+k2b (kol 2 door tot 13)', ['k2b'], None),
    ('+k5b (kol 5 door)', ['k5b'], None),
    ('+k9t (paar 9-10)', ['k9t'], None),
    ('+k11t (paar 10-11-12)', ['k11t'], None),
    # maskervarianten met gelijke of bijna gelijke ankermaat
    ('twin r0 (eiland 13 i.p.v. 12)', [], {0: (0, 3, 7, 8, 11, 12, 14)}),
    ('twin r0 + k14t', ['k14t'], {0: (0, 3, 7, 8, 11, 12, 14)}),
    ('r0 3-drager (-120)', [], {0: (0, 1, 7, 8, 11, 13, 14)}),
    ('r0 3-drager + k14t', ['k14t'], {0: (0, 1, 7, 8, 11, 13, 14)}),
    ('r0 3-drager + k0t+k1t', ['k0t', 'k1t'], {0: (0, 1, 7, 8, 11, 13, 14)}),
    ('r0 2-drager (-234)', [], {0: (0, 1, 2, 3, 6, 7, 14)}),
    ('r0 2-drager + k14t+k0t', ['k14t', 'k0t'], {0: (0, 1, 2, 3, 6, 7, 14)}),
    ('r0 5-drager (-5, mask 9)', [], {0: (0, 3, 7, 9, 11, 13, 14)}),
    ('r14 3-drager (-7)', [], {14: (0, 1, 3, 4, 7, 13, 14)}),
    ('r7 alt (-10, mask 8/11)', [], {7: (0, 1, 3, 8, 11, 12, 14)}),
]


def _probeworker(args):
    naam, adds, mo, iters, tmax, seed, lex = args
    masks = {y: tuple(REC[y]) for y in (0, 7, 14)}
    if mo:
        masks.update({y: tuple(v) for y, v in mo.items()})
    cells = cells_of(record_cols())
    for k in adds:
        cells |= set(COL[k])
    cells = repair_supports(cells, masks)
    r = joint_search(seed=seed, iters=iters, tmax=tmax, fixmask=True,
                     start=(sorted(cells), masks))
    r['naam'] = naam
    r['ankermaat'] = sum(mask_value(WORD[y], y, masks[y])[0] for y in (0, 7, 14))
    if r['moves'] and lex:
        mv = [[tuple(c) for c in z] for z in r['moves']]
        r['lex'] = DB.lex_feasible(mv, tlim=lex, nw=2)[0]
    print(f"{naam:34s} plafond {r['plafond']:5d} tegels {r['tegels']:3d} "
          f"anker {r['ankermaat']:5d} lex {r.get('lex','-')}", flush=True)
    return r


# ---------------------------------------------------------------- bouwblokken + coordinaatstijging
def _R(a, b):
    return list(range(a, b + 1))


BLOK = {
    'L3': [(x, 3) for x in _R(3, 11)],          # x4-laan rij 3 (DWS (3,3)/(11,3))
    'L3w': [(x, 3) for x in _R(2, 12)],
    'L10': [(x, 10) for x in _R(2, 11)],        # x4-laan rij 10 (DWS (4,10)/(10,10))
    'L10s': [(x, 10) for x in _R(4, 10)],
    'L11': [(x, 11) for x in _R(3, 11)],        # x4-laan rij 11
    'L5': [(x, 5) for x in _R(2, 12)],
    'L9': [(x, 9) for x in _R(2, 11)],
    'K1t': [(1, y) for y in _R(1, 6)],
    'K0t': [(0, y) for y in _R(1, 6)],
    'K0b': [(0, y) for y in _R(8, 13)],
    'K14t': [(14, y) for y in (1, 2, 3, 5, 6)],
    'K14b': [(14, y) for y in _R(8, 13)],
    'K13t': [(13, y) for y in (1, 2, 3, 5, 6)],
    'K8t': [(8, y) for y in (1, 2, 3, 5, 6)],
    'K9t': [(9, y) for y in (1, 2, 3, 5, 6)],
    'K5b': [(5, y) for y in _R(9, 13)],
    'K6b': [(6, y) for y in _R(8, 13)],
    'K12b': [(12, y) for y in _R(8, 13)],
    'K2b': [(2, y) for y in _R(11, 13)],
    'K7b': [(7, y) for y in _R(11, 13)],
}


def eval_set(blokken, masks, seeds=4, lex=0, static=0):
    cells = cells_of(record_cols())
    for b in blokken:
        cells |= set(BLOK[b])
    cells = repair_supports(cells, masks)
    if col_tables_ok(cells):
        return {'status': 'kolomtabel leeg', 'plafond': -1}
    cells = trim_cells(cells, masks)
    v, mv = quick_ceiling(cells, masks, seeds=seeds, penalty=False)
    if v is None:
        return {'status': 'geen schema', 'plafond': -1}
    d = T.diagnose(mv)
    rec = {'status': 'ok', 'plafond': v, 'straf': v - 250 * len(d), 'tegels': len(cells),
           'bingos': sum(1 for z in mv if len(z) == 7), 'dood': len(d),
           'blokken': list(blokken), 'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
           'cells': sorted(map(list, cells)),
           'moves': [[list(c) for c in z] for z in mv]}
    if static:
        rec['statisch'] = DB.static_feasible(sorted(cells), tlim=static, nw=2)[0]
    if lex:
        rec['lex'] = DB.lex_feasible(mv, tlim=lex, nw=2)[0]
    return rec


def _combworker(args):
    blokken, masks, lex, static = args
    r = eval_set(blokken, masks, lex=lex, static=static)
    r['naam'] = '+'.join(blokken) or 'BASIS'
    if masks[0] != tuple(REC[0]):
        r['naam'] += ' m0=' + fmt_mask(masks[0])
    if masks[14] != tuple(REC[14]):
        r['naam'] += ' m14=' + fmt_mask(masks[14])
    if masks[7] != tuple(REC[7]):
        r['naam'] += ' m7=' + fmt_mask(masks[7])
    print(f"{r['naam']:44s} {r.get('status'):14s} plafond {r['plafond']:5d} "
          f"dood {r.get('dood','-')} lex {r.get('lex','-')} st {r.get('statisch','-')}",
          flush=True)
    return r


def main_comb():
    """Coordinaatstijging over de bouwblokken EN de maskers tegelijk."""
    from multiprocessing import Pool
    nw = int(os.environ.get('NW', '10'))
    lex = int(os.environ.get('LEX', '0'))
    static = int(os.environ.get('STATIC', '0'))
    rondes = int(os.environ.get('RONDES', '4'))
    out = os.environ.get('OUT', f'{RES}/maskgeom_comb.json')
    M0 = [tuple(d['mask']) for d in sweep_row(0)[:8]]
    M14 = [tuple(d['mask']) for d in sweep_row(14)[:5]]
    M7 = [tuple(d['mask']) for d in sweep_row(7)[:5]]
    cur, masks = [], {0: tuple(REC[0]), 7: tuple(REC[7]), 14: tuple(REC[14])}
    hist = []
    with Pool(nw) as p:
        base = _combworker((tuple(cur), dict(masks), lex, static))
        hist.append(base)
        bestv = base['straf']
        for ronde in range(rondes):
            jobs = []
            for b in BLOK:
                jobs.append((tuple(cur + [b]) if b not in cur
                             else tuple(x for x in cur if x != b), dict(masks), lex, static))
            for y, pool in ((0, M0), (14, M14), (7, M7)):
                for m in pool:
                    if m == masks[y]:
                        continue
                    nm = dict(masks); nm[y] = m
                    jobs.append((tuple(cur), nm, lex, static))
            jobs = list({(j[0], tuple(sorted(j[1].items()))): j for j in jobs}.values())
            res = p.map(_combworker, jobs)
            hist += res
            res = [r for r in res if r['status'] == 'ok']
            res.sort(key=lambda r: -r['straf'])
            if not res or res[0]['straf'] <= bestv:
                print(f'-- ronde {ronde}: geen verbetering ({bestv})', flush=True)
                break
            top = res[0]
            bestv = top['straf']
            cur = list(top['blokken'])
            masks = {int(k): tuple(v) for k, v in top['masks'].items()}
            print(f"-- ronde {ronde}: {bestv} blokken {cur} m0 {sorted(masks[0])} "
                  f"m14 {sorted(masks[14])} m7 {sorted(masks[7])}", flush=True)
    json.dump(hist, open(out, 'w'))
    print('->', out)


# ---------------------------------------------------------------- bouwen: CP-SAT + arbiter
def build_one(naam, cells, masks, iters=8000, seeds=8, reflex=25, tlim=900, nw=6,
              out=None, sched_seeds=6):
    """Van BEZETTING naar geverifieerd spel: schema zoeken (lijn-consistent en lexicaal niet
    weerlegd), CP-SAT-letterinvulling, daarna MG.score_game als arbiter."""
    fin = {y: list(masks[y]) for y in (0, 7, 14)}
    kand = []
    for s in range(sched_seeds):
        mv, _ = DB.schedule(cells, finals=fin, seed=s, rnd_k=1 if s == 0 else 3)
        if mv:
            kand.append(mv)
    for boete in (15, 40):
        mv, _ = DB.schedule(cells, finals=fin, seed=0, boete=boete)
        if mv:
            kand.append(mv)
    if not kand:
        print(f'{naam}: geen zetschema', flush=True); return None
    best, bmv = -1, None
    for mv in kand:
        v = T.ceil_fixed(mv)
        if T.diagnose(mv):
            continue
        if reflex and DB.lex_feasible(mv, tlim=reflex, nw=2)[0] == 'NEE':
            continue
        if v > best:
            best, bmv = v, mv
    if bmv is None:                                   # niets schoons: neem het hoogste plafond
        bmv = max(kand, key=T.ceil_fixed); best = T.ceil_fixed(bmv)
    b2, m2 = DB.refine(bmv, iters=iters, seeds=seeds, lex=reflex)
    if b2 > best:
        best, bmv = b2, m2
    print(f'{naam}: plafond {best}, {len(bmv)} zetten, '
          f'{sum(1 for z in bmv if len(z)==7)} bingo, {sum(len(z) for z in bmv)} tegels',
          flush=True)
    st, ob, g, bl = T.fit(bmv, tlim=tlim, nw=nw)
    print(f'CP-SAT {naam}: {st} {ob}', flush=True)
    if st != 'ok':
        return None
    tot, per, ok, msg = MG.score_game([row[:] for row in g], bmv, bl)
    print(f'ARBITER {naam}: {int(tot)} ok={ok} {"" if ok else msg[:200]}', flush=True)
    if ok:
        out = out or f'{RES}/maskgeom_board_{naam.replace(" ", "_").replace("/", "-")}.json'
        json.dump({'grid': g, 'moves': [[list(c) for c in z] for z in bmv],
                   'blanks': [list(b) for b in sorted(bl)], 'total': int(tot), 'ok': True,
                   'topologie': naam, 'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
                   'triple': list(TRIPLET)}, open(out, 'w'))
        print('->', out, flush=True)
    return int(tot) if ok else None


def _fitworker(args):
    naam, cells, masks, tlim, nw, reflex = args
    try:
        return naam, build_one(naam, {tuple(c) for c in cells},
                               {int(k): tuple(v) for k, v in masks.items()},
                               tlim=tlim, nw=nw, reflex=reflex)
    except Exception as e:
        print(f'{naam}: FOUT {e}', flush=True)
        return naam, None


def main_fit():
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_comb.json')
    D = [r for r in json.load(open(src)) if r.get('status') == 'ok' and r.get('dood', 9) == 0
         and r.get('tegels', 999) <= CAP]
    seen, uniq = set(), []
    for r in sorted(D, key=lambda q: -q['plafond']):
        k = (tuple(sorted(map(tuple, r['cells']))),
             tuple(sorted((y, tuple(m)) for y, m in r['masks'].items())))
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    n = int(os.environ.get('N', '6'))
    nw = int(os.environ.get('NW', '6'))
    tlim = float(os.environ.get('TLIM', '900'))
    jobs = [(r['naam'], r['cells'], r['masks'], tlim, int(os.environ.get('CPNW', '4')),
             int(os.environ.get('REFLEX', '25'))) for r in uniq[:n]]
    with Pool(nw) as p:
        res = p.map(_fitworker, jobs)
    print('\n== arbiter-uitslag ==')
    for naam, tot in sorted(res, key=lambda t: -(t[1] or 0)):
        print(f'{naam:44s} {tot}')


def schedule_portfolio(cells, masks, seeds=8, boetes=(0, 15, 25, 40, 60, 100), ladder=0,
                       lex=0):
    """Een PORTFOLIO zetschema's voor dezelfde bezetting.  De boete bestraft elke tijdelijke run
    (een gescoorde run die geen maximale run van het eindbord is): dat is exact de lexicale
    schuld van een ladderschema.  Hoog plafond en lage schuld zijn tegengesteld, dus we leveren
    de hele curve en laten CP-SAT beslissen (DENSEBLOCK sec.5b: alleen schema's die de lexicale
    test eerst doorstaan leveren borden op)."""
    fin = {y: list(masks[y]) for y in (0, 7, 14)}
    eind = {tuple(r) for r in DB.board_runs(cells)}
    out = []
    for b in boetes:
        for s in range(seeds):
            mv, _ = DB.schedule(cells, finals=fin, seed=s, rnd_k=1 if s == 0 else 3, boete=b)
            if mv is None:
                continue
            if T.diagnose(mv):
                continue
            schuld = sum(1 for r in DB.runs_of(mv) if tuple(r) not in eind)
            out.append({'mv': mv, 'ceil': T.ceil_fixed(mv), 'boete': b, 'seed': s,
                        'schuld': schuld, 'runs': len(DB.runs_of(mv))})
    if ladder:
        for r in sorted(out, key=lambda q: -q['ceil'])[:3]:
            b2, m2 = DB.refine(r['mv'], iters=ladder, seeds=4, lex=lex)
            if b2 > r['ceil'] and not T.diagnose(m2):
                out.append({'mv': m2, 'ceil': b2, 'boete': -1, 'seed': -1,
                            'schuld': sum(1 for q in DB.runs_of(m2) if tuple(q) not in eind),
                            'runs': len(DB.runs_of(m2))})
    # ontdubbelen op de zettenreeks
    seen, uniq = set(), []
    for r in sorted(out, key=lambda q: -q['ceil']):
        k = tuple(tuple(sorted(z)) for z in r['mv'])
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    return uniq


def build_portfolio(naam, cells, masks, kmax=5, tlim=600, nw=3, lex=60, out=None,
                    ladder=0):
    """Probeer meerdere schema's van dezelfde bezetting tot er een geverifieerd bord uit komt."""
    port = schedule_portfolio(cells, masks, ladder=ladder, lex=lex)
    print(f'{naam}: {len(port)} lijn-consistente schema\'s, plafond '
          f'{[p["ceil"] for p in port[:8]]}', flush=True)
    best = None
    tried = 0
    for p in port:
        if tried >= kmax:
            break
        v, st, _ = DB.lex_feasible(p['mv'], tlim=lex, nw=2)
        if v == 'NEE':
            print(f'  {naam} plafond {p["ceil"]} boete {p["boete"]}: lex NEE', flush=True)
            continue
        tried += 1
        stt, ob, g, bl = T.fit(p['mv'], tlim=tlim, nw=nw)
        if stt != 'ok':
            print(f'  {naam} plafond {p["ceil"]} boete {p["boete"]} schuld {p["schuld"]}: '
                  f'CP-SAT {stt}', flush=True)
            continue
        tot, per, ok, msg = MG.score_game([row[:] for row in g], p['mv'], bl)
        print(f'  {naam} plafond {p["ceil"]} boete {p["boete"]} schuld {p["schuld"]}: '
              f'CP-SAT {int(ob)} ARBITER {int(tot)} ok={ok}', flush=True)
        if ok and (best is None or tot > best[0]):
            best = (int(tot), p['mv'], g, bl)
    if best:
        out = out or f'{RES}/maskgeom_board_{naam.replace(" ", "_").replace("/", "-")}.json'
        json.dump({'grid': best[2], 'moves': [[list(c) for c in z] for z in best[1]],
                   'blanks': [list(b) for b in sorted(best[3])], 'total': best[0], 'ok': True,
                   'topologie': naam, 'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
                   'triple': list(TRIPLET)}, open(out, 'w'))
        print(f'{naam}: BESTE {best[0]} -> {out}', flush=True)
    return best[0] if best else None


def _fit2worker(args):
    naam, cells, masks, kmax, tlim, nw, lex, ladder = args
    try:
        return naam, build_portfolio(naam, {tuple(c) for c in cells},
                                     {int(k): tuple(v) for k, v in masks.items()},
                                     kmax=kmax, tlim=tlim, nw=nw, lex=lex, ladder=ladder)
    except Exception as e:
        import traceback; traceback.print_exc()
        return naam, None


def main_fit2():
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_comb.json')
    D = [r for r in json.load(open(src)) if r.get('status') == 'ok' and r.get('dood', 9) == 0
         and r.get('tegels', 999) <= CAP]
    seen, uniq = set(), []
    for r in sorted(D, key=lambda q: -q['plafond']):
        k = (tuple(sorted(map(tuple, r['cells']))),
             tuple(sorted((y, tuple(m)) for y, m in r['masks'].items())))
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    n = int(os.environ.get('N', '4'))
    nw = int(os.environ.get('NW', '4'))
    jobs = [(r['naam'], r['cells'], r['masks'], int(os.environ.get('KMAX', '5')),
             float(os.environ.get('TLIM', '600')), int(os.environ.get('CPNW', '2')),
             int(os.environ.get('LEX', '60')), int(os.environ.get('LADDER', '0')))
            for r in uniq[:n]]
    with Pool(nw) as p:
        res = p.map(_fit2worker, jobs)
    print('\n== arbiter-uitslag ==')
    for naam, tot in sorted(res, key=lambda t: -(t[1] or 0)):
        print(f'{naam:44s} {tot}')


# ---------------------------------------------------------------- LAAN-INVOEGING
# De greedy bouwer is op de recordbezetting ~230 plafondpunten zwakker dan het handgemaakte
# recordschema.  Wie er een BORD uit wil halen moet de nieuwe structuur dus in het BESTAANDE
# schema invoegen in plaats van alles te herbouwen.  Dat kan omdat het tegelbudget precies
# genoeg speling heeft: het record bestaat uit bingo's van 7 plus een handvol LOSSE tegels
# (zetten van 1 tegel buiten de ankerrijen).  Die losse tegels weghalen kost geen bingo.
def solo_cells(mv):
    m = M.multiplicity(mv)
    out = [z[0] for z in mv if len(z) == 1 and z[0][1] not in (0, 7, 14)]
    out.sort(key=lambda c: m.get(c, 0))
    return out


def insert_group(mv, groep, weg, posities=None):
    """Verwijder `weg` uit het schema en voeg `groep` als nieuwe zet in; geeft het beste
    (plafond, schema) over alle invoegposities dat legaal EN woordbaar is."""
    nm = [[c for c in z if c not in weg] for z in mv]
    nm = [z for z in nm if z]
    try:
        fin = min(i for i, z in enumerate(nm)
                  if any(c in ((0, 0), (0, 7), (0, 14)) for c in z))
    except ValueError:
        return None
    best = None
    for pos in (posities or range(1, fin + 1)):
        if pos > fin:
            continue
        t = [list(z) for z in nm]
        t.insert(pos, [tuple(c) for c in groep])
        t = [[tuple(c) for c in z] for z in t]
        if not T.legal(t) or not T.words_ok(t):
            continue
        v = T.ceil_fixed(t)
        if best is None or v > best[0]:
            best = (v, t, pos)
    return best


def _laanworker(args):
    y, a, b, NEW, mvraw, solo = args
    import itertools
    mv = [[tuple(c) for c in z] for z in mvraw]
    k = len(NEW)
    best = None
    for weg in itertools.combinations(solo[:10], k):
        wegs = {tuple(c) for c in weg}
        if set(NEW) & wegs:
            continue
        r = insert_group(mv, NEW, wegs)
        if r and (best is None or r[0] > best[0]):
            best = (r[0], r[1], r[2], sorted(wegs))
    if best is None:
        return None
    v, t, pos, wegs = best
    return {'laan': [y, a, b], 'ceil': v, 'pos': pos, 'weg': [list(c) for c in wegs],
            'dood': len(T.diagnose(t)), 'bingo': sum(1 for z in t if len(z) == 7),
            'tegels': sum(len(z) for z in t),
            'moves': [[list(c) for c in z] for z in t]}


def main_laan():
    """Sweep: welke LAAN (aaneengesloten stuk van een niet-ankerrij) is het meeste waard als je
    hem in het bestaande recordschema invoegt en met losse tegels betaalt?"""
    from multiprocessing import Pool
    src = os.environ.get('MB', f'{RES}/maxgame_BEST.json')
    D = json.load(open(src))
    mv = [[tuple(c) for c in z] for z in D['moves']]
    base = T.ceil_fixed(mv)
    occ = {c for z in mv for c in z}
    solo = solo_cells(mv)
    print(f'basis {src}: score {D.get("total")} plafond {base} tegels {len(occ)} '
          f'losse vrije tegels {solo}', flush=True)
    jobs = []
    for y in list(range(1, 7)) + list(range(8, 14)):
        for a in range(15):
            for b in range(a + 1, 15):
                NEW = tuple((x, y) for x in range(a, b + 1) if (x, y) not in occ)
                if 1 <= len(NEW) <= 7 and len(NEW) <= len(solo):
                    jobs.append((y, a, b, NEW, [[list(c) for c in z] for z in mv], solo))
    print(f'{len(jobs)} kandidaat-lanen', flush=True)
    with Pool(int(os.environ.get('NW', '8'))) as p:
        R = [r for r in p.map(_laanworker, jobs) if r and r['ceil'] > base]
    R.sort(key=lambda r: -r['ceil'])
    seen, U = set(), []
    for r in R:
        k = (tuple(map(tuple, r['weg'])), tuple(tuple(sorted(map(tuple, z))) for z in r['moves']))
        if k in seen:
            continue
        seen.add(k); U.append(r)
    print(f'{"laan":14s} {"plafond":>8s} {"delta":>6s} bingo dood pos  weg')
    for r in U[:25]:
        y, a, b = r['laan']
        print(f'rij{y:2d} [{a:2d},{b:2d}] {r["ceil"]:8d} {r["ceil"]-base:+6d} {r["bingo"]:5d} '
              f'{r["dood"]:4d} {r["pos"]:4d}  {r["weg"]}', flush=True)
    out = os.environ.get('OUT', f'{RES}/maskgeom_laansweep.json')
    json.dump(U[:40], open(out, 'w'))
    print('->', out)


def fit_hint(mv, tlim=600, nw=4, hintgrid=None, lb=None):
    """Zelfde model als `mg_newtopo.fit` (gescoorde runs als woordtabellen, zak als telling,
    <= 2 blanco's, score maximaliseren) maar MET een warme start.

    `mg_newtopo.fit` accepteert een `hint`-argument en gebruikt het nergens; op een model van
    ~5*10^5 variabelen kost dat veel: de solver moet elke invulling koud vinden.  Hier krijgt
    elke cel die ook op het referentiebord ligt diens letter als hint, en `lb` legt bovendien een
    ondergrens op de doelfunctie (zodat de solver niet in slechte incumbents blijft hangen)."""
    from ortools.sat.python import cp_model
    LMa = np.array(r.letter_multiplier); WMa = np.array(r.word_multiplier)
    bag = Counter({c: r.counts[c] for c in r.counts})
    occ = sorted({c for z in mv for c in z})
    fixed = {c: T.FIXED[c] for c in occ if c in T.FIXED}
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
        tab = [w for w in T.BYLEN.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
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
    VV = [0] + [VAL[i] for i in range(1, 27)]
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
                wm *= int(WMa[y][x])
        obj.append(sum(vv[(x, y)] * (int(LMa[y][x]) if (x, y) in cset else 1)
                       for (x, y) in run) * wm)
    tot = sum(obj) + bingos
    if lb:
        m_.add(tot >= int(lb))
    m_.maximize(tot)
    if hintgrid:
        for c in free:
            g = hintgrid[c[1]][c[0]]
            if g:
                m_.add_hint(L[c], g)
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


def fit_local(mv, ring=1, tlim=300, nw=2, refpad=None, lb=None):
    """LOKALE invulling: houd de letters van het referentiebord vast, laat alleen de omgeving
    van de NIEUWE cellen vrij.

    Het volle model (`fit_hint`) heeft met een 11- en 12-letter middenrij ~5*10^5 variabelen en
    komt binnen 40 minuten niet uit presolve.  Maar we hoeven het bord niet opnieuw uit te
    vinden: alle lijnen die de nieuwe groep niet raakt zijn ongewijzigd en al geverifieerd.
    `ring` = hoe ver de vrije zone doorpropageert langs de gescoorde runs."""
    from ortools.sat.python import cp_model
    ref = json.load(open(refpad or f'{RES}/maxgame_BEST.json'))
    GR = ref['grid']
    refbl = {tuple(b) for b in ref['blanks']}
    LMa = np.array(r.letter_multiplier).astype(int)
    WMa = np.array(r.word_multiplier).astype(int)
    bag = Counter({c: r.counts[c] for c in r.counts})
    occ = sorted({c for z in mv for c in z})
    NEW = [c for c in occ if not GR[c[1]][c[0]]]
    placed, events, runs = set(), [], []
    for z in mv:
        for run in T.move_runs(placed, z):
            events.append((run, set(z))); runs.append(tuple(run))
        placed |= set(z)
    raak = set(NEW)
    for _ in range(ring):
        add = set()
        for run in runs:
            if raak & set(run):
                add |= set(run)
        raak |= add
    m_ = cp_model.CpModel()
    L = {}
    for c in occ:
        if c in T.FIXED:
            L[c] = m_.new_constant(T.FIXED[c])
        elif c in raak:
            L[c] = m_.new_int_var(1, 26, f'L{c}')
        else:
            L[c] = m_.new_constant(GR[c[1]][c[0]])
    for run in sorted(set(runs), key=len):
        fx = {i: (T.FIXED[c] if c in T.FIXED else GR[c[1]][c[0]])
              for i, c in enumerate(run) if c in T.FIXED or c not in raak}
        tab = [w for w in T.BYLEN.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab:
            return 'nowords', run, None, None
        m_.add_allowed_assignments([L[c] for c in run], tab)
    free = [c for c in occ if c not in T.FIXED]
    BLv = {c: m_.new_bool_var(f'b{c}') for c in free}
    m_.add(sum(BLv.values()) <= 2)
    for c in free:
        if c not in raak:
            m_.add(BLv[c] == (1 if c in refbl else 0))
    for ch in range(1, 27):
        cnt = []
        for c in free:
            if c in raak:
                b = m_.new_bool_var(f'i{c}_{ch}')
                m_.add(L[c] == ch).only_enforce_if(b)
                m_.add(L[c] != ch).only_enforce_if(b.negated())
                nb = m_.new_bool_var(f'n{c}_{ch}')
                m_.add_bool_and([b, BLv[c].negated()]).only_enforce_if(nb)
                m_.add_bool_or([b.negated(), BLv[c]]).only_enforce_if(nb.negated())
                cnt.append(nb)
            elif GR[c[1]][c[0]] == ch and c not in refbl:
                cnt.append(1)
        m_.add(sum(cnt) + sum(1 for c in occ if c in T.FIXED and T.FIXED[c] == ch) <= bag[ch])
    VV = [0] + [VAL[i] for i in range(1, 27)]
    vv = {}
    for c in occ:
        v = m_.new_int_var(0, 10, f'v{c}')
        m_.add_element(L[c], VV, v)
        if c in BLv:
            ve = m_.new_int_var(0, 10, f've{c}')
            m_.add(ve == v).only_enforce_if(BLv[c].negated())
            m_.add(ve == 0).only_enforce_if(BLv[c])
            vv[c] = ve
        else:
            vv[c] = v
    obj = []
    for run, cset in events:
        wm = 1
        for (x, y) in run:
            if (x, y) in cset:
                wm *= int(WMa[y][x])
        obj.append(sum(vv[(x, y)] * (int(LMa[y][x]) if (x, y) in cset else 1)
                       for (x, y) in run) * wm)
    tot = sum(obj) + sum(50 for z in mv if len(z) == 7)
    if lb:
        m_.add(tot >= int(lb))
    m_.maximize(tot)
    for c in raak:
        if c not in T.FIXED and GR[c[1]][c[0]]:
            m_.add_hint(L[c], GR[c[1]][c[0]])
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = tlim
    s.parameters.num_workers = nw
    st = s.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeasible' if st == cp_model.INFEASIBLE else 'unknown'), None, None, None
    g = [[0] * 15 for _ in range(15)]
    for c in occ:
        g[c[1]][c[0]] = s.value(L[c])
    return ('optimaal' if st == cp_model.OPTIMAL else 'ok'), s.objective_value, g, \
        {c for c in free if c in BLv and s.value(BLv[c])}


def _lokaalworker(args):
    naam, mvraw, ring, tlim, nw = args
    mv = [[tuple(c) for c in z] for z in mvraw]
    st, ob, g, bl = fit_local(mv, ring=ring, tlim=tlim, nw=nw)
    if st in ('nowords', 'infeasible', 'unknown'):
        print(f'{naam} ring{ring}: {st}', flush=True)
        return naam, ring, None, None, None, mvraw
    tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
    print(f'{naam} ring{ring}: {st} obj {int(ob)} ARBITER {int(tot)} ok={ok} '
          f'{"" if ok else msg[:100]}', flush=True)
    return naam, ring, (int(tot) if ok else None), g, [list(b) for b in sorted(bl)], mvraw


def main_lokaalfit():
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_laansweep.json')
    D = json.load(open(src))
    ref = json.load(open(f'{RES}/maxgame_BEST.json'))
    jobs = []
    for i, rr in enumerate(D[:int(os.environ.get('N', '4'))]):
        for ring in (1, 2, 3):
            jobs.append((f'#{i}c{rr["ceil"]}', rr['moves'], ring,
                         float(os.environ.get('TLIM', '300')),
                         int(os.environ.get('CPNW', '2'))))
    print(f'referentie {ref.get("total")}, {len(jobs)} jobs', flush=True)
    with Pool(int(os.environ.get('NW', '6'))) as p:
        res = p.map(_lokaalworker, jobs)
    goed = [x for x in res if x[2]]
    goed.sort(key=lambda x: -x[2])
    print('\n== arbiter ==')
    for x in res:
        print(f'{x[0]:16s} ring{x[1]} -> {x[2]}')
    if goed and goed[0][2] > int(ref.get('total', 0)):
        naam, ring, tot, g, bl, mvraw = goed[0]
        out = os.environ.get('OUT', f'{RES}/maskgeom_board_laan3.json')
        json.dump({'grid': g, 'moves': mvraw, 'blanks': bl, 'total': tot, 'ok': True,
                   'topologie': f'record + x4-laan rij 3 ({naam}, ring {ring})',
                   'triple': list(TRIPLET)}, open(out, 'w'))
        print(f'NIEUW RECORD {tot} -> {out}', flush=True)


def _laanfitworker(args):
    naam, mvraw, ceil, tlim, nw, lex = args
    mv = [[tuple(c) for c in z] for z in mvraw]
    if lex > 1:
        v, st, _ = DB.lex_feasible(mv, tlim=lex, nw=nw)
        if v == 'NEE':
            print(f'{naam} c{ceil}: lex NEE', flush=True)
            return naam, ceil, None, None, None, mvraw
    else:
        v = '-'
    hg = None
    if os.environ.get('HINT', '1') == '1':
        try:
            hg = json.load(open(os.environ.get('MB', f'{RES}/maxgame_BEST.json')))['grid']
        except Exception:
            hg = None
    stt, ob, g, bl = fit_hint(mv, tlim=tlim, nw=nw, hintgrid=hg,
                              lb=os.environ.get('LB') and int(os.environ['LB']))
    if stt != 'ok':
        print(f'{naam} c{ceil}: lex {v} CP-SAT {stt}', flush=True)
        return naam, ceil, None, None, None, mvraw
    tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
    print(f'{naam} c{ceil}: lex {v} CP-SAT {int(ob)} ARBITER {int(tot)} ok={ok} '
          f'{"" if ok else msg[:120]}', flush=True)
    return naam, ceil, (int(tot) if ok else None), g, [list(b) for b in sorted(bl)], mvraw


def main_laanfit():
    """Vul de laan-kandidaten met CP-SAT en laat MG.score_game beslissen.  Schrijft alleen naar
    een EIGEN json; maxgame_BEST.json en lns_best.json blijven onaangeraakt."""
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_laansweep.json')
    D = json.load(open(src))
    n = int(os.environ.get('N', '6'))
    jobs = []
    seen = set()
    for r in D:
        k = tuple(tuple(sorted(map(tuple, z))) for z in r['moves'])
        if k in seen or r.get('dood'):
            continue
        seen.add(k)
        naam = f"laan{r.get('laan', '')}pos{r.get('pos', '')}"
        jobs.append((naam, r['moves'], r['ceil'], float(os.environ.get('TLIM', '1800')),
                     int(os.environ.get('CPNW', '2')), int(os.environ.get('LEX', '150'))))
        if len(jobs) >= n:
            break
    with Pool(int(os.environ.get('NW', '6'))) as p:
        res = p.map(_laanfitworker, jobs)
    goed = [r for r in res if r[2]]
    goed.sort(key=lambda r: -r[2])
    print('\n== arbiter ==')
    for r in res:
        print(f'{r[0]:28s} plafond {r[1]:5d} -> {r[2]}')
    if goed:
        naam, ceil, tot, g, bl, mvraw = goed[0]
        out = os.environ.get('OUT', f'{RES}/maskgeom_board_laan3.json')
        json.dump({'grid': g, 'moves': mvraw, 'blanks': bl, 'total': tot, 'ok': True,
                   'topologie': f'record + x4-laan rij 3 ({naam}, plafond {ceil})',
                   'triple': list(TRIPLET)}, open(out, 'w'))
        print(f'BESTE {tot} -> {out}')


def _deepworker(args):
    naam, mv, tlim, nw, lex = args
    mv = [[tuple(c) for c in z] for z in mv]
    v, st, _ = DB.lex_feasible(mv, tlim=lex, nw=nw)
    if v == 'NEE':
        print(f'{naam}: lex NEE', flush=True)
        return naam, None, None, None, None
    stt, ob, g, bl = T.fit(mv, tlim=tlim, nw=nw)
    if stt != 'ok':
        print(f'{naam}: CP-SAT {stt}', flush=True)
        return naam, None, None, None, None
    tot, per, ok, msg = MG.score_game([row[:] for row in g], mv, bl)
    print(f'{naam}: CP-SAT {int(ob)} ARBITER {int(tot)} ok={ok}', flush=True)
    return naam, (int(tot) if ok else None), g, [list(b) for b in sorted(bl)], \
        [[list(c) for c in z] for z in mv]


def main_deep():
    """EEN bezetting, een groot portfolio zetschema's, alles parallel door lex + CP-SAT.
    Dit is de enige eerlijke manier om te weten wat een bezetting waard is: het verschil tussen
    het greedy-schema en een handgemaakt schema is op het record 224 plafondpunten."""
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_comb.json')
    naam = os.environ.get('NAAM', 'L3')
    D = [r for r in json.load(open(src)) if r.get('status') == 'ok']
    rec = next(r for r in D if r['naam'] == naam)
    cells = {tuple(c) for c in rec['cells']}
    masks = {int(k): tuple(v) for k, v in rec['masks'].items()}
    port = schedule_portfolio(cells, masks, seeds=int(os.environ.get('SEEDS', '14')),
                              ladder=int(os.environ.get('LADDER', '6000')),
                              lex=int(os.environ.get('REFLEX', '20')))
    lo = float(os.environ.get('LO', '4700'))
    port = [p for p in port if p['ceil'] >= lo]
    n = int(os.environ.get('N', '24'))
    port = port[:n]
    print(f'{naam}: {len(port)} schema\'s, plafonds {[p["ceil"] for p in port]}', flush=True)
    jobs = [(f'{naam}#{i} c{p["ceil"]} b{p["boete"]} s{p["schuld"]}', p['mv'],
             float(os.environ.get('TLIM', '600')), int(os.environ.get('CPNW', '2')),
             int(os.environ.get('LEX', '90'))) for i, p in enumerate(port)]
    with Pool(int(os.environ.get('NW', '6'))) as p:
        res = p.map(_deepworker, jobs)
    goed = [r for r in res if r[1]]
    goed.sort(key=lambda r: -r[1])
    print('\n== arbiter ==')
    for r in res:
        print(f'{r[0]:34s} {r[1]}')
    if goed:
        r = goed[0]
        out = os.environ.get('OUT', f'{RES}/maskgeom_board_{naam.replace(" ", "_")}.json')
        json.dump({'grid': r[2], 'moves': r[4], 'blanks': r[3], 'total': r[1], 'ok': True,
                   'topologie': r[0], 'masks': {str(y): list(masks[y]) for y in (0, 7, 14)},
                   'triple': list(TRIPLET)}, open(out, 'w'))
        print(f'BESTE {r[1]} -> {out}')


def _saworker(args):
    cells, masks, seed, iters, tmax = args
    r = joint_search(seed=seed, iters=iters, tmax=tmax, log=f's{seed}',
                     start=(cells, {int(k): tuple(v) for k, v in masks.items()}))
    return r


def main_sa():
    """Vrije SA (maskers EN bezetting) vanaf de beste coordinaat-uitkomst."""
    from multiprocessing import Pool
    src = os.environ.get('IN', f'{RES}/maskgeom_comb.json')
    D = [r for r in json.load(open(src)) if r.get('status') == 'ok'
         and r.get('dood', 9) == 0 and r.get('tegels', 999) <= CAP]
    D.sort(key=lambda r: -r['plafond'])
    st = D[0]
    print(f"start: {st['naam']} plafond {st['plafond']}", flush=True)
    nw = int(os.environ.get('NW', '6'))
    iters = int(os.environ.get('ITERS', '100000'))
    tmax = float(os.environ.get('TMAX', '2400'))
    jobs = [(st['cells'], st['masks'], s, iters, tmax) for s in range(nw)]
    with Pool(nw) as p:
        res = p.map(_saworker, jobs)
    res.sort(key=lambda d: -d['plafond'])
    for d in res:
        print(f"seed {d['seed']:2d} plafond {d['plafond']:5d} tegels {d['tegels']:3d} "
              f"m0 {d['masks']['0']} m7 {d['masks']['7']} m14 {d['masks']['14']}")
    json.dump(res, open(os.environ.get('OUT', f'{RES}/maskgeom_sa.json'), 'w'))


def main_probe():
    from multiprocessing import Pool
    nw = int(os.environ.get('NW', '6'))
    iters = int(os.environ.get('ITERS', '100000'))
    tmax = float(os.environ.get('TMAX', '240'))
    seed = int(os.environ.get('SEED', '1'))
    lex = int(os.environ.get('LEX', '0'))
    out = os.environ.get('OUT', f'{RES}/maskgeom_probe.json')
    jobs = [(n, a, m, iters, tmax, seed, lex) for n, a, m in PROBES]
    only = os.environ.get('ONLY')
    if only:
        jobs = [j for j in jobs if only in j[0]]
    with Pool(nw) as p:
        res = p.map(_probeworker, jobs)
    res.sort(key=lambda d: -d['plafond'])
    print('\n== probes ==')
    for d in res:
        print(f"{d['naam']:34s} plafond {d['plafond']:5d} tegels {d['tegels']:3d} "
              f"anker {d['ankermaat']:5d} lex {d.get('lex','-')}")
    json.dump(res, open(out, 'w'))
    print('->', out)


def main_fam():
    from multiprocessing import Pool
    nw = int(os.environ.get('NW', '10'))
    iters = int(os.environ.get('ITERS', '2500'))
    tmax = float(os.environ.get('TMAX', '900'))
    seed = int(os.environ.get('SEED', '0'))
    out = os.environ.get('OUT', f'{RES}/maskgeom_fam.json')
    jobs = [(n, m, seed, iters, tmax) for n, m in fam_list()]
    only = os.environ.get('ONLY')
    if only:
        jobs = [j for j in jobs if only in j[0]]
    print(f'{len(jobs)} maskercombinaties, {nw} workers', flush=True)
    with Pool(nw) as p:
        res = p.map(_famworker, jobs)
    res.sort(key=lambda d: -d['plafond'])
    print('\n== ranglijst (greedy m-plafond, zelfde bouwer op elke kandidaat) ==')
    for d in res:
        print(f"{d['naam']:34s} plafond {d['plafond']:5d} tegels {d['tegels']:3d} "
              f"ankermaat {d['ankermaat']:5d}")
    json.dump(res, open(out, 'w'))
    print('->', out)


def main_joint():
    from multiprocessing import Pool
    nw = int(os.environ.get('NW', '8'))
    iters = int(os.environ.get('ITERS', '4000'))
    tmax = float(os.environ.get('TMAX', '1800'))
    out = os.environ.get('OUT', f'{RES}/maskgeom_joint.json')
    with Pool(nw) as p:
        res = p.map(_worker, [(s, iters, tmax) for s in range(nw)])
    res.sort(key=lambda d: -d['plafond'])
    for d in res:
        print(f"seed {d['seed']:2d} plafond {d['plafond']:5d} tegels {d['tegels']:3d} "
              f"m0 {d['masks']['0']} m7 {d['masks']['7']} m14 {d['masks']['14']}")
    json.dump(res, open(out, 'w'))
    print('->', out)


if __name__ == '__main__':
    mode = os.environ.get('MODE', 'formal')
    if mode == 'formal':
        main_formal()
    elif mode == 'sweep':
        main_sweep()
    elif mode == 'geo':
        main_geo()
    elif mode == 'joint':
        main_joint()
    elif mode == 'fam':
        main_fam()
    elif mode == 'probe':
        main_probe()
    elif mode == 'comb':
        main_comb()
    elif mode == 'fit':
        main_fit()
    elif mode == 'sa':
        main_sa()
    elif mode == 'fit2':
        main_fit2()
    elif mode == 'deep':
        main_deep()
    elif mode == 'laan':
        main_laan()
    elif mode == 'laanfit':
        main_laanfit()
    elif mode == 'lokaalfit':
        main_lokaalfit()
