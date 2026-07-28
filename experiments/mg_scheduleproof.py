"""ZETVOLGORDE-BEWIJS bij VASTE BEZETTING.

Kern: de score van een spel valt EXACT uiteen over de maximale runs ("lijnen") van het
eindbord:

        score = SOM over lijnen L van  g_L(geschiedenis van L)

met g_L = (alle woordscores op L) + 50 * (aantal zetten van precies 7 tegels waarvan L de
hoofdlijn is).  Bewijs/argument staat in experiments/SCHEDULEPROOF.md; hier wordt de identiteit
bij het opstarten numeriek geverifieerd tegen MG.score_game.

Daarmee kan per lijn een EXACTE DP over deelverzamelingen (2^n toestanden, n = lijnlengte <= 15)
de maximale bijdrage max_h g_L(h) uitrekenen, en ook de staart-bovengrens suffix_L(S) = maximale
toekomstige bijdrage van lijn L vanaf lijntoestand S.  Die staartgrens is TOELAATBAAR voor de
globale zoektocht: elk werkelijk spel projecteert op legale lijn-geschiedenissen, dus

        toekomstige score <= SOM_L suffix_L(S_L).

Met die grens draait een exacte branch-and-bound over ALLE legale zetvolgordes bij de gegeven
bezetting.  Alle spelregels worden hard afgedwongen: centrum in zet 1, aanraakregel, <= 7 tegels
per zet, elke gevormde run >= 2 moet een woord zijn, en de zet ligt op een lijn met gevulde span.

CLI:
    MBASE=<spel.json> [LB=4778] [MODE=lines|bnb] .venv/bin/python experiments/mg_scheduleproof.py
"""
import os, sys, json, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import numpy as np
import maxgame_score as MG

r = MG.r
ABC = {v: k for k, v in r.alphabet.cba.items()}
LM = np.array(r.letter_multiplier).tolist()
WM = np.array(r.word_multiplier).tolist()
VAL = {i: r.scores[i] for i in range(1, 27)}
WORDS = set(r.words_str)
NEG = -1 << 40
NB = ((1, 0), (-1, 0), (0, 1), (0, -1))
CENTER = (7, 7)


# ---------------------------------------------------------------- bord & lijnen
class Board:
    def __init__(self, path):
        D = json.load(open(path))
        self.D = D
        self.grid = D['grid']
        self.blanks = set(tuple(b) for b in D['blanks'])
        self.moves = [[tuple(c) for c in m] for m in D['moves']]
        self.occ = set((x, y) for y in range(15) for x in range(15) if self.grid[y][x])
        self.lines = self._lines()
        self.cellline = {}
        for li, (tag, run) in enumerate(self.lines):
            for i, c in enumerate(run):
                self.cellline.setdefault(c, []).append((li, i))
        assert set(self.cellline) == self.occ

    def _lines(self):
        out = []
        for tag, (dx, dy) in (('H', (1, 0)), ('V', (0, 1))):
            for (x, y) in sorted(self.occ, key=lambda t: (t[1], t[0])):
                if (x - dx, y - dy) in self.occ: continue
                run = []; x0, y0 = x, y
                while (x0, y0) in self.occ:
                    run.append((x0, y0)); x0 += dx; y0 += dy
                if len(run) >= 2: out.append((tag, tuple(run)))
        return out

    def val(self, c):
        return 0 if c in self.blanks else VAL[self.grid[c[1]][c[0]]]


class Line:
    """een maximale run van het eindbord, met woordtabel, DP-maxima en staartgrens."""
    def __init__(self, bd, li):
        tag, run = bd.lines[li]
        self.tag, self.run, self.li = tag, run, li
        self.n = n = len(run)
        self.full = (1 << n) - 1
        self.s = ''.join(ABC[bd.grid[y][x]] for (x, y) in run)
        self.ok = [[False] * (n + 1) for _ in range(n + 1)]
        for i in range(n):
            for j in range(i + 2, n + 1):
                self.ok[i][j] = self.s[i:j] in WORDS
        self.val = [bd.val(c) for c in run]
        self.wm = [WM[c[1]][c[0]] for c in run]
        self.lm = [LM[c[1]][c[0]] for c in run]
        self.groups = self._groups()          # S -> [(g, inc, ok)]
        self.suffix = self._suffix()

    # alle (toestand, groep) overgangen: groep = interval [a..e] minus S, randen nieuw
    def _trans(self, S):
        n = self.n; out = []
        for a in range(n):
            if S >> a & 1: continue
            cnt = 0
            for e in range(a, n):
                if S >> e & 1: continue
                cnt += 1
                if cnt > 7: break
                span = ((1 << (e + 1)) - 1) ^ ((1 << a) - 1)
                g = span & ~S
                T = S | g
                lo = a
                while lo - 1 >= 0 and (T >> (lo - 1) & 1): lo -= 1
                hi = e
                while hi + 1 < n and (T >> (hi + 1) & 1): hi += 1
                if hi - lo + 1 < 2:
                    inc = 0
                else:
                    if not self.ok[lo][hi + 1]: continue
                    w = 1
                    for k in range(a, e + 1):
                        if g >> k & 1: w *= self.wm[k]
                    inc = 0
                    for k in range(lo, hi + 1):
                        inc += w * (self.val[k] * self.lm[k] if (g >> k & 1) else self.val[k])
                    if cnt == 7: inc += 50
                out.append((g, inc, cnt))
        return out

    def _groups(self):
        return [self._trans(S) for S in range(1 << self.n)]

    def _suffix(self):
        """suffix[S] = max toekomstige bijdrage van deze lijn vanaf toestand S tot vol."""
        suf = [NEG] * (1 << self.n)
        suf[self.full] = 0
        for S in range(self.full - 1, -1, -1):
            b = NEG
            for g, inc, cnt in self.groups[S]:
                v = suf[S | g]
                if v > NEG and inc + v > b: b = inc + v
            suf[S] = b
        return suf

    def maxg(self, center_first_idx=None):
        """max_h g_L(h); met center_first_idx: de groep met dat veld moet de EERSTE groep zijn."""
        if center_first_idx is None: return self.suffix[0]
        best = NEG
        for g, inc, cnt in self.groups[0]:
            if not (g >> center_first_idx & 1): continue
            if self.suffix[g] > NEG: best = max(best, inc + self.suffix[g])
        return best


# ---------------------------------------------------------------- verificatie identiteit
def replay(bd, LN, moves):
    """speel een zetlijst na via de lijn-decompositie; geeft (score, eindtoestanden)."""
    masks = [0] * len(LN)
    total = 0
    placed = set()
    for mv in moves:
        cs = [tuple(c) for c in mv]
        assert not (set(cs) & placed), "cel dubbel gelegd"
        # hoofdlijn = de lijn die alle cellen bevat (bij 1 tegel: beide lijnen als singleton)
        gl = {}
        for c in cs:
            for (li, i) in bd.cellline[c]: gl.setdefault(li, []).append(i)
        main = [li for li, idx in gl.items() if len(idx) == len(cs) and len(cs) > 1]
        for li, idx in gl.items():
            L = LN[li]; S = masks[li]
            g = 0
            for i in idx: g |= 1 << i
            a, e = min(idx), max(idx)
            T = S | g
            lo = a
            while lo - 1 >= 0 and (T >> (lo - 1) & 1): lo -= 1
            hi = e
            while hi + 1 < L.n and (T >> (hi + 1) & 1): hi += 1
            if hi - lo + 1 >= 2:
                w = 1
                for k in idx: w *= L.wm[k]
                inc = 0
                for k in range(lo, hi + 1):
                    inc += w * (L.val[k] * L.lm[k] if (g >> k & 1) else L.val[k])
                if len(cs) == 7 and len(idx) == 7: inc += 50
                total += inc
            masks[li] = T
        placed |= set(cs)
    return total, masks


# ---------------------------------------------------------------- globale B&B
class Search:
    def __init__(self, bd, LN, lb):
        self.bd, self.LN, self.lb = bd, LN, lb
        self.nl = len(LN)
        self.cellline = bd.cellline
        self.cells = sorted(bd.occ, key=lambda t: (t[1], t[0]))
        self.nbrs = {c: [(c[0] + dx, c[1] + dy) for dx, dy in NB
                         if (c[0] + dx, c[1] + dy) in bd.occ] for c in bd.occ}
        self.shared = [(c, v[1]) for c, v in bd.cellline.items() if len(v) == 2]

    def placed(self, masks, c):
        li, i = self.cellline[c][0]
        return (masks[li] >> i) & 1

    def cross_inc(self, masks, c, skip_li):
        """singleton-gebeurtenis van cel c in zijn KRUIS-lijn(en) (alle lijnen != skip_li)."""
        tot = 0; upd = []
        for (li, i) in self.cellline[c]:
            if li == skip_li: continue
            L = self.LN[li]; S = masks[li]
            T = S | (1 << i)
            lo = i
            while lo - 1 >= 0 and (T >> (lo - 1) & 1): lo -= 1
            hi = i
            while hi + 1 < L.n and (T >> (hi + 1) & 1): hi += 1
            if hi - lo + 1 >= 2:
                if not L.ok[lo][hi + 1]: return None, None
                w = L.wm[i]
                inc = 0
                for k in range(lo, hi + 1):
                    inc += w * (L.val[k] * L.lm[k] if k == i else L.val[k])
                tot += inc
            upd.append((li, T))
        return tot, upd

    def succ(self, masks, first):
        """alle legale zetten vanaf deze toestand -> [(nieuwe masks, delta, cellen)]"""
        out = []
        # (a) meer-tegelzetten: groep binnen een lijn
        for li, L in enumerate(self.LN):
            S = masks[li]
            for g, inc, cnt in L.groups[S]:
                if cnt < 2: continue
                cs = [L.run[k] for k in range(L.n) if g >> k & 1]
                if first:
                    if CENTER not in cs: continue
                    # openingszet: bord leeg -> span moet exact de groep zijn
                    if len(cs) != (max(k for k in range(L.n) if g >> k & 1)
                                   - min(k for k in range(L.n) if g >> k & 1) + 1): continue
                else:
                    if not any(self.placed(masks, d) for c in cs for d in self.nbrs[c]): continue
                nm = list(masks); nm[li] = S | g
                delta = inc; bad = False
                for c in cs:
                    t, upd = self.cross_inc(nm, c, li)
                    if t is None: bad = True; break
                    delta += t
                    for (li2, T2) in upd: nm[li2] = T2
                if bad: continue
                out.append((tuple(nm), delta, cs))
        # (b) een-tegelzetten
        for c in self.cells:
            if self.placed(masks, c): continue
            if first:
                if c != CENTER: continue
            elif not any(self.placed(masks, d) for d in self.nbrs[c]): continue
            nm = list(masks)
            t, upd = self.cross_inc(nm, c, -1)
            if t is None: continue
            for (li2, T2) in upd: nm[li2] = T2
            out.append((tuple(nm), t, [c]))
        return out

    def bound(self, masks):
        b = 0
        for li in range(self.nl):
            s = self.LN[li].suffix[masks[li]]
            if s <= NEG: return NEG
            b += s
        return b

    def ncells(self, masks):
        n = 0
        for li in range(self.nl): n += bin(masks[li]).count('1')
        for (c, (li, i)) in self.shared: n -= (masks[li] >> i) & 1
        return n

    def run(self, tmax=None, keep_path=True):
        """exacte DP/B&B over ALLE legale zetvolgordes.

        Lagen zijn genummerd naar het aantal GELEGDE CELLEN (monotoon stijgend), zodat elke
        bordtoestand in precies een laag valt en de DP-waarde best[toestand] = maximale tot dan
        toe behaalde score welgedefinieerd is.  Snoeien is gezond:
            acc + SOM_L suffix_L(S_L) <= huidige beste   ==>   weggooien,
        want SOM_L suffix_L is een toelaatbare bovengrens op alle toekomstige score.
        """
        t0 = time.time()
        N = len(self.bd.occ)
        layers = [dict() for _ in range(N + 1)]
        layers[0][tuple([0] * self.nl)] = 0
        par = {tuple([0] * self.nl): None}
        bestscore = self.lb; bestpath = None
        seen = 0
        for k in range(N):
            cur = layers[k]
            if not cur: continue
            for masks, acc in cur.items():
                seen += 1
                for nm, d, cs in self.succ(masks, k == 0):
                    a2 = acc + d
                    if all(nm[i] == self.LN[i].full for i in range(self.nl)):
                        if a2 > bestscore:
                            bestscore = a2
                            bestpath = self._path(par, masks, cs) if keep_path else None
                        continue
                    ub = self.bound(nm)
                    if ub <= NEG or a2 + ub <= bestscore: continue
                    tgt = layers[k + len(cs)]
                    if tgt.get(nm, NEG) < a2:
                        tgt[nm] = a2
                        if keep_path: par[nm] = (masks, cs)
            layers[k] = None
            if cur:
                print(f"  {k} cellen: {len(cur)} toestanden  (beste {bestscore})  "
                      f"{time.time()-t0:.1f}s", flush=True)
            if tmax and time.time() - t0 > tmax:
                print("  TIJDLIMIET"); return bestpath, bestscore, False
        print(f"  bezochte toestanden: {seen}  ({time.time()-t0:.1f}s)")
        return bestpath, bestscore, True

    def _path(self, par, masks, last):
        out = [last]
        while par.get(masks):
            pm, cs = par[masks]; out.append(cs); masks = pm
        out.reverse(); return out


def build(path):
    bd = Board(path)
    LN = [Line(bd, i) for i in range(len(bd.lines))]
    return bd, LN


# ---------------------------------------------------------------- VRIJE LETTERS
# De 45 ankercellen (rijen 0/7/14) liggen vast; de 56 overige cellen mogen elke letter
# krijgen. Per lijn L wordt dan gemaximaliseerd over ALLE woorden W van lengte n die op de
# ankerletters passen (de hele lijn is aan het eind altijd een gescoorde run, dus W moet zelf
# een woord zijn).  U_L^vrij = max_W max_h g_L(h, W).  Dat is een geldige per-lijn-bovengrens
# ongeacht wat de andere lijnen doen.
BYLEN = {}
for _w in r.words_str: BYLEN.setdefault(len(_w), []).append(_w)
CBA = r.alphabet.cba


def candidates(bd, L):
    anch = {(x, y): bd.grid[y][x] for y in (0, 7, 14) for x in range(15) if bd.grid[y][x]}
    fx = [(i, ABC[anch[c]]) for i, c in enumerate(L.run) if c in anch]
    return [w for w in BYLEN.get(L.n, ()) if all(w[i] == ch for i, ch in fx)], fx


def maxg_word(L, W, center_idx=None):
    """exacte max_h g_L(h) als lijn L de letters van W draagt."""
    n = L.n
    ok = [[False] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(i + 2, n + 1): ok[i][j] = W[i:j] in WORDS
    val = [VAL[CBA[ch]] for ch in W]
    wm, lm = L.wm, L.lm
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
    return best[L.full]


def free_line(bd, LN, li, shard=0, nshard=1):
    L = LN[li]
    cands, fx = candidates(bd, L)
    ci = L.run.index(CENTER) if CENTER in L.run else None
    out = []
    for k in range(shard, len(cands), nshard):
        W = cands[k]
        out.append((W, maxg_word(L, W, ci)))
    return out


# ------------------------------------------------------- VRIJE-LETTER-BOVENGRENS (CP-SAT)
def freebound(bd, LN, valdir):
    """Zak- en kruispuntbewuste bovengrens voor de VRIJE-LETTER-klasse.

    Ankerrijen 0/7/14 hebben vaste letters -> hun maximum ligt vast (som ANCHCAP).
    Voor elke vrije lijn L kiest CP-SAT een woord W (tabelbeperking op de letters van die lijn)
    met bijbehorende exacte lijn-bovengrens U_L(W); gedeelde cellen dwingen consistentie af en
    de zak begrenst het totale lettergebruik.  Blanco's: hoogstens 2 cellen mogen de zak
    overschrijden en tellen tóch hun volle waarde -> overschatting, dus gezond.
    """
    from ortools.sat.python import cp_model
    anch = {(x, y): bd.grid[y][x] for y in (0, 7, 14) for x in range(15) if bd.grid[y][x]}
    fixedlines = [li for li, L in enumerate(LN) if all(c in anch for c in L.run)]
    freelines = [li for li in range(len(LN)) if li not in fixedlines]
    cap = 0
    for li in fixedlines:
        L = LN[li]
        cap += L.maxg(L.run.index(CENTER) if CENTER in L.run else None)
    m = cp_model.CpModel()
    cellv = {}
    for c in bd.occ:
        cellv[c] = m.NewConstant(anch[c]) if c in anch else m.NewIntVar(1, 26, f"c{c}")
    obj = []
    for li in freelines:
        L = LN[li]
        rows = json.load(open(os.path.join(valdir, f"L{li}.json")))
        vmax = max(v for _, v in rows)
        u = m.NewIntVar(0, vmax, f"u{li}")
        tup = [[CBA[ch] for ch in W] + [v] for W, v in rows]
        m.AddAllowedAssignments([cellv[c] for c in L.run] + [u], tup)
        obj.append(u)
    over = []
    for ch in range(1, 27):
        ind = []
        for c in bd.occ:
            b = m.NewBoolVar("")
            m.Add(cellv[c] == ch).OnlyEnforceIf(b)
            m.Add(cellv[c] != ch).OnlyEnforceIf(b.Not())
            ind.append(b)
        ov = m.NewIntVar(0, 2, f"ov{ch}")
        m.Add(sum(ind) <= r.counts[ch] + ov)
        over.append(ov)
    m.Add(sum(over) <= 2)
    m.Maximize(sum(obj))
    sol = cp_model.CpSolver()
    sol.parameters.log_search_progress = True
    sol.parameters.max_time_in_seconds = float(os.environ.get('CPSEC', '900'))
    sol.parameters.num_search_workers = int(os.environ.get('CPW', '16'))
    st = sol.Solve(m)
    print(f"ankerrijen-plafond {cap}; CP-SAT status {sol.StatusName(st)} "
          f"vrije lijnen <= {sol.BestObjectiveBound():.0f} (beste gevonden {sol.ObjectiveValue():.0f})")
    print(f"VRIJE-LETTER-BOVENGRENS = {cap + sol.BestObjectiveBound():.0f}")
    return cap, sol.BestObjectiveBound()


if __name__ == '__main__':
    path = os.environ.get('MBASE', 'experiments/results/maxgame_BEST.json')
    t0 = time.time()
    bd, LN = build(path)
    print(f"lijnen: {len(LN)}  cellen: {len(bd.occ)}  ({time.time()-t0:.1f}s)")
    tot, per, ok, msg = MG.score_game([row[:] for row in bd.grid], bd.moves, bd.blanks)
    dec, masks = replay(bd, LN, bd.moves)
    print(f"arbiter MG.score_game = {int(tot)} (ok={ok}) | lijn-decompositie = {dec} | "
          f"identiek: {int(tot)==dec}")
    assert all(masks[i] == LN[i].full for i in range(len(LN)))
    ci = None
    som_vrij = som_cen = 0
    for li, L in enumerate(LN):
        cidx = L.run.index(CENTER) if CENTER in L.run else None
        a = L.maxg(); b = L.maxg(cidx) if cidx is not None else a
        som_vrij += a; som_cen += b
        print(f"  {L.tag}{L.n} {L.run[0]} '{L.s}': max {a}"
              + (f" -> met centrumregel {b}" if cidx is not None else ""))
    print(f"PER-LIJN-BOVENGRENS: vrij {som_vrij}, met centrumregel {som_cen}")
    MODE = os.environ.get('MODE', 'bnb')
    if MODE == 'count':
        tot = 1
        for L in LN:
            cnt = [0] * (1 << L.n); cnt[0] = 1
            for S in range(1 << L.n):
                if not cnt[S]: continue
                for g, inc, c in L.groups[S]: cnt[S | g] += cnt[S]
            print(f"  {L.tag}{L.n} {L.run[0]} '{L.s}': {cnt[L.full]:,} legale lijn-geschiedenissen")
            tot *= cnt[L.full]
        print(f"product over de {len(LN)} lijnen = {tot:.3e}  (aantal echte schema's is nog groter: "
              f"de lijn-geschiedenissen kunnen ook nog onderling verweven worden)")
        sys.exit(0)
    if MODE == 'freebound':
        freebound(bd, LN, os.environ['VALDIR']); sys.exit(0)
    if MODE == 'audit':
        import random
        rnd = random.Random(int(os.environ.get('SEED', '12345')))
        S = Search(bd, LN, NEG)
        n = int(os.environ.get('N', '400')); good = bad = 0
        for _ in range(n):
            masks = tuple([0] * len(LN)); acc = 0; mvs = []; first = True
            while not all(masks[i] == LN[i].full for i in range(len(LN))):
                sc = S.succ(masks, first)
                if not sc: break
                nm, d, cs = rnd.choice(sc)
                masks = nm; acc += d; mvs.append([tuple(c) for c in cs]); first = False
            else:
                t, _p, o, _m = MG.score_game([row[:] for row in bd.grid], mvs, bd.blanks)
                if o and int(t) == acc: good += 1
                else: bad += 1; print("MISMATCH", o, _m, int(t), acc)
        print(f"AUDIT: {good+bad} willekeurige volledige schema's, arbiter-identiek {good}, fout {bad}")
        sys.exit(0)
    if MODE == 'free':
        li = int(os.environ['LI']); sh = int(os.environ.get('SHARD','0')); ns = int(os.environ.get('NSHARD','1'))
        res = free_line(bd, LN, li, sh, ns)
        json.dump(res, open(os.environ['OUT'], 'w'))
        print(f'lijn {li} shard {sh}/{ns}: {len(res)} woorden, max {max(v for _, v in res) if res else None}')
        sys.exit(0)
    if MODE == 'bnb':
        lb = int(os.environ.get('LB', str(dec)))
        S = Search(bd, LN, lb)
        best, bs, done = S.run(tmax=float(os.environ.get('TMAX', '1e9')))
        print(f"B&B klaar={done} beste score {bs} (ondergrens was {lb})")
        if best is not None:
            mvs = [[tuple(c) for c in m] for m in best]
            t, _p, o, msg = MG.score_game([row[:] for row in bd.grid], mvs, bd.blanks)
            print(f"  getuige: {len(mvs)} zetten, arbiter {int(t)} ok={o} {msg}")
            out = os.environ.get('WOUT')
            if out and int(t) > dec:
                json.dump({'grid': bd.grid, 'blanks': [list(b) for b in bd.blanks],
                           'moves': [[list(c) for c in m] for m in mvs], 'total': int(t),
                           'note': 'nieuw schema bij bezetting van maxgame_BEST'}, open(out, 'w'))
                print(f"  *** BETER DAN {dec}: weggeschreven naar {out}")
        if done and bs == dec:
            print(f"BEWEZEN: bij deze bezetting EN deze letters haalt GEEN ENKELE legale "
                  f"zetvolgorde meer dan {dec}.")
