"""Algemene constructie ZONDER opening/bingo-eis op R7 (bob's idee): verticale kol-7-seed door (7,7)
+ bruggen (up: rij0-7, dn: rij7-14) die pre-cellen van ALLE DRIE de 15-woorden scaffolden;
R7 net als R0/R14 afgemaakt met een ×9-slotzet. Alle stappen score_game-gevalideerd.
Env: MGR0/MGR14/MGR7 + MGM0/MGM14/MGM7 (maskers). Doel: sluit een top-10-triple."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import ast
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[c] for c in s) in lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
random.seed(int(os.environ.get('SEED', '1')))
words = r.words_str
byl = {L: [w for w in words if len(w) == L] for L in range(2, 9)}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})
R0 = os.environ['MGR0']; R14 = os.environ['MGR14']; R7 = os.environ['MGR7']
M0 = ast.literal_eval(os.environ['MGM0'])
M14 = ast.literal_eval(os.environ['MGM14'])
M7 = ast.literal_eval(os.environ['MGM7'])
ROWS = {0: (R0, M0), 7: (R7, M7), 14: (R14, M14)}

grid = [[0]*15 for _ in range(15)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = {(c, y) for y, (W, M) in ROWS.items() for c in M}

def snap(): return ([row[:] for row in grid], [m[:] for m in moves], Counter(used), set(blankcells), blanks_left)
def restore(st):
    global blanks_left
    g, m, u, b, bl = st
    for y in range(15): grid[y][:] = g[y]
    moves[:] = [x[:] for x in m]; used.clear(); used.update(u); blankcells.clear(); blankcells.update(b); blanks_left = bl

def play(word, x, y, h, final=False):
    global blanks_left
    dx, dy = (1, 0) if h else (0, 1)
    if x < 0 or y < 0 or x+dx*(len(word)-1) > 14 or y+dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < 15 and 0 <= py < 15 and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < 15 and 0 <= ey < 15 and grid[ey][ex]: return False
    new = []; need = Counter(); byc = {}; cross = False
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
                                 for (nx, ny) in new for a, b in ((1,0),(-1,0),(0,1),(0,-1))): return False
    elif (7, 7) not in new: return False
    ov = sum(max(0, used[ch]+n-bag0[ch]) for ch, n in need.items())
    if ov > (blanks_left if final else 0): return False
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

def preruns(W, M):
    pre = [c for c in range(15) if c not in M]; out = []; i = 0
    while i < len(pre):
        j = i
        while j+1 < len(pre) and pre[j+1] == pre[j]+1: j += 1
        out.append(list(range(pre[i], pre[j]+1))); i = j+1
    return out

# ---- 1) VERTICALE kol-7-opening door (7,7)=R7[7] ----
def open_col7():
    tgt = R7[7]
    cands = []
    for L in (7, 6, 5, 4, 3, 2):
        for a in range(max(0, 8-L), 8):
            b = a+L
            if not (a <= 7 < b): continue
            for w in byl[L]:
                if w[7-a] == tgt: cands.append((w, a))
    random.shuffle(cands)
    for (w, a) in cands[:2000]:
        # opening mag geen R7-maskercel op rij 7 raken behalve (7,7); en (7,7) niet in M7
        if 7 in M7: return None
        st = snap()
        if play(w, 7, a, 0): return (w, a)
        restore(st)
    return None

# ---- 2) bruggen: up (kol c, rij0..7) w[0]=R0[c],w[7]=R7[c]; dn (kol c, rij7..14) w[0]=R7[c],w[7]=R14[c]
#         een brug plaatst tegelijk pre-cellen van 2 rijen. Backtracking over kolommen voor connectiviteit.
def up_words(c): return [w for w in byl[8] if w[0] == R0[c] and w[7] == R7[c]]
def dn_words(c): return [w for w in byl[8] if w[0] == R7[c] and w[7] == R14[c]]

def connect_run(y, run):
    """verbind pre-run van rij y: via brug (levert (c,y)) of horizontaal subwoord of korte connector."""
    W, M = ROWS[y]
    word = ''.join(W[c] for c in run); x0 = run[0]
    base = snap()
    if len(run) >= 2:
        st = snap()
        if play(word, x0, y, 1): yield snap()
        restore(st)
    for c in run:
        # brug door deze cel
        cands = up_words(c) if y in (0, 7) else []
        if y == 7:
            cands = up_words(c) + dn_words(c)
        if y == 0: cands = up_words(c)
        if y == 14: cands = dn_words(c)
        for w8 in cands:
            st = snap()
            y8 = 0 if (y == 0 or (y == 7 and w8 in up_words(c))) else 7
            if play(w8, c, y8, 0):
                if len(run) == 1 or all(grid[y][cc] for cc in run) or play(word, x0, y, 1):
                    yield snap()
            restore(st)
    # korte verticale connector (2-4 tegels) vanaf ankercel, evt + horizontale schakel op tussenrij
    for c in run:
        for L in (2, 3, 4):
            vwords = ([w for w in byl[L] if w[0] == W[c]] if y == 0 else
                      [w for w in byl[L] if w[L-1] == W[c]] if y == 14 else [])
            random.shuffle(vwords)
            for vw in vwords[:60]:
                st = snap()
                vy = 0 if y == 0 else (14-L+1)
                if not play(vw, c, vy, 0): restore(st); continue
                # verticaal staat; nu run-woord (indien lengte>1) + check connectie
                placed_run = (len(run) == 1) or all(grid[y][cc] for cc in run) or play(word, x0, y, 1)
                if not placed_run: restore(st); continue
                # als de verticaal al aan bestaande structuur raakt: klaar
                touch = any(0 <= c+a < 15 and 0 <= vy+j+b < 15 and grid[vy+j+b][c+a]
                            for j in range(L) for a, b in ((1,0),(-1,0)))
                if touch: yield snap()
                else:
                    # horizontale schakel op de onderste/bovenste tussenrij naar bestaande tegel
                    hr = vy+L-1 if y == 0 else vy   # tussenrij-cel van de verticaal (niet op ankerrij)
                    hookcol = c
                    # zoek dichtstbijzijnde bezette cel op rij hr
                    for bc in range(15):
                        if grid[hr][bc] and bc != c:
                            lo, hi = min(c, bc), max(c, bc); Lh = hi-lo+1
                            if 2 <= Lh <= 7:
                                for hw in byl.get(Lh, []):
                                    if hw[c-lo] == chr(96+grid[hr][c]) and hw[bc-lo] == chr(96+grid[hr][bc]):
                                        st2 = snap()
                                        if play(hw, lo, hr, 1): yield snap()
                                        restore(st2)
                            break
                restore(st)
    restore(base)

def solve():
    if 7 in M7: return None, "center in M7 (ongeldig)"
    o = open_col7()
    if not o: return None, "geen kol-7-opening"
    allruns = []
    for y in (0, 7, 14):
        W, M = ROWS[y]
        for run in preruns(W, M): allruns.append((y, run))
    import time as _t
    t_end = _t.time() + float(os.environ.get('MGTL','80'))
    def done(): return all(all(grid[y][c] for c in run) for (y,run) in allruns)
    def bt():
        if _t.time() > t_end: return False
        if done(): return True
        # kies elke run die nog niet ligt; probeer verbindingsopties; recurse
        rem = [(y,run) for (y,run) in allruns if not all(grid[y][c] for c in run)]
        # prioriteer runs met de minste opties (fail-first) — hier: probeer allemaal
        for (y,run) in rem:
            got=False
            for snapshot in connect_run(y, run):
                restore(snapshot); got=True
                if bt(): return True
            if got:
                # deze run had opties maar geen leidde tot succes -> herstel gebeurt in connect_run's restore
                pass
        return False
    if not bt(): return None, "pre-run-verbinding faalt"
    res = {}
    for y in (7, 0, 14):
        W, M = ROWS[y]
        res[y] = play(W, 0, y, 1, final=True)
    if not all(res.values()): return None, f"completie faalt {res}"
    return snap(), "OK"

st, msg = solve()
if st: restore(st)
nt = sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot, per, ok, m2 = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"solve4: {msg} | zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok}", flush=True)
if st and ok:
    json.dump({'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
               'blanks': [list(b) for b in blankcells], 'total': int(tot), 'triple': [R0, R7, R14]},
              open('experiments/results/maxgame_solve4.json', 'w'))
    print("*** SKELET SLUIT (verticale-opening-constructie) ***", flush=True)
