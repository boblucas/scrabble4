"""WEERLEGGINGSMOTOR (Python-zijde): precompute, ijking, opsomming-hand-off, CP-SAT.

Doel: de stelling
    "met geschenkcheques/flexwerkstertje/polymelkzuurtje op rij 0/7/14 en de maskers
     rij 0 {0,3,7,8,11,13,14}, rij 7 {0,1,2,3,12,13,14}, rij 14 {0,1,2,3,7,13,14}
     haalt geen enkel legaal spel 4819"
zo goedkoop mogelijk WEERLEGGEN in plaats van oplossen.  Het rekenwerk zit in
`experiments/mg_refute.rs`; dit bestand levert de gegevens aan, ijkt en beslist de overlevenden.

De wiskunde staat in experiments/REFUTE.md.  Kort:

    score = SOM over de maximale EINDruns L van g_L(geschiedenis van L)           (SCHEDULEPROOF)
    g_L   = alle woordscores op L + 50 * (aantal 7-tegelzetten met L als hoofdlijn)

De drie ankerrijen zijn ALTIJD volle runs met vaste letters, dus hun bijdrage is een
constante bovengrens ANCH (hier 3865, exact per-lijn-DP met masker- en centrumregel).
Wat overblijft is een budget van 4819 - ANCH = 954 voor alle overige lijnen.

MODES
  MODE=dump     schrijft dict.bin / board.txt / keys.txt naar $REFDIR
  MODE=anchor   herberekent ANCH (per-lijn-DP op de drie ankerrijen, masker + centrum)
  MODE=occ      schrijft een bezetting (uit een bord-json) als occ-bestand voor Rust
  MODE=decide   CP-SAT-beslissing op de overlevenden
"""
import os, sys, json, struct, time
from collections import Counter

sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import numpy as np
import maxgame_score as MG

r = MG.r
CBA = r.alphabet.cba
ABC = {v: k for k, v in CBA.items()}
LM = np.array(r.letter_multiplier).astype(int)      # [y][x]
WM = np.array(r.word_multiplier).astype(int)
VAL = {i: r.scores[i] for i in range(1, 27)}
WORDS = set(r.words_str)
NBLANK = r.blank_count
BAG = {c: r.counts[c] for c in r.counts}

TRIPLET = tuple(os.environ.get(
    'TRIPLET', 'geschenkcheques,flexwerkstertje,polymelkzuurtje').split(','))
ANCHOR_ROWS = (0, 7, 14)
MASKS = {0: tuple(int(v) for v in os.environ.get('M0', '0,3,7,8,11,13,14').split(',')),
         7: tuple(int(v) for v in os.environ.get('M7', '0,1,2,3,12,13,14').split(',')),
         14: tuple(int(v) for v in os.environ.get('M14', '0,1,2,3,7,13,14').split(','))}

REFDIR = os.environ.get('REFDIR', '/home/bob/programming/scrabble4/experiments/results/refute')
NEG = -1 << 40
CAP_TILES = 101                      # zak 100 letters + 2 blanco, tegenstander houdt >=1 tegel
NFREE_MAX = CAP_TILES - 45           # 56


# ------------------------------------------------------------------ zak na de ankerrijen
def anchor_letters():
    c = Counter()
    for w, y in zip(TRIPLET, ANCHOR_ROWS):
        for ch in w:
            c[CBA[ch]] += 1
    return c


def rest_bag():
    a = anchor_letters()
    return {ch: BAG[ch] - a.get(ch, 0) for ch in range(1, 27)}


# ------------------------------------------------------------------ exacte lijn-DP (Python-ijk)
def line_maxg(wm, lm, val, isw, n, center_idx=None, maskbits=None, supbits=None):
    """max_h g_L(h) voor een lijn met multiplier-profiel (wm,lm), letterwaarden val en
    woordtoets isw[i][j] = "W[i:j] is een woord".  center_idx: de groep met dat veld moet de
    EERSTE groep zijn.  maskbits: die cellen mogen alleen als LAATSTE groep, allemaal tegelijk.

    supbits (AANRAAKREGEL, sound): elke zet moet het bord raken.  Een groep g in deze lijn is
    een zet; hij raakt het bord als (a) zijn span al gelegde cellen van deze lijn bevat of het
    gevormde blok doorloopt in al gelegde cellen, of (b) een van zijn cellen een LOODRECHTE
    buurcel heeft die in het EINDbord bezet is (dat is een noodzakelijke voorwaarde -- of die
    buur op dat moment al ligt weten we niet, dus dit is een verruiming), of (c) het de
    openingszet is (alleen rij 7, groep met het centrum).  supbits = de cellen met loodrechte
    steun in het eindbord.  supbits=None schakelt de regel uit."""
    full = (1 << n) - 1
    best = [NEG] * (1 << n)
    best[0] = 0
    for S in range(1 << n):
        b = best[S]
        if b == NEG:
            continue
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
                if center_idx is not None and (g >> center_idx & 1) and S != 0:
                    continue
                if maskbits is not None and (g & maskbits):
                    if not (g == maskbits and T == full):
                        continue
                if supbits is not None and not (g & supbits):
                    # geen loodrechte steun: dan moet de zet binnen de lijn zelf aanraken
                    inline = (span & S) != 0 or (a > 0 and (S >> (a - 1) & 1)) or \
                             (e + 1 < n and (S >> (e + 1) & 1))
                    opening = (center_idx is not None and S == 0 and (g >> center_idx & 1))
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
                    if not isw[lo][hi + 1]:
                        continue
                    w = 1
                    for k in range(a, e + 1):
                        if g >> k & 1:
                            w *= wm[k]
                    inc = 0
                    for k in range(lo, hi + 1):
                        inc += w * (val[k] * lm[k] if (g >> k & 1) else val[k])
                    if cnt == 7:
                        inc += 50
                if b + inc > best[T]:
                    best[T] = b + inc
    return best[full]


def anchor_table():
    """A_y[sup] = exacte bovengrens van de bijdrage van ankerrij y, gegeven WELKE van zijn
    pre-cellen loodrechte steun hebben in het eindbord.

    Dit is de koppeling tussen de ankerrijen en de rest van de geometrie.  De maskercellen
    komen in de slotzet (die raakt sowieso, want de pre-cellen liggen dan al), dus alleen de
    pre-cellen tellen: rij 0 heeft er 8, rij 7 heeft er 8, rij 14 heeft er 8 -> 256 patronen
    per rij.  A_y[sup] = -oneindig betekent: met dit steunpatroon is rij y NIET te leggen --
    dat is precies het EILAND-LEMMA, hier automatisch afgeleid.
    """
    out = {}
    for y, W in zip(ANCHOR_ROWS, TRIPLET):
        n = 15
        isw = [[False] * (n + 1) for _ in range(n + 1)]
        for i in range(n):
            for j in range(i + 2, n + 1):
                isw[i][j] = W[i:j] in WORDS
        val = [VAL[CBA[ch]] for ch in W]
        wm = [int(WM[y][x]) for x in range(n)]
        lm = [int(LM[y][x]) for x in range(n)]
        mb = sum(1 << x for x in MASKS[y])
        ci = 7 if y == 7 else None
        pre = [x for x in range(15) if x not in MASKS[y]]
        row = []
        for s in range(1 << len(pre)):
            # maskercellen tellen altijd als 'gesteund' (de slotzet raakt sowieso aan)
            sup = mb
            for i, x in enumerate(pre):
                if s >> i & 1:
                    sup |= 1 << x
            row.append(line_maxg(wm, lm, val, isw, n, center_idx=ci, maskbits=mb, supbits=sup))
        out[y] = (pre, row)
    return out


def anchor_cap(verbose=True):
    """ANCH = som van de drie ankerrij-maxima (exacte DP, masker + centrumregel)."""
    tot, det = 0, {}
    for y, W in zip(ANCHOR_ROWS, TRIPLET):
        n = 15
        isw = [[False] * (n + 1) for _ in range(n + 1)]
        for i in range(n):
            for j in range(i + 2, n + 1):
                isw[i][j] = W[i:j] in WORDS
        val = [VAL[CBA[ch]] for ch in W]
        wm = [int(WM[y][x]) for x in range(n)]
        lm = [int(LM[y][x]) for x in range(n)]
        mb = sum(1 << x for x in MASKS[y])
        ci = 7 if y == 7 else None
        a_free = line_maxg(wm, lm, val, isw, n)
        a_mask = line_maxg(wm, lm, val, isw, n, maskbits=mb)
        a_both = line_maxg(wm, lm, val, isw, n, center_idx=ci, maskbits=mb)
        det[y] = (a_free, a_mask, a_both)
        tot += a_both
        if verbose:
            print(f'  rij {y:2d} {W}: vrij {a_free}  +masker {a_mask}  +centrum {a_both}')
    return tot, det


# ------------------------------------------------------------------ MODE=dump
def dump():
    os.makedirs(REFDIR, exist_ok=True)
    bylen = {}
    for w in r.words_str:
        bylen.setdefault(len(w), []).append(w)
    with open(os.path.join(REFDIR, 'dict.bin'), 'wb') as f:
        f.write(struct.pack('<I', 0x52454644))
        for L in range(1, 16):
            ws = bylen.get(L, [])
            f.write(struct.pack('<I', len(ws)))
            buf = bytearray()
            for w in ws:
                for ch in w:
                    buf.append(CBA[ch])
            f.write(bytes(buf))
    rb = rest_bag()
    with open(os.path.join(REFDIR, 'board.txt'), 'w') as f:
        for y in range(15):
            f.write(' '.join(str(int(LM[y][x])) for x in range(15)) + '\n')
        for y in range(15):
            f.write(' '.join(str(int(WM[y][x])) for x in range(15)) + '\n')
        f.write(' '.join(str(VAL[i]) for i in range(1, 27)) + '\n')
        f.write(' '.join(str(BAG[i]) for i in range(1, 27)) + '\n')
        f.write(' '.join(str(rb[i]) for i in range(1, 27)) + '\n')
        f.write(f'{NBLANK}\n')
        for w in TRIPLET:
            f.write(' '.join(str(CBA[ch]) for ch in w) + '\n')
        for y in ANCHOR_ROWS:
            f.write(' '.join(str(v) for v in MASKS[y]) + '\n')
    # ---- lijnsleutels
    # verticaal: run [a,b] in kolom x.  Rijen 0/7/14 liggen ALTIJD, dus a-1 en b+1 mogen daar
    # niet zijn: a not in {1,8} (dan zou de run doorlopen), b not in {6,13}.
    keys = []
    A = [a for a in range(15) if a not in (1, 8)]
    B = [b for b in range(15) if b not in (6, 13)]
    for x in range(15):
        for a in A:
            for b in B:
                if b > a:
                    keys.append(('V', x, a, b))
    for y in range(15):
        if y in ANCHOR_ROWS:
            continue
        for x0 in range(15):
            for x1 in range(x0 + 1, 15):
                keys.append(('H', y, x0, x1))
    with open(os.path.join(REFDIR, 'keys.txt'), 'w') as f:
        for k in keys:
            f.write(' '.join(str(v) for v in k) + '\n')
    print(f'dict.bin / board.txt / keys.txt -> {REFDIR}   ({len(keys)} lijnsleutels)')
    print(f'restzak: ' + ' '.join(f'{ABC[i]}{rb[i]}' for i in range(1, 27) if rb[i]) +
          f'  = {sum(rb.values())} tegels + {NBLANK} blanco')


# ------------------------------------------------------------------ MODE=occ
def occ_of_grid(grid):
    return {(x, y) for y in range(15) for x in range(15) if grid[y][x]}


def write_occ(path, occs, names=None):
    with open(path, 'w') as f:
        for i, occ in enumerate(occs):
            cols = []
            for x in range(15):
                m = 0
                for y in range(15):
                    if y in ANCHOR_ROWS:
                        continue
                    if (x, y) in occ:
                        m |= 1 << y
                cols.append(m)
            nm = names[i] if names else str(i)
            f.write(nm + ' ' + ' '.join(str(v) for v in cols) + '\n')


def mode_occ():
    src = os.environ.get('BOARD',
                         '/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json')
    D = json.load(open(src))
    occ = occ_of_grid(D['grid'])
    out = os.environ.get('OUT', os.path.join(REFDIR, 'occ_record.txt'))
    write_occ(out, [occ], ['record'])
    nfree = len([c for c in occ if c[1] not in ANCHOR_ROWS])
    print(f'{src}: {len(occ)} tegels, {nfree} vrije cellen -> {out}')
    # de lijnen van deze bezetting
    print('vrije lijnen:')
    for x in range(15):
        y = 0
        while y < 15:
            if (x, y) not in occ:
                y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (x, y1 + 1) in occ:
                y1 += 1
            if y1 > y:
                print(f'  V {x} {y}..{y1}  (len {y1-y+1})')
            y = y1 + 1
    for y in range(15):
        if y in ANCHOR_ROWS:
            continue
        x = 0
        while x < 15:
            if (x, y) not in occ:
                x += 1; continue
            x1 = x
            while x1 + 1 < 15 and (x1 + 1, y) in occ:
                x1 += 1
            if x1 > x:
                print(f'  H {y} {x}..{x1}  (len {x1-x+1})')
            x = x1 + 1



# ------------------------------------------------------------------ MODE=calib
def decompose(D):
    """de per-lijn-ontbinding van een gespeeld bord: (lijnen, gerealiseerde g_L, totaal)."""
    grid = D['grid']
    moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    occ = occ_of_grid(grid)

    def v(c):
        return 0 if c in blanks else VAL[grid[c[1]][c[0]]]

    lines = []
    for tag, (dx, dy) in (('H', (1, 0)), ('V', (0, 1))):
        for (x, y) in sorted(occ, key=lambda t: (t[1], t[0])):
            if (x - dx, y - dy) in occ:
                continue
            run = []
            x0, y0 = x, y
            while (x0, y0) in occ:
                run.append((x0, y0)); x0 += dx; y0 += dy
            if len(run) >= 2:
                lines.append((tag, tuple(run)))
    cl = {}
    for li, (tag, run) in enumerate(lines):
        for i, c in enumerate(run):
            cl.setdefault(c, []).append((li, i))
    per = [0] * len(lines)
    placed = set()
    for mv in moves:
        cs = [tuple(c) for c in mv]
        gl = {}
        for c in cs:
            for (li, i) in cl[c]:
                gl.setdefault(li, []).append(i)
        for li, idx in gl.items():
            tag, run = lines[li]
            n = len(run)
            S = sum(1 << i for i, c in enumerate(run) if c in placed)
            g = sum(1 << i for i in idx)
            T = S | g
            a, e = min(idx), max(idx)
            lo = a
            while lo - 1 >= 0 and T >> (lo - 1) & 1:
                lo -= 1
            hi = e
            while hi + 1 < n and T >> (hi + 1) & 1:
                hi += 1
            if hi - lo + 1 >= 2:
                w = 1
                for k in idx:
                    w *= int(WM[run[k][1]][run[k][0]])
                inc = 0
                for k in range(lo, hi + 1):
                    cc = run[k]
                    inc += w * (v(cc) * int(LM[cc[1]][cc[0]]) if (g >> k & 1) else v(cc))
                if len(cs) == 7 and len(idx) == 7:
                    inc += 50
                per[li] += inc
        placed |= set(cs)
    return lines, per


def line_ub_for_word(run, word_codes):
    """max_h g_L(h) voor deze run met deze concrete letters (geen blanco-korting)."""
    n = len(run)
    W = ''.join(ABC[c] for c in word_codes)
    isw = [[False] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(i + 2, n + 1):
            isw[i][j] = W[i:j] in WORDS
    val = [VAL[c] for c in word_codes]
    wm = [int(WM[y][x]) for (x, y) in run]
    lm = [int(LM[y][x]) for (x, y) in run]
    ci = run.index((7, 7)) if (7, 7) in run else None
    return line_maxg(wm, lm, val, isw, n, center_idx=ci)


def mode_calib():
    """IJKING.  Drie eisen, alle drie hard:
       (1) de ontbindingsidentiteit reproduceert de arbiterscore exact;
       (2) elke gerealiseerde lijnbijdrage g_L ligt onder de per-lijn-DP met DEZELFDE letters
           (anders is de DP zelf onsound);
       (3) de motor-bovengrens op de recordbezetting is >= de recordscore.
    """
    src = os.environ.get('BOARD',
                         '/home/bob/programming/scrabble4/experiments/results/maxgame_BEST.json')
    D = json.load(open(src))
    grid = D['grid']
    moves = [[tuple(c) for c in m] for m in D['moves']]
    blanks = set(tuple(b) for b in D.get('blanks', []))
    tot, _per, ok, msg = MG.score_game([row[:] for row in grid], moves, blanks)
    lines, per = decompose(D)
    print(f'(1) arbiter {int(tot)} ok={ok} | lijn-ontbinding {sum(per)} | '
          f'identiek: {int(tot) == sum(per)}')
    assert int(tot) == sum(per), 'ONTBINDINGSIDENTITEIT GEFAALD'
    bad = 0
    anch_real = free_real = 0
    for (tag, run), g in zip(lines, per):
        codes = [grid[y][x] for (x, y) in run]
        ub = line_ub_for_word(run, codes)
        isanch = tag == 'H' and run[0][1] in ANCHOR_ROWS
        if isanch:
            anch_real += g
        else:
            free_real += g
        flag = '' if g <= ub else '   <<< ONSOUND'
        if g > ub:
            bad += 1
        print(f'    {tag}{len(run):2d} {str(run[0]):8s} '
              f'{"".join(ABC[c] for c in codes):16s} gerealiseerd {g:5d}  '
              f'per-lijn-DP {ub:5d}{flag}')
    print(f'(2) {len(lines)} lijnen, {bad} schendingen van g_L <= per-lijn-DP')
    assert bad == 0, 'PER-LIJN-DP IS ONSOUND'
    print(f'    anker gerealiseerd {anch_real}, vrije lijnen {free_real}')
    a, _det = anchor_cap(verbose=False)
    print(f'(3) ANCH-grens {a} >= anker gerealiseerd {anch_real}: {a >= anch_real}')
    assert a >= anch_real
    print(f'    score {int(tot)} = {anch_real} + {free_real};  bij drempel 4819 moeten de '
          f'vrije lijnen >= {4819 - a} halen')



# ------------------------------------------------------------------ MODE=refine (CP-SAT)
def read_tabdump(path):
    """de door Rust weggeschreven per-lijn-tabellen: {(tag,a,b,var): [(U, [lettercodes])]}"""
    out = {}
    cur = None
    for line in open(path):
        if line.startswith('#'):
            p = line.split()
            cur = (p[1], int(p[2]), int(p[3]), int(p[4]), int(p[5]))
            out[cur] = []
        else:
            v = line.split()
            out[cur].append((int(v[0]), [int(t) for t in v[1:]]))
    return out


def lines_of(cols):
    """(verticale, horizontale) maximale runs + de geldige steunvariant, identiek aan Rust."""
    def full(x):
        return cols[x] | 1 | (1 << 7) | (1 << 14)
    vs, hs = [], []
    for x in range(15):
        y = 0
        while y < 15:
            if not (full(x) >> y & 1):
                y += 1; continue
            y1 = y
            while y1 + 1 < 15 and (full(x) >> (y1 + 1) & 1):
                y1 += 1
            if y1 > y:
                var = 1
                for yy in range(y, y1 + 1):
                    if yy in ANCHOR_ROWS:
                        continue
                    if (x > 0 and full(x - 1) >> yy & 1) or (x < 14 and full(x + 1) >> yy & 1):
                        var = 0; break
                vs.append(('V', x, y, y1, var))
            y = y1 + 1
    for y in range(15):
        if y in ANCHOR_ROWS:
            continue
        x = 0
        while x < 15:
            if not (full(x) >> y & 1):
                x += 1; continue
            x1 = x
            while x1 + 1 < 15 and (full(x1 + 1) >> y & 1):
                x1 += 1
            if x1 > x:
                var = 1
                for xx in range(x, x1 + 1):
                    if (y > 0 and full(xx) >> (y - 1) & 1) or (y < 14 and full(xx) >> (y + 1) & 1):
                        var = 0; break
                hs.append(('H', y, x, x1, var))
            x = x1 + 1
    return vs, hs


def cells_of_line(L):
    tag, i, a, b, _var = L
    return [(i, y) for y in range(a, b + 1)] if tag == 'V' else [(x, i) for x in range(a, b + 1)]


def refine_decide(cols, tabs, target, tlim=120, nw=2):
    """ZETVOLGORDE-VRIJE beslissingstoets (scherper dan de Lagrange-grens):
    kies per lijn EEN woord uit zijn tabel; gedeelde cellen delen een lettervariabele
    (kruispuntconsistentie); het totale lettergebruik van de VRIJE cellen past in de restzak
    op ten hoogste 2 blanco's na; en SOM_L U_L(W_L) + ANCH >= target.
    INFEASIBLE bewijst dat GEEN ENKELE zetvolgorde en GEEN ENKELE lettering deze bezetting
    boven de drempel brengt."""
    from ortools.sat.python import cp_model
    vs, hs = lines_of(cols)
    at = anchor_table_cached()
    anch = anchor_cap_of(cols, at)
    if anch is None:
        return 'NEE', 0
    m = cp_model.CpModel()
    occ = set()
    for L in vs + hs:
        occ |= set(cells_of_line(L))
    occ |= {(x, y) for y in ANCHOR_ROWS for x in range(15)}
    fixed = {}
    for w, y in zip(TRIPLET, ANCHOR_ROWS):
        for x, ch in enumerate(w):
            fixed[(x, y)] = CBA[ch]
    cell = {}
    for c in sorted(occ):
        cell[c] = m.NewConstant(fixed[c]) if c in fixed else m.NewIntVar(1, 26, f'c{c}')
    obj = []
    for L in vs + hs:
        key = L                     # (tag, index, a, b, steunvariant) -- de variant HOORT erbij:
        rows = tabs.get(key)        # variant 1 is alleen geldig als de bezetting hem toestaat
        if not rows:
            return 'NEE', 0
        cs = cells_of_line(L)
        vmax = max(u for u, _ in rows)
        u = m.NewIntVar(0, vmax, f'u{key}')
        m.AddAllowedAssignments([cell[c] for c in cs] + [u], [w + [uu] for uu, w in rows])
        obj.append(u)
    free = [c for c in sorted(occ) if c not in fixed]
    over = []
    for ch in range(1, 27):
        ind = []
        for c in free:
            b = m.NewBoolVar('')
            m.Add(cell[c] == ch).OnlyEnforceIf(b)
            m.Add(cell[c] != ch).OnlyEnforceIf(b.Not())
            ind.append(b)
        ov = m.NewIntVar(0, NBLANK, f'ov{ch}')
        m.Add(sum(ind) <= rest_bag()[ch] + ov)
        over.append(ov)
    m.Add(sum(over) <= NBLANK)
    if os.environ.get('MAXIMIZE'):
        m.Maximize(sum(obj))
    else:
        m.Add(sum(obj) >= target - anch)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = tlim
    sol.parameters.num_workers = nw
    st = sol.Solve(m)
    if os.environ.get('MAXIMIZE'):
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return ('OPT' if st == cp_model.OPTIMAL else 'BOVENGRENS',
                    anch + int(sol.BestObjectiveBound()))
        return ('NEE' if st == cp_model.INFEASIBLE else 'ONBEKEND'), 0
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return 'JA', anch + int(sum(sol.Value(o) for o in obj))
    return ('NEE' if st == cp_model.INFEASIBLE else 'ONBEKEND'), 0


_ATC = [None]


def anchor_table_cached():
    if _ATC[0] is None:
        rows = {}
        for line in open(os.path.join(REFDIR, 'anchtab.txt')):
            p = line.split()
            y = int(p[0]); pre = [int(v) for v in p[1].split(',')]
            rows[y] = (pre, [int(v) for v in p[2:]])
        _ATC[0] = rows
    return _ATC[0]


def anchor_cap_of(cols, at):
    def full(x):
        return cols[x] | 1 | (1 << 7) | (1 << 14)
    tot = 0
    for y in ANCHOR_ROWS:
        pre, vals = at[y]
        s = 0
        for i, x in enumerate(pre):
            if y == 0:
                ok = full(x) >> 1 & 1
            elif y == 7:
                ok = (full(x) >> 6 & 1) or (full(x) >> 8 & 1)
            else:
                ok = full(x) >> 13 & 1
            if ok:
                s |= 1 << i
        v = vals[s]
        if v < 0:
            return None
        tot += v
    return tot


def mode_refine():
    src = os.environ.get('IN', os.path.join(REFDIR, 'surv.txt'))
    tabs = read_tabdump(os.environ.get('TAB', os.path.join(REFDIR, 'tabdump.txt')))
    target = int(os.environ.get('TARGET', '4819'))
    tlim = float(os.environ.get('TLIM', '120'))
    nw = int(os.environ.get('NW', '2'))
    topn = int(os.environ.get('TOPN', '10000'))
    rows = []
    for line in open(src):
        t = line.split('#')[0].split()
        if not t:
            continue
        rows.append((t[0], [int(v) for v in t[1:16]]))
    rows = rows[:topn]
    out = open(os.environ.get('OUT', os.path.join(REFDIR, 'refine.txt')), 'w')
    cnt = Counter()
    t0 = time.time()
    for i, (name, cols) in enumerate(rows):
        st, sc = refine_decide(cols, tabs, target, tlim, nw)
        cnt[st] += 1
        out.write(f'{name} {st} {sc}\n'); out.flush()
        if i % 20 == 0 or st == 'JA':
            print(f'[{i+1}/{len(rows)}] {name} {st} {sc}   {dict(cnt)}  {time.time()-t0:.0f}s',
                  flush=True)
    print('EINDSTAND', dict(cnt))


if __name__ == '__main__':
    MODE = os.environ.get('MODE', 'dump')
    if MODE == 'dump':
        dump()
    elif MODE == 'anchor':
        t0 = time.time()
        tot, det = anchor_cap()
        print(f'ANCH = {tot}   budget vrije lijnen bij 4819 = {4819 - tot}'
              f'   ({time.time()-t0:.1f}s)')
        json.dump({'anch': tot, 'detail': {str(k): v for k, v in det.items()}},
                  open(os.path.join(REFDIR, 'anchor.json'), 'w'))
    elif MODE == 'anchtab':
        t0 = time.time()
        tab = anchor_table()
        with open(os.path.join(REFDIR, 'anchtab.txt'), 'w') as f:
            for y in ANCHOR_ROWS:
                pre, row = tab[y]
                f.write(f'{y} ' + ','.join(str(v) for v in pre) + ' ' +
                        ' '.join(str(v if v > NEG else -1) for v in row) + '\n')
        for y in ANCHOR_ROWS:
            pre, row = tab[y]
            live = [v for v in row if v > NEG]
            print(f'  rij {y:2d} pre={pre}: {len(live)}/{len(row)} steunpatronen legbaar, '
                  f'max {max(live)}, min {min(live)}')
        tot = sum(max(v for v in tab[y][1]) for y in ANCHOR_ROWS)
        print(f'ANCH (volle steun) = {tot}   -> budget vrije lijnen bij 4819 = {4819 - tot}'
              f'   ({time.time()-t0:.1f}s)')
    elif MODE == 'refine':
        mode_refine()
    elif MODE == 'calib':
        mode_calib()
    elif MODE == 'occ':
        mode_occ()
    else:
        raise SystemExit('onbekende MODE')
