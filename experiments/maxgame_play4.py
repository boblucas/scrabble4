"""MAXGAME v4: ketenbare maskers (2026-07-14).
R0/R14-masker (0,3,7,11,12,13,14) -> pre-runs w[1:3],w[4:7],w[8:11]; R7-masker (0,1,2,3,11,13,14)
-> pre = center7 + (12,7).  Keten: center7, 4 bruggen (upW/upO/dnW/dnO), rij-runs, span1/span13,
span8+j2.  Planner: backtracking over kolommen+woorden met zak-budget; blanks alleen op maskers.
Daarna vullers + 3 slotzetten LAATST; engine-score; best-keeper."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

r = MG.r; W15 = 15
cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[ch] for ch in s) in lk
random.seed(int(os.environ.get('SEED', '1')))

R0 = os.environ.get('MGR0', 'ketchupmagazijn')
R7 = os.environ.get('MGR7', 'babyzwemmertjes')
R14 = os.environ.get('MGR14', 'flauwekulexcuus')
C7 = R7[4:11]
M014 = (0, 3, 7, 11, 12, 13, 14); M7 = (0, 1, 2, 3, 11, 13, 14)  # variant B: 12 i.p.v. 13 (na plan gezet)
words = r.words_str
AF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(c+x)} for c in set(R0+R7+R14+C7)}
BF = {c: {x for x in 'abcdefghijklmnopqrstuvwxyz' if isw(x+c)} for c in set(R14)}
C8 = {}
for w in words:
    if len(w) == 8: C8.setdefault((w[0], w[7]), []).append(w)
byl = {L: [w for w in words if len(w) == L] for L in (2, 3, 4, 5, 6)}

bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
anch = Counter(R0) + Counter(R7) + Counter(R14)
# blanks op masker-overflow-letters
over = {ch: max(0, anch[ch]-bag0[ch]) for ch in anch if anch[ch] > bag0[ch]}
assert sum(over.values()) <= r.blank_count, over
maskletters = Counter([R0[c] for c in M014] + [R14[c] for c in M014] + [R7[c] for c in M7])
for ch, n in over.items():
    assert maskletters[ch] >= n, (ch, n)   # blank-cel moet maskercel kunnen zijn
    anch[ch] -= n
budget0 = Counter(bag0); budget0.subtract(anch)
assert all(v >= 0 for v in budget0.values())

def bridge_cands(kind, c):
    a = (R0[c], C7[c-4]) if kind == 'up' else (C7[c-4], R14[c])
    return C8.get(a, [])
SPAN1 = {}; SPAN13 = {}
for L in (4, 5, 6):
    for w in byl[L]:
        if all(w[c-1] in AF[R0[c]] for c in range(1, L)):
            SPAN1.setdefault((L, w[L-1]), []).append(w)
        if all(w[c-1] in BF[R14[c]] for c in range(1, L)):
            SPAN13.setdefault((L, w[L-1]), []).append(w)
def span1_cands(bcol, bw): return SPAN1.get((bcol, bw[1]), [])
def span13_cands(bcol, bw): return SPAN13.get((bcol, bw[6]), [])
SP8 = []   # (woord, startkolom, variant): A legt (12,8)->j2; B legt (13,8)->2w op (13,7)
for L, x0 in ((3, 10), (4, 9)):
    off = 11-x0
    for w in byl[L]:
        if x0 == 9 and w[0] not in AF[C7[5]]: continue
        if w[off-1] not in AF[C7[6]]: continue
        if w[off] in AF[R7[11]] and w[off+1] in AF[R7[12]] and isw(R7[12]+w[off+1]):
            SP8.append((w, x0, 'A'))
for w in byl[4]:
    if w[0] in AF[C7[6]] and w[1] in AF[R7[11]] and w[2] in AF[R7[12]] \
       and w[3] in AF[R7[13]] and isw(R7[13]+w[3]) and isw(R7[12]+w[2]):
        SP8.append((w, 10, 'B'))

plan = {}
def newlet(name, w):
    if name.startswith(('up', 'dn')): return w[1:7]
    if name in ('span1', 'span13'): return w[:-1]
    if name == 'span8': return w[0]  # tuple (woord,x0,var): heel woord nieuw
    return ''
def bt(slots, i, rem):
    if i == len(slots): return True
    name, cands = slots[i]
    cl = list(cands(plan)); random.shuffle(cl)
    for w in cl[:80]:
        need = Counter(newlet(name, w))
        if any(rem[ch] < n for ch, n in need.items()): continue
        plan[name] = w
        r2 = Counter(rem); r2.subtract(need)
        if bt(slots, i+1, r2): return True
        del plan[name]
    return False

found = False
cols = [(uw, uo, dw, do) for uw in (4,5,6) for uo in (8,9,10)
        for dw in (4,5,6) if dw != uw for do in (8,9,10) if do != uo]
random.shuffle(cols)
for (uw, uo, dw, do) in cols:
    plan.clear()
    slots = [
        ('span1',    lambda st, c=uw: [w for w in SPAN1.get((c, ch), []) for ch in []] or
                     [w for ch in {b[1] for b in bridge_cands('up', c)}
                      for w in SPAN1.get((c, ch), [])]),
        (f'up{uw}',  lambda st, c=uw: [b for b in bridge_cands('up', c)
                                       if b[1] == st['span1'][-1]]),
        ('span13',   lambda st, c=dw: [w for ch in {b[6] for b in bridge_cands('dn', c)}
                                       for w in SPAN13.get((c, ch), [])]),
        (f'dn{dw}',  lambda st, c=dw: [b for b in bridge_cands('dn', c)
                                       if b[6] == st['span13'][-1]]),
        (f'up{uo}',  lambda st, c=uo: bridge_cands('up', c)),
        (f'dn{do}',  lambda st, c=do: bridge_cands('dn', c)),
        ('span8',    lambda st: SP8),
    ]
    # center7-cellen zijn R7-ankercellen: al in anch geteld
    if bt(slots, 0, Counter(budget0)):
        plan['cols'] = (uw, uo, dw, do); found = True; break
print("PLAN:", plan if found else "GEEN PLAN", flush=True)
if not found: sys.exit(1)
if plan['span8'][2] == 'B': M7 = (0, 1, 2, 3, 11, 12, 14)

# ---------- SPEEL ----------
grid = [[0]*15 for _ in range(15)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = {(c, 0) for c in M014} | {(c, 7) for c in M7} | {(c, 14) for c in M014}

def play(word, x, y, h, final=False):
    global blanks_left
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < 15 and 0 <= py < 15 and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < 15 and 0 <= ey < 15 and grid[ey][ex]: return False
    new = []; need = Counter(); byc = {}
    cross = False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return False
            cross = True
        else:
            if not final and (cx, cy) in MASKC: return False
            new.append((cx, cy)); need[ch] += 1; byc.setdefault(ch, []).append((cx, cy))
    if not new or len(new) > 7: return False
    if moves:
        if not cross and not any(0 <= nx+a < 15 and 0 <= ny+b < 15 and grid[ny+b][nx+a]
                                 for (nx, ny) in new for a, b in ((1,0),(-1,0),(0,1),(0,-1))):
            return False
    elif (7, 7) not in new: return False
    ov = sum(max(0, used[ch]+n-bag0[ch]) for ch, n in need.items())
    if ov > (blanks_left if final else 0): return False
    if not final:
        resv = Counter()
        for (ry, wd, mk) in ((0, R0, M014), (7, R7, M7), (14, R14, M014)):
            for cx2 in range(15):
                if not grid[ry][cx2] and (cx2, ry) not in new:
                    resv[wd[cx2]] += 1
        for ch, n in over.items(): resv[ch] -= n
        for ch in set(list(need)+list(resv)):
            if used[ch]+need.get(ch, 0)+max(0, resv.get(ch, 0)) > bag0[ch]: return False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    okr = True
    for yy in range(15):
        xx = 0
        while xx < 15:
            if not grid[yy][xx]: xx += 1; continue
            x2 = xx
            while x2 < 15 and grid[yy][x2]: x2 += 1
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx, x2))): okr = False
            xx = x2
    for xx in range(15):
        yy = 0
        while yy < 15:
            if not grid[yy][xx]: yy += 1; continue
            y2 = yy
            while y2 < 15 and grid[y2][xx]: y2 += 1
            if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy, y2))): okr = False
            yy = y2
    if not okr:
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    for ch, n in need.items():
        o2 = max(0, used[ch]+n-bag0[ch]); used[ch] += n
        for k in range(o2): blankcells.add(byc[ch][k]); blanks_left -= 1
    moves.append(new)
    return True

uw, uo, dw, do = plan['cols']
steps = [
    (C7, 4, 7, 1),
    (plan[f'up{uw}'], uw, 0, 0), (plan[f'up{uo}'], uo, 0, 0),
    (plan[f'dn{dw}'], dw, 7, 0), (plan[f'dn{do}'], do, 7, 0),
    (R0[4:7], 4, 0, 1), (R0[8:11], 8, 0, 1), (R14[4:7], 4, 14, 1), (R14[8:11], 8, 14, 1),
    (plan['span1'], 1, 1, 1), (R0[1:3], 1, 0, 1),
    (plan['span13'], 1, 13, 1), (R14[1:3], 1, 14, 1),
]
sp8w, sp8x, sp8v = plan['span8']
steps.append((sp8w, sp8x, 8, 1))
if sp8v == 'A':
    steps.append((R7[12]+sp8w[12-sp8x], 12, 7, 0))
else:
    steps.append((R7[13]+sp8w[13-sp8x], 13, 7, 0))
fails = [(w, x, y, h) for (w, x, y, h) in steps if not play(w, x, y, h)]
print(f"keten-fails: {fails}", flush=True)
# vullers
wl = [w for w in words if 2 <= len(w) <= 8]; random.shuffle(wl); wl = wl[:120000]
for rnd in range(25):
    anchors = [(x, y) for y in range(15) for x in range(15) if grid[y][x]]
    random.shuffle(anchors); prog = False
    for (ax, ay) in anchors[:70]:
        achr = chr(96+grid[ay][ax])
        for w in wl[:25000]:
            if achr not in w: continue
            done = False
            for i, ch in enumerate(w):
                if ch != achr: continue
                if play(w, ax-i, ay, 1) or play(w, ax, ay-i, 0): done = True; break
            if done: prog = True; break
    if not prog: break
s7 = play(R7, 0, 7, 1, final=True)
s0 = play(R0, 0, 0, 1, final=True)
s14 = play(R14, 0, 14, 1, final=True)
nt = sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot, per, ok2, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"SPEL: zetten={len(moves)} tegels={nt} score={tot} ok={ok2} ({msg}) slot=({s7},{s0},{s14})", flush=True)
out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
       'blanks': [list(b) for b in blankcells], 'total': int(tot), 'plan': {k: str(v) for k, v in plan.items()},
       'triple': [R0, R7, R14]}
json.dump(out, open(f'experiments/results/maxgame_play4_{os.environ.get("SEED","1")}.json', 'w'))
BEST = 'experiments/results/maxgame_BEST.json'
prev = json.load(open(BEST)).get('total', 0) if os.path.exists(BEST) else 0
if ok2 and tot > prev:
    json.dump(out, open(BEST, 'w'))
    print(f"*** NIEUW RECORD {tot} (was {prev}) ***", flush=True)
