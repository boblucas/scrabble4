"""Reachable top-10 #1: schone backtracking. Opening vert kol7 rijen4-10. Daarna DFS die ELKE zet
plaatst die (a) play() accepteert (cross-checks kloppen), (b) een anker-pre-cel vult of struct
uitbreidt naar een pre-cel. Doel: alle pre-cellen gevuld -> finals. Connectiviteit gegarandeerd
door play()'s aanhaak-eis."""
import sys, os, json, random, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
A='abcdefghijklmnopqrstuvwxyz'
random.seed(int(os.environ.get('SEED','1')))
words=r.words_str;byl={}
for w in words: byl.setdefault(len(w),[]).append(w)
bag0=Counter({chr(96+c):r.counts[c] for c in r.counts})
R0,R14,R7='bouwcuratrixjes','geschenkcheques','playoffticketje'
M0=(0,1,3,5,7,11,14);M14=(0,3,7,8,11,12,14);M7=(0,3,6,9,11,12,14)
ROWS={0:(R0,M0),7:(R7,M7),14:(R14,M14)}
grid=[[0]*15 for _ in range(15)]
moves=[];used=Counter();blankcells=set();blanks_left=r.blank_count
MASKC={(c,y) for y,(W,M) in ROWS.items() for c in M}
PRECELLS={(c,y) for y,(W,M) in ROWS.items() for c in range(15) if c not in M}
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

# opening
op=None
for w in byl[7]:
    if w[3]==R7[7] and play(w,7,4,0): op=w;break
def pre_open():  # aantal pre-cellen nog leeg
    return sum(1 for (c,y) in PRECELLS if not grid[y][c])
# genereer kandidaat-zetten die minstens 1 lege pre-cel vullen EN aanhaken
def gen():
    out=[]
    filled=[(x,y) for y in range(15) for x in range(15) if grid[y][x]]
    # zetten die een pre-cel vullen: verticaal vanaf anker-pre-cel, of horizontaal pre-run, of
    # support-woord op rij1/6/8/13 onder/naast pre-cel, of strut die aanhaakt
    cands=set()
    for (c,y) in PRECELLS:
        if grid[y][c]: continue
        W,M=ROWS[y]
        # horizontaal pre-run vanaf deze cel
        for L in range(2,8):
            if c+L<=15:
                run=list(range(c,c+L))
                if all(cc not in M for cc in run):
                    wr=''.join(W[cc] for cc in run)
                    if isw(wr): cands.add((wr,c,y,1))
        # verticaal 2-4 vanaf anker-pre-cel (omlaag rij0/rij7, omhoog rij14/rij7)
        for L in range(2,5):
            if y==0 or y==7:
                for vw in byl.get(L,[]):
                    if vw[0]==W[c]: cands.add((vw,c,y,0))
            if y==14 or y==7:
                for vw in byl.get(L,[]):
                    if vw[L-1]==W[c]: cands.add((vw,c,y-L+1,0))
    # support/verbind-woorden op tussenrijen naast bestaande tegels (elke lege cel adj aan filled)
    for (fx,fy) in filled:
        for (ax,ay) in ((fx+1,fy),(fx-1,fy),(fx,fy+1),(fx,fy-1)):
            if not(0<=ax<15 and 0<=ay<15) or grid[ay][ax] or (ax,ay) in MASKC: continue
            for L in range(2,7):
                for h in (0,1):
                    for off in range(L):
                        x0=ax-off*(1 if h else 0); y0=ay-off*(0 if h else 1)
                        for w in byl.get(L,[]):
                            cands.add((w,x0,y0,h))
                        break
    res=[]
    for (w,x,y,h) in cands:
        st=snap()
        if play(w,x,y,h):
            gain=pre_open(); res.append((gain,w,x,y,h,snap()))
            restore(st)
    res.sort(key=lambda t:t[0])
    return res[:30]

t0=time.time();TL=float(os.environ.get('MGTL','180'))
best_pre=[pre_open()]
def dfs(depth):
    if time.time()-t0>TL: return False
    if pre_open()==0:
        s7=play(R7,0,7,1,final=True);s0=play(R0,0,0,1,final=True);s14=play(R14,0,14,1,final=True)
        if s7 and s0 and s14: return True
        return False
    if depth>26: return False
    for gain,w,x,y,h,ss in gen()[:8]:
        restore(ss)
        if dfs(depth+1): return True
    return False
ok_build=dfs(0)
nt=sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot,per,ok,msg=MG.score_game([row[:] for row in grid],moves,blankcells)
print(f"BUILD2: sluit={ok_build} zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} pre-open={pre_open()}",flush=True)
if ok_build and ok:
    print("*** REACHABLE TOP-10 #1 SLUIT! score",int(tot),"***",flush=True)
    json.dump({'grid':grid,'moves':[[list(c) for c in mv] for mv in moves],'blanks':[list(b) for b in blankcells],'total':int(tot),'triple':[R0,R7,R14]},open('experiments/results/mg_top10_1.json','w'))
