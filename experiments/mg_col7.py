"""KOLOM-7-INGREEP: verbind de drie losse stukken van kolom 7 tot een 15-letterwoord.

Nu is kolom 7 = 'k...wankend...k': (7,0), de run rijen 4-10, en (7,14) raken elkaar niet,
dus bij de rij-0-final en de rij-14-final is het verticale kruiswoord daar maar EEN letter.
Vullen we (7,1),(7,2),(7,3),(7,11),(7,12),(7,13), dan is kolom 7 een doorlopend 15-letterwoord
dat door BEIDE x27-slotzetten met x3 wordt meegescoord (kolom 7 heeft TWS op (7,0) en (7,14)).
Met dit ankertriplet zijn er precies 2 kandidaten: koekbakkerswerk en kleermakerswerk.

Het bord zit vol (101), dus er moeten 6 tegels wijken. Kandidaten: de laagste-m cellen die
een RUN-EINDE zijn (een middelste cel weghalen splitst een woord).

Env: CBASE, TLIM, COUT, NDROP (aantal sloopsets dat geprobeerd wordt).
"""
import sys, os, json, itertools
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

# hergebruik de model-bouwer van mg_ruil (run(drops, adds) doet sloop + herordening + CP-SAT + arbiter)
src = open('/home/bob/programming/scrabble4/experiments/mg_ruil.py').read()
head = src.split("DROPS = eval(")[0].replace("os.environ.get('RBASE'", "os.environ.get('CBASE'")
G = {}
exec(compile(head, 'ruil_head', 'exec'), G)
run = G['run']; D = G['D']; grid0 = G['grid0']; moves0 = G['moves0']

import importlib.util
spec = importlib.util.spec_from_file_location("mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)

ADD = eval(os.environ.get('COLADD', '[(7,1),(7,2),(7,3),(7,11),(7,12),(7,13)]'))
occ = {(x, y) for y in range(15) for x in range(15) if grid0[y][x]}
assert not (set(ADD) & occ), "kolom-7-cellen zijn niet allemaal leeg"

m = mc.multiplicity(moves0)
PROTECT = set(eval(os.environ.get('PROTECT', '[]')))
# run-einden: een cel is een einde als hij in elke richting hoogstens aan EEN kant een buur heeft
def is_end(c):
    x, y = c
    h = [(x - 1, y) in occ, (x + 1, y) in occ]
    v = [(x, y - 1) in occ, (x, y + 1) in occ]
    return not (all(h) or all(v))

def peel(k, skip=(), occ0=None):
    """pel k tegels af: telkens het goedkoopste vrije run-EINDE; na verwijdering wordt de
    buur een nieuw einde, dus zo komen we voorbij de 5 initiele einden."""
    cur = set(occ0 or occ); out = []
    def ends(o):
        res = []
        for c in o:
            if c[1] in (0, 7, 14) or c in skip or c in PROTECT: continue
            x, y = c
            if (x - 1, y) in o and (x + 1, y) in o: continue
            if (x, y - 1) in o and (x, y + 1) in o: continue
            res.append((m[c], c))
        return sorted(res)
    for _ in range(k):
        e = ends(cur)
        if not e: break
        cur.discard(e[0][1]); out.append(e[0][1])
    return out

variants = []
K = len(ADD)
DS = os.environ.get('DROPSET')
if DS:
    variants.append(tuple(eval(DS)))
variants.append(tuple(peel(K)))
for skipn in range(1, 5):                      # varieer: sla de n goedkoopste over
    sk = tuple(c for _, c in sorted(((m[c], c) for c in occ if c[1] not in (0, 7, 14) and c not in PROTECT))[:skipn])
    v = tuple(peel(K, skip=sk))
    if len(v) == K and v not in variants: variants.append(v)
print("sloopvarianten:", variants, flush=True)

NDROP = int(os.environ.get('NDROP', '6'))
best = (int(D.get('total', 0)), None)
tried = 0
for drops in variants:
    if len(drops) < K: continue
    tried += 1
    if tried > NDROP: break
    res = run(list(drops), list(ADD))
    print(f"sloop {drops} + kolom7 -> {res[0]}", res[1] if res[0] in ('ok', 'rej') else '',
          (res[5][:60] if res[0] == 'rej' else ''), flush=True)
    if res[0] == 'ok' and res[1] > best[0]:
        best = (res[1], drops)
        json.dump({'grid': res[2], 'moves': [[list(c) for c in mv] for mv in res[3]],
                   'blanks': [list(b) for b in res[4]], 'total': res[1], 'triple': D['triple'],
                   'plan': f'kolom-7-ingreep: sloop {drops}, vul {ADD}'},
                  open(os.environ.get('COUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/col7_best.json'), 'w'))
        print("NIEUW BEST", res[1], flush=True)
print("BEST:", best, flush=True)
