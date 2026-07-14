"""MAXGAME v5: triple-itererende keten-planner (2026-07-14).
plan_for_triple(R0,R7,R14): kolommen+bruggen+spans via backtracking binnen zak-budget.
Main: loop over top-triples (score-gesorteerd) tot een plan bestaat; speel; slotzetten laatst."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[ch] for ch in s) in lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
ALPH = 'abcdefghijklmnopqrstuvwxyz'
random.seed(int(os.environ.get('SEED', '1')))
words = r.words_str
AF = {c: {x for x in ALPH if isw(c+x)} for c in ALPH}
BF = {c: {x for x in ALPH if isw(x+c)} for c in ALPH}
C8 = {}
for w in words:
    if len(w) == 8: C8.setdefault((w[0], w[7]), []).append(w)
byl = {L: [w for w in words if len(w) == L] for L in (2, 3, 4, 5, 6)}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
M014 = (0, 3, 7, 11, 12, 13, 14)

def plan_for_triple(R0, R7, R14):
    C7 = R7[4:11]
    anch = Counter(R0) + Counter(R7) + Counter(R14)
    over = {ch: anch[ch]-bag0[ch] for ch in anch if anch[ch] > bag0[ch]}
    if sum(over.values()) > r.blank_count: return None
    a2 = Counter(anch)
    for ch, n in over.items(): a2[ch] -= n
    budget = Counter(bag0); budget.subtract(a2)
    SP1 = {}; SP13 = {}
    for L in (4, 5, 6):
        for w in byl[L]:
            if all(w[c-1] in AF[R0[c]] for c in range(1, L)):
                SP1.setdefault((L, w[L-1]), []).append(w)
            if all(w[c-1] in BF[R14[c]] for c in range(1, L)):
                SP13.setdefault((L, w[L-1]), []).append(w)
    SP8 = []
    for L, x0 in ((3, 10), (4, 9)):
        off = 11 - x0
        for w in byl[L]:
            if x0 == 9 and w[0] not in AF[C7[5]]: continue
            if w[off-1] not in AF[C7[6]]: continue
            if w[off] in AF[R7[11]] and w[off+1] in AF[R7[12]] and isw(R7[12]+w[off+1]):
                SP8.append((w, x0, 'A'))
    for w in byl[4]:
        if w[0] in AF[C7[6]] and w[1] in AF[R7[11]] and w[2] in AF[R7[12]] \
           and w[3] in AF[R7[13]] and isw(R7[13]+w[3]) and isw(R7[12]+w[2]):
            SP8.append((w, 10, 'B'))
    if not SP8: return None
    def bridge(kind, c):
        return C8.get((R0[c], C7[c-4]) if kind == 'up' else (C7[c-4], R14[c]), [])
    def newlet(name, w):
        if name.startswith(('up', 'dn')): return w[1:7]
        if name in ('span1', 'span13'): return w[:-1]
        if name == 'span8':
            t, x0, _ = w
            return ''.join(t[c-x0] for c in range(x0, x0+len(t)) if c != do_now[0])
        return ''
    plan = {}
    def bt(slots, i, rem):
        if i == len(slots): return True
        name, gen = slots[i]
        cl = list(gen(plan)); random.shuffle(cl)
        for w in cl[:120]:
            need = Counter(newlet(name, w))
            if any(rem[ch] < n for ch, n in need.items()): continue
            plan[name] = w
            r2 = Counter(rem); r2.subtract(need)
            if bt(slots, i+1, r2): return True
            del plan[name]
        return False
    do_now = [None]
    cols = [(uw, uo, dw, do) for uw in (4, 5, 6) for uo in (8, 9, 10)
            for dw in (4, 5, 6) if dw != uw for do in (8, 9, 10) if do != uo]
    random.shuffle(cols)
    for (uw, uo, dw, do) in cols:
        plan.clear(); do_now[0] = do
        def sp8_ok(st, t):
            w, x0, v = t
            for col in range(x0, x0+len(w)):
                if col == uo: return False   # cel onder up-brug -> illegale 9-run
                if col == do and w[col-x0] != st[f'dn{do}'][1]: return False
            return True
        slots = [
            ('span1', lambda st, c=uw: [w for ch in {b[1] for b in bridge('up', c)}
                                        for w in SP1.get((c, ch), [])]),
            (f'up{uw}', lambda st, c=uw: [b for b in bridge('up', c) if b[1] == st['span1'][-1]]),
            ('span13', lambda st, c=dw: [w for ch in {b[6] for b in bridge('dn', c)}
                                         for w in SP13.get((c, ch), [])]),
            (f'dn{dw}', lambda st, c=dw: [b for b in bridge('dn', c) if b[6] == st['span13'][-1]]),
            (f'up{uo}', lambda st, c=uo: bridge('up', c)),
            (f'dn{do}', lambda st, c=do: bridge('dn', c)),
            ('span8', lambda st: [t for t in SP8 if sp8_ok(st, t)]),
        ]
        if bt(slots, 0, Counter(budget)):
            plan['cols'] = (uw, uo, dw, do); plan['over'] = over
            return dict(plan)
    return None

# ---------- triple-lijst ----------
w15 = [w for w in words if len(w) == 15]
def rowscore(w, wm): return wm*(sum(val[c] for c in w)+val[w[3]]+val[w[11]])+50
c7ok = sorted(((rowscore(w, 9), w) for w in w15 if isw(w[4:11])), reverse=True)
upok = sorted(((rowscore(w, 27), w) for w in w15
               if isw(w[1:3]) and isw(w[4:7]) and isw(w[8:11])), reverse=True)[:250]
triples = []
for s7, w7 in c7ok[:40]:
    for s0, w0 in upok[:120]:
        for s14, w14 in upok[:120]:
            if w14 == w0: continue
            tot = Counter(w0)+Counter(w7)+Counter(w14)
            if sum(max(0, tot[ch]-bag0.get(ch, 0)) for ch in tot) > r.blank_count: continue
            triples.append((s0+s7+s14, w0, w7, w14))
triples.sort(reverse=True)
print(f"# {len(triples)} zak-feasible triples; planner-iteratie...", flush=True)
chosen = None
for k, (sc, w0, w7, w14) in enumerate(triples[:4000]):
    p = plan_for_triple(w0, w7, w14)
    if p:
        chosen = (sc, w0, w7, w14, p)
        print(f"PLAN op triple #{k} score={sc}: r0={w0} r7={w7} r14={w14}", flush=True)
        print("PLAN:", p, flush=True)
        break
if not chosen: print("GEEN ENKEL PLAN"); sys.exit(1)
sc, R0, R7, R14, plan = chosen
C7 = R7[4:11]
M7 = (0, 1, 2, 3, 11, 13, 14) if plan['span8'][2] == 'A' else (0, 1, 2, 3, 11, 12, 14)

# ---------- speel ----------
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
            if not final:
                if (cx, cy) in MASKC: return False
                if cy == 0 and ch != R0[cx]: return False
                if cy == 7 and ch != R7[cx]: return False
                if cy == 14 and ch != R14[cx]: return False
                for (mx, my, wd) in ((cx, 0, R0), (cx, 7, R7), (cx, 14, R14)):
                    if (mx, my) in MASKC and abs(cy-my) == 1 and not grid[my][mx]:
                        L = wd[mx]
                        pair = L+ch if cy > my else ch+L
                        if not isw(pair): return False
                        oy = 2*my-cy
                        if 0 <= oy < 15 and grid[oy][mx]: return False
                        ny2 = cy+(cy-my)
                        if 0 <= ny2 < 15 and grid[ny2][mx]: return False
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
        for (ry, wd) in ((0, R0), (7, R7), (14, R14)):
            for cx2 in range(15):
                if not grid[ry][cx2] and (cx2, ry) not in new:
                    resv[wd[cx2]] += 1
        for ch, n in plan['over'].items(): resv[ch] -= n
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
sp8w, sp8x, sp8v = plan['span8']
steps = [
    (C7, 4, 7, 1),
    (plan[f'up{uw}'], uw, 0, 0), (plan[f'up{uo}'], uo, 0, 0),
    (plan[f'dn{dw}'], dw, 7, 0), (plan[f'dn{do}'], do, 7, 0),
    (R0[4:7], 4, 0, 1), (R0[8:11], 8, 0, 1), (R14[4:7], 4, 14, 1), (R14[8:11], 8, 14, 1),
    (plan['span1'], 1, 1, 1), (R0[1:3], 1, 0, 1),
    (plan['span13'], 1, 13, 1), (R14[1:3], 1, 14, 1),
    (sp8w, sp8x, 8, 1),
]
steps.append((R7[12]+sp8w[12-sp8x], 12, 7, 0) if sp8v == 'A' else (R7[13]+sp8w[13-sp8x], 13, 7, 0))
fails = [(w, x, y, h) for (w, x, y, h) in steps if not play(w, x, y, h)]
print(f"keten-fails: {fails}", flush=True)
LM = r.letter_multiplier; WM = r.word_multiplier
def est_score(w, x, y, h):
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(w)-1) > 14 or y+dy*(len(w)-1) > 14: return -1
    s = 0; wm = 1; nnew = 0; cross = 0
    for i, ch in enumerate(w):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return -1
            s += val[ch]; continue
        lm = int(LM[cy][cx]); wmc = int(WM[cy][cx])
        s += val[ch]*lm; wm *= wmc; nnew += 1
        # kruiswoord-schatting loodrecht
        cs = 0
        for d in (-1, 1):
            k = 1
            while True:
                ox, oy = cx+dy*d*k, cy+dx*d*k
                if 0 <= ox < 15 and 0 <= oy < 15 and grid[oy][ox]:
                    cs += val[chr(96+grid[oy][ox])]; k += 1
                else: break
        if cs: cross += (cs + val[ch]*lm) * wmc
    if nnew == 0 or nnew > 7: return -1
    return s*wm + cross + (50 if nnew == 7 else 0)
let2w = {}
for w in words:
    if 2 <= len(w) <= 8:
        for ch in set(w): let2w.setdefault(ch, []).append(w)
for ch in let2w:
    let2w[ch].sort(key=lambda w: -(sum(val[c] for c in w) + len(w)))
    let2w[ch] = let2w[ch][:9000]
for rnd in range(40):
    anchors = [(x, y) for y in range(15) for x in range(15) if grid[y][x]]
    random.shuffle(anchors)
    cands = []
    for (ax, ay) in anchors[:45]:
        achr = chr(96+grid[ay][ax])
        for w in let2w.get(achr, [])[:2500]:
            for i, ch in enumerate(w):
                if ch != achr: continue
                for (px, py, h) in ((ax-i, ay, 1), (ax, ay-i, 0)):
                    e = est_score(w, px, py, h)
                    if e > 0: cands.append((e, w, px, py, h))
    cands.sort(key=lambda t: (-t[0], -len(t[1])))
    played = False
    for (e, w, px, py, h) in cands[:2000]:
        if play(w, px, py, h): played = True; break
    if not played:
        # fallback: eerste-de-beste over alle woorden (dekt gaten die de top-schatting mist)
        for (ax, ay) in anchors[:70]:
            achr = chr(96+grid[ay][ax])
            for w in let2w.get(achr, []):
                done = False
                for i, ch in enumerate(w):
                    if ch != achr: continue
                    if play(w, ax-i, ay, 1) or play(w, ax, ay-i, 0): done = True; break
                if done: played = True; break
            if played: break
    if not played: break
s7 = play(R7, 0, 7, 1, final=True)
s0 = play(R0, 0, 0, 1, final=True)
s14 = play(R14, 0, 14, 1, final=True)
nt = sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot, per, ok2, msg = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"SPEL: zetten={len(moves)} tegels={nt} score={tot} ok={ok2} ({msg}) slot=({s7},{s0},{s14})", flush=True)
out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
       'blanks': [list(b) for b in blankcells], 'total': int(tot),
       'plan': {k: str(v) for k, v in plan.items()}, 'triple': [R0, R7, R14]}
json.dump(out, open(f'experiments/results/maxgame_play5_{os.environ.get("SEED","1")}.json', 'w'))
BEST = 'experiments/results/maxgame_BEST.json'
prev = json.load(open(BEST)).get('total', 0) if os.path.exists(BEST) else 0
if ok2 and tot > prev:
    json.dump(out, open(BEST, 'w'))
    print(f"*** NIEUW RECORD {tot} (was {prev}) ***", flush=True)
