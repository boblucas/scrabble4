"""Mask-AWARE decompositie van een mg_decomp_{tag}.json (verbonden eindbord + M0/M7/M14).
Pre-bord = eindbord minus de 21 masker-cellen. Decomponeer pre-bord greedy in legale prep-zetten
(vanaf center), append dan de 3 slot-zetten (R0-masker ×27, R14-masker ×27, R7-masker ×9) als LAATSTE
zetten. score_game = arbiter (multipliers + kruiswoorden). Env: MGTAG (welke mg_decomp), MGOUT."""
import sys, os, json, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ.setdefault('N15_LANG','dutch2026')
from collections import Counter
import maxgame_score as MG
r=MG.r;lk=MG.lk
TAG=os.environ.get('MGTAG','x')
D=json.load(open(f'experiments/results/mg_decomp_{TAG}.json'))
grid=[row[:] for row in D['grid']];M0=set(D['M0']);M7=set(D['M7']);M14=set(D['M14'])
R0,R7,R14=D['triple'][0],D['triple'][1],D['triple'][2]
cba=r.alphabet.cba
W=H=15
# solver bewaart het PRE-bord (masker-cellen leeg). Reconstrueer het VOLLEDIGE bord: vul ankerrijen.
for y,Wd in ((0,R0),(7,R7),(14,R14)):
    for c in range(15): grid[y][c]=cba[Wd[c]]
maskcells={(c,0) for c in M0}|{(c,7) for c in M7}|{(c,14) for c in M14}
def isw_codes(t): return tuple(t) in lk
def runs_legal(pl):
    for y in range(H):
        x=0
        while x<W:
            if not pl[y][x]:x+=1;continue
            x2=x
            while x2<W and pl[y][x2]:x2+=1
            if x2-x>=2 and not isw_codes([grid[y][k] for k in range(x,x2)]):return False
            x=x2
    for x in range(W):
        y=0
        while y<H:
            if not pl[y][x]:y+=1;continue
            y2=y
            while y2<H and pl[y2][x]:y2+=1
            if y2-y>=2 and not isw_codes([grid[k][x] for k in range(y,y2)]):return False
            y=y2
    return True
# pre-bord lijnen (segmenten van niet-masker eindbordcellen)
pre=[[ (grid[y][x] if (x,y) not in maskcells else 0) for x in range(W)] for y in range(H)]
lines=[]
for y in range(H):
    x=0
    while x<W:
        if not pre[y][x]:x+=1;continue
        x2=x
        while x2<W and pre[y][x2]:x2+=1
        if x2-x>=2: lines.append([(k,y) for k in range(x,x2)])
        x=x2
for x in range(W):
    y=0
    while y<H:
        if not pre[y][x]:y+=1;continue
        y2=y
        while y2<H and pre[y2][x]:y2+=1
        if y2-y>=2: lines.append([(x,k) for k in range(y,y2)])
        y=y2
npre=sum(1 for y in range(H) for x in range(W) if pre[y][x])
def solve_pre():
    pl=[[False]*W for _ in range(H)];moves=[];t0=time.time()
    # eerste zet moet center (7,7) bevatten
    while sum(sum(row) for row in pl)<npre:
        if time.time()-t0>600: return None,moves,pl
        best=None
        for line in lines:
            n=len(line)
            for i in range(n):
                for j in range(i,n):
                    seg=line[i:j+1]
                    new=[(x,y) for (x,y) in seg if not pl[y][x]]
                    if not(1<=len(new)<=7): continue
                    if not moves:
                        if (7,7) not in new: continue
                    else:
                        touch=any(pl[y][x] for (x,y) in seg) or any(
                            0<=x+dx<W and 0<=y+dy<H and pl[y+dy][x+dx]
                            for (x,y) in new for dx,dy in((1,0),(-1,0),(0,1),(0,-1)))
                        if not touch: continue
                    for (x,y) in new: pl[y][x]=True
                    ok=runs_legal(pl)
                    if ok:
                        sc=len(new)+(50 if len(new)==7 else 0)
                        if best is None or sc>best[0]: best=(sc,[tuple(c) for c in new])
                    for (x,y) in new: pl[y][x]=False
        if best is None: return False,moves,pl
        for (x,y) in best[1]: pl[y][x]=True
        moves.append(best[1])
    return True,moves,pl
ok,moves,pl=solve_pre()
rest=sum(1 for y in range(H) for x in range(W) if pre[y][x] and not pl[y][x])
print(f"# pre-decompositie ok={ok} prep-zetten={len(moves)} onplaatsbaar={rest}",flush=True)
if not ok:
    print(f"DECOMP {TAG}: pre-bord niet decomponeerbaar",flush=True);sys.exit(0)
# append de 3 slot-zetten (masker-cellen), volgorde 7->0->14 (elke moet legaal aanhaken)
slot={7:sorted(M7),0:sorted(M0),14:sorted(M14)}
allmoves=[m for m in moves]
for yrow in (7,0,14):
    mv=[(c,yrow) for c in slot[yrow]]
    allmoves.append(mv)
# blanks: overflow tegels als blanco. Kies de GOEDKOOPSTE cellen (laagste letterwaarde × premie-positie)
# om scoreverlies te minimaliseren; sta ALLE cellen toe (ook ankerrijen) want overflow kan daar zitten.
blanks=set()
bag=Counter({chr(96+c):r.counts[c] for c in r.counts})
cnt=Counter()
for y in range(H):
    for x in range(W):
        if grid[y][x]: cnt[chr(96+grid[y][x])]+=1
over=[ch for ch in cnt if cnt[ch]>bag[ch] for _ in range(cnt[ch]-bag[ch])]
# premie-map (dubbel/drievoud letter/woord) om goedkoopste blank-cel te kiezen
def cellcost(x,y,ch):
    lv=r.scores[ord(ch)-96]
    # ruwe premie-benadering: TWS-kolommen 0,7,14 op ankerrijen zijn duur -> vermijd
    prem=1
    if y in (0,14) and x in (0,7,14): prem=27
    elif y==7 and x in (0,14): prem=9
    return lv*prem
for ch in over:
    best=None
    for y in range(H):
        for x in range(W):
            if grid[y][x]==ord(ch)-96 and (x,y) not in blanks:
                cost=cellcost(x,y,ch)
                if best is None or cost<best[0]: best=(cost,x,y)
    if best: blanks.add((best[1],best[2]))
tot,per,vok,msg=MG.score_game([row[:] for row in grid],allmoves,blanks)
print(f"DECOMP {TAG}: ECHTE SPELSCORE={int(tot)} zetten={len(allmoves)} blanks={len(blanks)} ok={vok} ({msg})",flush=True)
if vok:
    out=os.environ.get('MGOUT',f'experiments/results/mg_game_{TAG}.json')
    json.dump({'grid':grid,'moves':[[list(c) for c in mv] for mv in allmoves],
               'blanks':[list(b) for b in blanks],'total':int(tot),'triple':D['triple']},open(out,'w'))
    print(f"*** GELDIG BEREIKBAAR SPEL score={int(tot)} -> {out} ***",flush=True)
