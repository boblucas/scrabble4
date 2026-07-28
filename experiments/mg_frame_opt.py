"""FRAME-OPTIMALISATIE ONDER ZAKDRUK.

Waarde-gulzig kiezen is zak-dood (min. tekort 5 tegels), puur schaarste-gulzig geeft
waardeloze woorden. De juiste formulering is een gezamenlijke optimalisatie:

    max  waarde(R0)+waarde(R7)+waarde(R14)+waarde(C0)+waarde(C7)+waarde(C14)
    o.v.v. 9 snijpuntgelijkheden  en  letterverbruik <= zak (+2 blanco's)

De zak is de enige koppeling tussen de zes lijnen. Met een schaarsteprijs p(letter) valt
het probleem uiteen: elke lijn kiest onafhankelijk het woord met de hoogste
gepenaliseerde waarde  waarde(w) - lambda * SOM_letters p(letter).  Door lambda op te
voeren wordt de selectie vanzelf zakvriendelijker; per lambda toetsen we de ECHTE zak.

Env: LAMBDAS (kommalijst), TOPN (rijkandidaten per rol), CW (kolomkandidaten per patroon),
     OUT (json). Draai: .venv/bin/python experiments/mg_frame_opt.py
"""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter, defaultdict
import numpy as np, maxgame_score as MG

r = MG.r; cba = r.alphabet.cba
VAL = {i: r.scores[i] for i in range(1, 27)}
LM = np.array(r.letter_multiplier).tolist()
WM = np.array(r.word_multiplier).tolist()
BAG = Counter({c: r.counts[c] for c in r.counts})
ANCH = (0, 7, 14)
NTILES = sum(BAG.values())

W15 = [w for w in r.words_str if len(w) == 15]
CODE = {w: tuple(cba[ch] for ch in w) for w in W15}
print(f"15-letterwoorden {len(W15)} | zak {NTILES} + 2 blanco", flush=True)

def line_wm(kind, i):
    p = 1
    for k in range(15): p *= WM[i][k] if kind == 'R' else WM[k][i]
    return p
RWM = {y: line_wm('R', y) for y in ANCH}
CWM = {x: line_wm('C', x) for x in ANCH}

def row_value(w, y):
    c = CODE[w]
    return RWM[y] * sum(LM[y][x] * VAL[c[x]] for x in range(15))

def col_value(w, x):
    c = CODE[w]
    return CWM[x] * sum(VAL[c[y]] for y in range(15))

# schaarsteprijs: hoe krap is een letter t.o.v. de zak
PRICE = {ch: 100.0 / max(1, BAG[ch]) for ch in range(1, 27)}
def scarcity(w): return sum(PRICE[c] for c in CODE[w])

# kolomindex per (pos0,pos7,pos14)-patroon
IDX = defaultdict(list)
for w in W15:
    c = CODE[w]; IDX[(c[0], c[7], c[14])].append(w)
print("kolompatronen:", len(IDX), flush=True)

# baseline: huidig triplet onder hetzelfde waardemodel
CUR = ('geschenkcheques', 'flexwerkstertje', 'polymelkzuurtje')
cur_val = sum(row_value(w, y) for w, y in zip(CUR, ANCH))
print(f"baseline huidig triplet (alleen 3 rijen, analytisch): {int(cur_val)}", flush=True)

TOPN = int(os.environ.get('TOPN', '120'))
CW = int(os.environ.get('CW', '10'))
LAMBDAS = [float(x) for x in os.environ.get('LAMBDAS', '0,2,5,10,20,40,80').split(',')]

best_overall = None
report = []
for lam in LAMBDAS:
    # per rol: kandidaten op gepenaliseerde waarde
    rows = {y: sorted(W15, key=lambda w: -(row_value(w, y) - lam * scarcity(w)))[:TOPN] for y in ANCH}
    colcand = {}
    for x in ANCH:
        d = {}
        for k, lst in IDX.items():
            d[k] = sorted(lst, key=lambda w: -(col_value(w, x) - lam * scarcity(w)))[:CW]
        colcand[x] = d
    found = None; tested = 0; feasible = 0
    for w0 in rows[0]:
        c0 = CODE[w0]
        for w7 in rows[7]:
            c7 = CODE[w7]
            for w14 in rows[14]:
                c14 = CODE[w14]
                tested += 1
                keys = [(c0[x], c7[x], c14[x]) for x in ANCH]
                cols = [colcand[x].get(k) for x, k in zip(ANCH, keys)]
                if not all(cols): continue
                base = Counter()
                for cc in (c0, c7, c14):
                    for ch in cc: base[ch] += 1
                rv = row_value(w0, 0) + row_value(w7, 7) + row_value(w14, 14)
                for a in cols[0]:
                    for b in cols[1]:
                        for d in cols[2]:
                            need = Counter(base)
                            for x, cw in ((0, a), (7, b), (14, d)):
                                cc = CODE[cw]
                                for y in range(15):
                                    if y not in ANCH: need[cc[y]] += 1
                            short = sum(max(0, n - BAG[ch]) for ch, n in need.items())
                            if short > 2: continue
                            feasible += 1
                            tot = rv + col_value(a, 0) + col_value(b, 7) + col_value(d, 14)
                            if found is None or tot > found[0]:
                                found = (tot, w0, w7, w14, a, b, d, short, sum(need.values()))
    if found:
        report.append((lam, int(found[0]), found[7], found[8], found[1:7]))
        print(f"lambda {lam:5.1f}: beste zak-haalbare frame = {int(found[0])} "
              f"(tekort {found[7]}, {found[8]} tegels) {found[1:7]}", flush=True)
        if best_overall is None or found[0] > best_overall[0]: best_overall = found
    else:
        report.append((lam, None, None, None, None))
        print(f"lambda {lam:5.1f}: geen zak-haalbaar frame in {tested} rijtripletten", flush=True)

if best_overall:
    tot, w0, w7, w14, a, b, d = best_overall[:7]
    print(f"\nBESTE FRAME: {int(tot)}")
    print(f"  rijen   R0={w0}  R7={w7}  R14={w14}")
    print(f"  kolommen C0={a}  C7={b}  C14={d}")
    print(f"  rijdeel {int(row_value(w0,0)+row_value(w7,7)+row_value(w14,14))} | "
          f"kolomdeel {int(col_value(a,0)+col_value(b,7)+col_value(d,14))}")
    print(f"  vergelijk: huidig triplet rijen-alleen {int(cur_val)}; "
          f"frame-winst rijen+kolommen {int(tot - cur_val)}")
    print(f"  framecellen 81 van de 101 => {101-81} tegels over voor bingo's/steigers")
    if os.environ.get('OUT'):
        json.dump({'value': int(tot), 'rows': [w0, w7, w14], 'cols': [a, b, d],
                   'baseline_rows_only': int(cur_val)}, open(os.environ['OUT'], 'w'))
