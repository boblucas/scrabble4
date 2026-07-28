"""SLOOPKOSTEN-BOEKHOUDING + KANDIDAAT-INGREPEN.

Het bord zit op de cap van 101, dus elke toevoeging vergt een sloop. De eerdere netto-schattingen
waren misleidend omdat de afpelling BINGO'S brak: een 7-tegelzet die naar 6 zakt kost 50 punten
bovenop de directe waarde van de tegel. Deze module rekent per cel de echte sloopkosten uit:

    kosten(c) = m(c)*waarde(c)  +  50 als c in een 7-tegelzet zit  +  (structuurbreuk)

en zoekt daarmee de goedkoopste sloopset voor een gegeven toevoeging. Alles via de m-calculus,
dus zonder woordenboek en in microseconden; de CP-SAT-vulling is pas de laatste stap.
"""
import sys, os, json, importlib.util
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

spec = importlib.util.spec_from_file_location("mc", "/home/bob/programming/scrabble4/experiments/mg_mceiling.py")
mc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mc)

D = json.load(open(os.environ.get('TBASE', 'experiments/results/maxgame_BEST.json')))
grid = D['grid']; moves = [[tuple(c) for c in m] for m in D['moves']]
blanks = set(tuple(b) for b in D.get('blanks', []))
FIXED = {(x, y): grid[y][x] for y in (0, 7, 14) for x in range(15) if grid[y][x]}
VAL = {i: MG.r.scores[i] for i in range(1, 27)}
occ = {(x, y) for y in range(15) for x in range(15) if grid[y][x]}
base, m = mc.score_of(moves, FIXED)
print(f"basis: gerealiseerd {D['total']} | plafond {base} | {len(occ)} tegels", flush=True)

owner = {}
for i, mv in enumerate(moves):
    for c in mv: owner[c] = i

def drop_cost(c):
    """directe waardeverlies + bingo-breuk"""
    v = 0 if c in blanks else VAL[grid[c[1]][c[0]]]
    cost = m[c] * v
    if len(moves[owner[c]]) == 7: cost += 50
    return cost

free = [c for c in occ if c[1] not in (0, 7, 14)]
costs = sorted((drop_cost(c), c, len(moves[owner[c]])) for c in free)
print("\ngoedkoopste sloopkandidaten (kosten, cel, zetgrootte):")
for t in costs[:16]: print(f"   {t[0]:5d}  {t[1]}  zet van {t[2]}")
print(f"\nsom van de 12 goedkoopste: {sum(t[0] for t in costs[:12])}")
print(f"som van de 6 goedkoopste:  {sum(t[0] for t in costs[:6])}")
print(f"som van de 3 goedkoopste:  {sum(t[0] for t in costs[:3])}")

# --- bruto-waarde van kandidaat-toevoegingen (cap genegeerd)
fi = min(i for i, mm in enumerate(moves)
         if len(mm) == 7 and len({y for (_, y) in mm}) == 1 and mm[0][1] in (0, 7, 14) and i >= len(moves) - 12)

def gross(adds, label, before=None):
    pos = fi if before is None else before
    chunks = [list(adds[i:i + 6]) for i in range(0, len(adds), 6)]
    mv2 = moves[:pos] + chunks + moves[pos:]
    cap2, _ = mc.score_of(mv2, FIXED)
    print(f"   {label}: bruto {cap2 - base:+d} voor {len(adds)} tegels "
          f"({(cap2 - base) / max(1, len(adds)):.0f}/tegel)")
    return cap2 - base

print("\nBRUTO-waarde van kandidaat-toevoegingen (cap genegeerd):")
gross([(14, y) for y in range(1, 7)] + [(14, y) for y in range(8, 14)], "kolom 14 volledig (12)")
gross([(14, y) for y in range(1, 7)], "kolom 14 boven (6)")
gross([(14, y) for y in range(8, 14)], "kolom 14 onder (6)")
gross([(0, y) for y in range(8, 14)], "kolom 0 onder (6)")
gross([(0, y) for y in range(1, 7)], "kolom 0 boven (6)")
gross([(7, y) for y in (1, 2, 3, 11, 12, 13)], "kolom 7 gaten (6)")

# --- bingo-hergroepering: welke niet-bingo-tegels liggen op een lijn en aaneengesloten?
print("\nBINGO-HERGROEPERING: niet-bingo-tegels per lijn")
small = [c for c in free if len(moves[owner[c]]) < 7]
byrow = {}; bycol = {}
for c in small:
    byrow.setdefault(c[1], []).append(c); bycol.setdefault(c[0], []).append(c)
for tag, d in (('rij', byrow), ('kol', bycol)):
    for k, v in sorted(d.items()):
        if len(v) >= 3: print(f"   {tag} {k}: {sorted(v)}")
