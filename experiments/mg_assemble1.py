"""Assemblage-poging reachable top-10 #1: opening(vert kol7) + support-rijen + struts + finals.
Elke zet via play() (score_game-compatibel). Backtracking op woordkeuzes per pre-run."""
import sys, os, json, random
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
val={ch:r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
random.seed(int(os.environ.get('SEED','1')))
words=r.words_str;byl={L:[w for w in words if len(w)==L] for L in range(2,9)}
bag0=Counter({chr(96+c):r.counts[c] for c in r.counts})
R0,R14,R7='bouwcuratrixjes','geschenkcheques','playoffticketje'
M0=(0,1,3,5,7,11,14);M14=(0,3,7,8,11,12,14);M7=(0,3,6,9,11,12,14)
ROWS={0:(R0,M0),7:(R7,M7),14:(R14,M14)}
grid=[[0]*15 for _ in range(15)]
moves=[];used=Counter();blankcells=set();blanks_left=r.blank_count
MASKC={(c,y) for y,(W,M) in ROWS.items() for c in M}
def snap():return([row[:] for row in grid],[m[:] for m in moves],Counter(used),set(blankcells),blanks_left)
def restore(st):
    global blanks_left
    g,m,u,b,bl=st
    for y in range(15):grid[y][:]=g[y]
    moves[:]=[x[:] for x in m];used.clear();used.update(u);blankcells.clear();blankcells.update(b);blanks_left=bl
def play(word,x,y,h,final=False):
    global blanks_left
    dx,dy=(1,0) if h else (0,1)
    if x<0 or y<0 or x+dx*(len(word)-1)>14 or y+dy*(len(word)-1)>14:return False
    px,py=x-dx,y-dy
    if 0<=px<15 and 0<=py<15 and grid[py][px]:return False
    ex,ey=x+dx*len(word),y+dy*len(word)
    if 0<=ex<15 and 0<=ey<15 and grid[ey][ex]:return False
    new=[];need=Counter();byc={};cross=False
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx]!=cba[ch]:return False
            cross=True
        else:
            if not final and (cx,cy) in MASKC:return False
            new.append((cx,cy));need[ch]+=1;byc.setdefault(ch,[]).append((cx,cy))
    if not new or len(new)>7:return False
    if moves:
        if not cross and not any(0<=nx+a<15 and 0<=ny+b<15 and grid[ny+b][nx+a] for (nx,ny) in new for a,b in((1,0),(-1,0),(0,1),(0,-1))):return False
    elif (7,7) not in new:return False
    ov=sum(max(0,used[ch]+n-bag0[ch]) for ch,n in need.items())
    if ov>(blanks_left if final else 0):return False
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if not grid[cy][cx]:grid[cy][cx]=cba[ch]
    okr=True
    for yy in range(15):
        xx=0
        while xx<15:
            if not grid[yy][xx]:xx+=1;continue
            x2=xx
            while x2<15 and grid[yy][x2]:x2+=1
            if x2-xx>=2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx,x2))):okr=False
            xx=x2
    for xx in range(15):
        yy=0
        while yy<15:
            if not grid[yy][xx]:yy+=1;continue
            y2=yy
            while y2<15 and grid[y2][xx]:y2+=1
            if y2-yy>=2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy,y2))):okr=False
            yy=y2
    if not okr:
        for(cx,cy) in new:grid[cy][cx]=0
        return False
    for ch,n in need.items():
        o2=max(0,used[ch]+n-bag0[ch]);used[ch]+=n
        for k in range(o2):blankcells.add(byc[ch][k]);blanks_left-=1
    moves.append(new)
    return True
def preruns(W,M):
    pre=[c for c in range(15) if c not in M];o=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1:j+=1
        o.append(list(range(pre[i],pre[j]+1)));i=j+1
    return o
log=[]
def L(n,res):log.append((n,res));return res
# 1) opening verticaal kol7 rijen4-10 (bingo), idx3=(7,7)=R7[7]
opok=False
for w in byl[7]:
    if w[3]==R7[7] and play(w,7,4,0):opok=True;L('opening',w);break
# 2) R7 pre-runs: [7,8] grenst aan (7,7); leg horizontaal vanaf (7,7). rest via struts later
# strategie: bouw rij 7 zo veel mogelijk als horizontale pre-run-woordjes die aan opening haken
# 3) support-rij 1 onder R0-pre-runs + R0-pre-run-woordjes; verbind via struts naar opening
# 4) support-rij 13 onder R14; 5) finals
# -- vereenvoudigde greedy: probeer alles, rapporteer hoever
def try_row(y, updown):
    W,M=ROWS[y]
    for run in preruns(W,M):
        wr=''.join(W[c] for c in run)
        if len(run)>=2:
            if play(wr,run[0],y,1): L(f'r{y}-run{run}',wr); continue
        # enkele cel of niet-verbonden: probeer verticale connector
        placed=False
        for c in run:
            for x in 'abcdefghijklmnopqrstuvwxyz':
                if updown=='down' and isw(W[c]+x) and play(W[c]+x,c,y,0):placed=True;break
                if updown=='up' and isw(x+W[c]) and play(x+W[c],c,y-1,0):placed=True;break
            if placed:
                if len(run)==1 or all(grid[y][cc] for cc in run) or play(wr,run[0],y,1):break
        L(f'r{y}-run{run}',placed)
try_row(7,'down')
try_row(0,'down')
try_row(14,'up')
s7=play(R7,0,7,1,final=True);s0=play(R0,0,0,1,final=True);s14=play(R14,0,14,1,final=True)
for n,res in log:print(f"  {n}: {res}",flush=True)
nt=sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot,per,ok,msg=MG.score_game([row[:] for row in grid],moves,blankcells)
print(f"\nASSEMBLAGE: zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} slot=({s7},{s0},{s14})",flush=True)
if ok and s7 and s0 and s14:
    print("*** REACHABLE TOP-10 SLUIT ***",flush=True)
    json.dump({'grid':grid,'moves':[[list(c) for c in mv] for mv in moves],'blanks':[list(b) for b in blankcells],'total':int(tot),'triple':[R0,R7,R14]},open('experiments/results/mg_top10_1.json','w'))
