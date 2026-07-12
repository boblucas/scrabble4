"""MAXGAME constructor (geen CP-SAT): bouw het 3-anker-bord expliciet.
Skelet: rijen 0/7/14 (ankers) + kol 14 = stationsentrees + per pre-run 1 verticale steun
(2-letter woord), singles verplicht.  Zak-geteld, alle runs gecheckt, component-check."""
import sys, os, json
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
from scrabble import construct_rules
r = construct_rules('dutch2026', '15')
W = H = 15
cba = r.alphabet.cba
lk = r.words_lookup
def isw(s): return tuple(cba[ch] for ch in s) in lk

R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'
COL14 = 'stationsentrees'
grid = [[''] * W for _ in range(H)]
for x in range(15): grid[0][x] = R0[x]; grid[7][x] = R7[x]; grid[14][x] = R14[x]
for y in range(15): grid[y][14] = COL14[y]
bag = Counter({chr(96+c): r.counts[c] for c in r.counts}); BL = r.blank_count
used = Counter()
for y in range(H):
    for x in range(W):
        if grid[y][x]: used[grid[y][x]] += 1
# steunen: (kolom, rij-van-nieuwe-cel, richting): nieuw = grid[rij][kol]
# rij-0 runs: es(1-2) hen(4-6) he(9-10) e(13) -> steun onder een kolom van de run (rij 1)
# rij-14 runs: u(2) c(4) r(6) tri(8-10) je(12-13) -> steun boven (rij 13)
# rij-7 runs: myalgie(4-10) e(13) -> steun op rij 6 of 8
supports = [
    ('r0', [1, 2], 1), ('r0', [4, 5, 6], 1), ('r0', [9, 10], 1), ('r0', [13], 1),
    ('r14', [2], 13), ('r14', [4], 13), ('r14', [6], 13), ('r14', [8, 9, 10], 13), ('r14', [12, 13], 13),
    ('r7', [4, 5, 6, 7, 8, 9, 10], 6), ('r7', [13], 6),
]
def vword(c, y):
    """2-letterwoord: nieuw op (c,y); anker-cel eronder/erboven."""
    if y == 1:   return lambda ch: isw(R0[c] + ch)      # (c,0)+(c,1)
    if y == 13:  return lambda ch: isw(ch + R14[c])     # (c,13)+(c,14)
    if y == 6:   return lambda ch: isw(ch + R7[c])      # (c,6)+(c,7)
    if y == 8:   return lambda ch: isw(R7[c] + ch)      # (c,7)+(c,8)


def try3_up(c):
    """3-letter steun boven rij 14: (c,12)+(c,13)+(c,14) = ab + R14[c]."""
    for a in letters:
        if bag[a] - used[a] <= 0: continue
        for b in letters:
            if bag[b] - used[b] - (1 if b == a else 0) <= 0: continue
            if isw(a + b + R14[c]):
                return a, b
    return None
letters = 'enadiortslgkmpbfvwzjhcuxy'   # zak-rijk eerst
placed = []
ok_all = True
for tag, cols, y in supports:
    done = False
    for c in cols:                        # kies kolom binnen de run
        for yy in ([6, 8] if y == 6 else [y]):
            chk = vword(c, yy)
            for ch in letters:
                if bag[ch] - used[ch] <= 0: continue
                if not chk(ch): continue
                # geen horizontale buren op die rij (kruisrun-vrij) behalve kol14
                nb = []
                for dx in (-1, 1):
                    xx = c + dx
                    if 0 <= xx < W and grid[yy][xx]: nb.append(xx)
                if nb:
                    # run zou ontstaan: check of de run een woord is (max 1 buur hier: kol 14)
                    if len(nb) == 1 and nb[0] == 14:
                        run = ch + grid[yy][14] if False else None
                        s = ''.join(grid[yy][x] if x != c else ch for x in range(min(c, nb[0]), max(c, nb[0]) + 1))
                        if not isw(s): continue
                    else:
                        continue
                grid[yy][c] = ch; used[ch] += 1
                placed.append((tag, c, yy, ch))
                done = True
                break
            if done: break
        if done: break
    if not done and tag == 'r14' and len(cols) == 1:
        c = cols[0]
        ab = try3_up(c)
        if ab and not grid[12][c] and not grid[13][c]:
            a, b = ab
            grid[12][c] = a; grid[13][c] = b; used[a] += 1; used[b] += 1
            placed.append((tag, c, '12-13', a + b))
            done = True
    if not done:
        print(f"!! geen steun voor {tag} {cols}"); ok_all = False
print(f"steunen: {placed}")
# tegels + zak
nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
over = {ch: used[ch] - bag[ch] for ch in used if used[ch] > bag[ch]}
print(f"tegels: {nt}  blanks nodig: {sum(over.values())} {over}  (max {BL})")
# alle runs checken
bad = []
for y in range(H):
    x = 0
    while x < W:
        if not grid[y][x]: x += 1; continue
        x2 = x
        while x2 < W and grid[y][x2]: x2 += 1
        if x2 - x >= 2 and not isw(''.join(grid[y][x:x2])): bad.append(('H', y, ''.join(grid[y][x:x2])))
        x = x2
for x in range(W):
    y = 0
    while y < H:
        if not grid[y][x]: y += 1; continue
        y2 = y
        while y2 < H and grid[y2][x]: y2 += 1
        if y2 - y >= 2 and not isw(''.join(grid[yy][x] for yy in range(y, y2))): bad.append(('V', x, ''.join(grid[yy][x] for yy in range(y, y2))))
        y = y2
print(f"illegale runs: {bad if bad else 'GEEN'}")
# component-check
seen = set(); stack = [(7, 7)]
while stack:
    (x, y) = stack.pop()
    if (x, y) in seen or not (0 <= x < W and 0 <= y < H) or not grid[y][x]: continue
    seen.add((x, y))
    stack += [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
print(f"component via center: {len(seen)}/{nt} {'OK' if len(seen)==nt else 'LOS!'}")
if ok_all and not bad and len(seen) == nt and sum(over.values()) <= BL:
    g2 = [[cba[grid[y][x]] if grid[y][x] else 0 for x in range(W)] for y in range(H)]
    json.dump({'grid': g2}, open('experiments/results/maxgame_board_final.json', 'w'))
    val = {chr(96+i): r.scores[i] for i in range(1, 27)}
    finalcells = {(c,0) for c in (0,3,7,8,11,12,14)} | {(c,7) for c in (0,1,2,3,11,12,14)} | {(c,14) for c in (0,1,3,5,7,11,14)}
    blankover = []
    for ch, n in over.items():
        blankover += [ch]*n
    setup_face = 0
    for y in range(H):
        for x in range(W):
            if grid[y][x] and (x, y) not in finalcells:
                setup_face += val[grid[y][x]]
    setup_face -= sum(val[ch] for ch in blankover)     # conservatief: blanks op duurste
    nsetup = nt - 21
    lb = 1724 + 536 + 1616 + setup_face + 50 * (nsetup // 7)
    print(f"\n*** BORD OK -> SPEL-LB >= 3876 + {setup_face} + {50*(nsetup//7)} = {lb} ***")
    for y in range(H):
        print('  ' + ' '.join(grid[y][x] if grid[y][x] else '.' for x in range(W)))
