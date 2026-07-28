"""FRAME-ZESTET-ENUMERATOR (woordkant van de frame-klasse).

Zoekt zestallen (R0,R7,R14,C0,C7,C14) van 15-letterwoorden die:
  (a) consistent zijn op de 9 snijpunten:  C_x[y] == R_y[x]  voor x,y in {0,7,14};
  (b) in de ZAK passen: de 6 lijnen beslaan 6*15 - 9 = 81 cellen; die 81 letters moeten
      met hoogstens 2 blanco's uit de 102-tegelzak komen (harde toets, nooit eerder gedaan);
  (c) zo veel mogelijk waarde opleveren onder een m-profiel.

Waardering: score-bijdrage van een ankerlijn = wm * SOM_cellen lm(c)*v(c) voor de cellen die in
die zet nieuw zijn, en 1*v(c) voor cellen die er al lagen. Elke ankercel ligt op precies een rij-
en (bij de frame-klasse) een kolomlijn en wordt dus door beide gescoord. Welke lijn de cel 'nieuw'
legt, is een schema-keuze: standaard leggen de rij-slotzetten de tegels (lm telt op de rij) en
completeren de kolommen daarna zonder nieuwe tegels op die cel (lm telt daar niet).
Met MPROFILE=<json van experiments/mg_mceiling.py> gebruik je in plaats daarvan het exacte
m-profiel van een echte geometrie.

Env: TOPN (kandidaten per rijrol, default 300), KEEP (aantal te bewaren zestallen, default 40),
     MPROFILE (optioneel), OUT (json-uitvoer).
"""
import sys, os, json, heapq
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
BLANKS = 2
ANCH = (0, 7, 14)

W15 = [w for w in r.words_str if len(w) == 15]
print(f"15-letterwoorden: {len(W15)}", flush=True)
CODE = {w: tuple(cba[ch] for ch in w) for w in W15}

# --- lijnmultipliers: rij y volledig gelegd => wm = product van WM over de 15 cellen
def line_wm(kind, idx):
    p = 1
    for k in range(15):
        p *= WM[idx][k] if kind == 'R' else WM[k][idx]
    return p

RWM = {y: line_wm('R', y) for y in ANCH}
CWM = {x: line_wm('C', x) for x in ANCH}
print("lijnmultipliers rijen", RWM, "kolommen", CWM, flush=True)

MPROF = None
if os.environ.get('MPROFILE'):
    P = json.load(open(os.environ['MPROFILE']))
    MPROF = {tuple(int(v) for v in k.split(',')): val for k, val in P['m'].items()}
    print("m-profiel geladen:", len(MPROF), "cellen", flush=True)


def row_value(w, y):
    """bijdrage van rijwoord w op rij y: eigen completering (lm actief) + latere kolomscore"""
    code = CODE[w]
    if MPROF:
        return sum(MPROF.get((x, y), 0) * VAL[code[x]] for x in range(15))
    s = sum(LM[y][x] * VAL[code[x]] for x in range(15))
    return RWM[y] * s


def col_value(w, x):
    """bijdrage van kolomwoord w op kolom x: de 12 niet-anker-cellen liggen er al (lm telt niet
    want ze zijn in hun eigen zet gelegd), de completering scoort de hele lijn x wm."""
    code = CODE[w]
    if MPROF:
        return sum(MPROF.get((x, y), 0) * VAL[code[y]] for y in range(15))
    return CWM[x] * sum(VAL[code[y]] for y in range(15))


# --- kolomindex: welke kolomwoorden hebben letters (a,b,c) op posities 0,7,14?
COLIDX = {x: defaultdict(list) for x in ANCH}
for w in W15:
    code = CODE[w]
    key = (code[0], code[7], code[14])
    for x in ANCH:
        COLIDX[x][key].append(w)
for x in ANCH:
    for k in COLIDX[x]:
        COLIDX[x][k].sort(key=lambda w: -col_value(w, x))
        del COLIDX[x][k][8:]          # top-8 per patroon volstaat
print("kolompatronen bezet:", {x: len(COLIDX[x]) for x in ANCH}, flush=True)

TOPN = int(os.environ.get('TOPN', '300'))
KEEP = int(os.environ.get('KEEP', '40'))
ROWS = {y: sorted(W15, key=lambda w: -row_value(w, y))[:TOPN] for y in ANCH}
for y in ANCH:
    print(f"rij {y} top-3:", [(w, int(row_value(w, y))) for w in ROWS[y][:3]], flush=True)


def bag_ok(cells):
    """cells: dict (x,y)->letter-id over de 81 framecellen; hoogstens 2 blanco's nodig?"""
    need = Counter(cells.values())
    short = sum(max(0, n - BAG[ch]) for ch, n in need.items())
    return short <= BLANKS, short


best = []
shortages = []
CW = int(os.environ.get('CW','6'))
tested = pruned_col = pruned_bag = 0
rv = {y: {w: row_value(w, y) for w in ROWS[y]} for y in ANCH}
bestcol = {x: {k: col_value(v[0], x) for k, v in COLIDX[x].items()} for x in ANCH}
maxcol = {x: max(bestcol[x].values()) for x in ANCH}

for w0 in ROWS[0]:
    c0 = CODE[w0]
    for w7 in ROWS[7]:
        c7 = CODE[w7]
        for w14 in ROWS[14]:
            c14 = CODE[w14]
            tested += 1
            keys = {x: (c0[x], c7[x], c14[x]) for x in ANCH}
            cols = {}
            ok = True
            for x in ANCH:
                lst = COLIDX[x].get(keys[x])
                if not lst: ok = False; break
                cols[x] = lst
            if not ok: pruned_col += 1; continue
            cells = {}
            for x in range(15):
                cells[(x, 0)] = c0[x]; cells[(x, 7)] = c7[x]; cells[(x, 14)] = c14[x]
            base = rv[0][w0] + rv[7][w7] + rv[14][w14]
            for cw0 in cols[0][:CW]:
                for cw7 in cols[7][:CW]:
                    for cw14 in cols[14][:CW]:
                        full = dict(cells)
                        for x, cw in ((0, cw0), (7, cw7), (14, cw14)):
                            code = CODE[cw]
                            for y in range(15): full[(x, y)] = code[y]
                        okbag, short = bag_ok(full)
                        shortages.append(short)
                        if not okbag: pruned_bag += 1; continue
                        tot = base + col_value(cw0, 0) + col_value(cw7, 7) + col_value(cw14, 14)
                        item = (int(tot), w0, w7, w14, cw0, cw7, cw14, short)
                        if len(best) < KEEP: heapq.heappush(best, item)
                        elif item[0] > best[0][0]: heapq.heapreplace(best, item)

print(f"\ngetest {tested} rijtripletten | kolompatroon-dood {pruned_col} | zak-dood {pruned_bag}")
if shortages:
    from collections import Counter as _C
    h=_C(shortages)
    print("zaktekort-verdeling (aantal tegels te kort, aantal zestallen):", sorted(h.items())[:12])
    print("kleinste tekort gezien:", min(shortages))
res = sorted(best, reverse=True)
print(f"beste {len(res)} zestallen (ankerwaarde, zonder bingo's/vullers):")
for it in res[:15]:
    print(f"  {it[0]:5d}  R {it[1]}/{it[2]}/{it[3]}  C {it[4]}/{it[5]}/{it[6]}  blanco {it[7]}")
if os.environ.get('OUT'):
    json.dump([{'value': it[0], 'rows': it[1:4], 'cols': it[4:7], 'blanks': it[7]} for it in res],
              open(os.environ['OUT'], 'w'))
    print("weggeschreven ->", os.environ['OUT'])
