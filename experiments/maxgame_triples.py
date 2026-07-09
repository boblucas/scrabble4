"""MAXGAME stap 1: rangschik (rij0 x27, rij14 x27, rij7 x9)-triples van 15-letter dutch2026-woorden.

Rij 0/14: 7 nieuwe tegels incl kol {0,7,14} (x3x3x3=27), DLS x2 op kol 3/11 indien nieuw, +50 bingo.
Rij 7:    center (7,7) is PRE-PLACED (x2 al verbruikt door de openingszet), dus de scoringsbeurt
          legt kol {0,14} nieuw (x3x3=9) maar NIET kol 7; DLS x2 op 3/11 indien nieuw, +50.
Legaliteit: elke maximale run van >=2 pre-placed kolommen moet een woord zijn (setup-legaliteit).
Triple-eis: gezamenlijke 45 tegels passen in de zak met <=2 blanks (overflow gerapporteerd).
"""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
os.environ.setdefault('N15_HMAX', '15')
from collections import Counter
from itertools import combinations
import n15_twolevel as T

r = T.r
val = T.val
lk = r.words_lookup
cba = r.alphabet.cba
words15 = sorted({w for w in r.words_str if len(w) == 15})
print(f"# {len(words15)} 15-letter woorden", flush=True)


def pre_runs_legal(w, mask):
    preset = set(range(15)) - set(mask)
    x = 0
    while x < 15:
        if x not in preset:
            x += 1; continue
        x2 = x
        while x2 < 15 and x2 in preset:
            x2 += 1
        if x2 - x >= 2 and tuple(cba[c] for c in w[x:x2]) not in lk:
            return False
        x = x2
    return True


def best_row(w, mustcols, wmv):
    """Beste legale 7-mask-score: mask bevat mustcols, 7 nieuwe tegels, pre-runs legaal.
    score = wmv * (letter-sum met DLS x2 op 3/11 indien nieuw) + 50."""
    free = [c for c in range(15) if c not in mustcols]
    best = 0
    for extra in combinations(free, 7 - len(mustcols)):
        mask = tuple(sorted(mustcols + extra))
        if not pre_runs_legal(w, mask):
            continue
        ms = set(mask)
        s = sum(val[w[x]] * (2 if x in (3, 11) and x in ms else 1) for x in range(15))
        sc = wmv * s + 50
        if sc > best:
            best = sc
    return best


def cheap_bound(w, mustcols, wmv):
    """Bovengrens op best_row zonder legaliteit: DLS x2 op 3/11 als die BUITEN mustcols mogen (dwz
    kunnen worden gekozen als extra newly).  Snel; gebruikt om alleen top-kandidaten exact te doen."""
    ms = set(mustcols)
    s = sum(val[w[x]] * (2 if x in (3, 11) else 1) for x in range(15))  # optimistisch: 3&11 newly
    return wmv * s + 50


# TWEE-FASE: cheap bound over alle woorden -> exact best_row alleen op top-K per rij
K = 400
b0 = sorted(((cheap_bound(w, (0, 7, 14), 27), w) for w in words15), reverse=True)[:4000]
b7 = sorted(((cheap_bound(w, (0, 14), 9), w) for w in words15), reverse=True)[:4000]
print(f"# cheap-bound top-4000 gekozen; exacte legaliteit op deze subset", flush=True)
rows0, rows7 = [], []
for _, w in b0:
    s0 = best_row(w, (0, 7, 14), 27)
    if s0:
        rows0.append((s0, w))
for _, w in b7:
    s7 = best_row(w, (0, 14), 9)
    if s7:
        rows7.append((s7, w))
rows0.sort(reverse=True)
rows7.sort(reverse=True)
print(f"# rij0/14: {len(rows0)}, rij7: {len(rows7)}", flush=True)
print("\ntop-15 rij0/14 (x27):")
for s, w in rows0[:15]:
    print(f"  {s:5d}  {w}")
print("\ntop-15 rij7 (x9, center pre-placed):")
for s, w in rows7[:15]:
    print(f"  {s:5d}  {w}")

# TRIPLES: 2 uit rows0 (rij0 & rij14) + 1 uit rows7; 45 tegels <= zak + <=2 blanks
bag = Counter({c: r.counts[c] for c in r.counts})
BL = r.blank_count
codes = {w: Counter(cba[ch] for ch in w)
         for w in set(x[1] for x in rows0[:80]) | set(x[1] for x in rows7[:80])}
best_triples = []
for (sa, wa), (sb, wb) in combinations(rows0[:80], 2):
    cab = codes[wa] + codes[wb]
    for sc7, wc in rows7[:80]:
        tot = cab + codes[wc]
        over = sum(max(0, tot[c] - bag.get(c, 0)) for c in tot)
        if over > BL:
            continue
        best_triples.append((sa + sb + sc7, over, sa, sb, sc7, wa, wb, wc))
best_triples.sort(reverse=True)
print(f"\n# {len(best_triples)} zak-compatibele triples; top-15 (3-woord backbone-score):")
for s, o, sa, sb, sc, wa, wb, wc in best_triples[:15]:
    print(f"  {s:5d} (blanks {o})  r0={wa}({sa}) r14={wb}({sb}) r7={wc}({sc})")
