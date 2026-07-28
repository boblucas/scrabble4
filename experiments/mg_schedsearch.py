"""WOORDENBOEK-BEWUSTE SCHEMAZOEKER.

De kale m-plafond-zoeker vindt schema's met een hoog plafond die vervolgens 'nowords' geven:
een hoog plafond ontstaat juist door lijnen tegel-voor-tegel te leggen, en dan moet ELKE
tussenstand een woord zijn. Deze zoeker legt daarom een NOODZAKELIJKE woordenboekvoorwaarde
op tijdens het zoeken: voor elke maximale run die in een zet gescoord wordt, moet er minstens
een woord van die lengte bestaan dat op de vaste ankerletters past. Dat is precies de test die
het footprint-CP-SAT-model later als tabel gebruikt, dus schema's die hier slagen hebben een
reele kans om ook echt gevuld te worden.

Levert de top-N schema's (plafond + zetlijst) zodat we ze een voor een kunnen laten fitten:
een iets lager plafond dat WEL woordbaar is, wint van een onbereikbaar maximum.

Env: SSBASE (spel-json), ITERS, SEEDS (aantal restarts), TOPN, SSOUT (json met top-N).
"""
import sys, os, json, random, importlib.util
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

spec = importlib.util.spec_from_file_location("mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)

r = MG.r; cba = r.alphabet.cba
BYLEN = {}
for w in r.words_str:
    BYLEN.setdefault(len(w), []).append(tuple(cba[ch] for ch in w))

D = json.load(open(os.environ.get('SSBASE', 'experiments/results/maxgame_BEST.json')))
grid = D['grid']; moves0 = [[tuple(c) for c in m] for m in D['moves']]
FIXED = {(x, y): grid[y][x] for y in (0, 7, 14) for x in range(15) if grid[y][x]}

_cache = {}
def table_nonempty(run):
    """bestaat er een woord van deze lengte dat op de vaste ankerletters van deze run past?"""
    key = (len(run),) + tuple((i, FIXED[c]) for i, c in enumerate(run) if c in FIXED)
    hit = _cache.get(key)
    if hit is None:
        fx = key[1:]
        hit = any(all(w[i] == v for i, v in fx) for w in BYLEN.get(len(run), ()))
        _cache[key] = hit
    return hit

def words_ok(moves):
    for run, _ in mc.events_of(moves):
        if not table_nonempty(run): return False
    return True

def evaluate(moves):
    if not mc.legal_schedule(moves): return None
    if not words_ok(moves): return None
    cap, _ = mc.score_of(moves, FIXED)
    return cap

base = evaluate(moves0)
print(f"basis-schema: plafond {base} (gerealiseerd {D.get('total')})", flush=True)

ITERS = int(os.environ.get('ITERS', '20000'))
SEEDS = int(os.environ.get('SEEDS', '6'))
TOPN = int(os.environ.get('TOPN', '8'))
found = {}

for seed in range(SEEDS):
    rnd = random.Random(seed * 7919 + 13)
    cur = [list(m) for m in moves0]; curcap = base
    for it in range(ITERS):
        cand = [list(m) for m in cur]
        op = rnd.random()
        multi = [i for i, m in enumerate(cand) if len(m) > 1]
        if op < 0.55 and multi:
            i = rnd.choice(multi); m = sorted(cand[i], key=lambda c: (c[1], c[0]))
            if rnd.random() < 0.5: m = m[::-1]
            k = rnd.randrange(1, len(m))
            cand[i:i + 1] = [m[:k], m[k:]]
        elif op < 0.85 and len(cand) > 2:
            i = rnd.randrange(len(cand) - 1); j = rnd.randrange(i + 1, len(cand))
            mv = cand.pop(i); cand.insert(j, mv)
        else:
            i = rnd.randrange(max(1, len(cand) - 1))
            if i + 1 < len(cand) and len(cand[i]) + len(cand[i + 1]) <= 7:
                cand[i:i + 2] = [cand[i] + cand[i + 1]]
        cap = evaluate(cand)
        if cap is None: continue
        if cap >= curcap:
            cur, curcap = cand, cap
            key = tuple(tuple(sorted(m)) for m in cand)
            if key not in found: found[key] = (cap, [list(m) for m in cand])
    print(f"  seed {seed}: beste woordbare plafond {curcap}", flush=True)

top = sorted(found.values(), key=lambda t: -t[0])[:TOPN]
print(f"\n{len(found)} woordbare schema's gevonden; top-{len(top)}:")
for cap, mv in top:
    print(f"  plafond {cap} | {len(mv)} zetten | bingo's {sum(1 for m in mv if len(m)==7)}")
out = os.environ.get('SSOUT', '/tmp/claude-1000/-home-bob-programming-scrabble4/da7ed622-7493-428d-96da-a3b3144f633e/scratchpad/sched_top.json')
json.dump([{'ceiling': c, 'moves': [[list(x) for x in m] for m in mv]} for c, mv in top], open(out, 'w'))
print("weggeschreven ->", out)
