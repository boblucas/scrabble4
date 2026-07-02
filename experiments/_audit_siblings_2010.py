"""INDEPENDENT audit of the 6 gross-290 combos' exclusion from the (8,12)@lb2010 band.
For each: reconstruct the combo from its content key, compute bag deficits of the tails vs
avail = base - newly_ct, and the EXACT minimal realized penalty:
   each deficit unit of letter X must blank a scored tail cell carrying X
   (bridges can't mint tiles), costing val[X] * wm[col]; minimize over eligible cells.
best_realized = nominal - minpen.  Exclusion from the beats-2010 band is SOUND iff
best_realized <= 2010 (i.e. minpen >= nominal_total - 2010)."""
import sys
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import Counter
import n15_twolevel as T

r = T.r
WORD = 'geschenkcheques'
MASK = (0, 3, 7, 8, 11, 12, 14)
mc = T.main_const(WORD, MASK)
avail, _ = T.build_avail(WORD, MASK, 1)
KEYS = [
 "0:glazuurt|3:capex|7:kwalmpje|8:cambiere|11:qatjes|12:uzelf|14:storytje",
 "0:glazuurt|3:cambrere|7:kwalmpje|8:campers|11:qatjes|12:uzelf|14:storytje",
 "0:glazuurt|3:cambreer|7:kwalmpje|8:campers|11:qatjes|12:uzelf|14:storytje",
 "0:glazuurt|3:cambrere|7:kwalmpje|8:camperen|11:qatjes|12:uzelf|14:storytje",
 "0:glazuurt|3:cambreer|7:kwalmpje|8:camperen|11:qatjes|12:uzelf|14:storytje",
 "0:glazuurt|3:capex|7:kwalmpje|8:cambieer|11:qatjes|12:uzelf|14:storytje",
]
ok_all = True
for key in KEYS:
    combo = {}
    for part in key.split('|'):
        c, w = part.split(':')
        combo[int(c)] = None if w == '-' else tuple(ord(ch) - 96 for ch in w)
    nominal = sum(T.vert_gross(ww, c) for c, ww in combo.items() if ww)
    # tails demand
    demand = Counter()
    cells = []          # (letter, col) for every tail cell
    for c, ww in combo.items():
        if not ww:
            continue
        for y in range(1, len(ww)):
            demand[ww[y]] += 1
            cells.append((ww[y], c))
    minpen = 0
    feas = True
    for code, q in demand.items():
        over = q - max(avail.get(code, 0), 0)
        if over <= 0:
            continue
        costs = sorted(T.val[chr(96 + code)] * T.wm[c] for (lt, c) in cells if lt == code)
        if len(costs) < over:
            feas = False
        minpen += sum(costs[:over])
    total_deficit = sum(max(0, q - max(avail.get(code, 0), 0)) for code, q in demand.items())
    best = mc + nominal - minpen
    verdict = 'EXCLUDED-SOUND' if best <= 2010 else '!!! MUST BE TESTED'
    if best > 2010:
        ok_all = False
    print(f"{key.split('|')[1]}+{key.split('|')[3]}: nominal={mc+nominal} deficit_blanks={total_deficit} "
          f"minpen={minpen} best_realized={best} -> {verdict}")
print("\nAUDIT:", "PASS -- all 6 exclusions sound, CERTIFIED<=2010 stands" if ok_all
      else "FAIL -- certification INVALID, siblings must be solved")
