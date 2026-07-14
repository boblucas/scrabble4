"""MAXGAME v3: DETERMINISTISCHE keten-planner + uitvoering + best-keeper.
Plan (backtracking, zak-gedeeld, ankerletters gereserveerd) -> speel: myalgie, bruggen, ketens,
vullers, dan de 3 slotzetten LAATST.  Engine-gescoord; record naar maxgame_BEST.json."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

r = MG.r; W = H = 15
cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[ch] for ch in s) in lk
R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'
after = lambda ch: [x for x in 'enadiortslgkmpbfvwzjhcuxy' if isw(ch+x)]
before = lambda ch: [x for x in 'enadiortslgkmpbfvwzjhcuxy' if isw(x+ch)]

# ---------- PLAN ----------
words = r.words_str
w8 = [w for w in words if len(w) == 8]
def cands8(a, b): return [w for w in w8 if w[0] == a and w[7] == b]
by = {L: [w for w in words if len(w) == L] for L in (2, 3, 4, 5)}
AFT = {c: set(after(c)) for c in 'tjesc'}
BEF = {c: set(before(c)) for c in 'xjwe'}

# zak minus ankers (blanks dekken c,y)
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
anchors_ct = Counter(R0) + Counter(R7) + Counter(R14)
anchors_ct['c'] -= 1; anchors_ct['y'] -= 1
budget = Counter(bag0); budget.subtract(anchors_ct)
assert all(v >= 0 for v in budget.values()), budget

# precompute gekoppelde kandidaten per koppelletter (1x, daarna O(1) lookup in bt)
SP8 = {}; SP13B = {}; SP1 = {}; SP12 = {}
for w in by[4]:
    if w[1] in AFT['t'] and w[2] in AFT['j'] and w[3] in AFT['e']: SP8.setdefault(w[0], []).append(w)
    if w[1] in BEF['x'] and w[2] == 'i' and w[3] in BEF['e']: SP13B.setdefault(w[0], []).append(w)
    if w[0] in AFT['e'] and w[1] in AFT['s'] and w[2] in AFT['c']: SP1.setdefault(w[3], []).append(w)
for w in by[5]:
    if w[0] == 'g' and isw(w[2] + 'ec'): SP12.setdefault(w[4], []).append(w)
SLOTS = [
    ('dn10', lambda st: [w for w in cands8('e', 'i') if w[1] in SP8 and w[6] in SP13B]),
    ('span8', lambda st: SP8[st['dn10'][1]]),
    ('span13b', lambda st: SP13B[st['dn10'][6]]),
    ('up4',  lambda st: [w for w in cands8('h', 'm') if w[1] in SP1]),
    ('span1', lambda st: SP1[st['up4'][1]]),
    ('dn6',  lambda st: [w for w in cands8('a', 'r') if w[5] in SP12]),
    ('span12', lambda st: SP12[st['dn6'][5]]),
    ('up9',  lambda st: cands8('h', 'i')),
    ('dn8',  lambda st: cands8('g', 't')),
    ('up13', lambda st: cands8('e', 'e')),
]
# nieuwe letters per slot (deel dat niet op al-liggende cellen valt)
def newletters(name, w, st):
    # ALLEEN letters die niet op ankerrijen (0/7/14, al in anchors_ct) en niet op al-liggende cellen vallen
    if name in ('up4', 'up9', 'up13', 'dn6', 'dn8', 'dn10'): return w[1:7]
    if name == 'span8': return w[1:]                  # (10,8)=dn10[1] ligt; rij 8 geen anker
    if name == 'span1': return w[0:3]
    if name == 'span12': return w[0:4]                # (6,12)=dn6[5] ligt
    if name == 'span13b': return w[1:]                # (10,13)=dn10[6] ligt
    return w

EXTRA = list('en') + list('ec') + list('u') + list('e') + list('je'[0:1])  # e13_7('n'?), sec e+c, nu-u, e13_14-e, je-j... conservatief
FIXED_EXTRA = Counter({'e': 1, 'n': 1})   # (4,13)'e' + (2,13)'n'; rest ligt op ankerrijen

plan = {}
def bt(i, rem):
    if i == len(SLOTS): return True
    name, gen = SLOTS[i]
    cl = gen(plan)
    random.shuffle(cl)
    for w in cl[:60]:
        need = Counter(newletters(name, w, plan))
        if any(rem[ch] < n for ch, n in need.items()): continue
        plan[name] = w
        r2 = Counter(rem); r2.subtract(need)
        if bt(i+1, r2): return True
        del plan[name]
    return False

random.seed(int(os.environ.get('SEED', '1')))
rem0 = Counter(budget); rem0.subtract(FIXED_EXTRA)
ok = bt(0, rem0)
print("PLAN:", plan if ok else "GEEN PLAN", flush=True)
if not ok: sys.exit(1)

# ---------- SPEEL ----------
grid = [[0]*W for _ in range(H)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = ({(c,0) for c in (0,3,7,8,11,12,14)} | {(c,7) for c in (0,1,2,3,11,12,14)}
         | {(c,14) for c in (0,1,3,5,7,11,14)})

def play(word, x, y, h, final=False):
    global blanks_left
    dx, dy = (1,0) if h else (0,1)
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
        if not cross and not any(0<=nx+a<15 and 0<=ny+b<15 and grid[ny+b][nx+a]
                                 for (nx,ny) in new for a,b in ((1,0),(-1,0),(0,1),(0,-1))):
            return False
    elif (7,7) not in new: return False
    over = sum(max(0, used[ch]+n-bag0[ch]) for ch, n in need.items())
    if over > (blanks_left if final else 0): return False
    if not final:
        resv = Counter()
        for (ry, wd) in ((0, R0), (7, R7), (14, R14)):
            for cx2 in range(15):
                if not grid[ry][cx2] and (cx2, ry) not in [(a,b) for (a,b) in new]:
                    resv[wd[cx2]] += 1
        resv['c'] -= 1; resv['y'] -= 1
        for ch in set(list(need)+list(resv)):
            if used[ch]+need.get(ch,0)+max(0,resv.get(ch,0)) > bag0[ch]: return False
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
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx,x2))): okr = False
            xx = x2
    for xx in range(15):
        yy = 0
        while yy < 15:
            if not grid[yy][xx]: yy += 1; continue
            y2 = yy
            while y2 < 15 and grid[y2][xx]: y2 += 1
            if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy,y2))): okr = False
            yy = y2
    if not okr:
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    for ch, n in need.items():
        ov = max(0, used[ch]+n-bag0[ch]); used[ch] += n
        for k in range(ov): blankcells.add(byc[ch][k]); blanks_left -= 1
    moves.append(new)
    return True

P = plan
steps = [
    ('myalgie', 4, 7, 1), (P['up4'], 4, 0, 0), (P['up9'], 9, 0, 0),
    (P['dn6'], 6, 7, 0), (P['dn8'], 8, 7, 0), (P['dn10'], 10, 7, 0),
    (P['span8'], 10, 8, 1), ('e' + P['span8'][3], 13, 7, 0), (P['up13'], 13, 0, 0),
    ('hen', 4, 0, 1), ('he', 9, 0, 1), ('tri', 8, 14, 1),
    (P['span1'], 1, 1, 1), ('es', 1, 0, 1),
    (P['span12'], 2, 12, 1), (P['span12'][2] + 'ec', 4, 12, 0), ('gnu', 2, 12, 0),
    (P['span13b'], 10, 13, 1), (P['span13b'][3] + 'e', 13, 13, 0), ('je', 12, 14, 1),
]
fails = []
for (w, x, y, h) in steps:
    if not play(w, x, y, h): fails.append((w, x, y, h))
print(f"keten-fails: {fails}", flush=True)
# vullers
wl = [w for w in words if 2 <= len(w) <= 8]
random.shuffle(wl); wl = wl[:150000]
for rnd in range(25):
    anchors = [(x, y) for y in range(H) for x in range(W) if grid[y][x]]
    random.shuffle(anchors)
    prog = False
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
# SLOTZETTEN LAATST
s7 = play(R7, 0, 7, 1, final=True)
s0 = play(R0, 0, 0, 1, final=True)
s14 = play(R14, 0, 14, 1, final=True)
nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
tot, per, ok2, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"SPEL: zetten={len(moves)} tegels={nt} score={tot} ok={ok2} ({msg}) slot=({s7},{s0},{s14})", flush=True)
out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
       'blanks': [list(b) for b in blankcells], 'total': int(tot), 'plan': plan}
json.dump(out, open(f'experiments/results/maxgame_play3_{os.environ.get("SEED","1")}.json', 'w'))
BEST = 'experiments/results/maxgame_BEST.json'
prev = 0
if os.path.exists(BEST):
    prev = json.load(open(BEST)).get('total', 0)
if ok2 and tot > prev:
    json.dump(out, open(BEST, 'w'))
    print(f"*** NIEUW RECORD {tot} (was {prev}) -> maxgame_BEST.json ***", flush=True)
