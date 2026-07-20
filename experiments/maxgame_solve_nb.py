"""Algemene skelet-solver: gegeven triple + maskers, verbind ALLE anker-pre-runs via backtracking
(brug -> verticale connector -> span), met snapshot/restore + score_game-validatie. Geen hand-patches.
R7-connector (opening+teee+je) blijft vast; R0/R14-pre-runs worden generiek verbonden."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, 'experiments')
os.environ['N15_LANG'] = 'dutch2026'
from collections import Counter
import maxgame_score as MG
r = MG.r; cba = r.alphabet.cba; lk = MG.lk
def isw(s): return tuple(cba[c] for c in s) in lk
val = {ch: r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
random.seed(int(os.environ.get('SEED', '1')))
words = r.words_str
byl = {L: [w for w in words if len(w) == L] for L in range(2, 9)}
bag0 = Counter({chr(96+c): r.counts[c] for c in r.counts})

R0 = os.environ.get('MGR0', 'vluchtreflexjes')
R14 = os.environ.get('MGR14', 'chequeformulier')
R7 = os.environ.get('MGR7', 'babyzwemmertjes')
C7 = R7[4:11]
import ast
M0 = ast.literal_eval(os.environ.get('MGM0', '(0,6,7,8,9,11,14)'))
M14 = ast.literal_eval(os.environ.get('MGM14', '(0,3,5,7,8,11,14)'))
M7 = (0, 1, 2, 3, 11, 13, 14)

grid = [[0]*15 for _ in range(15)]
moves = []; used = Counter(); blankcells = set(); blanks_left = r.blank_count
MASKC = {(c, 0) for c in M0} | {(c, 7) for c in M7} | {(c, 14) for c in M14}

def snap(): return ([row[:] for row in grid], [m[:] for m in moves], Counter(used), set(blankcells), blanks_left)
def restore(st):
    global blanks_left
    g, m, u, b, bl = st
    for y in range(15): grid[y][:] = g[y]
    moves[:] = [x[:] for x in m]; used.clear(); used.update(u)
    blankcells.clear(); blankcells.update(b); blanks_left = bl

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

def preruns(w, mask):
    pre = [c for c in range(15) if c not in mask]; out = []; i = 0
    while i < len(pre):
        j = i
        while j+1 < len(pre) and pre[j+1] == pre[j]+1: j += 1
        out.append(list(range(pre[i], pre[j]+1))); i = j+1
    return out

# ---- gegeneraliseerde R7-kant: opening-window + plank+connector per pre-cel (backtracking) ----
def connect_r7_run(run):
    """probeer de R7-pre-run te verbinden; yield True als geplaatst (grid gemuteerd). Backtrackt zelf niet
    over meerdere opties -> caller doet dat via snapshot. Retourneert lijst van (snapshot-na) opties?
    Simpeler: generator van succesvolle plaatsingen."""
    wr=''.join(R7[c] for c in run)
    opencols=OPEN[0]
    base=snap()
    # (a) grenst aan opening
    if (run[0]-1 in opencols or run[-1]+1 in opencols):
        st=snap()
        if play(wr, run[0], 7, 1): yield snap()
        restore(st)
    # (b) plank rij8 + connector
    for c in run:
        for sstart in sorted(opencols):
            lo,hi=min(sstart,c),max(sstart,c); Lp=hi-lo+1
            if Lp<2 or Lp>7: continue
            for shelf in byl.get(Lp,[]):
                bad=False
                for t,col in enumerate(range(lo,hi+1)):
                    if grid[7][col] and not isw(chr(96+grid[7][col])+shelf[t]): bad=True; break
                if bad: continue
                st=snap()
                if not play(shelf, lo, 8, 1): restore(st); continue
                cn=R7[c]+chr(96+grid[8][c])
                if isw(cn) and play(cn, c, 7, 0):
                    if len(run)==1 or all(grid[7][cc] for cc in run) or play(wr,run[0],7,1):
                        yield snap()
                restore(st)
    restore(base)

OPEN=[None]
def build_r7():
    # openingswoorden: elk deelwoord R7[a:b] door center (a<=7<b), lengte 7..2 (prefer langer=bingo)
    cands=[]
    for Ln in range(7,1,-1):
        for a in range(max(0,7-Ln+1), min(7,15-Ln)+1):
            b=a+Ln
            if a<=7<b and isw(R7[a:b]): cands.append((a,b))
    for (a,b) in cands:
        st=snap()
        if not play(R7[a:b], a, 7, 1): restore(st); continue
        opencols=set(range(a,b)); OPEN[0]=opencols
        pre=sorted(c for c in range(15) if c not in M7 and c not in opencols)
        runs=[]; i=0
        while i<len(pre):
            j=i
            while j+1<len(pre) and pre[j+1]==pre[j]+1: j+=1
            runs.append(pre[i:j+1]); i=j+1
        def rec(idx):
            if idx==len(runs):
                st2=snap()
                if play(R7,0,7,1,final=True): return True
                restore(st2); return False
            for snapshot in connect_r7_run(runs[idx]):
                restore(snapshot)
                if rec(idx+1): return True
            return False
        if rec(0): return True
        restore(st)
    return False

# ---- generieke pre-run-verbinding: GENERATOR van alle connectie-opties (snapshots) ----
def connect_prerun(row, run, is_top):
    W = R0 if is_top else R14
    word = ''.join(W[c] for c in run); x0 = run[0]
    base = snap()
    # (a) horizontaal sub-woord (haakt aan bestaande brug-cel)
    if len(run) >= 2:
        st = snap()
        if play(word, x0, row, 1): yield snap()
        restore(st)
    # (b) verticale brug op run-kolom
    for c in run:
        st = snap()
        top_letter = W[c]; cross = R7[c]; placed = False
        for w8 in byl[8]:
            if is_top and w8[0]==top_letter and w8[7]==cross and play(w8, c, 0, 0): placed=True; break
            if not is_top and w8[0]==cross and w8[7]==top_letter and play(w8, c, 7, 0): placed=True; break
        if placed and (len(run)==1 or all(grid[row][cc] for cc in run) or play(word,x0,row,1)):
            yield snap()
        restore(st)
    # (c) verticale 2-connector
    for c in run:
        st = snap(); ok=False
        if is_top:
            for x in 'abcdefghijklmnopqrstuvwxyz':
                if isw(W[c]+x) and play(W[c]+x, c, 0, 0): ok=True; break
        else:
            for x in 'abcdefghijklmnopqrstuvwxyz':
                if isw(x+W[c]) and play(x+W[c], c, 13, 0): ok=True; break
        if ok and (len(run)==1 or all(grid[row][cc] for cc in run) or play(word,x0,row,1)):
            yield snap()
        restore(st)
    # (d) horizontale span rij1/rij13 naar bestaande cel
    sr = 1 if is_top else 13
    for c in run:
        for bc in list(range(c-1,-1,-1))+list(range(c+1,15)):
            if not grid[sr][bc]: continue
            lo,hi=min(c,bc),max(c,bc); Lh=hi-lo+1
            if Lh<2 or Lh>7: break
            for w in byl.get(Lh,[]):
                if w[bc-lo]!=chr(96+grid[sr][bc]): continue
                bad=False
                for kk,col in enumerate(range(lo,hi+1)):
                    if grid[row][col] and not (isw(chr(96+grid[row][col])+w[kk]) if is_top
                                               else isw(w[kk]+chr(96+grid[row][col]))): bad=True; break
                if bad: continue
                st=snap()
                if not play(w, lo, sr, 1): restore(st); continue
                good=False
                if len(run)==1:
                    if grid[row][c]: good=True
                    elif is_top and isw(W[c]+chr(96+grid[sr][c])) and play(W[c]+chr(96+grid[sr][c]),c,row,0): good=True
                    elif not is_top and isw(chr(96+grid[sr][c])+W[c]) and play(W[c],c,row,1): good=True
                elif play(word,x0,row,1): good=True
                if good: yield snap()
                restore(st)
            break
    restore(base)

def solve():
    if not build_r7(): return None, "R7 faalt"
    runs0 = preruns(R0, M0); runs14 = preruns(R14, M14)
    # verbind alle pre-runs (backtracking-orde: grootste eerst)
    allruns = [(0, run, True) for run in runs0] + [(14, run, False) for run in runs14]
    allruns.sort(key=lambda t: (len(t[1]) == 1, -len(t[1])))
    def bt(i):
        if i == len(allruns): return True
        row, run, top = allruns[i]
        if all(grid[row][c] for c in run): return bt(i+1)
        for snapshot in connect_prerun(row, run, top):
            restore(snapshot)
            if bt(i+1): return True
        return False
    if not bt(0): return None, "pre-run-verbinding faalt"
    s0 = play(R0, 0, 0, 1, final=True)
    s14 = play(R14, 0, 14, 1, final=True)
    if not (s0 and s14): return None, f"completie faalt (R0={s0} R14={s14})"
    return snap(), "OK"

st, msg = solve()
if st: restore(st)
nt = sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot, per, ok, m2 = MG.score_game([row[:] for row in grid], moves, blankcells)
print(f"solve: {msg} | zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} ({m2})", flush=True)
if st and ok:
    out = {'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
           'blanks': [list(b) for b in blankcells], 'total': int(tot), 'triple': [R0, R7, R14]}
    json.dump(out, open('experiments/results/maxgame_solve.json', 'w'))
    print("*** SKELET SLUIT ***", flush=True)
