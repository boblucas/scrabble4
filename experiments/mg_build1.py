"""Reachable top-10 #1 constructor. Fasen: opening(vert kol7) -> up/down-connectie naar rij0/14
via horizontale schakel op tussenrij + verticale strut -> support-rijen(1/13) -> pre-runs -> finals.
Backtracking op woordkeuzes; elke zet via play() (score_game-compatibel)."""
import sys, os, json, random
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
after={c:{x for x in A if isw(c+x)} for c in A}
before={c:{x for x in A if isw(x+c)} for c in A}

# Fase 1: opening verticaal kol7 rijen 1-7 (top rij1, bottom (7,7)) -> reikt tot rij1 (support-rij!)
def place_opening():
    cand=[w for w in byl[7] if w[6]==R7[7]]  # idx6=(7,7)
    random.shuffle(cand)
    for w in cand:
        st=snap()
        if play(w,7,1,0): return w
        restore(st)
    return None

# Fase 2: support-rij y (1 voor R0 omlaag, 13 voor R14 omhoog) — vul woorden die pre-cellen dekken
#   en waarvan er minstens één de bestaande structuur raakt (kol 7).
def support_row(y, anchor_row, direction):
    W,M=ROWS[anchor_row]
    allow=[ (after[W[c]] if direction=='down' else before[W[c]]) for c in range(15)]
    pre=set(c for c in range(15) if c not in M)
    # plaats woorden op rij y die alleen pre-kolommen dekken (mask-kol => leeg, tenzij allow ok)
    # greedy links->rechts: voor elke run van pre-kolommen, kies een woord dat past
    for run in preruns(W,M):
        L=len(run)
        candw=[w for w in byl.get(L,[]) if all(w[i] in allow[run[i]] for i in range(L))]
        random.shuffle(candw)
        done=False
        for w in candw[:200]:
            st=snap()
            if play(w,run[0],y,1): done=True; break
            restore(st)
        # (verbinding checkt play via aanhaken; als los -> later strut)

place_opening()
support_row(1,0,'down')
support_row(13,14,'up')
# Fase 3: verticale connectoren pre-cel(anker) <-> support-rij (2-woord)
def connect_anchor(anchor_row, direction):
    W,M=ROWS[anchor_row]
    for c in range(15):
        if c in M: continue
        if grid[anchor_row][c]: continue
        sy=1 if anchor_row==0 else 13
        if not grid[sy][c]: continue  # geen support onder/boven
        # verticaal 2-woord anker+support
        if direction=='down':
            w2=W[c]+chr(96+grid[1][c])
            if isw(w2): play(w2,c,0,0)
        else:
            w2=chr(96+grid[13][c])+W[c]
            if isw(w2): play(w2,c,14,0)
connect_anchor(0,'down')
connect_anchor(14,'up')
# Fase 4: R7 pre-runs op rij 7 (haken aan opening/structuur)
for run in preruns(R7,M7):
    wr=''.join(R7[c] for c in run)
    if len(run)>=2: play(wr,run[0],7,1)
# Fase 5: finals
s7=play(R7,0,7,1,final=True);s0=play(R0,0,0,1,final=True);s14=play(R14,0,14,1,final=True)
nt=sum(1 for y in range(15) for x in range(15) if grid[y][x])
tot,per,ok,msg=MG.score_game([row[:] for row in grid],moves,blankcells)
print(f"BUILD: zetten={len(moves)} tegels={nt} score={int(tot)} ok={ok} slot=({s7},{s0},{s14}) ({msg})",flush=True)
# toon bord bij (bijna-)succes
if s7 or s0 or s14 or nt>60:
    for y in range(15): print(''.join(chr(96+grid[y][x]).upper() if grid[y][x] else '.' for x in range(15)))
if ok and s7 and s0 and s14:
    print("*** REACHABLE TOP-10 #1 SLUIT! ***",flush=True)
    json.dump({'grid':grid,'moves':[[list(c) for c in mv] for mv in moves],'blanks':[list(b) for b in blankcells],'total':int(tot),'triple':[R0,R7,R14]},open('experiments/results/mg_top10_1.json','w'))
