import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'; os.environ['N15_HMAX'] = '15'
from collections import Counter
import n15_twolevel as T
r = T.r; val = T.val; lk = r.words_lookup; cba = r.alphabet.cba

def pre_runs_legal(w, mask):
    preset = set(range(15)) - set(mask); x = 0
    while x < 15:
        if x not in preset: x += 1; continue
        x2 = x
        while x2 < 15 and x2 in preset: x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in lk: return False
        x = x2
    return True

def best_mask(w, mustcols, wmv):
    from itertools import combinations
    free = [c for c in range(15) if c not in mustcols]
    best = (0, None)
    for extra in combinations(free, 7 - len(mustcols)):
        mask = tuple(sorted(mustcols + extra))
        if not pre_runs_legal(w, mask): continue
        ms = set(mask)
        s = sum(val[w[x]] * (2 if x in (3,11) and x in ms else 1) for x in range(15))
        sc = wmv*s + 50
        if sc > best[0]: best = (sc, mask)
    return best

anchors = [('geschenkcheques', 0, (0,7,14), 27), ('bouwcuratrixjes', 14, (0,7,14), 27),
           ('polymyalgietjes', 7, (0,14), 9)]
print("=== ANKERS ===")
alltiles = Counter()
for w, row, must, wmv in anchors:
    sc, mask = best_mask(w, must, wmv)
    newcols = set(mask); pre = [c for c in range(15) if c not in newcols]
    print(f"rij {row:2d}: {w}  score={sc}  mask(newly)={mask}")
    print(f"         pre-placed kol {pre}: '{''.join(w[c] for c in pre)}'  (via verticalen/eerdere beurten)")
    for c in range(15): alltiles[w[c]] += 1
print(f"\nanker-tegels totaal: {sum(alltiles.values())} = {dict(alltiles)}")
bag = Counter({chr(96+c): r.counts[c] for c in r.counts}); BL = r.blank_count
over = {ch: alltiles[ch]-bag.get(ch,0) for ch in alltiles if alltiles[ch] > bag.get(ch,0)}
print(f"blanks nodig voor ankers: {sum(over.values())} ({over})  (zak-blanks: {BL})")
rest = Counter(bag)
for ch in alltiles: rest[ch] -= alltiles[ch]
restpos = {ch: n for ch, n in rest.items() if n > 0}
restneg = {ch: n for ch, n in rest.items() if n < 0}  # gedekt door blanks
print(f"\nRESTZAK na ankers: {sum(v for v in rest.values() if v>0)} letters + {BL-sum(over.values())} blanks over")
print(f"  rest positief: {restpos}")
print(f"\n=== CONNECTIVITEIT ===")
print("rij 0, 7, 14 zijn 3 losse horizontale woorden. Om 1 component te vormen door center (7,7):")
print("  - verticalen nodig die rij0<->rij7 en rij7<->rij14 overbruggen (kol met legale vert-woorden).")
