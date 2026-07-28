"""KLASSEGRENS voor triplet + masker, bovenop de decompositie-identiteit.

De identiteit uit experiments/SCHEDULEPROOF.md,

        score = SOM over de maximale eindruns L van g_L(geschiedenis van L),

is niet aan een bezetting gebonden: elke gescoorde run ligt in precies een rij of kolom. Dus

        score = SOM over de 15 rijen van (bijdrage van die rij) + SOM over de 15 kolommen.

Rijen 0/7/14 dragen het triplet (geschenkcheques / flexwerkstertje / polymelkzuurtje) en hebben
dus VASTE letters; hun maximum ligt exact vast, ongeacht bezetting, masker of vrije letters.
Voor alle overige lijnen varieert hier ook de BEZETTING van de lijn zelf.

Modi (env MODE):
  anchor   - exact plafond van de drie ankerrijen (+ de rekenkundige gevolgen voor 4819)
  runs     - per lijn en per interval het beste haalbare g (gecertificeerde ONDERgrens op het
             interval-plafond; woordenlijst gesnoeid op een rangschikkingsheuristiek)
  lines    - per lijn C_line(k): beste haalbare lijnbijdrage met k vrije tegels in die lijn
  knap     - tegelknapzak over de lijnen (indicatie van hoe ver de niet-ankerlijnen kunnen komen)
"""
import os, sys, json, time, itertools
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import numpy as np
import maxgame_score as MG

r = MG.r
CBA = r.alphabet.cba
VAL = {i: r.scores[i] for i in range(1, 27)}
WORDS = set(r.words_str)
WM = np.array(r.word_multiplier).tolist()
LM = np.array(r.letter_multiplier).tolist()
NEG = -1 << 40
TRIPLET = {0: 'geschenkcheques', 7: 'flexwerkstertje', 14: 'polymelkzuurtje'}
ANCHROWS = (0, 7, 14)
BYLEN = {}
for _w in r.words_str: BYLEN.setdefault(len(_w), []).append(_w)


def line_profile(kind, idx):
    """(wm, lm) langs de lijn; kind 'row'/'col'.  Het bord is transponeer-symmetrisch."""
    if kind == 'row': return [WM[idx][x] for x in range(15)], [LM[idx][x] for x in range(15)]
    return [WM[y][idx] for y in range(15)], [LM[y][idx] for y in range(15)]


def line_fixed(kind, idx):
    """vaste letters op de lijn: kolommen snijden de drie ankerrijen, rijen 0/7/14 zijn zelf anker."""
    if kind == 'col': return {r_: TRIPLET[r_][idx] for r_ in ANCHROWS}
    if idx in ANCHROWS: return {x: TRIPLET[idx][x] for x in range(15)}
    return {}


# ---------------------------------------------------------------- exacte run-DP
def g_of_word(wm, lm, W, center_idx=None, single=()):
    """max_h g voor EEN run: woord W, multipliers wm/lm (al gesneden op de run).

    single: posities die alleen als LOSSE tegel gelegd mogen worden (nooit in een meer-tegelzet
    van deze lijn).  Dat is precies de koppeling 'een cel kan in hoogstens een van zijn twee
    lijnen in een meer-tegelzet zitten': geeft de rij het kruispunt, dan moet de kolom hem als
    singleton nemen, en omgekeerd.

    Identiek aan de per-lijn-DP van mg_scheduleproof: toestand = deelverzameling gelegde cellen,
    zet = interval [a..e] minus S met a,e nieuw, gebeurtenis = het ontstane blok (moet een woord
    zijn zodra het >= 2 lang is), bingo = groep van precies 7.
    """
    n = len(W)
    ok = [[False] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(i + 2, n + 1): ok[i][j] = W[i:j] in WORDS
    val = [VAL[CBA[ch]] for ch in W]
    best = [NEG] * (1 << n); best[0] = 0
    for S in range(1 << n):
        b = best[S]
        if b == NEG: continue
        for a in range(n):
            if S >> a & 1: continue
            cnt = 0
            for e in range(a, n):
                if S >> e & 1: continue
                cnt += 1
                if cnt > 7: break
                span = ((1 << (e + 1)) - 1) ^ ((1 << a) - 1)
                g = span & ~S; T = S | g
                if center_idx is not None and (g >> center_idx & 1) and S != 0: continue
                if cnt >= 2 and any((g >> k & 1) for k in single): continue
                lo = a
                while lo - 1 >= 0 and (T >> (lo - 1) & 1): lo -= 1
                hi = e
                while hi + 1 < n and (T >> (hi + 1) & 1): hi += 1
                if hi - lo + 1 < 2:
                    inc = 0
                else:
                    if not ok[lo][hi + 1]: continue
                    w = 1
                    for k in range(a, e + 1):
                        if g >> k & 1: w *= wm[k]
                    inc = 0
                    for k in range(lo, hi + 1):
                        inc += w * (val[k] * lm[k] if (g >> k & 1) else val[k])
                    if cnt == 7: inc += 50
                if b + inc > best[T]: best[T] = b + inc
    return best[(1 << n) - 1]


def topn_for(L):
    if L <= 9: return int(os.environ.get('TOPN', '300'))
    if L <= 11: return 120
    if L <= 13: return 50
    return 24


def rank_weight(wm, lm):
    """rangschikkingsheuristiek: gewicht van positie i ~ lm_i * product(wm).  Alleen om de
    kansrijke woorden vooraan te zetten; raakt de correctheid van de uitkomst niet, want elk
    geevalueerd woord wordt exact doorgerekend."""
    p = 1
    for w in wm: p *= w
    return [p * lm[i] + 3 * (len(wm) - 1) for i in range(len(wm))]


SINGLE = tuple(int(v) for v in os.environ.get('SINGLE', '').split(',') if v != '')


def best_interval(kind, idx, a, b, cache=None):
    """beste haalbare g voor de run [a..b] op deze lijn (ONDERgrens op het interval-plafond)."""
    wm, lm = line_profile(kind, idx)
    fx = line_fixed(kind, idx)
    L = b - a + 1
    wmc, lmc = wm[a:b + 1], lm[a:b + 1]
    pat = [(k - a, ch) for k, ch in fx.items() if a <= k <= b]
    sing = tuple(k - a for k in SINGLE if a <= k <= b)
    key = (tuple(wmc), tuple(lmc), tuple(sorted(pat)), sing,
           (7 - a) if (kind == 'col' and idx == 7 and a <= 7 <= b) else None)
    if cache is not None and key in cache: return cache[key]
    cand = [w for w in BYLEN.get(L, ()) if all(w[i] == ch for i, ch in pat)]
    rw = rank_weight(wmc, lmc)
    cand.sort(key=lambda W: -sum(rw[i] * VAL[CBA[c]] for i, c in enumerate(W)))
    ci = key[4]
    best = 0
    for W in cand[:topn_for(L)]:
        v = g_of_word(wmc, lmc, W, ci, sing)
        if v > best: best = v
    if cache is not None: cache[key] = best
    return best


# ---------------------------------------------------------------- per lijn: C_line(k)
def line_ceiling(kind, idx, cache):
    """C[k] = beste haalbare bijdrage van deze lijn met k VRIJE cellen bezet.

    Kolommen: rijen 0/7/14 zijn altijd bezet (ankerrijen) en tellen niet als vrije tegel.
    Niet-ankerrijen: alle 15 cellen zijn vrij.
    """
    forced = set(ANCHROWS) if kind == 'col' else set()
    freepos = [i for i in range(15) if i not in forced]
    nf = len(freepos)
    BI = {}
    C = [NEG] * (nf + 1); C[0] = NEG
    out = [0] * (nf + 1)
    for m in range(1 << nf):
        occ = set(forced)
        for j in range(nf):
            if m >> j & 1: occ.add(freepos[j])
        k = bin(m).count('1')
        tot = 0; i = 0
        while i < 15:
            if i in occ:
                j = i
                while j + 1 < 15 and j + 1 in occ: j += 1
                if j > i:
                    if (i, j) not in BI: BI[(i, j)] = best_interval(kind, idx, i, j, cache)
                    tot += BI[(i, j)]
                i = j + 1
            else: i += 1
        if tot > out[k]: out[k] = tot
    for k in range(1, nf + 1): out[k] = max(out[k], out[k - 1])
    return out


if __name__ == '__main__':
    MODE = os.environ.get('MODE', 'anchor')
    t0 = time.time()

    if MODE == 'anchor':
        import mg_scheduleproof as SP
        caps = {}
        for r_ in ANCHROWS:
            wm, lm = line_profile('row', r_)
            ci = 7 if r_ == 7 else None
            caps[r_] = g_of_word(wm, lm, TRIPLET[r_], ci, SINGLE)
        tot = sum(caps.values())
        for r_ in ANCHROWS: print(f"  rij {r_:2d} '{TRIPLET[r_]}': plafond {caps[r_]}")
        print(f"ANKERRIJ-PLAFOND (exact, over ALLE bezettingen/maskers/geschiedenissen) = {tot}")
        print(f"  record haalt 3840 -> nog {tot-3840} beschikbaar op de ankerrijen")
        for T in (4778, 4819):
            print(f"  voor {T}: niet-ankerlijnen moeten >= {T-tot} leveren "
                  f"(record: 938)")
        sys.exit(0)

    if MODE == 'lines':
        cache = {}
        which = os.environ.get('WHICH', 'all')
        res = {}
        jobs = []
        if which in ('all', 'col'):
            jobs += [('col', c) for c in range(15)]
        if which in ('all', 'row'):
            jobs += [('row', r_) for r_ in range(15) if r_ not in ANCHROWS]
        sh = int(os.environ.get('SHARD', '0')); ns = int(os.environ.get('NSHARD', '1'))
        for j, (kind, idx) in enumerate(jobs):
            if j % ns != sh: continue
            C = line_ceiling(kind, idx, cache)
            res[f"{kind}{idx}"] = C
            print(f"  {kind} {idx}: plafond per aantal vrije tegels {C}  ({time.time()-t0:.0f}s)",
                  flush=True)
        json.dump(res, open(os.environ.get('OUT', '/tmp/lines.json'), 'w'))
        sys.exit(0)

    if MODE == 'knap':
        res = {}
        for f in os.environ['IN'].split(','): res.update(json.load(open(f)))
        cols = {k: v for k, v in res.items() if k.startswith('col')}
        rows = {k: v for k, v in res.items() if k.startswith('row')}
        B = int(os.environ.get('BUDGET', '56'))

        def knap(d):
            dp = [0] * (B + 1)
            for name, C in d.items():
                nd = dp[:]
                for used in range(B + 1):
                    for k in range(1, min(len(C) - 1, B - used) + 1):
                        if dp[used] + C[k] > nd[used + k]: nd[used + k] = dp[used] + C[k]
                dp = nd
                for i in range(1, B + 1): dp[i] = max(dp[i], dp[i - 1])
            return dp[B]
        kc, kr = knap(cols), knap(rows)
        print(f"kolom-knapzak({B} vrije tegels) = {kc}")
        print(f"rij-knapzak({B} vrije tegels)   = {kr}")
        print(f"indicatie max R (niet-ankerlijnen) = {kc + kr}   (record R = 938)")
        sys.exit(0)

    if MODE == 'runs':
        cache = {}
        kind = os.environ.get('KIND', 'col'); idx = int(os.environ.get('IDX', '2'))
        for a in range(15):
            for b in range(a + 1, 15):
                v = best_interval(kind, idx, a, b, cache)
                if v: print(f"  {kind}{idx} [{a}..{b}] len {b-a+1}: {v}")
        sys.exit(0)
