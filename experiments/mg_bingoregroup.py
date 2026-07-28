"""BINGO-HERGROEPERING: dezelfde bezetting, een andere ZETINDELING.

score(spel) = SOM_c m(c)*waarde(c) + 50*#zetten-van-7   (mg_mceiling)

Bij VASTE bezetting en VASTE letters is de m-calculus geen plafond maar de score zelf.
Daarmee kun je elke herindeling van de 101 tegels over de zetten exact evalueren zonder
solver: split/merge/verplaats zetten, tel de bingo's, klaar.  Het woordenboek komt pas
aan het eind (score_game is de arbiter; deelruns moeten woorden zijn).

Analyses (env MODE, default 'all'):
  lines     lijn-eigendom + bingo-capaciteit per lijn  (waar zit ruimte voor een 12e bingo?)
  ub        bovengrens op het aantal bingo's in DEZE bezetting (CP-SAT set-packing)
  merge     uitputtend: alle samenvoegingen van niet-bingo-zetten tot 7 tegels, alle posities
  split     uitputtend: alle splitsingen van een 7-zet in tweeen, alle posities
  repart    uitputtend: per lijn een volledige herindeling in intervallen, alle posities
  anneal    lokale zoektocht (split/merge/verplaats) met exacte doelfunctie
  refit     CP-SAT hervulling van de letters voor het beste gevonden schema

Env: RBASE (basisbord), OUT (json voor een verbeterd bord), TLIM/NW (CP-SAT), ITERS.
"""
import sys, os, json, random, itertools, importlib.util
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter, defaultdict
import maxgame_score as MG

_spec = importlib.util.spec_from_file_location("mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mc)

BASE = os.environ.get('RBASE', 'experiments/results/maxgame_BEST.json')
OUT = os.environ.get('OUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/'
                            'da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/bingoregroup_best.json')
MODE = os.environ.get('MODE', 'all')
D = json.load(open(BASE))
GRID = D['grid']
MOVES = [[tuple(c) for c in m] for m in D['moves']]
BLANKS = set(tuple(b) for b in D.get('blanks', []))
VAL = {i: mc.r.scores[i] for i in range(1, 27)}
OCC = {(x, y) for y in range(15) for x in range(15) if GRID[y][x]}


def val(c):
    return 0 if c in BLANKS else VAL[GRID[c[1]][c[0]]]


def exact(mvs):
    """EXACTE score van een schema bij deze bezetting+letters (geldig zodra alle deelruns
    woorden zijn; score_game is de arbiter)."""
    m = mc.multiplicity(mvs)
    return sum(v * val(c) for c, v in m.items()) + 50 * sum(1 for q in mvs if len(q) == 7)


def nbingo(mvs):
    return sum(1 for q in mvs if len(q) == 7)


def arbiter(mvs):
    tot, per, ok, msg = MG.score_game([r[:] for r in GRID], mvs, BLANKS)
    return int(tot), ok, msg


_BYLEN = {}
for _w in MG.r.words_str: _BYLEN.setdefault(len(_w), []).append(tuple(MG.r.alphabet.cba[_c] for _c in _w))
_FIX37 = {(x, y): GRID[y][x] for y in (0, 7, 14) for x in range(15) if GRID[y][x]}
_WCACHE = {}


def runs_of(mvs):
    """alle (run, nieuwe-cellen) gebeurtenissen van een schema"""
    return mc.events_of(mvs)


def badruns(mvs):
    """aantal tussenruns dat GEEN woord kan zijn gegeven de vaste rij-0/7/14-letters"""
    n = 0
    for run, _ in mc.events_of(mvs):
        key = (len(run), tuple((i, _FIX37[c]) for i, c in enumerate(run) if c in _FIX37))
        r = _WCACHE.get(key)
        if r is None:
            r = any(all(w[i] == v for i, v in key[1]) for w in _BYLEN.get(key[0], ()))
            _WCACHE[key] = r
        if not r: n += 1
    return n


def wordable(mvs):
    """NOODZAKELIJKE voorwaarde voor woordlegaliteit, zonder solver: elke tussenrun moet
    een woord KUNNEN zijn gegeven de vaste letters van rij 0/7/14.  dutch2026 heeft GEEN
    woorden van lengte 2, dus elke run van 2 is meteen fataal -- dat sloopt veel schema's."""
    for run, _ in mc.events_of(mvs):
        key = (len(run), tuple((i, _FIX37[c]) for i, c in enumerate(run) if c in _FIX37))
        r = _WCACHE.get(key)
        if r is None:
            r = any(all(w[i] == v for i, v in key[1]) for w in _BYLEN.get(key[0], ()))
            _WCACHE[key] = r
        if not r: return False
    return True


def line_of(mv):
    xs = {x for x, y in mv}; ys = {y for x, y in mv}
    if len(ys) == 1 and len(xs) == 1: return ('pt', mv[0])
    if len(ys) == 1: return ('rij', next(iter(ys)))
    if len(xs) == 1: return ('kol', next(iter(xs)))
    return None


BASESC = exact(MOVES)
_t, _ok, _msg = arbiter(MOVES)
print(f"BASIS {BASE}: m-calculus {BASESC} | arbiter {_t} ok={_ok} ({_msg})")
print(f"  {len(OCC)} tegels, {len(MOVES)} zetten, {nbingo(MOVES)} bingo's "
      f"({50*nbingo(MOVES)} bonus), maten {sorted(Counter(len(m) for m in MOVES).items())}")
assert BASESC == _t and _ok, "m-identiteit klopt niet op de basis"


# ---------------------------------------------------------------- 1. lijn-eigendom
def owners():
    """Wijs elke zet aan een lijn toe; 1-tegelzetten aan zowel rij als kolom (ambigu)."""
    d = defaultdict(list)
    for i, mv in enumerate(MOVES):
        k = line_of(mv)
        if k[0] == 'pt':
            d[('rij', mv[0][1])].append(i); d[('kol', mv[0][0])].append(i)
        else:
            d[k].append(i)
    return d


def an_lines():
    print("\n=== LIJN-EIGENDOM & BINGO-CAPACITEIT ===")
    print("  (1-tegelzetten tellen bij rij EN kolom mee: bovengrens per lijn)")
    for k, v in sorted(owners().items()):
        n = sum(len(MOVES[i]) for i in v); b = sum(1 for i in v if len(MOVES[i]) == 7)
        if n < 7: continue
        star = '   <== RUIMTE VOOR +%d BINGO' % (n // 7 - b) if n // 7 > b else ''
        print(f"  {k[0]} {k[1]:2d}: {n:2d} eigen tegels, {len(v)} zetten, {b} bingo's, "
              f"capaciteit {n//7}{star}")


# ---------------------------------------------------------------- 2. bingo-bovengrens
def an_ub():
    """Set-packing: hoogstens hoeveel disjuncte 7-groepen passen er in DEZE bezetting?
    Een 7-groep = 7 cellen op een lijn waarvan het interval (met de andere bezette cellen
    als opvulling) aaneengesloten is.  Negeert zetvolgorde -> echte bovengrens."""
    print("\n=== BOVENGRENS AANTAL BINGO'S (set-packing over 7-groepen) ===")
    # een 7-groep = 7 cellen op een lijn waarvan het eigen interval [a,b] VOLLEDIG bezet is
    # (de gaten worden dan door al liggende tegels gevuld -- zonder volgorde-eis, dus ruim).
    groups = set()
    for y in range(15):
        for a in range(15):
            for b in range(a + 6, 15):
                iv = [(x, y) for x in range(a, b + 1)]
                if len(iv) > 13 or not all(c in OCC for c in iv): continue
                for sub in itertools.combinations(iv, 7):
                    if sub[0] == iv[0] and sub[-1] == iv[-1]: groups.add(sub)
    for x in range(15):
        for a in range(15):
            for b in range(a + 6, 15):
                iv = [(x, y) for y in range(a, b + 1)]
                if len(iv) > 13 or not all(c in OCC for c in iv): continue
                for sub in itertools.combinations(iv, 7):
                    if sub[0] == iv[0] and sub[-1] == iv[-1]: groups.add(sub)
    groups = sorted(groups)
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    u = [m.new_bool_var(f"g{i}") for i in range(len(groups))]
    bycell = defaultdict(list)
    for i, g in enumerate(groups):
        for c in g: bycell[c].append(i)
    for c, idx in bycell.items(): m.add(sum(u[i] for i in idx) <= 1)
    m.maximize(sum(u))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 60
    s.parameters.num_workers = int(os.environ.get('NW', '8'))
    st = s.solve(m)
    print(f"  {len(groups)} kandidaat-7-groepen; max disjuncte pakking = {int(s.objective_value)} "
          f"({s.status_name(st)})  [zetvolgorde nog niet meegewogen]")
    print(f"  huidig: {nbingo(MOVES)} bingo's; 101 tegels => absolute plafond 14")
    return int(s.objective_value)


# ---------------------------------------------------------------- helpers voor schema's
def insert_variants(rest, parts):
    """Alle manieren om de nieuwe zetten `parts` (in vaste onderlinge volgorde) tussen de
    overgebleven zetten `rest` te schuiven."""
    n = len(rest)
    for pos in itertools.combinations_with_replacement(range(n + 1), len(parts)):
        out = []; k = 0
        for i in range(n + 1):
            while k < len(parts) and pos[k] == i:
                out.append(list(parts[k])); k += 1
            if i < n: out.append(list(rest[i]))
        yield out


def report(cands, title, top=12):
    print(f"\n=== {title} ===")
    good = sorted(cands, key=lambda t: -t[0])
    if not good:
        print("  geen enkele legale kandidaat"); return None
    seen = set(); shown = 0
    for sc, nb, mvs, lab in good:
        if lab in seen: continue
        seen.add(lab); shown += 1
        print(f"  {sc-BASESC:+6d}  score {sc}  bingo's {nb}  {lab}")
        if shown >= top: break
    best = good[0]
    print(f"  beste: {best[0]-BASESC:+d} ({best[0]}), bingo's {best[1]}")
    return best


# ---------------------------------------------------------------- 3. merge-scan
def an_merge():
    """Uitputtend: welke deelverzamelingen niet-bingo-tegels kunnen tot EEN zet van 7
    worden samengevoegd?  Alle collineaire 7-deelverzamelingen x alle posities."""
    print("\n=== SAMENVOEGEN VAN NIET-BINGO-TEGELS TOT EEN BINGO ===")
    small = [i for i, m in enumerate(MOVES) if len(m) < 7]
    cells = [(c, i) for i in small for c in MOVES[i]]
    print(f"  {len(cells)} niet-bingo-tegels in {len(small)} zetten")
    # collineaire 7-deelverzamelingen
    byline = defaultdict(list)
    for c, i in cells:
        byline[('rij', c[1])].append(c); byline[('kol', c[0])].append(c)
    cand = []
    ntried = 0
    for k, cs in sorted(byline.items()):
        if len(cs) < 7: continue
        print(f"  lijn {k}: {len(cs)} niet-bingo-tegels -> {len(list(itertools.combinations(cs,7)))} 7-deelverz.")
        for sub in itertools.combinations(sorted(cs), 7):
            S = set(sub)
            rest = []
            for m in MOVES:
                keep = [c for c in m if c not in S]
                if keep: rest.append(keep)
            for mvs in insert_variants(rest, [list(sub)]):
                ntried += 1
                if not mc.legal_schedule(mvs): continue
                cand.append((exact(mvs), nbingo(mvs), mvs, f"samenvoeging {sorted(sub)}"))
    if not any(len(cs) >= 7 for cs in byline.values()):
        print("  GEEN lijn heeft 7 niet-bingo-tegels -> een 12e bingo kan NIET uit losse tegels alleen")
    print(f"  {ntried} schema's getest, {len(cand)} legaal")
    return report(cand, "samenvoegingen (netto)")


# ---------------------------------------------------------------- 4. split-scan
def an_split():
    """Omgekeerde richting: splits een 7-zet (verlies 50, win herscoring)."""
    cand = []
    for i, mv in enumerate(MOVES):
        if len(mv) != 7: continue
        maxfill = OCC - set(mv)          # ruimste denkbare opvulling -> vormfilter vooraf
        for k in range(1, 7):
            for sub in itertools.combinations(mv, k):
                A = list(sub); B = [c for c in mv if c not in set(sub)]
                if not mc.shape_ok(A, maxfill) or not mc.shape_ok(B, maxfill): continue
                rest = [m for j, m in enumerate(MOVES) if j != i]
                for mvs in insert_variants(rest, [A, B]):
                    if not mc.legal_schedule(mvs): continue
                    cand.append((exact(mvs), nbingo(mvs), mvs, f"splits zet {i} -> {len(A)}+{len(B)}"))
                for mvs in insert_variants(rest, [B, A]):
                    if not mc.legal_schedule(mvs): continue
                    cand.append((exact(mvs), nbingo(mvs), mvs, f"splits zet {i} -> {len(B)}+{len(A)}"))
    return report(cand, "SPLITSEN van een bingo (verlies 50, win herscoring)")


# ---------------------------------------------------------------- 5. lijn-herindeling
def intervals_on(line, cells, filler):
    """Alle 7-groepen op een lijn: het interval tussen min en max moet vol zijn met
    cellen uit de groep zelf of uit `filler` (tegels die er al liggen)."""
    tag, k = line
    coord = (lambda c: c[0]) if tag == 'rij' else (lambda c: c[1])
    have = {coord(c) for c in cells}
    fl = {coord(c) for c in filler}
    out = []
    for a in range(15):
        for b in range(a, 15):
            grp = [c for c in cells if a <= coord(c) <= b]
            if len(grp) != 7: continue
            if coord(min(grp, key=coord)) != a or coord(max(grp, key=coord)) != b: continue
            if all(t in have or t in fl for t in range(a, b + 1)):
                out.append(tuple(sorted(grp, key=coord)))
    return out


def an_repart(lines=None):
    """Volledige herindeling van de eigen tegels van een lijn in twee 7-zetten
    (de enige manier om een bingo BIJ te maken zonder er een te slopen)."""
    print("\n=== LIJN-HERINDELING NAAR 2 BINGO'S ===")
    cand = []
    own = owners()
    for k, idx in sorted(own.items()):
        if lines and k not in lines: continue
        cs = [c for i in idx for c in MOVES[i]]
        if len(cs) < 14: continue
        nb = sum(1 for i in idx for _ in [0] if len(MOVES[i]) == 7)
        filler = [c for c in OCC if c not in set(cs)]
        As = intervals_on(k, cs, filler)
        print(f"  {k}: {len(cs)} eigen tegels, {nb} bingo's -> {len(As)} vormlegale 7-groepen")
        for A in As:
            B = [c for c in cs if c not in set(A)]
            if len(B) != 7: continue
            rest = []
            for j, m in enumerate(MOVES):
                keep = [c for c in m if c not in set(cs)]
                if keep: rest.append(keep)
            for order in ([A, B], [B, A]):
                for mvs in insert_variants(rest, order):
                    if not mc.legal_schedule(mvs): continue
                    a0 = sorted(order[0]);
                    cand.append((exact(mvs), nbingo(mvs), mvs,
                                 f"{k[0]}{k[1]} = {_fmt(order[0])} + {_fmt(order[1])}"))
    return report(cand, "herindelingen naar 2 bingo's op een lijn", top=16)


def _fmt(g):
    xs = sorted(g)
    if len({y for x, y in xs}) == 1: return 'x' + ','.join(str(x) for x, y in xs)
    return 'y' + ','.join(str(y) for x, y in xs)


# ---------------------------------------------------------------- 6. anneal
def an_anneal(iters=None, seeds=6):
    """Lokale zoektocht over schema's bij dezelfde bezetting, exacte doelfunctie.
    Houdt naast het m-optimum ook het beste DOOR DE ARBITER GEKEURDE schema bij
    (zelfde letters, dus alle deelruns moeten woorden zijn)."""
    iters = iters or int(os.environ.get('ITERS', '20000'))
    seeds = int(os.environ.get('SEEDS', seeds))
    print(f"\n=== LOKALE ZOEKTOCHT ({seeds} runs x {iters} stappen) ===")
    best = (BASESC, nbingo(MOVES), MOVES)
    ver = (BASESC, nbingo(MOVES), MOVES)
    for s in range(seeds):
        rnd = random.Random(1234 + s)
        cur = [list(m) for m in MOVES]; cs = BASESC
        for it in range(iters):
            cand = [list(m) for m in cur]
            op = rnd.random()
            if op < 0.35:                                   # splits
                idx = [i for i, m in enumerate(cand) if len(m) > 1]
                if not idx: continue
                i = rnd.choice(idx); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
                k = rnd.randrange(1, len(m))
                if rnd.random() < 0.5: m = m[::-1]
                cand[i:i + 1] = [m[:k], m[k:]]
            elif op < 0.7:                                  # samenvoegen (niet per se buren)
                i = rnd.randrange(len(cand)); j = rnd.randrange(len(cand))
                if i == j or len(cand[i]) + len(cand[j]) > 7: continue
                a, b = max(i, j), min(i, j)
                mg = cand[a] + cand[b]
                cand[a] = mg; cand.pop(b)
            else:                                           # verplaats
                i = rnd.randrange(len(cand)); mv = cand.pop(i)
                cand.insert(rnd.randrange(len(cand) + 1), mv)
            if not mc.legal_schedule(cand): continue
            sc = exact(cand)
            if sc >= cs:
                cur = cand; cs = sc
                if sc > best[0]:
                    best = (sc, nbingo(cand), [list(m) for m in cand])
                if sc > ver[0]:
                    t, ok, msg = arbiter(cand)
                    if ok and t == sc: ver = (sc, nbingo(cand), [list(m) for m in cand])
        print(f"  run {s}: {cs} ({cs-BASESC:+d})")
    print(f"  BESTE m-schema {best[0]} ({best[0]-BASESC:+d}), bingo's {best[1]}")
    print(f"  BESTE ARBITER-GEKEURD (zelfde letters) {ver[0]} ({ver[0]-BASESC:+d}), bingo's {ver[1]}")
    json.dump({'m': best[0], 'moves': [[list(c) for c in m] for m in best[2]],
               'verified': ver[0], 'vmoves': [[list(c) for c in m] for m in ver[2]]},
              open(OUT + '.anneal.json', 'w'))
    if ver[0] > BASESC:
        save(GRID, ver[2], BLANKS, ver[0], 'hergroepering (arbiter-gekeurd, zelfde letters)')
    return best


def an_cross(iters=None, seeds=None):
    """KRUIS-LIJN-HERVERDELING -> 12e BINGO.

    Een lijn kan pas 2 bingo's dragen als hij >=14 EIGEN tegels heeft.  Alleen rij 14 haalt
    dat (14), maar daar is de 12e bingo onmogelijk: de slotzet moet x=0,7,14 bevatten (x27),
    en de overige eigen cellen vallen dan in twee blokken van 6 (x1..6 en x8..13) -- een
    7-groep zou over x=7 moeten bruggen en die ligt er nog niet.

    Rij 7 kan het WEL, want daar ligt (7,7) al vanaf zet 1 (kolom 7 = openingszet).  Geef rij 7
    de drie cellen (5,7),(10,7),(11,7) die nu bij kolom 5/10/11 horen -> rij 7 heeft 14 eigen
    tegels en dus 2 bingo's; de drie kolommen halen hun 7e tegel elders:
        kol 5 : rijen 0,1,2,3,5,6,8   (gaten 4 en 7 al gevuld)
        kol 10: rijen 0,1,2,3,5,6,8
        kol 11: rijen 8..14           (pakt (11,14) van rij 14 over)
    Netto +1 bingo zonder ook maar een x27-slotzet te breken.
    """
    iters = iters or int(os.environ.get('ITERS', '20000'))
    seeds = int(os.environ.get('SEEDS', seeds or 10))
    print("\n=== KRUIS-LIJN-HERVERDELING: 12e BINGO OP RIJ 7 ===")
    Rw = lambda y, *xs: [(x, y) for x in xs]
    Cl = lambda x, *ys: [(x, y) for y in ys]
    col7 = Cl(7, 4, 5, 6, 7, 8, 9, 10); row4 = Rw(4, 3, 4, 5, 6, 8, 9, 10)
    col2 = Cl(2, 0, 1, 2, 3, 4, 5, 6); col5 = Cl(5, 0, 1, 2, 3, 5, 6, 8)
    col12 = Cl(12, 0, 1, 2, 3, 4, 5, 6); col4 = Cl(4, 8, 9, 10, 11, 12, 13, 14)
    col10 = Cl(10, 0, 1, 2, 3, 5, 6, 8); col11 = Cl(11, 8, 9, 10, 11, 12, 13, 14)
    fixed37 = {(x, y): GRID[y][x] for y in (0, 7, 14) for x in range(15) if GRID[y][x]}
    baseceil = mc.score_of(MOVES, fixed37)[0]
    # de slotzet moet x=0,7,14 bevatten (x27/x9); de resterende 4 cellen kiezen we vrij, maar
    # de DLS-cellen (x=3 en x=11) horen ER IN: daar levert de slotzet LM 2 x WM 27 = m 54.
    r0must, r0free = [3, 11], [1, 4, 6, 8, 9, 13]
    r14must, r14free = [3], [1, 2, 5, 6, 8, 9, 10, 12, 13]     # (11,14) is nu van kolom 11
    best = None
    windows = [int(v) for v in os.environ['AWIN'].split(',')] if os.environ.get('AWIN') else range(1, 7)
    for a in windows:                                          # rij-7-voorgroep = [a,a+7] \ {7}
        A = [(x, 7) for x in range(a, a + 8) if x != 7]
        F = [(0, 7)] + [(x, 7) for x in range(1, 14) if not (a <= x <= a + 7)] + [(14, 7)]
        if len(A) != 7 or len(F) != 7: continue
        for s in range(seeds):
            rnd = random.Random(9000 + 31 * a + s)
            cur = None; groups = None; bestbad = None
            for _try in range(int(os.environ.get('TRIES', '120'))):
                # slotzet-samenstelling: mag geen losse tegel INSLUITEN (onbereikbaar) en moet
                # woordbare tussenruns overlaten -> kies de samenstelling met de minste bad-runs
                q0 = r0must + rnd.sample(r0free, 2); q14 = r14must + rnd.sample(r14free, 3)
                F0 = Rw(0, *sorted([0, 7, 14] + q0)); F14 = Rw(14, *sorted([0, 7, 14] + q14))
                gs = [col7, row4, A, col2, col5, col12, col4, F, col10, col11, F0, F14]
                used = {c for g in gs for c in g}
                pool = gs + [[c] for c in sorted(OCC - used)]
                c0 = _greedy_order(pool, rnd)
                if c0 is None: continue
                bb = badruns(c0)
                if bestbad is None or bb < bestbad:
                    bestbad, cur, groups = bb, c0, gs
                if bb == 0: break
            if cur is None: continue
            prot = {tuple(sorted(g)) for g in groups}      # de 12 bingo-groepen blijven heel
            # OBJ=ceil: optimaliseer het m-PLAFOND (rij 0/7/14 vast, rest vrij) i.p.v. de score
            # met de huidige letters -- dat is de juiste maat als je toch gaat herletteren.
            if os.environ.get('OBJ') == 'ceil':
                obj = lambda mm: mc.score_of(mm, fixed37)[0] - 1000 * badruns(mm)
            else:
                obj = lambda mm: exact(mm) - 1000 * badruns(mm)
            cs = obj(cur); loc = None
            for it in range(iters):
                cand = [list(m) for m in cur]
                op = rnd.random()
                if op < 0.55:                                  # verplaats
                    i = rnd.randrange(len(cand)); mv = cand.pop(i)
                    cand.insert(rnd.randrange(len(cand) + 1), mv)
                elif op < 0.8:                                 # splits een NIET-beschermde zet
                    idx = [i for i, m in enumerate(cand) if len(m) > 1 and tuple(sorted(m)) not in prot]
                    if not idx: continue
                    i = rnd.choice(idx); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
                    k = rnd.randrange(1, len(m))
                    if rnd.random() < 0.5: m = m[::-1]
                    cand[i:i + 1] = [m[:k], m[k:]]
                else:                                          # voeg twee niet-beschermde samen
                    idx = [i for i, m in enumerate(cand) if tuple(sorted(m)) not in prot]
                    if len(idx) < 2: continue
                    i, j = rnd.sample(idx, 2)
                    if len(cand[i]) + len(cand[j]) > 7: continue
                    a2, b2 = max(i, j), min(i, j)
                    cand[a2] = cand[a2] + cand[b2]; cand.pop(b2)
                if not mc.legal_schedule(cand): continue
                sc = obj(cand)
                if sc >= cs:
                    cur = cand; cs = sc
                    if badruns(cand) == 0 and (loc is None or sc > loc[2]):
                        loc = (exact(cand), [list(m) for m in cand], sc)
            if loc is None: continue
            cur = loc[1]
            ce = mc.score_of(cur, fixed37)[0]
            t, ok, msg = arbiter(cur)
            if ok and t > BASESC:
                print(f"  !! ARBITER-OK 12-bingo-bord {t} (> {BASESC}) met de huidige letters")
                save(GRID, cur, BLANKS, t, 'kruis-lijn 12e bingo op rij 7')
            if best is None or (ce, loc[0]) > (best[1], best[0]):
                best = (loc[0], ce, nbingo(cur), [list(m) for m in cur], a)
        w = ''.join(chr(96 + GRID[7][x]) for x in range(a, a + 8))
        if best is None:
            print(f"  A=x{a}..{a+7}\\{{7}} ('{w}'): geen woordlegaal schema", flush=True); continue
        print(f"  A=x{a}..{a+7}\\{{7}} ('{w}'): beste exact {best[0]} ({best[0]-BASESC:+d}), "
              f"m-plafond {best[1]} (basis {baseceil}), bingo's {best[2]}", flush=True)
    if best is None:
        print("  GEEN woordlegaal 12-bingo-schema in deze familie"); return None
    print(f"  BESTE 12-BINGO-SCHEMA: exact {best[0]} ({best[0]-BASESC:+d}) met de HUIDIGE letters, "
          f"m-plafond {best[1]} vs basis {baseceil} ({best[1]-baseceil:+d})")
    json.dump({'moves': [[list(c) for c in m] for m in best[3]], 'exact': best[0], 'ceil': best[1],
               'bingos': best[2]}, open(OUT + '.cross12.json', 'w'))
    print(f"  schema opgeslagen in {OUT}.cross12.json")
    return (best[0], best[2], best[3], f'kruis-lijn 12 bingo (A=x{best[4]}..)')


def move_runs_ok(m, placed):
    """kunnen alle runs die zet m vormt woorden zijn (gegeven de vaste rij-0/7/14-letters)?"""
    pl = placed | set(m); cset = set(m); seen = set()
    for (x, y) in m:
        for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
            x0, y0 = x, y
            while x0-dx >= 0 and y0-dy >= 0 and (x0-dx, y0-dy) in pl: x0 -= dx; y0 -= dy
            x1, y1 = x, y
            while x1+dx < 15 and y1+dy < 15 and (x1+dx, y1+dy) in pl: x1 += dx; y1 += dy
            n = max(x1-x0, y1-y0) + 1
            if n < 2 or (tag, x0, y0) in seen: continue
            seen.add((tag, x0, y0))
            run = [(x0+i*dx, y0+i*dy) for i in range(n)]
            if not any(c in cset for c in run): continue
            key = (n, tuple((i, _FIX37[c]) for i, c in enumerate(run) if c in _FIX37))
            r = _WCACHE.get(key)
            if r is None:
                r = any(all(w[i] == v for i, v in key[1]) for w in _BYLEN.get(n, ()))
                _WCACHE[key] = r
            if not r: return False
    return True


def _greedy_order(pool, rnd, words=True):
    cur = []; placed = set(); rest = [list(m) for m in pool]
    while rest:
        cand = [i for i, m in enumerate(rest)
                if (not placed and (7, 7) in m) or
                   (placed and any((x + dx, y + dy) in placed for (x, y) in m for dx, dy in mc.NB)
                    and mc.shape_ok(m, placed))]
        if not cand: return None
        good = [i for i in cand if move_runs_ok(rest[i], placed)] if words else cand
        i = rnd.choice(good or cand); m = rest.pop(i); cur.append(m); placed |= set(m)
    return cur


def an_legal(iters=None, seeds=4):
    """Zoektocht die ALLEEN door de arbiter goedgekeurde schema's accepteert (zelfde letters):
    elke tussenrun moet een woord zijn.  Levert direct verifieerde borden."""
    iters = iters or int(os.environ.get('ITERS', '6000'))
    seeds = int(os.environ.get('SEEDS', seeds))
    print(f"\n=== WOORDLEGALE ZOEKTOCHT ({seeds} runs x {iters} stappen, arbiter als harde eis) ===")
    best = (BASESC, MOVES)
    for s in range(seeds):
        rnd = random.Random(777 + s)
        cur = [list(m) for m in MOVES]; cs = BASESC
        for it in range(iters):
            cand = [list(m) for m in cur]
            op = rnd.random()
            if op < 0.3:
                idx = [i for i, m in enumerate(cand) if len(m) > 1]
                if not idx: continue
                i = rnd.choice(idx); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
                k = rnd.randrange(1, len(m))
                if rnd.random() < 0.5: m = m[::-1]
                cand[i:i + 1] = [m[:k], m[k:]]
            elif op < 0.55:
                i = rnd.randrange(len(cand)); j = rnd.randrange(len(cand))
                if i == j or len(cand[i]) + len(cand[j]) > 7: continue
                a, b = max(i, j), min(i, j)
                cand[a] = cand[a] + cand[b]; cand.pop(b)
            else:
                i = rnd.randrange(len(cand)); mv = cand.pop(i)
                cand.insert(rnd.randrange(len(cand) + 1), mv)
            if not mc.legal_schedule(cand): continue
            sc = exact(cand)
            if sc < cs: continue
            t, ok, msg = arbiter(cand)
            if not ok or t != sc: continue
            cur = cand; cs = sc
            if sc > best[0]: best = (sc, [list(m) for m in cand])
        print(f"  run {s}: {cs} ({cs-BASESC:+d})")
    print(f"  BESTE WOORDLEGAAL {best[0]} ({best[0]-BASESC:+d})")
    if best[0] > BASESC:
        save(GRID, best[1], BLANKS, best[0], 'woordlegale hergroepering (zelfde letters)')
    return (best[0], nbingo(best[1]), best[1], 'legale hergroepering')


# ---------------------------------------------------------------- 7. CP-SAT hervulling
def refit(mvs, tlim=None, nw=None):
    """Hervul de letters voor een gegeven schema (zelfde bezetting) met CP-SAT en
    verifieer met score_game."""
    from ortools.sat.python import cp_model
    import numpy as np
    tlim = tlim or float(os.environ.get('TLIM', '300')); nw = nw or int(os.environ.get('NW', '8'))
    r = MG.r; cba = r.alphabet.cba
    LM = np.array(r.letter_multiplier); WM = np.array(r.word_multiplier)
    bag = Counter({c: r.counts[c] for c in r.counts})
    bylen = {}
    for w in r.words_str: bylen.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))
    occ = sorted(OCC)
    fix = {}
    if os.environ.get('FIX37', '1') == '1':      # rij 0/7/14 (de x27/x9-slotwoorden) vastzetten
        fix = {(x, y): GRID[y][x] for y in (0, 7, 14) for x in range(15) if GRID[y][x]}
    m_ = cp_model.CpModel()
    L = {c: (m_.new_constant(fix[c]) if c in fix else m_.new_int_var(1, 26, f"L{c}")) for c in occ}
    placed = set(); events = []; runs = set()
    for cells in mvs:
        placed |= set(cells); cset = set(cells); seen = set()
        for (x, y) in cells:
            for dx, dy, tag in ((1, 0, 'H'), (0, 1, 'V')):
                x0, y0 = x, y
                while x0-dx >= 0 and y0-dy >= 0 and (x0-dx, y0-dy) in placed: x0 -= dx; y0 -= dy
                x1, y1 = x, y
                while x1+dx < 15 and y1+dy < 15 and (x1+dx, y1+dy) in placed: x1 += dx; y1 += dy
                n = max(x1-x0, y1-y0) + 1
                if n < 2 or (tag, x0, y0) in seen: continue
                seen.add((tag, x0, y0))
                run = [(x0+i*dx, y0+i*dy) for i in range(n)]
                if any(c in cset for c in run): events.append((run, cset)); runs.add(tuple(run))
    for run in runs:
        fx = {i: fix[c] for i, c in enumerate(run) if c in fix}
        tab = [w for w in bylen.get(len(run), []) if all(w[i] == v for i, v in fx.items())]
        if not tab: return 'geenwoorden', len(run), None, None
        m_.add_allowed_assignments([L[c] for c in run], tab)
    BL = {c: m_.new_bool_var(f"bl{c}") for c in occ}
    for c in fix: m_.add(BL[c] == (1 if c in BLANKS else 0))
    m_.add(sum(BL.values()) <= 2)
    for ch in range(1, 27):
        cnt = []
        for c in occ:
            b = m_.new_bool_var(f"i{c}_{ch}")
            m_.add(L[c] == ch).only_enforce_if(b); m_.add(L[c] != ch).only_enforce_if(b.negated())
            nb = m_.new_bool_var(f"nb{c}_{ch}")
            m_.add_bool_and([b, BL[c].negated()]).only_enforce_if(nb)
            m_.add_bool_or([b.negated(), BL[c]]).only_enforce_if(nb.negated())
            cnt.append(nb)
        m_.add(sum(cnt) <= bag[ch])
    VV = [0] + [VAL[i] for i in range(1, 27)]
    vv = {}
    for c in set(q for run, _ in events for q in run):
        v = m_.new_int_var(0, 10, f"v{c}"); m_.add_element(L[c], VV, v)
        ve = m_.new_int_var(0, 10, f"ve{c}")
        m_.add(ve == v).only_enforce_if(BL[c].negated()); m_.add(ve == 0).only_enforce_if(BL[c])
        vv[c] = ve
    obj = []
    for run, cset in events:
        wm = 1
        for (x, y) in run:
            if (x, y) in cset: wm *= int(WM[y][x])
        obj.append(sum(vv[(x, y)] * (int(LM[y][x]) if (x, y) in cset else 1) for (x, y) in run) * wm)
    m_.maximize(sum(obj) + 50 * nbingo(mvs))
    for c in occ:
        if c not in fix: m_.add_hint(L[c], GRID[c[1]][c[0]])
        m_.add_hint(BL[c], 1 if c in BLANKS else 0)
    sol = cp_model.CpSolver(); sol.parameters.max_time_in_seconds = tlim
    sol.parameters.num_workers = nw; sol.parameters.log_search_progress = True
    st = sol.solve(m_)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeasible' if st == cp_model.INFEASIBLE else 'unknown'), None, None, None
    g2 = [[0]*15 for _ in range(15)]
    for c in occ: g2[c[1]][c[0]] = sol.value(L[c])
    bl = {c for c in occ if sol.value(BL[c])}
    return 'ok', int(sol.objective_value), g2, bl


def save(g2, mvs, bl, tot, plan):
    json.dump({'grid': g2, 'moves': [[list(c) for c in m] for m in mvs],
               'blanks': [list(b) for b in sorted(bl)], 'total': int(tot),
               'triple': D.get('triple'), 'plan': plan}, open(OUT, 'w'))
    print(f"  >>> WEGGESCHREVEN naar {OUT}")


# ---------------------------------------------------------------- main
if __name__ == '__main__':
    todo = MODE.split(',') if MODE != 'all' else ['lines', 'ub', 'merge', 'split', 'repart', 'anneal']
    best = None
    if 'refit12' in todo:
        # herlettering van een eerder gevonden schema (env SCHED=<json met 'moves'>)
        S = json.load(open(os.environ['SCHED']))
        mvs = [[tuple(c) for c in m] for m in S['moves']]
        print(f"HERLETTERING van {os.environ['SCHED']}: {len(mvs)} zetten, {nbingo(mvs)} bingo's, "
              f"exact met huidige letters {exact(mvs)}, m-plafond "
              f"{mc.score_of(mvs, {(x,y): GRID[y][x] for y in (0,7,14) for x in range(15) if GRID[y][x]})[0]}")
        st, ob, g2, bl = refit(mvs)
        print("refit:", st, ob)
        if st == 'ok':
            tot, per, ok, msg = MG.score_game([r[:] for r in g2], mvs, bl)
            print(f"arbiter na refit: {int(tot)} ok={ok} ({msg})")
            for y in range(15):
                print('   ' + ''.join(chr(96 + g2[y][x]) if g2[y][x] else '.' for x in range(15)))
            if ok:
                save(g2, mvs, bl, tot, 'kruis-lijn 12e bingo + herlettering')
                if int(tot) > int(D['total']): print(f"*** NIEUW RECORD {int(tot)} > {D['total']} ***")
                else: print(f"(geen record: {int(tot)} <= {D['total']})")
        sys.exit(0)
    if 'lines' in todo: an_lines()
    if 'ub' in todo: an_ub()
    if 'merge' in todo:
        b = an_merge()
        if b and (best is None or b[0] > best[0]): best = b
    if 'split' in todo:
        b = an_split()
        if b and (best is None or b[0] > best[0]): best = b
    if 'repart' in todo:
        b = an_repart()
        if b and (best is None or b[0] > best[0]): best = b
    if 'anneal' in todo:
        b = an_anneal()
        if b and (best is None or b[0] > best[0]): best = (b[0], b[1], b[2], 'anneal')
    if 'legal' in todo:
        b = an_legal()
        if b and (best is None or b[0] > best[0]): best = b
    if 'cross' in todo:
        b = an_cross()
        if b and (best is None or b[0] > best[0]): best = b
    if best and best[0] > BASESC:
        mvs = best[2]
        tot, ok, msg = arbiter(mvs)
        print(f"\n=== BESTE HERGROEPERING ===\n  m-calculus {best[0]} ({best[0]-BASESC:+d}), "
              f"bingo's {best[1]}\n  arbiter met HUIDIGE letters: {tot} ok={ok} ({msg})")
        if ok and tot > int(D['total']):
            save(GRID, mvs, BLANKS, tot, f"hergroepering {best[3]}")
        else:
            print("  -> letters hervullen met CP-SAT (schema vast, bezetting vast)")
            st, ob, g2, bl = refit(mvs)
            print(f"  refit: {st} {ob}")
            if st == 'ok':
                tot, per, ok, msg = MG.score_game([r[:] for r in g2], mvs, bl)
                print(f"  arbiter na refit: {int(tot)} ok={ok} ({msg})")
                if ok and int(tot) > int(D['total']):
                    print(f"  *** NIEUW RECORD {int(tot)} > {D['total']} ***")
                    save(g2, mvs, bl, tot, f"hergroepering+refit {best[3]}")
    else:
        print(f"\n=== GEEN NETTO-POSITIEVE HERGROEPERING GEVONDEN (basis {BASESC}) ===")
