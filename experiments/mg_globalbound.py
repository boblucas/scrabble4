"""GLOBALE BOVENGRENS voor de score van ELK legaal dutch2026-spel (15x15).

Gebaseerd op de multipliciteitsidentiteit (zie experiments/mg_mceiling.py):

    score(spel) = SOM_c m(c) * waarde(letter op c)  +  50 * #7-tegelzetten

waarbij voor elke scorende gebeurtenis (maximale run van >=2 cellen die minstens
een NIEUWE tegel bevat) met woordmultiplier wm = PRODUCT van word_multiplier over
de NIEUWE cellen van die zet in die run, elke cel c van de run bijdraagt met
    wm * (letter_multiplier(c)  als c nieuw is in die zet, anders 1).

Dit script leidt een per-cel maximum af over ALLE legale spellen en daarna een
globale bovengrens.  Elke stap is een RELAXATIE: alle getallen zijn geldige
bovengrenzen, de laatste is de scherpste.  Onderbouwing: experiments/GLOBALBOUND.md

===========================================================================
AANNAMES (uitsluitend spelregels + bordgeometrie; niets over het woordenboek)
===========================================================================
A1. Bord 15x15 met de multiplier-arrays uit maxgame_score (r.letter_multiplier,
    r.word_multiplier) -- dat is de arbiter (MG.score_game gebruikt deze arrays).
A2. Een zet legt 1..7 NIEUWE tegels, allemaal in EEN lijn (rij of kolom).
    (Standaard-Scrabble; hand = r.hand_size = 7.)
A3. Hoogstens 101 tegels komen op het bord (102 in de zak, tegenstander houdt
    er >=1).  De zak = 100 lettertegels + 2 blanco's; blanco's zijn 0 punten.
A4. Een zet die precies 7 tegels legt geeft 50 bonus (r.emptyhand_bonus).
A5. Scorende gebeurtenissen zijn precies de maximale runs (>=2) die minstens een
    nieuwe tegel bevatten; per zet is er per cel hoogstens EEN horizontale en
    EEN verticale zulke run.  (Exact wat MG.score_game / events_of doen.)
A6. Er wordt NIETS aangenomen over legaliteit van woorden: elke afgeleide grens
    geldt dus zeker ook voor spellen die het woordenboek respecteren.

===========================================================================
LEMMA'S
===========================================================================
L1 (per lijn).  Fixeer cel c en zijn rij R.  Elke horizontale gebeurtenis die c
   bevat hoort bij precies EEN zet die minstens een tegel in R legt (de run ligt
   binnen R).  Verschillende zetten leggen DISJUNCTE cellen.  De wm van zo'n
   gebeurtenis = product van word_multiplier over de nieuwe cellen van die zet
   binnen de run <= product over ALLE cellen van die zet in R (want wm >= 1).
   De factor lm(c) telt alleen in de gebeurtenis van de zet die c zelf legt, dus
   in het blok dat c bevat.  Met w(B) = PROD_{p in B} wm(p):
      m_rij(c) <= max over partities P van R in blokken van <=7 cellen van
                  SOM_{B in P} w(B) + (lm(c)-1) * w(B_c).
   (Volledige bedekking van R is optimaal: elk blok draagt w(B) >= 1 bij.)
   Analoog voor de kolom, en m(c) <= m_rij(c) + m_kol(c).

L2 (orientatie-exclusiviteit).  De zet die c legt ligt in EEN lijn.  Ligt die in
   de rij, dan legt die zet in de kolom van c alleen c, dus daar is B_c = {c}.
   Dus m(c) <= max( Hb_vrij + Vb_singleton , Hb_singleton + Vb_vrij ) =: M2(c).

L3 (lijn-decompositie).  Met W_L = SOM_{B in P_L} w(B) en V_L = som van de
   tegelwaarden in lijn L geldt per lijn
      SOM_{c in L} val(c)*m_L(c) = W_L*V_L + SOM_{c in L} val(c)*(lm(c)-1)*w(B_c).
   De factor W_L wordt dus GEDEELD door alle 15 cellen van de lijn.  Combineren
   met de tegelschaarste (SOM over rijen van #tegels = SOM over kolommen van
   #tegels = #tegels <= 101) geeft echte druk.

L4 (rij/kolom-koppeling).  Een cel met wm>1 zit in hoogstens EEN blok van
   grootte >=2 (dat van zijn eigen zet); in de loodrechte lijn is hij singleton
   en draagt daar los wm(c) bij i.p.v. in een product.  Rij 0 haalt w=27 alleen
   als (0,0),(7,0),(14,0) alle drie H-georienteerd zijn -- maar kolom 0 heeft
   voor zijn 27 juist (0,0) V-georienteerd nodig.

L5 (blok- en zetbudget).  Blokken in de RIJ-partities zijn: de celverzameling
   C_m van elke horizontale zet m, plus {c} voor elke cel c die door een
   VERTICALE zet is gelegd.  Dus
      SOM over rijen van b_L = K_H + n_V   en   SOM over kolommen van b_L = K_V + n_H,
   met K_H/K_V = aantal horizontale/verticale zetten en n_H/n_V = aantal tegels
   met horizontale/verticale zet-orientatie.  Omdat K_H <= n_H en K_V <= n_V:
      SOM_rijen b_L <= T,   SOM_kolommen b_L <= T,   SOM_alle b_L = T + K,
   met T = #tegels <= 101 en K = #zetten.  Verder 7K >= T (elke zet <=7 tegels)
   en, met beta = aantal 7-tegelzetten, T >= 7*beta + (K-beta) = 6*beta + K.
   Dit KOPPELT bingo-bonus en multipliciteit: veel blokken (= hoge W_L) vergt
   veel zetten, en veel zetten sluit bingo's uit.
   Ook: k_L <= 7*b_L (b_L blokken van <=7 cellen dekken k_L bezette cellen).

L6 (elke tegel in een woord).  De openingszet vormt een woord van >=2 letters,
   elke latere zet raakt het bestaande bord, en een zet van >=2 tegels ligt zelf
   in een aaneengesloten run.  Dus elke bezette cel heeft een orthogonaal
   bezette buur.  (Uitzondering: een bord met precies 1 tegel -- dat scoort 0.)

L7 (bezettingskoppeling).  De k_r bezette cellen van rij r liggen in k_r
   VERSCHILLENDE kolommen, die dus niet leeg zijn: k_r <= n_kol; analoog
   k_x <= n_rij.  Dit verhindert dat rijen EN kolommen tegelijk geconcentreerd
   zijn.

Stappen die dit script rapporteert (alle geldig, kleinste telt):
  1  per-cel M1 = Hb_vrij + Vb_vrij                        (L1)
  2  per-cel M2 (orientatie-exclusiviteit)                 (L1+L2)
  3  aggregaatmodel (alleen per-lijn-variabelen)           (L1..L3, L7)
  4  + rij/kolom-orientatiekoppeling                       (+L4)
  5  + blok/zet/bingo-budget                               (+L5)
  6  celmodel met alle 225 cellen                          (L1..L7)

Stap 1 en 2 zijn ANALYTISCH (geen solver-gap).  Stappen 3-6 zijn CP-SAT-modellen;
er wordt altijd de OBJECTIVE BOUND gerapporteerd, die ook bij een time-out een
geldige bovengrens is (het gevonden modeloptimum staat er als '>=' bij en is
GEEN bewezen grens).  Het aggregaatmodel (3-5) is los: rijen en kolommen mogen
daar allebei de hoogste tegels claimen; het celmodel (6) heeft die koppeling wel
maar is veel zwaarder.

CLI:  .venv/bin/python experiments/mg_globalbound.py [--tl SEC] [--only STAP]
                                                     [--workers N]
"""
import sys, os, json, itertools, argparse
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
from math import prod, ceil
import numpy as np
import maxgame_score as MG

N = 15
MAXTILES = 101          # A3
MAXMOVE = 7             # A2
BONUS = 50              # A4
FIXBINGO = BONUS * (MAXTILES // MAXMOVE)   # 700

r = MG.r
LM = np.array(r.letter_multiplier).tolist()   # LM[y][x]
WM = np.array(r.word_multiplier).tolist()
VAL = {i: r.scores[i] for i in range(1, 27)}
assert r.hand_size == MAXMOVE and r.emptyhand_bonus == BONUS

# ---------------------------------------------------------------- zak
LETTER_VALUES = sorted((VAL[ch] for ch, n in r.counts.items() for _ in range(n)),
                       reverse=True)
NBLANK = r.blank_count
assert len(LETTER_VALUES) + NBLANK == 102, (len(LETTER_VALUES), NBLANK)
TILE_VALUES = (LETTER_VALUES + [0] * NBLANK)[:MAXTILES]   # voor de herschikking
# voor het CP-SAT-model: de VOLLEDIGE zak als waardeklassen (het aantal cellen
# wordt apart begrensd door T <= 101), zodat ook spellen met 2 blanco's op het
# bord een geldig modelpunt hebben.
VALUE_COUNTS = Counter(LETTER_VALUES + [0] * NBLANK)


# ---------------------------------------------------------------- partities
def partitions(items, maxblock):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for P in partitions(rest, maxblock):
        yield [[first]] + P
        for i in range(len(P)):
            if len(P[i]) < maxblock:
                yield P[:i] + [[first] + P[i]] + P[i + 1:]


def line_cells(kind, idx):
    return [(idx, y) for y in range(N)] if kind == 'col' else [(x, idx) for x in range(N)]


LINES = [('row', i) for i in range(N)] + [('col', i) for i in range(N)]


def line_arrays(kind, idx):
    cs = line_cells(kind, idx)
    return [WM[y][x] for (x, y) in cs], [LM[y][x] for (x, y) in cs], cs


# ------------------------------------------------- L1/L2: per-lijn per-cel
def line_bound(wm, lm, c, force_single):
    """max over partities van de VOLLE lijn van SOM_B w(B) + (lm[c]-1)*w(B_c)."""
    I = sorted(set([i for i in range(N) if wm[i] > 1] + [c]))
    plain = N - len(I)          # wm=1 en != c: singleton is altijd optimaal
    best = -1
    for P in partitions(I, MAXMOVE):
        Bc = next(B for B in P if c in B)
        if force_single and len(Bc) > 1:
            continue
        W = sum(prod(wm[i] for i in B) for B in P) + plain
        best = max(best, W + (lm[c] - 1) * prod(wm[i] for i in Bc))
    return best


def block_max(wm, c):
    """grootste w(B) over blokken B (<=7 cellen) van de lijn die c bevatten."""
    others = sorted((wm[i] for i in range(N) if wm[i] > 1 and i != c), reverse=True)
    return wm[c] * prod(others[:MAXMOVE - 1])


def per_cell_bounds():
    hb_free = {}; hb_sing = {}; vb_free = {}; vb_sing = {}
    bmax_row = {}; bmax_col = {}
    for y in range(N):
        wmr, lmr, _ = line_arrays('row', y)
        for x in range(N):
            hb_free[(x, y)] = line_bound(wmr, lmr, x, False)
            hb_sing[(x, y)] = line_bound(wmr, lmr, x, True)
            bmax_row[(x, y)] = block_max(wmr, x)
    for x in range(N):
        wmc, lmc, _ = line_arrays('col', x)
        for y in range(N):
            vb_free[(x, y)] = line_bound(wmc, lmc, y, False)
            vb_sing[(x, y)] = line_bound(wmc, lmc, y, True)
            bmax_col[(x, y)] = block_max(wmc, y)
    return hb_free, hb_sing, vb_free, vb_sing, bmax_row, bmax_col


def rearrange(coeffs):
    """Herschikkingsongelijkheid: hoogste tegelwaarden op hoogste coefficienten."""
    cs = sorted(coeffs, reverse=True)[:MAXTILES]
    return sum(a * b for a, b in zip(cs, TILE_VALUES))


# ------------------------------------------------- L3/L4/L5: W-tabellen
def w_table(wm):
    """tab[mask][k][b] = bovengrens op W_L = SOM_B w(B) voor een lijn met k
    bezette cellen, b blokken (elk <=7 cellen), waarbij alleen de premiumcellen
    (wm>1) in `mask` in een blok van >=2 mogen zitten (L4).
    None = die combinatie (k,b) is onmogelijk (k > 7b)."""
    S = [i for i in range(N) if wm[i] > 1]
    nplain = N - len(S)
    tab = {}
    for mask in range(1 << len(S)):
        inm = [S[j] for j in range(len(S)) if mask >> j & 1]
        out = [S[j] for j in range(len(S)) if not mask >> j & 1]
        # premium-configs: (aantal bezette premiumcellen, #blokken, gewicht)
        cfg = []
        for rin in range(len(inm) + 1):
            for sub_in in itertools.combinations(inm, rin):
                for P in partitions(list(sub_in), MAXMOVE):
                    wp = sum(prod(wm[i] for i in B) for B in P)
                    for rout in range(len(out) + 1):
                        for sub_out in itertools.combinations(out, rout):
                            cfg.append((rin + rout, len(P) + rout,
                                        wp + sum(wm[i] for i in sub_out)))
        best = [[None] * (N + 1) for _ in range(N + 1)]     # best[k][b]
        for k in range(N + 1):
            for b in range(N + 1):
                if k > MAXMOVE * b or (k == 0) != (b == 0):
                    continue
                v = 0 if k == 0 else -1
                for (np_, b1, wp) in cfg:
                    if np_ > k or b1 > b:
                        continue
                    q = k - np_                       # gewone bezette cellen
                    b2 = min(b - b1, q)               # zoveel als singleton
                    if k > MAXMOVE * (b1 + b2):       # capaciteit blokken
                        continue
                    v = max(v, wp + b2)
                best[k][b] = None if v < 0 else v
        tab[mask] = best
    return S, tab


# ------------------------------------------------------------------ CP-SAT
def cpsat_bound(couple_orientation, block_budget, neighbour, timelimit, log=False, workers=8):
    """Bovengrens via L3 (+L4 / +L5).  Retourneert de CP-SAT OBJECTIVE BOUND:
    ook bij time-out een geldige bovengrens."""
    from ortools.sat.python import cp_model
    hb_free, hb_sing, vb_free, vb_sing, bmax_row, bmax_col = PC
    M2 = {c: max(hb_free[c] + vb_sing[c], hb_sing[c] + vb_free[c]) for c in hb_free}

    m = cp_model.CpModel()
    vals = sorted(VALUE_COUNTS)
    maxval = max(vals)
    cells = [(x, y) for y in range(N) for x in range(N)]

    y_, occ, valv = {}, {}, {}
    for c in cells:
        lits = []
        for v in vals:
            b = m.NewBoolVar('')
            y_[(c, v)] = b
            lits.append(b)
        occ[c] = m.NewBoolVar('')
        m.Add(sum(lits) == occ[c])
        valv[c] = m.NewIntVar(0, maxval, '')
        m.Add(valv[c] == sum(v * y_[(c, v)] for v in vals))
    for v in vals:
        m.Add(sum(y_[(c, v)] for c in cells) <= VALUE_COUNTS[v])
    T = m.NewIntVar(0, MAXTILES, 'T')
    m.Add(T == sum(occ[c] for c in cells))

    if neighbour:
        # L6: elke gelegde tegel zit in minstens een woord (run >= 2), dus heeft
        # een orthogonaal bezette buur.  (Openingszet vormt een woord van >=2
        # letters; elke latere zet raakt het bestaande bord; een zet van >=2
        # tegels ligt zelf in een aaneengesloten run.)  Enige uitzondering is
        # een bord met precies 1 tegel -- dat scoort 0.
        for (x, yy) in cells:
            nb = [occ[(x + dx, yy + dy)] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                  if 0 <= x + dx < N and 0 <= yy + dy < N]
            m.AddBoolOr(nb).OnlyEnforceIf(occ[(x, yy)])

    # orientatie: 1 = de zet die deze cel legt loopt HORIZONTAAL
    ori = {c: m.NewBoolVar('') for c in cells
           if WM[c[1]][c[0]] > 1 or LM[c[1]][c[0]] > 1}

    Wof = {}          # (kind,idx) -> W-variabele
    Wmaxof = {}; neof = {}; kof = {}
    bvars = {'row': [], 'col': []}
    for kind, idx in LINES:
        wm, lm, cs = line_arrays(kind, idx)
        S, tab = w_table(wm)
        kL = m.NewIntVar(0, N, '')
        m.Add(kL == sum(occ[cs[i]] for i in range(N)))
        bL = m.NewIntVar(0, N, '')
        bvars[kind].append(bL)
        wmax = max(v for t in tab.values() for row in t for v in row if v is not None)
        WT = m.NewIntVar(0, wmax, '')
        if couple_orientation and S:
            bits = []
            for i in S:
                c = cs[i]
                if kind == 'row':
                    bits.append(ori[c])
                else:
                    nb = m.NewBoolVar('')
                    m.Add(nb == 1 - ori[c])
                    bits.append(nb)
            tuples = [tuple([k] + [mask >> j & 1 for j in range(len(S))] + [b, tab[mask][k][b]])
                      for mask in range(1 << len(S))
                      for k in range(N + 1) for b in range(N + 1)
                      if tab[mask][k][b] is not None]
            m.AddAllowedAssignments([kL] + bits + [bL, WT], tuples)
        else:
            full = (1 << len(S)) - 1
            tuples = [(k, b, tab[full][k][b]) for k in range(N + 1) for b in range(N + 1)
                      if tab[full][k][b] is not None]
            m.AddAllowedAssignments([kL, bL, WT], tuples)
        WL = m.NewIntVar(0, wmax, '')
        m.Add(WL <= WT)
        Wof[(kind, idx)] = WL
        Wmaxof[(kind, idx)] = wmax
        # redundante LINEAIRE cuts (dezelfde inhoud als de tabel, maar zichtbaar
        # voor de LP-relaxatie -- dat is wat de gap sluit):
        gmax = max(v - b for t in tab.values() for b, row in enumerate(zip(*t))
                   for v in row if v is not None)
        m.Add(WL <= bL + gmax)          # W = SOM_B w(B) = b + SOM_B (w(B)-1)
        m.Add(kL <= MAXMOVE * bL)
        # lijn niet leeg?
        ne = m.NewBoolVar('')
        m.Add(kL >= 1).OnlyEnforceIf(ne)
        m.Add(kL == 0).OnlyEnforceIf(ne.Not())
        neof[(kind, idx)] = ne
        kof[(kind, idx)] = kL

    # L7 (redundante koppeling rij/kolom-bezetting, zie aggregate_bound)
    nrow = m.NewIntVar(0, N, '')
    ncol = m.NewIntVar(0, N, '')
    m.Add(nrow == sum(neof[('row', i)] for i in range(N)))
    m.Add(ncol == sum(neof[('col', i)] for i in range(N)))
    for i in range(N):
        m.Add(kof[('row', i)] <= ncol)
        m.Add(kof[('col', i)] <= nrow)

    if block_budget:
        K = m.NewIntVar(0, MAXTILES, 'K')          # aantal zetten
        beta = m.NewIntVar(0, MAXTILES // MAXMOVE, 'beta')   # 7-tegelzetten
        m.Add(sum(bvars['row']) <= T)                        # L5
        m.Add(sum(bvars['col']) <= T)
        m.Add(sum(bvars['row']) + sum(bvars['col']) <= T + K)
        m.Add(MAXMOVE * K >= T)
        m.Add(T >= 6 * beta + K)
        m.Add(beta <= K)
        bonus = BONUS * beta
    else:
        bonus = FIXBINGO

    # ---- doelfunctie, per LIJN (algebraisch identiek aan de per-cel-som, maar
    # met 30 i.p.v. 225 producten -> CP-SAT kan de gap wel sluiten):
    #   SOM_c val(c)*(W_rij(c)+W_kol(c))  =  SOM_L W_L * V_L
    # TOPSUM[k] = som van de k hoogste tegelwaarden in de zak: een lijn met k
    # bezette cellen heeft V_L <= TOPSUM[k].  Dit koppelt waarde aan bezetting
    # en maakt de LP-relaxatie van het product W_L*V_L veel scherper.
    TOPSUM = [sum(TILE_VALUES[:k]) for k in range(N + 1)]
    terms = []
    for kind, idx in LINES:
        _, _, cs = line_arrays(kind, idx)
        VL = m.NewIntVar(0, TOPSUM[N], '')
        m.Add(VL == sum(valv[c] for c in cs))
        m.AddAllowedAssignments([kof[(kind, idx)], VL],
                                [(k, v) for k in range(N + 1) for v in range(TOPSUM[k] + 1)])
        WL = Wof[(kind, idx)]
        p = m.NewIntVar(0, Wmaxof[(kind, idx)] * TOPSUM[N], '')
        m.AddMultiplicationEquality(p, [WL, VL])
        terms.append(p)

    # ---- letter-premium-term  SOM_c val(c)*(lm(c)-1)*(w(B_rij)+w(B_kol))
    evar = {}
    for c in cells:
        x, yy = c
        lmc, wmc = LM[yy][x], WM[yy][x]
        if lmc == 1:
            continue
        A = (lmc - 1) * (wmc + bmax_row[c])          # eigen zet horizontaal
        B = (lmc - 1) * (wmc + bmax_col[c])          # eigen zet verticaal
        e = m.NewIntVar(0, max(A, B), '')
        m.Add(e <= B + (A - B) * ori[c])
        evar[c] = e
        p = m.NewIntVar(0, max(A, B) * maxval, '')
        m.AddMultiplicationEquality(p, [e, valv[c]])
        terms.append(p)

    # ---- per-cel-cap (L2): voor elke BEZETTE cel geldt m(c) <= M2(c), en in de
    # lijn-decompositie is m(c) = W_rij + W_kol + e(c).
    for c in cells:
        x, yy = c
        e = evar.get(c, 0)
        m.Add(Wof[('row', yy)] + Wof[('col', x)] + e <= M2[c]).OnlyEnforceIf(occ[c])

    m.Maximize(sum(terms) + bonus)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = timelimit
    s.parameters.num_workers = workers
    s.parameters.log_search_progress = log
    st = s.Solve(m)
    ub = s.BestObjectiveBound
    ub = ub() if callable(ub) else ub
    obj = s.ObjectiveValue
    obj = obj() if callable(obj) else obj
    nm = s.StatusName
    nm = nm(st) if callable(nm) else nm
    inc = int(obj) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return int(np.floor(ub + 1e-6)), inc, nm


# -------------------------------------------------------- letter-premium-term
def emax():
    """Bovengrens op  E = SOM_c val(c)*(lm(c)-1)*(w(B_c^rij) + w(B_c^kol)).
    Per cel met lm>1 geldt met L2 (in een richting is B_c = {c}):
        (lm-1)*(w(B^rij)+w(B^kol)) <= (lm-1)*(wm(c) + max(bmax_rij, bmax_kol)).
    Daarna herschikking met de hoogste tegelwaarden."""
    _, _, _, _, bmax_row, bmax_col = PC
    g = sorted(((LM[y][x] - 1) * (WM[y][x] + max(bmax_row[(x, y)], bmax_col[(x, y)]))
                for y in range(N) for x in range(N) if LM[y][x] > 1), reverse=True)
    return sum(a * b for a, b in zip(g, TILE_VALUES)), len(g)


# ------------------------------------------------------------ AGGREGAATMODEL
def aggregate_bound(couple_orientation, block_budget, timelimit, log=False, workers=8):
    """Zelfde relaxatie, maar zonder de 225 celvariabelen: alleen per LIJN
    (k_L, b_L, W_L, V_L) plus de zakverdeling per waardeklasse.  Klein genoeg
    om door CP-SAT tot OPTIMALITEIT te worden opgelost.

    Extra geldige koppeling tussen rijen en kolommen (L7):
      de bezette cellen van rij r liggen in even zoveel VERSCHILLENDE kolommen,
      en die kolommen zijn dus niet leeg  ->  k_r <= n_kol;  analoog k_x <= n_rij.
    Dat is precies wat verhindert dat rijen EN kolommen tegelijk geconcentreerd
    zijn (7 volle rijen  ->  alle 15 kolommen niet-leeg maar hoogstens 7 hoog)."""
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    vals = sorted(VALUE_COUNTS)
    maxval = max(vals)

    place = {v: m.NewIntVar(0, VALUE_COUNTS[v], '') for v in vals}
    T = m.NewIntVar(0, MAXTILES, 'T')
    m.Add(T == sum(place.values()))

    ori = {}
    for y in range(N):
        for x in range(N):
            if WM[y][x] > 1:
                ori[(x, y)] = m.NewBoolVar('')      # 1 = zet-lijn is de RIJ

    kof, bof, Wof, neof = {}, {}, {}, {}
    terms = []
    for kind, idx in LINES:
        wm, lm, cs = line_arrays(kind, idx)
        S, tab = w_table(wm)
        nv = {v: m.NewIntVar(0, VALUE_COUNTS[v], '') for v in vals}
        kL = m.NewIntVar(0, N, '')
        m.Add(kL == sum(nv.values()))
        VL = m.NewIntVar(0, maxval * N, '')
        m.Add(VL == sum(v * nv[v] for v in vals))
        bL = m.NewIntVar(0, N, '')
        wmax = max(v for t in tab.values() for row in t for v in row if v is not None)
        WT = m.NewIntVar(0, wmax, '')
        if couple_orientation and S:
            bits = []
            for i in S:
                c = cs[i]
                if kind == 'row':
                    bits.append(ori[c])
                else:
                    nb = m.NewBoolVar('')
                    m.Add(nb == 1 - ori[c])
                    bits.append(nb)
            tuples = [tuple([k] + [mask >> j & 1 for j in range(len(S))] + [b, tab[mask][k][b]])
                      for mask in range(1 << len(S))
                      for k in range(N + 1) for b in range(N + 1)
                      if tab[mask][k][b] is not None]
            m.AddAllowedAssignments([kL] + bits + [bL, WT], tuples)
        else:
            full = (1 << len(S)) - 1
            tuples = [(k, b, tab[full][k][b]) for k in range(N + 1) for b in range(N + 1)
                      if tab[full][k][b] is not None]
            m.AddAllowedAssignments([kL, bL, WT], tuples)
        WL = m.NewIntVar(0, wmax, '')
        m.Add(WL <= WT)
        ne = m.NewBoolVar('')                       # lijn niet leeg
        m.Add(kL >= 1).OnlyEnforceIf(ne)
        m.Add(kL == 0).OnlyEnforceIf(ne.Not())
        kof[(kind, idx)] = (kL, nv)
        bof[(kind, idx)] = bL
        Wof[(kind, idx)] = WL
        neof[(kind, idx)] = ne
        p = m.NewIntVar(0, wmax * maxval * N, '')
        m.AddMultiplicationEquality(p, [WL, VL])
        terms.append(p)

    # zak: elke tegel zit in precies een rij en precies een kolom
    for v in vals:
        for kind in ('row', 'col'):
            m.Add(sum(kof[(kind, i)][1][v] for i in range(N)) == place[v])

    # L7: rij/kolom-bezettingskoppeling
    nrow = m.NewIntVar(0, N, '')
    ncol = m.NewIntVar(0, N, '')
    m.Add(nrow == sum(neof[('row', i)] for i in range(N)))
    m.Add(ncol == sum(neof[('col', i)] for i in range(N)))
    for i in range(N):
        m.Add(kof[('row', i)][0] <= ncol)
        m.Add(kof[('col', i)][0] <= nrow)

    if block_budget:
        K = m.NewIntVar(0, MAXTILES, 'K')
        beta = m.NewIntVar(0, MAXTILES // MAXMOVE, 'beta')
        br = sum(bof[('row', i)] for i in range(N))
        bc = sum(bof[('col', i)] for i in range(N))
        m.Add(br <= T)
        m.Add(bc <= T)
        m.Add(br + bc <= T + K)
        m.Add(MAXMOVE * K >= T)
        m.Add(T >= 6 * beta + K)
        m.Add(beta <= K)
        bonus = BONUS * beta
    else:
        bonus = FIXBINGO

    E, _ = emax()
    m.Maximize(sum(terms) + bonus + E)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = timelimit
    s.parameters.num_workers = workers
    s.parameters.log_search_progress = log
    st = s.Solve(m)
    ub = s.BestObjectiveBound
    ub = ub() if callable(ub) else ub
    obj = s.ObjectiveValue
    obj = obj() if callable(obj) else obj
    nm = s.StatusName
    nm = nm(st) if callable(nm) else nm
    inc = int(obj) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    return int(np.floor(ub + 1e-6)), inc, nm


# ------------------------------------------------------------------ zelftest
def selftest():
    """Op het huidige record: m(c) <= M2(c) voor elke cel?"""
    import mg_mceiling as MC
    p = 'experiments/results/maxgame_BEST.json'
    if not os.path.exists(p):
        return None
    D = json.load(open(p))
    moves = [[tuple(c) for c in mv] for mv in D['moves']]
    mm = MC.multiplicity(moves)
    hb_free, hb_sing, vb_free, vb_sing, _, _ = PC
    bad = [(c, v, max(hb_free[c] + vb_sing[c], hb_sing[c] + vb_free[c]))
           for c, v in mm.items()
           if v > max(hb_free[c] + vb_sing[c], hb_sing[c] + vb_free[c])]
    # L5-identiteit controleren: SOM_rijen b_L + SOM_kol b_L == T + K
    Tn, Kn = sum(len(mv) for mv in moves), len(moves)
    br = sum(len(set(yy for _, yy in mv)) for mv in moves)
    bc = sum(len(set(xx for xx, _ in mv)) for mv in moves)
    assert br + bc == Tn + Kn, (br, bc, Tn, Kn)
    assert br <= Tn and bc <= Tn, (br, bc, Tn)
    return len(mm), max(mm.values()), bad, (Tn, Kn, br, bc)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tl', type=float, default=300.0)
    ap.add_argument('--log', action='store_true')
    ap.add_argument('--only', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--agg', action='store_true', help='ook het (lossere) aggregaatmodel draaien')
    a = ap.parse_args()

    PC = per_cell_bounds()
    hb_free, hb_sing, vb_free, vb_sing, bmax_row, bmax_col = PC

    st = selftest()
    if st:
        print(f'zelftest record: {st[0]} bezette cellen, max m(c) = {st[1]}, '
              f'M2-schendingen: {len(st[2])}')
        print(f'  L5-identiteit OK: T={st[3][0]} K={st[3][1]} '
              f'SOM_rij b={st[3][2]} SOM_kol b={st[3][3]} '
              f'-> {st[3][2] + st[3][3]} == T+K = {st[3][0] + st[3][1]}')
        assert not st[2], f'SCHENDING van M2 op het record: {st[2][:5]}'

    rows = []
    M1 = {c: hb_free[c] + vb_free[c] for c in hb_free}
    rows.append(('1  per-cel, vrije blokken (L1)', rearrange(M1.values()) + FIXBINGO, ''))
    M2 = {c: max(hb_free[c] + vb_sing[c], hb_sing[c] + vb_free[c]) for c in hb_free}
    rows.append(('2  + orientatie-exclusiviteit (L2)', rearrange(M2.values()) + FIXBINGO, ''))

    E, nE = emax()
    print(f'letter-premium-term E <= {E}  ({nE} cellen met lm>1)')

    todo = [(3, 'agg', False, False, False, 'aggregaat: gedeelde W_L + zak + L7'),
            (4, 'agg', True, False, False, '+ rij/kolom-orientatiekoppeling (L4)'),
            (5, 'agg', True, True, False, '+ blok/zet/bingo-budget (L5)'),
            (6, 'cell', True, True, True, 'celmodel: L1-L6 (225 cellen)')]
    for nr, mode, co, bb, nbr, label in todo:
        if a.only and a.only != nr:
            continue
        if not a.only and mode == 'agg' and not a.agg:
            continue      # aggregaatmodel is aantoonbaar LOSSER; alleen op verzoek
        f = aggregate_bound if mode == 'agg' else cpsat_bound
        ub, inc, status = (f(co, bb, a.tl, a.log, a.workers) if mode == 'agg'
                           else f(co, bb, nbr, a.tl, a.log, a.workers))
        rows.append((f'{nr}  {label}', ub, f'[{status}] modeloptimum >= {inc}'))

    print()
    print('  stap                                                bovengrens')
    print('  ' + '-' * 66)
    for name, v, note in rows:
        print(f'  {name:<50s} {v:>9d}   {note}')
    best = min(v for _, v, _ in rows)
    print('  ' + '-' * 66)
    print(f'  SCHERPSTE GELDIGE BOVENGRENS                         {best:>9d}')
    print(f'  sanity: record intern 4751, extern 4819  <=  {best}')
    assert best >= 4819, 'FOUT: bovengrens onder het bekende externe record!'
    json.dump({'steps': [(n, v, t) for n, v, t in rows], 'bound': best},
              open('experiments/results/mg_globalbound.json', 'w'), indent=1)
