"""LETTERBUDGET: wat LAAT een ankertriplet OVER?

Alle bestaande tripletrankers (TRIPLET_RERANK, ROW7, ANCHORCHAIN) wegen wat een triplet ZELF
oplevert.  Geen enkele weegt wat het OVERLAAT: het ankertriplet eist 45 van de 100 lettertegels
op, en de overige 56 cellen moeten uit de RESTZAK gevuld worden.  Dit script meet die restzak,
maakt er een zak-LEXICALE maat van, en herrangschikt de tripletten op

        ankerwaarde  +  restwaarde(restzak)

M-CALCULUS-DECOMPOSITIE (exact, zie deel 0).  Bij een VAST voetafdruk (celposities + zetvolgorde)
is de totaalscore lineair in de letterwaarden:

        score  =  SOM_cellen m(c) * v(letter op c)  +  50 * #bingos

met m(c) = som over alle scoringsgebeurtenissen die c raken van wm(gebeurtenis)*lm(c-indien-nieuw).
Daarmee splitst de score EXACT in
        ankerdeel  A_m(T) = SOM over rijen 0/7/14      (hangt alleen van het triplet af)
        restdeel   R(T)   = SOM over de 56 vrije cellen (hangt af van de RESTZAK)
Dat maakt "ankerwaarde minus restzak-armoede" voor het eerst een optelsom in dezelfde eenheid.

CLI:  .venv/bin/python experiments/mg_letterbudget.py
Env:  PART=0,1,2,3,4  DELTA (ankerslack, default 400)  TOP  TLIM  NTEST  OUT  MB
"""
import sys, os, json, time, pickle, heapq
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter, defaultdict
import numpy as np
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba
INV = {v: k for k, v in cba.items()}
AL = 'abcdefghijklmnopqrstuvwxyz'
LM = np.array(r.letter_multiplier).astype(int)
WM = np.array(r.word_multiplier).astype(int)
V = {ch: r.scores[cba[ch]] for ch in AL}
VARR = np.array([0] + [r.scores[i] for i in range(1, 27)])
BAG = Counter({ch: r.counts[cba[ch]] for ch in AL})
BAGV = np.array([BAG[ch] for ch in AL], dtype=np.int16)
BLANKS = r.blank_count
CUR = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')
VOW = set('aeiouy')
BIND = 'enaodrsti'                       # bindletters uit de opdracht

PARTS = set(os.environ.get('PART', '0,1,2,3,4').split(','))
TOP = int(os.environ.get('TOP', '25'))
DELTA = int(os.environ.get('DELTA', '400'))
MB = os.environ.get('MB', 'experiments/results/maxgame_BEST.json')
SCRATCH = ('/tmp/claude-1000/-home-bob-programming-scrabble4/'
           'da7ed622-7493-428d-96da-a3b3144f633e/scratchpad')
RESULT = {}

BYLEN = defaultdict(list)
for w in r.words_str:
    BYLEN[len(w)].append(w)
for L in BYLEN:                     # r.words_str is een SET -> volgorde is hash-afhankelijk;
    BYLEN[L].sort()                 # sorteren maakt alle gelijkspel-keuzes reproduceerbaar
SETS = {L: set(ws) for L, ws in BYLEN.items()}
def isw(s):
    return s in SETS.get(len(s), ())


def hdr(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78, flush=True)


def vec(word):
    a = np.zeros(26, dtype=np.int16)
    for ch in word:
        a[ord(ch) - 97] += 1
    return a


# ---------------------------------------------------------------- voetafdruk + m-kaart
def load_board(path=MB):
    D = json.load(open(path))
    grid = D['grid']
    moves = [[tuple(c) for c in m] for m in D['moves']]
    bl = set(tuple(b) for b in D['blanks'])
    return D, grid, moves, bl


def mmap(grid, moves):
    """m(c) per cel + lijst van scoringsgebeurtenissen (run, nieuwe cellen)."""
    placed = set(); m = Counter(); events = []; bingo = 0
    for cells in moves:
        placed |= set(cells); cset = set(cells); seen = set()
        if len(cells) == 7:
            bingo += 50
        for (x, y) in cells:
            for h in (1, 0):
                dx, dy = (1, 0) if h else (0, 1)
                x0, y0 = x, y
                while 0 <= x0 - dx < 15 and 0 <= y0 - dy < 15 and (x0 - dx, y0 - dy) in placed:
                    x0 -= dx; y0 -= dy
                run = []; xx, yy = x0, y0
                while 0 <= xx < 15 and 0 <= yy < 15 and (xx, yy) in placed:
                    run.append((xx, yy)); xx += dx; yy += dy
                if len(run) < 2:
                    continue
                k = (run[0], h, len(run))
                if k in seen or not any(c in cset for c in run):
                    continue
                seen.add(k); events.append((tuple(run), frozenset(cset)))
                wm = 1
                for c in run:
                    if c in cset:
                        wm *= int(WM[c[1]][c[0]])
                for c in run:
                    m[c] += wm * (int(LM[c[1]][c[0]]) if c in cset else 1)
    return m, events, bingo


D0, GRID0, MOVES0, BL0 = load_board()
MMAP, EVENTS, BINGO = mmap(GRID0, MOVES0)
OCC = [(x, y) for y in range(15) for x in range(15) if GRID0[y][x]]
ANCHOR_CELLS = [c for c in OCC if c[1] in (0, 7, 14)]
FREE_CELLS = [c for c in OCC if c[1] not in (0, 7, 14)]
# eindbord-runs die vrije cellen bevatten (voor de restwaarde-maten)
def final_runs(occ):
    S = set(occ); out = []
    for h in (1, 0):
        for a in range(15):
            cells = []
            for b in range(15):
                xy = (b, a) if h else (a, b)
                if xy in S:
                    cells.append(xy)
                else:
                    if len(cells) >= 2:
                        out.append(tuple(cells))
                    cells = []
            if len(cells) >= 2:
                out.append(tuple(cells))
    return out
FRUNS = final_runs(OCC)


def anchor_value(triple):
    """A_m(T): exacte ankerbijdrage van dit triplet op het recordvoetafdruk."""
    tot = 0
    for (x, y) in ANCHOR_CELLS:
        w = triple[{0: 0, 7: 1, 14: 2}[y]]
        tot += MMAP[(x, y)] * V[w[x]]
    return tot


# ---------------------------------------------------------------- restzak
def residual(triple):
    """(restzak Counter, tekortlijst).  Tekort = letters die de zak niet levert (blanco nodig)."""
    need = Counter(''.join(triple))
    short = {ch: n - BAG[ch] for ch, n in need.items() if n > BAG[ch]}
    res = Counter({ch: BAG[ch] - need.get(ch, 0) for ch in AL if BAG[ch] - need.get(ch, 0) > 0})
    return res, short


def blank_loss(triple, short):
    """Puntverlies als een tekortletter als blanco op een ankerrij moet: m(c)*v, goedkoopste cel."""
    loss = 0
    for ch, k in short.items():
        cands = sorted(MMAP[(x, y)] * V[ch]
                       for y, w in ((0, triple[0]), (7, triple[1]), (14, triple[2]))
                       for x in range(15) if w[x] == ch)
        loss += sum(cands[:k])
    return loss


def profile(res):
    n = sum(res.values())
    vow = sum(res[c] for c in VOW)
    return {'n': n, 'klinkers': vow, 'medeklinkers': n - vow,
            'bind': {ch: res[ch] for ch in BIND},
            'bindsom': sum(res[ch] for ch in BIND),
            'alfabet': ''.join(ch for ch in AL if res[ch]),
            'weg': ''.join(ch for ch in AL if not res[ch])}


# ---------------------------------------------------------------- zak-lexicale maten
_LEXCACHE = {}
def lexarr(L):
    """(woordenlijst, letterteldmatrix Nx26, lettercodematrix NxL met 0..25)."""
    if L not in _LEXCACHE:
        ws = BYLEN[L]
        ch = (np.frombuffer(''.join(ws).encode(), dtype=np.uint8).reshape(len(ws), L)
              .astype(np.int16) - 97)
        cnt = np.zeros((len(ws), 26), dtype=np.int16)
        for i in range(L):
            np.add.at(cnt, (np.arange(len(ws)), ch[:, i]), 1)
        _LEXCACHE[L] = (ws, cnt, ch)
    return _LEXCACHE[L]


def lex_free(res, lengths=(6, 8, 10, 12)):
    """Generieke maat: hoeveel woorden per lengte zijn nog UIT DE RESTZAK ALLEEN te bouwen."""
    b = np.array([res[ch] for ch in AL], dtype=np.int16)
    out = {}
    for L in lengths:
        ws, cnt, chm = lexarr(L)
        out[L] = int((cnt <= b).all(axis=1).sum())
    return out


# kolomtabellen: 8-letterwoorden gegroepeerd op (eerste, laatste); 15-letters op (0,7,14)
_G8 = None
def grp8():
    global _G8
    if _G8 is None:
        g = defaultdict(list)
        for w in BYLEN[8]:
            g[(w[0], w[7])].append(w)
        _G8 = {k: (v, np.array([vec(w[1:7]) for w in v], dtype=np.int16)) for k, v in g.items()}
    return _G8


def col_tables(triple, res):
    """Zakgefilterde kolomcensus: per binnenkolom hoeveel 8-letter kop- resp. staartkolommen
    er nog bouwbaar zijn uit de restzak (de anker-letters zijn gratis)."""
    b = np.array([res[ch] for ch in AL], dtype=np.int16)
    G = grp8(); a, m, c = triple
    top = {}; bot = {}
    for x in range(1, 14):
        if x == 7:
            continue
        for (p, q, d) in ((a[x], m[x], top), (m[x], c[x], bot)):
            ent = G.get((p, q))
            d[x] = 0 if ent is None else int((ent[1] <= b).all(axis=1).sum())
    return top, bot


# ---------------------------------------------------------------- restwaarde-maten
# de vrije runs van het voetafdruk met hun vaste (anker)posities
def run_spec():
    specs = []
    for run in FRUNS:
        fr = [i for i, c in enumerate(run) if c[1] not in (0, 7, 14)]
        if not fr:
            continue                                  # zuivere ankerrij
        fx = [(i, c) for i, c in enumerate(run) if c[1] in (0, 7, 14)]
        specs.append({'run': run, 'free': fr, 'fix': fx, 'L': len(run),
                      'w': [MMAP[c] for c in run]})
    return specs
RSPEC = run_spec()
# hoofdrun per vrije cel = de run met de grootste m-som (voor de decoupled schatting)
_OWNER = {}
for sp in sorted(RSPEC, key=lambda s: -sum(s['w'][i] for i in s['free'])):
    for i in sp['free']:
        _OWNER.setdefault(sp['run'][i], sp['run'])
BIGRUNS = [sp for sp in RSPEC if any(_OWNER[sp['run'][i]] == sp['run'] for i in sp['free'])]


def rest_estimate(triple, res, greedy=True):
    """Ontkoppelde restwaarde-schatting op het recordvoetafdruk.
    Per hoofdrun: kies het woord dat de m-gewogen waarde van ZIJN EIGEN vrije cellen
    maximeert, gegeven de ankerletters en de (bij greedy: uitputtende) restzak.
    greedy=False -> bovengrens (zak niet gedeeld); greedy=True -> realistische schatting."""
    b = np.array([res[ch] for ch in AL], dtype=np.int16)
    order = sorted(BIGRUNS, key=lambda s: -sum(s['w'][i] for i in s['free']
                                               if _OWNER[s['run'][i]] == s['run']))
    tot = 0; okall = True
    for sp in order:
        L = sp['L']
        ws, cnt, chm = lexarr(L)
        mask = np.ones(len(ws), dtype=bool)
        for i, c in sp['fix']:
            w = triple[{0: 0, 7: 1, 14: 2}[c[1]]]
            mask &= chm[:, i] == (ord(w[c[0]]) - 97)
        idx = np.nonzero(mask)[0]
        if len(idx) == 0:
            okall = False
            continue
        fv = cnt[idx].copy()                      # zakvraag = woord minus de vaste ankerletters
        for i, c in sp['fix']:
            w = triple[{0: 0, 7: 1, 14: 2}[c[1]]]
            fv[:, ord(w[c[0]]) - 97] -= 1
        good = (fv <= b).all(axis=1)
        if not good.any():
            okall = False
            continue
        idx = idx[good]; fv = fv[good]
        own = [i for i in sp['free'] if _OWNER[sp['run'][i]] == sp['run']]
        wts = np.array([sp['w'][i] for i in own], dtype=np.int64)
        sc = (VARR[chm[np.ix_(idx, own)] + 1] * wts).sum(axis=1)
        k = int(np.argmax(sc)); tot += int(sc[k])
        if greedy:
            b = np.maximum(b - fv[k], 0)
    return tot, okall


# ---------------------------------------------------------------- exacte voetafdruk-solver
def exact_fill(triple, tlim=180, workers=8, nblank_free=None, target=None):
    """CP-SAT: optimale letterinvulling van de 56 vrije cellen bij dit triplet op het
    recordvoetafdruk (zetvolgorde vast).  Blanco's zijn VRIJ te plaatsen op ELKE bezette cel
    (waarde 0, geen zakverbruik), hoogstens BLANKS stuks -- dus ook op ankercellen, waarmee een
    triplet dat de zak overvraagt automatisch en optimaal wordt afgestraft.
    target=T: geen maximalisatie maar de BESLISSING "bestaat er een invulling met score >= T";
    status INFEASIBLE is dan een BEWIJS dat dit triplet op dit voetafdruk onder T blijft.
    Geeft (status, totaal, grid, blanks, msg, grens)."""
    from ortools.sat.python import cp_model
    res, short = residual(triple)
    if sum(short.values()) > BLANKS:
        return ('zak', 0, None, None, f"tekort {short}", -1)
    m_ = cp_model.CpModel()
    fixed = {}
    for (x, y) in ANCHOR_CELLS:
        fixed[(x, y)] = cba[triple[{0: 0, 7: 1, 14: 2}[y]][x]]
    L = {}
    for c in FREE_CELLS:
        L[c] = m_.new_int_var(1, 26, f"L{c}")
    for c, v in fixed.items():
        L[c] = m_.new_constant(v)
    for run in sorted({run for run, _ in EVENTS}):
        fx = {i: fixed[c] for i, c in enumerate(run) if c in fixed}
        tab = [t for t in (tuple(cba[ch] for ch in w) for w in BYLEN[len(run)])
               if all(t[i] == v for i, v in fx.items())]
        if not tab:
            return ('nowords', 0, None, None, f"run {run}", -1)
        m_.add_allowed_assignments([L[c] for c in run], tab)
    isbl = {c: m_.new_bool_var(f"b{c}") for c in OCC}
    m_.add(sum(isbl.values()) <= BLANKS)
    for ch in range(1, 27):
        cnt = []
        for c in FREE_CELLS:
            v = m_.new_bool_var(f"i{c}_{ch}")
            m_.add(L[c] == ch).only_enforce_if(v)
            m_.add(L[c] != ch).only_enforce_if(~v)
            u = m_.new_bool_var(f"u{c}_{ch}")
            m_.add_bool_and([v, ~isbl[c]]).only_enforce_if(u)
            m_.add_bool_or([~v, isbl[c]]).only_enforce_if(~u)
            cnt.append(u)
        anch = [~isbl[c] for c, v in fixed.items() if v == ch]
        m_.add(sum(cnt) + sum(anch) <= int(r.counts[ch]))
    VV = [0] + [r.scores[i] for i in range(1, 27)]
    valvar = {}
    for c in FREE_CELLS:
        e = m_.new_int_var(0, 10, f"e{c}")
        m_.add_element(L[c], VV, e)
        v = m_.new_int_var(0, 10, f"v{c}")
        m_.add(v == 0).only_enforce_if(isbl[c])
        m_.add(v == e).only_enforce_if(~isbl[c])
        valvar[c] = v
    for c, fv in fixed.items():
        v = m_.new_int_var(0, 10, f"v{c}")
        m_.add(v == 0).only_enforce_if(isbl[c])
        m_.add(v == VV[fv]).only_enforce_if(~isbl[c])
        valvar[c] = v
    obj = []
    for run, cset in EVENTS:
        wm = 1
        for (x, y) in run:
            if (x, y) in cset:
                wm *= int(WM[y][x])
        obj.append(sum(valvar[(x, y)] * (int(LM[y][x]) if (x, y) in cset else 1)
                       for (x, y) in run) * wm)
    if target is None:
        m_.maximize(sum(obj) + BINGO)
    else:
        m_.add(sum(obj) + BINGO >= target)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = tlim
    sol.parameters.num_workers = workers
    sol.parameters.log_search_progress = False
    st = sol.solve(m_)
    bnd = int(sol.best_objective_bound) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else -1
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ('infeas', 0, None, None, sol.status_name(st), bnd)
    g = [[0] * 15 for _ in range(15)]
    for c in OCC:
        g[c[1]][c[0]] = sol.value(L[c])
    bl = sorted(c for c in OCC if sol.value(isbl[c]))
    tot, per, ok, msg = MG.score_game([row[:] for row in g], MOVES0, set(bl))
    return (sol.status_name(st) if ok else 'REJ', int(tot), g, bl, msg, bnd)


# ---------------------------------------------------------------- zak-bewuste restgrens
MFREE = np.array(sorted((MMAP[c] for c in FREE_CELLS), reverse=True), dtype=np.int64)
VAL_OF = np.array([V[ch] for ch in AL], dtype=np.int64)


def restub_bag(resvec):
    """Bovengrens op de restwaarde: koppel de DUURSTE resttegels aan de HOOGSTE m-cellen
    (herschikkingsongelijkheid).  Negeert woordvorming en zetvolgorde => geldige bovengrens,
    en hij hangt ALLEEN van de restzak af.  Blanco's krijgen de laagste m-cellen (waarde 0)."""
    vals = np.repeat(VAL_OF, resvec)
    vals = -np.sort(-vals)
    n = min(len(vals), len(MFREE))
    return int((MFREE[:n] * vals[:n]).sum())


# harde bovengrens over ALLE tripletten: laat de 55 duurste zaktegels over
_rich = sorted(BAG.elements(), key=lambda c: -V[c])[:len(MFREE) - 1]
RESTUB_MAX = restub_bag(np.bincount([ord(c) - 97 for c in _rich], minlength=26))


# ---------------------------------------------------------------- ankerpools (voetafdruk-eis)
def anchor_pools():
    """Per ankerrij: alle 15-letterwoorden die de FRAGMENTEN van het recordvoetafdruk
    respecteren (de tussenstand-runs op die rij moeten woorden zijn), met hun A_m-waarde."""
    frag = defaultdict(set)
    for run, _ in EVENTS:
        ys = {c[1] for c in run}
        if len(ys) == 1 and run[0][1] in (0, 7, 14) and len(run) < 15:
            frag[run[0][1]].add((run[0][0], len(run)))
    pools = {}
    for y in (0, 7, 14):
        m = [MMAP[(x, y)] for x in range(15)]
        req = sorted(frag[y])
        pool = [(sum(m[x] * V[w[x]] for x in range(15)), w) for w in BYLEN[15]
                if all(isw(w[s:s + l]) for s, l in req)]
        pool.sort(reverse=True)
        pools[y] = (pool, req, m)
    return pools


# gevectoriseerde restgrens: de restzak valt in waardeklassen, de m-cellen zijn gesorteerd
VCLASS = sorted({V[ch] for ch in AL}, reverse=True)
VMASK = np.array([[1 if V[ch] == v else 0 for ch in AL] for v in VCLASS], dtype=np.int64)
MPRE = np.concatenate([[0], np.cumsum(MFREE)])


def restub_vec(resmat):
    """resmat: (N,26) resttellingen -> (N,) bovengrens op de restwaarde."""
    k = resmat.astype(np.int64) @ VMASK.T                 # (N, #klassen) tellingen per waarde
    start = np.concatenate([np.zeros((len(k), 1), dtype=np.int64),
                            np.cumsum(k, axis=1)], axis=1)
    start = np.minimum(start, len(MFREE))
    seg = MPRE[start[:, 1:]] - MPRE[start[:, :-1]]
    return (seg * np.array(VCLASS, dtype=np.int64)).sum(axis=1)


def sweep(floor=None, verbose=True, rec=None):
    """VOLLEDIGE enumeratie over het recordvoetafdruk: alle tripletten waarvan de HARDE
    bovengrens  A_m - blancoverlies + RESTUB_bag + bingo  het record haalt.
    Snoeivloer A_m >= record - bingo - RESTUB_MAX is een geldige noodzakelijke voorwaarde
    (RESTUB_bag <= RESTUB_MAX voor elke restzak, blancoverlies >= 0)."""
    P = anchor_pools()
    if rec is None:
        rec = int(D0['total'])
    if floor is None:
        floor = rec - BINGO - RESTUB_MAX
    p0, p7, p14 = P[0][0], P[7][0], P[14][0]
    m7max = p7[0][0]
    v7 = np.array([v for v, w in p7], dtype=np.int64)
    c7 = np.array([vec(w) for v, w in p7], dtype=np.int16)
    out = []; npair = 0; nbagpair = 0; ntri = 0; nbl = 0
    t0 = time.time()
    for v0, w0 in p0:
        if v0 + m7max + p14[0][0] < floor:
            break
        c0 = vec(w0)
        for v14, w14 in p14:
            if v0 + v14 + m7max < floor:
                break
            npair += 1
            cp = BAGV - c0 - vec(w14)
            if -int(np.minimum(cp, 0).sum()) > BLANKS:
                continue                       # paar alleen al > 2 blanco's tekort
            nbagpair += 1
            need = floor - v0 - v14
            n = int(np.searchsorted(-v7, -need, side='right'))
            if n == 0:
                continue
            rest = cp[None, :] - c7[:n]
            defc = -np.minimum(rest, 0).sum(axis=1)
            ok = defc <= BLANKS
            if not ok.any():
                continue
            idx = np.nonzero(ok)[0]
            resid = np.maximum(rest[idx], 0)
            ub = restub_vec(resid)
            am = v0 + v14 + v7[idx]
            ntri += len(idx)
            loss = np.zeros(len(idx), dtype=np.int64)
            dpos = np.nonzero(defc[idx] > 0)[0]
            for j in dpos:                     # blanco op een ankercel kost m(c)*v
                tri = (w0, p7[idx[j]][1], w14)
                short = {AL[k]: int(-rest[idx[j]][k]) for k in range(26) if rest[idx[j]][k] < 0}
                loss[j] = blank_loss(tri, short)
                nbl += 1
            tot = am - loss + ub + BINGO
            for j in np.nonzero(tot > rec)[0]:
                i = idx[j]
                out.append((int(tot[j]), int(am[j] - loss[j]), int(ub[j]),
                            w0, p7[i][1], w14, int(defc[i])))
    if verbose:
        print(f"  paren bekeken {npair}, zak-haalbaar {nbagpair}, tripletten {ntri} "
              f"(waarvan {nbl} met blanco-tekort), boven record {len(out)}  "
              f"({time.time()-t0:.0f}s)", flush=True)
    out.sort(reverse=True)
    return out, P


# ---------------------------------------------------------------- delen
def part0():
    hdr("0. IJKING — de m-calculus-decompositie van het record")
    rec = int(D0['total'])
    tot, per, ok, msg = MG.score_game([row[:] for row in GRID0], MOVES0, BL0)
    am = anchor_value(CUR)
    rv = sum(MMAP[c] * (0 if c in BL0 else V[INV[GRID0[c[1]][c[0]]]]) for c in FREE_CELLS)
    ab = sum(MMAP[c] * (0 if c in BL0 else V[INV[GRID0[c[1]][c[0]]]]) for c in ANCHOR_CELLS)
    print(f"  arbiter: {tot} ok={ok} ({msg})")
    print(f"  cellen: {len(OCC)} bezet = {len(ANCHOR_CELLS)} anker + {len(FREE_CELLS)} vrij; "
          f"blanco's {sorted(BL0)}; bingo's {BINGO//50} (= {BINGO} punten)")
    print(f"  m-decompositie: anker {ab} + rest {rv} + bingo {BINGO} = {ab+rv+BINGO}  "
          f"(record {rec}) -> {'EXACT' if ab+rv+BINGO == rec else 'MISMATCH'}")
    print(f"  A_m(triplet) zonder blanco-korting = {am} (blanco's liggen op vrije cellen)")
    for y in (0, 7, 14):
        prof = [MMAP[(x, y)] for x in range(15)]
        print(f"    rij {y:2d} {CUR[{0:0,7:1,14:2}[y]]:16s} m={prof} som {sum(prof)}  "
              f"waarde {sum(MMAP[(x,y)]*V[CUR[{0:0,7:1,14:2}[y]][x]] for x in range(15))}")
    print(f"  m-profiel VRIJE cellen (gesorteerd): som {int(MFREE.sum())}, max {int(MFREE[0])}, "
          f"mediaan {int(np.median(MFREE))}")
    RESULT['ijking'] = {'record': rec, 'anker': ab, 'rest': rv, 'bingo': BINGO}


def part1():
    hdr("1. DE RESTZAK VAN HET HUIDIGE TRIPLET")
    res, short = residual(CUR)
    p = profile(res)
    print(f"  zak 100 letters + {BLANKS} blanco; triplet eist 45 tegels op")
    print(f"  verbruik  : " + ' '.join(f"{ch}{n}/{BAG[ch]}" for ch, n in
                                       sorted(Counter(''.join(CUR)).items())))
    print(f"  RESTZAK   : " + ' '.join(f"{ch}{n}" for ch, n in sorted(res.items())) +
          f"   ({p['n']} tegels voor {len(FREE_CELLS)} cellen + {BLANKS} blanco)")
    print(f"  klinkers {p['klinkers']} / medeklinkers {p['medeklinkers']}; "
          f"bindletters {p['bind']} (som {p['bindsom']})")
    print(f"  restalfabet {p['alfabet']}  --  VOLLEDIG OP: {p['weg']}")
    lf = lex_free(res, (4, 6, 8, 10, 12, 15))
    print("\n  zak-lexicale dekking (woorden nog UIT DE RESTZAK ALLEEN bouwbaar):")
    for L, n in sorted(lf.items()):
        print(f"    lengte {L:2d}: {n:6d} van {len(BYLEN[L]):6d}  ({100*n/len(BYLEN[L]):4.1f}%)")
    top, bot = col_tables(CUR, res)
    print("\n  kolomtabellen met zakfilter (8-letter verticalen rij0-rij7 resp. rij7-rij14,"
          "\n  ankerletters gratis, binnenletters uit de restzak):")
    print("    kolom : " + ' '.join(f"{x:4d}" for x in sorted(top)))
    print("    top   : " + ' '.join(f"{top[x]:4d}" for x in sorted(top)) + f"   som {sum(top.values())}")
    print("    bodem : " + ' '.join(f"{bot[x]:4d}" for x in sorted(bot)) + f"   som {sum(bot.values())}")
    g, _ = rest_estimate(CUR, res, True)
    ub = restub_bag(np.array([res[ch] for ch in AL]))
    rv = sum(MMAP[c] * (0 if c in BL0 else V[INV[GRID0[c[1]][c[0]]]]) for c in FREE_CELLS)
    print(f"\n  restwaarde-maten: werkelijk {rv}  |  greedy-schatting {g}  |  "
          f"zakgrens RESTUB {ub}  |  absoluut plafond over alle zakken {RESTUB_MAX}")
    RESULT['restzak'] = {'profiel': p, 'lex': lf, 'top': top, 'bot': bot,
                         'rest_echt': rv, 'rest_greedy': g, 'restub': ub}


def part2():
    hdr("2. VOLLEDIGE TRIPLET-SWEEP OVER HET RECORDVOETAFDRUK")
    out, P = sweep()
    rec = int(D0['total'])
    for y in (0, 7, 14):
        pool, req, m = P[y]
        cw = CUR[{0: 0, 7: 1, 14: 2}[y]]
        k = next(i for i, (v, w) in enumerate(pool) if w == cw)
        print(f"  rij {y:2d}: fragmenteis {req} -> pool {len(pool)}; "
              f"{cw} = {pool[k][0]}, rang {k+1};  #2 = {pool[1][1]} ({pool[1][0]})")
    rows = []
    for tot, am, ub, w0, w7, w14, d in out:
        tri = (w0, w7, w14)
        res, _ = residual(tri)
        g, _ok = rest_estimate(tri, res, True)
        rows.append((am + g + BINGO, am, g, ub, tri, d))
    rows.sort(reverse=True)
    print(f"\n  {'#':>3} {'schat':>6} {'A_m':>6} {'rest~':>6} {'UB':>5} {'bl':>3}  triplet")
    for i, (t, am, g, ub, tri, d) in enumerate(rows[:TOP]):
        print(f"  {i+1:>3} {t:>6} {am:>6} {g:>6} {ub:>5} {d:>3}  {'/'.join(tri)}")
    # wisselkoers
    cur = next(x for x in rows if tuple(x[4]) == CUR)
    ex = [((cur[1] - am), (g - cur[2]), (ub - cur[3]), tri)
          for t, am, g, ub, tri, d in rows if am < cur[1]]
    if ex:
        gem = sum(b for a, b, c, _ in ex) / sum(a for a, b, c, _ in ex)
        bg = max(ex, key=lambda e: e[1] / e[0])
        bu = max(ex, key=lambda e: e[2] / e[0])
        print(f"\n  WISSELKOERS: hoeveel restpunt levert 1 ingeleverd ankerpunt op? "
              f"(break-even = 1.00)")
        print(f"    gemiddeld over {len(ex)} rivalen : {gem:.2f}")
        print(f"    BESTE op de schatting        : {bg[1]}/{bg[0]} = {bg[1]/bg[0]:.2f}  "
              f"({bg[3][1]})")
        print(f"    BESTE op de harde zakgrens   : {bu[2]}/{bu[0]} = {bu[2]/bu[0]:.2f}  "
              f"({bu[3][1]})")
    RESULT['sweep'] = {'n': len(out), 'top': [{'schat': t, 'A_m': am, 'rest': g, 'ub': ub,
                                               'triplet': list(tri), 'blanco': d}
                                              for t, am, g, ub, tri, d in rows[:60]]}
    return rows


def part3(rows):
    hdr("3. RESTZAK-PROFIELEN VAN DE BESTE RIVALEN")
    print(f"  {'triplet':<50} {'A_m':>5} {'rest~':>5} {'e':>2} {'n':>2} {'a':>2} {'o':>2} "
          f"{'d':>2} {'r':>2} {'s':>2} {'t':>2} {'i':>2} {'kl':>3} {'mk':>3} weg")
    for t, am, g, ub, tri, d in rows[:TOP]:
        res, _ = residual(tri)
        p = profile(res)
        print(f"  {'/'.join(tri):<50} {am:>5} {g:>5} " +
              ' '.join(f"{res[ch]:>2}" for ch in BIND) +
              f" {p['klinkers']:>3} {p['medeklinkers']:>3} {p['weg']}")


def part4(rows):
    """Exacte toets in BESLISSINGSVORM: bestaat er voor dit triplet een invulling van het
    recordvoetafdruk met score >= record+1?  INFEASIBLE = bewijs van nee (voor dit voetafdruk).
    Env: TLIM (s/kandidaat), NTEST, SHARD/NSHARD (parallel), JOUT (jsonl)."""
    hdr("4. EXACTE TOETS (beslissingsvorm) + arbiter score_game")
    tlim = int(os.environ.get('TLIM', '150'))
    ntest = int(os.environ.get('NTEST', str(len(rows))))
    shard = int(os.environ.get('SHARD', '0')); nsh = int(os.environ.get('NSHARD', '1'))
    wk = int(os.environ.get('WORKERS', '8'))
    jout = os.environ.get('JOUT')
    rec = int(D0['total'])
    best = None; res_rows = []
    import zlib
    done = set()
    if jout and os.path.exists(jout):        # hervatten: al beslissende uitslagen overslaan
        for line in open(jout):
            try:
                q = json.loads(line)
            except Exception:
                continue
            if q.get('status') != 'UNKNOWN':
                done.add(tuple(q['triplet']))
    cand = [x for x in rows[:ntest] if tuple(x[4]) != CUR and tuple(x[4]) not in done]
    # sharden op een STABIELE hash, niet op de sorteervolgorde (die kan per proces verschillen)
    cand = [x for x in cand if zlib.crc32('/'.join(x[4]).encode()) % nsh == shard]
    print(f"  {len(cand)} kandidaten (shard {shard}/{nsh}), doel > {rec}, "
          f"{tlim}s en {wk} workers per kandidaat", flush=True)
    for i, (t, am, g, ub, tri, d) in enumerate(cand):
        t0 = time.time()
        st, tot, grid, bl, msg, bnd = exact_fill(tri, tlim=tlim, workers=wk, target=rec + 1)
        verdict = {'INFEASIBLE': 'DOOD (bewezen <= record)', 'UNKNOWN': 'onbeslist',
                   'FEASIBLE': 'BOVEN RECORD', 'OPTIMAL': 'BOVEN RECORD'}.get(msg, msg)
        print(f"  {i+1:>3}/{len(cand)} {'/'.join(tri):<50} schat {t:5d} UB {ub+am+BINGO:5d} "
              f"-> {verdict:26s} {tot if tot else '':>5} ({time.time()-t0:.0f}s)", flush=True)
        rec_row = {'triplet': list(tri), 'schat': t, 'A_m': am, 'ub': ub + am + BINGO,
                   'status': msg, 'score': tot, 'sec': round(time.time() - t0, 1)}
        res_rows.append(rec_row)
        if jout:
            with open(jout, 'a') as f:
                f.write(json.dumps(rec_row) + "\n")
        if msg in ('FEASIBLE', 'OPTIMAL') and tot > rec and (best is None or tot > best[0]):
            best = (tot, tri, grid, bl)
            out = f'experiments/results/mg_letterbudget_best.json'
            json.dump({'grid': grid, 'moves': [[list(c) for c in m] for m in MOVES0],
                       'blanks': [list(b) for b in bl], 'total': tot, 'triple': list(tri),
                       'plan': 'letterbudget: tripletwissel op het 4793-voetafdruk'},
                      open(out, 'w'))
            print(f"\n  *** BOVEN HET RECORD: {tot} met {'/'.join(tri)} -> {out}", flush=True)
    RESULT['toets'] = res_rows
    n_dood = sum(1 for x in res_rows if x['status'] == 'INFEASIBLE')
    print(f"\n  samenvatting: {n_dood}/{len(res_rows)} bewezen DOOD, "
          f"{sum(1 for x in res_rows if x['status']=='UNKNOWN')} onbeslist, "
          f"{sum(1 for x in res_rows if x['status'] in ('FEASIBLE','OPTIMAL'))} boven record")


if __name__ == '__main__':
    rows = []
    if '0' in PARTS:
        part0()
    if '1' in PARTS:
        part1()
    if '2' in PARTS:
        rows = part2()
    if '3' in PARTS and rows:
        part3(rows)
    if '4' in PARTS and rows:
        part4(rows)
    o = os.environ.get('OUT', 'experiments/results/letterbudget.json')
    json.dump(RESULT, open(o, 'w'), indent=1, default=str)
    print(f"\ngeschreven: {o}")
