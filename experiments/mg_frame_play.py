"""FRAME-BORD -> ECHT SPEL: zoek een legale zetvolgorde bij een vaste FRAME-bezetting en laat
de arbiter (MG.score_game) hem afkeuren of goedkeuren.

De bezetting en de lettering komen uit de weerleggingsmotor (experiments/REFUTE.md, sectie 7.4):
kolom 14 is in de recordmaskers in rij 0, 7 EN 14 een maskercel, dus een VOLLE TWS-kolom, en
draagt een 15-letterwoord (spreeuwennestje / steviabedrijfje).  Wat daar ontbrak was een
zetvolgorde; die wordt hier exact gezocht.

Gereedschap: de branch-and-bound van experiments/mg_scheduleproof.py.  Die is exact over ALLE
legale zetvolgordes bij vaste bezetting EN vaste letters, met de toelaatbare per-lijn-staartgrens
als snoeier, en dwingt alle spelregels hard af (centrum in zet 1, aanraakregel, <=7 tegels per
zet, span gevuld, elke gevormde run een woord).

De bezorgvolgorde die de motor moet vinden ligt geometrisch vast (MASKGEOM: kolom 14 is voor de
slotzetten onbereikbaar, want zijn enige buren zijn kolom 13 -- leeg -- en de maskercellen):

    zet 1 = de centrale verticaal door (7,7)
    -> overige verticalen + de pre-groepen van de ankerrijen
    -> slotzet rij 0    (daarna kan kolom-14-BOVEN aan (14,0) hangen)
    -> slotzet rij 7    (daarna kan kolom-14-ONDER aan (14,7) hangen)
    -> slotzet rij 14   (die het volledige 15-letterwoord in kolom 14 meescoort)

CLI:
    GRID=F1_55 BLANKS="14,5;13,7" LB=4400 TMAX=1800 .venv/bin/python experiments/mg_frame_play.py
"""
import os, sys, json, time, itertools

sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG
import mg_scheduleproof as SP

r = MG.r
CBA = r.alphabet.cba
ABC = {v: k for k, v in CBA.items()}
RES = '/home/bob/programming/scrabble4/experiments/results'
GRIDFILE = os.environ.get('GRIDFILE', f'{RES}/refute/frame_grids.txt')


def load_grids(path):
    out = {}
    for blk in open(path).read().split('--- ')[1:]:
        lines = blk.strip().split('\n')
        name = lines[0].split()[0]
        out[name] = lines[1:16]
    return out


def to_codes(g):
    return [[CBA[g[y][x]] if g[y][x] != '.' else 0 for x in range(15)] for y in range(15)]


def blank_candidates(grid):
    """Welke cellen MOETEN blanco zijn: per letter het overschot boven de zak."""
    from collections import Counter
    cnt = Counter(grid[y][x] for y in range(15) for x in range(15) if grid[y][x])
    need = {c: n - r.counts[c] for c, n in cnt.items() if n > r.counts[c]}
    return need


class FrameBoard(SP.Board):
    """zelfde als SP.Board maar zonder zetlijst (die zoeken we juist)"""
    def __init__(self, grid, blanks):
        self.D = {}
        self.grid = grid
        self.blanks = set(blanks)
        self.moves = []
        self.occ = set((x, y) for y in range(15) for x in range(15) if grid[y][x])
        self.lines = self._lines()
        self.cellline = {}
        for li, (tag, run) in enumerate(self.lines):
            for i, c in enumerate(run):
                self.cellline.setdefault(c, []).append((li, i))
        missing = self.occ - set(self.cellline)
        assert not missing, f'cellen zonder lijn (zwevend): {sorted(missing)}'


class FrameLine(SP.Line):
    """SP.Line met de AANRAAKREGEL erin.

    Een groep (= een zet) binnen deze lijn moet het bord raken.  Dat kan (a) binnen de lijn --
    de span bevat al gelegde cellen of het gevormde blok loopt door in gelegde cellen -- of
    (b) via een LOODRECHTE buur die in het EINDbord bezet is (of hij op dat moment al ligt weten
    we niet; dit is dus een noodzakelijke voorwaarde, en de staartgrens blijft daarmee
    toelaatbaar), of (c) het is de openingszet, en die bevat per definitie het centrum.

    Zonder deze regel is de staartgrens hopeloos los: kolom 14 (de volle TWS-kolom) haalt dan
    867 in plaats van 477, en de branch-and-bound sluit nooit.
    """
    def _groups(self):
        occ = self._occ
        n = self.n
        self.supbits = 0
        for i, (x, y) in enumerate(self.run):
            if self.tag == 'V':
                nb = [(x - 1, y), (x + 1, y)]
            else:
                nb = [(x, y - 1), (x, y + 1)]
            if any(c in occ for c in nb):
                self.supbits |= 1 << i
        self.cidx = self.run.index(SP.CENTER) if SP.CENTER in self.run else None
        return super()._groups()

    def _trans(self, S):
        n = self.n
        out = []
        for a in range(n):
            if S >> a & 1:
                continue
            cnt = 0
            for e in range(a, n):
                if S >> e & 1:
                    continue
                cnt += 1
                if cnt > 7:
                    break
                span = ((1 << (e + 1)) - 1) ^ ((1 << a) - 1)
                g = span & ~S
                T = S | g
                if not (g & self.supbits):
                    inline = (span & S) != 0 or (a > 0 and (S >> (a - 1) & 1)) or \
                             (e + 1 < n and (S >> (e + 1) & 1))
                    opening = (S == 0 and self.cidx is not None and (g >> self.cidx & 1))
                    if not inline and not opening:
                        continue
                lo = a
                while lo - 1 >= 0 and (T >> (lo - 1) & 1):
                    lo -= 1
                hi = e
                while hi + 1 < n and (T >> (hi + 1) & 1):
                    hi += 1
                if hi - lo + 1 < 2:
                    inc = 0
                else:
                    if not self.ok[lo][hi + 1]:
                        continue
                    w = 1
                    for k in range(a, e + 1):
                        if g >> k & 1:
                            w *= self.wm[k]
                    inc = 0
                    for k in range(lo, hi + 1):
                        inc += w * (self.val[k] * self.lm[k] if (g >> k & 1) else self.val[k])
                    if cnt == 7:
                        inc += 50
                out.append((g, inc, cnt))
        return out


def build(grid, blanks):
    bd = FrameBoard(grid, blanks)
    LN = []
    for i in range(len(bd.lines)):
        L = FrameLine.__new__(FrameLine)
        L._occ = bd.occ
        SP.Line.__init__(L, bd, i)
        LN.append(L)
    return bd, LN


def per_line_report(bd, LN):
    som = 0
    for L in LN:
        cidx = L.run.index(SP.CENTER) if SP.CENTER in L.run else None
        a = L.maxg()
        b = L.maxg(cidx) if cidx is not None else a
        som += b
        print(f'  {L.tag}{L.n:2d} {str(L.run[0]):8s} {L.s:16s} max {a:5d}'
              + (f' -> centrumregel {b}' if cidx is not None else ''))
    return som


def rollout(bd, LN, nroll=3000, seed=0, greedy=0.8):
    """Willekeurige-met-hebzucht uitrol met DEZELFDE zetgenerator als de exacte B&B
    (SP.Search.succ dwingt alle spelregels af).  Levert een ONDERGRENS plus een concreet
    schema; de exacte B&B heeft die ondergrens nodig om te kunnen snoeien."""
    import random
    rnd = random.Random(seed)
    S = SP.Search(bd, LN, SP.NEG)
    full = tuple(L.full for L in LN)
    best, bestmv = -1, None
    for it in range(nroll):
        masks = tuple([0] * len(LN))
        acc = 0
        mvs = []
        first = True
        while masks != full:
            sc = S.succ(masks, first)
            if not sc:
                break
            if rnd.random() < greedy:
                mx = max(d for _nm, d, _cs in sc)
                pool = [q for q in sc if q[1] >= mx - rnd.randrange(0, 30)]
            else:
                pool = sc
            nm, d, cs = pool[rnd.randrange(len(pool))]
            masks = nm
            acc += d
            mvs.append([tuple(c) for c in cs])
            first = False
        else:
            if acc > best:
                best, bestmv = acc, mvs
                print(f'   uitrol {it}: {acc} ({len(mvs)} zetten)', flush=True)
    return best, bestmv


def beam(bd, LN, K=3000, verbose=True):
    """BEAM over dezelfde gelaagde DP als de exacte B&B, maar per laag alleen de K beste
    toestanden op acc + staartgrens.  De hebzuchtige uitrol faalt hier structureel: de drie
    slotzetten zijn veruit de duurste zetten en een hebzuchtige speler legt ze meteen, terwijl
    ze juist LAATST moeten omdat hun kruiswoorden dan pas lang zijn.  De staartgrens weet dat
    wel, dus het beam op acc+grens vindt de goede volgorde."""
    S = SP.Search(bd, LN, SP.NEG)
    N = len(bd.occ)
    full = tuple(L.full for L in LN)
    start = tuple([0] * len(LN))
    layers = [dict() for _ in range(N + 1)]
    layers[0][start] = (0, [])
    best, bestmv = -1, None
    t0 = time.time()
    for k in range(N):
        cur = layers[k]
        if not cur:
            continue
        if len(cur) > K:
            keep = sorted(cur.items(), key=lambda kv: -(kv[1][0] + S.bound(kv[0])))[:K]
            cur = dict(keep)
        for masks, (acc, path) in cur.items():
            for nm, d, cs in S.succ(masks, k == 0):
                a2 = acc + d
                if nm == full:
                    if a2 > best:
                        best, bestmv = a2, path + [list(cs)]
                    continue
                ub = S.bound(nm)
                if ub <= SP.NEG:
                    continue
                tgt = layers[k + len(cs)]
                old = tgt.get(nm)
                if old is None or old[0] < a2:
                    tgt[nm] = (a2, path + [list(cs)])
        layers[k] = None
        if verbose and cur:
            print(f'   beam {k} cellen: {len(cur)} toestanden, beste volledig {best}  '
                  f'{time.time()-t0:.0f}s', flush=True)
    return best, bestmv


def main():
    name = os.environ.get('GRID', 'F1_55')
    if os.environ.get('BOARDJSON'):
        D = json.load(open(os.environ['BOARDJSON']))
        codes = D['grid']
        name = os.path.basename(os.environ['BOARDJSON']).replace('.json', '')
        os.environ['BLANKS'] = ';'.join(f'{b[0]},{b[1]}' for b in D.get('blanks', []))
    else:
        grids = load_grids(GRIDFILE)
        g = grids[name]
        codes = to_codes(g)
    need = blank_candidates(codes)
    if os.environ.get('BLANKS'):
        blanks = [tuple(int(v) for v in p.split(',')) for p in os.environ['BLANKS'].split(';') if p]
    else:
        blanks = []
    # controle: de gekozen blanco's moeten precies het tekort dekken
    from collections import Counter
    bl_cnt = Counter(codes[y][x] for (x, y) in blanks)
    for c, k in need.items():
        if bl_cnt.get(c, 0) != k:
            print(f'WAARSCHUWING letter {ABC[c]}: tekort {k}, blanco gekozen {bl_cnt.get(c,0)}')
    print(f'{name}: {len(blanks)} blanco op {blanks}; tekort {[ (ABC[c],k) for c,k in need.items() ]}')
    t0 = time.time()
    bd, LN = build(codes, blanks)
    print(f'lijnen {len(LN)}, cellen {len(bd.occ)}  ({time.time()-t0:.1f}s)')
    som = per_line_report(bd, LN)
    print(f'PER-LIJN-BOVENGRENS bij DEZE letters (met centrumregel): {som}')
    lb = int(os.environ.get('LB', '4400'))
    bestmv = None
    if os.environ.get('BEAM'):
        bb, bmv = beam(bd, LN, int(os.environ['BEAM']), verbose=bool(os.environ.get('V')))
        print(f'BEAM beste {bb}')
        if bmv:
            t, per, ok, msg = MG.score_game([row[:] for row in bd.grid],
                                            [[tuple(c) for c in m] for m in bmv], bd.blanks)
            print(f'  arbiter {int(t)} ok={ok} {"" if ok else msg[:150]}  ({len(bmv)} zetten, '
                  f'{sum(1 for m in bmv if len(m)==7)} bingo)')
            if ok:
                out0 = os.environ.get('OUT', f'{RES}/frame_game_{name}.json')
                json.dump({'grid': bd.grid, 'blanks': [list(b) for b in sorted(bd.blanks)],
                           'moves': [[list(c) for c in m] for m in bmv], 'total': int(t),
                           'ok': True, 'note': f'FRAME-bord {name} (beam)'}, open(out0, 'w'))
                print('  ->', out0)
                if int(t) > lb:
                    lb = int(t)
    if os.environ.get('ROLL'):
        rb, bestmv = rollout(bd, LN, int(os.environ['ROLL']),
                             int(os.environ.get('SEED', '0')),
                             float(os.environ.get('GREEDY', '0.8')))
        print(f'UITROL beste {rb}')
        if bestmv is not None:
            t, per, ok, msg = MG.score_game([row[:] for row in bd.grid], bestmv, bd.blanks)
            print(f'  arbiter {int(t)} ok={ok} {"" if ok else msg[:120]}')
            if ok and int(t) > lb:
                lb = int(t)
            if ok:
                out0 = os.environ.get('OUT', f'{RES}/frame_game_{name}.json')
                json.dump({'grid': bd.grid, 'blanks': [list(b) for b in sorted(bd.blanks)],
                           'moves': [[list(c) for c in m] for m in bestmv], 'total': int(t),
                           'ok': True, 'note': f'FRAME-bord {name} (uitrol)'}, open(out0, 'w'))
                print('  ->', out0)
    if os.environ.get('ROLLONLY'):
        return
    S = SP.Search(bd, LN, lb)
    best, bs, done = S.run(tmax=float(os.environ.get('TMAX', '1800')))
    print(f'B&B klaar={done} beste {bs} (ondergrens was {lb})')
    if best is None:
        print('GEEN zetvolgorde gevonden boven de ondergrens')
        return
    mvs = [[tuple(c) for c in m] for m in best]
    tot, per, ok, msg = MG.score_game([row[:] for row in bd.grid], mvs, bd.blanks)
    print(f'ARBITER {int(tot)} ok={ok} {"" if ok else msg[:150]}  ({len(mvs)} zetten, '
          f'{sum(1 for m in mvs if len(m)==7)} bingo)')
    if ok:
        out = os.environ.get('OUT', f'{RES}/frame_game_{name}.json')
        json.dump({'grid': bd.grid, 'blanks': [list(b) for b in sorted(bd.blanks)],
                   'moves': [[list(c) for c in m] for m in mvs], 'total': int(tot),
                   'ok': True, 'note': f'FRAME-bord {name} (kolom 14 = volle TWS-kolom)'},
                  open(out, 'w'))
        print('->', out)
        for i, m in enumerate(mvs):
            print(f'  zet {i+1:2d}: {sorted(m)}  +{per[i] if i < len(per) else "?"}')


if __name__ == '__main__':
    main()
