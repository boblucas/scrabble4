"""Joint solver v2: component-reductie-DFS. Statisch bord (3 volle ankerrijen + opening kol7).
Plaats verbindingswoorden (verticale bruggen + horizontale rungs op tussenrijen) tot board-minus-mask
= 1 component, alle runs geldig, zak OK. Volledige validatie + backtracking. Dan decompose+score."""
import sys, os, json, random, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter, deque
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
words=r.words_str;byl={}
for w in words: byl.setdefault(len(w),[]).append(w)
random.seed(int(os.environ.get('SEED','1')))
import ast
R0=os.environ.get('MGR0','bouwcuratrixjes');R14=os.environ.get('MGR14','geschenkcheques');R7=os.environ.get('MGR7','playoffticketje')
M0=set(ast.literal_eval(os.environ.get('MGM0','(0,1,3,5,7,11,14)')));M14=set(ast.literal_eval(os.environ.get('MGM14','(0,3,7,8,11,12,14)')));M7=set(ast.literal_eval(os.environ.get('MGM7','(0,3,6,8,9,13,14)')))
ANCH={0:R0,7:R7,14:R14};MASK={0:M0,7:M7,14:M14}
bag=Counter({chr(96+c):r.counts[c] for c in r.counts})
G=[[0]*15 for _ in range(15)]
for y,W in ANCH.items():
    for c in range(15): G[y][c]=cba[W[c]]
freebag=Counter(bag)
for y,W in ANCH.items():
    for c in range(15): freebag[W[c]]-=1
BLANKS=r.blank_count
# opening verticaal kol7 rijen4-10
opcands=[w for w in byl[7] if w[3]==R7[7]]
random.shuffle(opcands)
for w in opcands:
    nd=Counter(w);nd[R7[7]]-=1
    if all(freebag[c]>=nd[c] for c in nd):
        # opening moet horizontale cross-checks toelaten: plaats + valideer
        for i,ch in enumerate(w): G[4+i][7]=cba[ch]
        freebag.subtract(nd);break
FREE=lambda y:1<=y<=6 or 8<=y<=13
def runs_valid_after(cells):
    rows=set(y for _,y in cells);cols=set(x for x,_ in cells)
    for y in rows:
        x=0
        while x<15:
            if not G[y][x]:x+=1;continue
            x2=x
            while x2<15 and G[y][x2]:x2+=1
            if x2-x>=2 and not isw(''.join(chr(96+G[y][k]) for k in range(x,x2))):return False
            x=x2
    for x in cols:
        y=0
        while y<15:
            if not G[y][x]:y+=1;continue
            y2=y
            while y2<15 and G[y2][x]:y2+=1
            if y2-y>=2 and not isw(''.join(chr(96+G[k][x]) for k in range(y,y2))):return False
            y=y2
    return True
def mask_vert_ok():
    for y,ms in MASK.items():
        for c in ms:
            up=[];yy=y-1
            while yy>=0 and G[yy][c]:up.append(chr(96+G[yy][c]));yy-=1
            dn=[];yy=y+1
            while yy<15 and G[yy][c]:dn.append(chr(96+G[yy][c]));yy+=1
            if up or dn:
                if not isw(''.join(reversed(up))+ANCH[y][c]+''.join(dn)):return False
    return True
def comps_minus_mask():
    G2=[row[:] for row in G]
    for y,ms in MASK.items():
        for c in ms: G2[y][c]=0
    seen=[[False]*15 for _ in range(15)];comps=0
    for y in range(15):
        for x in range(15):
            if G2[y][x] and not seen[y][x]:
                comps+=1;dq=deque([(x,y)]);seen[y][x]=True
                while dq:
                    cx,cy=dq.popleft()
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and G2[ny][nx] and not seen[ny][nx]:seen[ny][nx]=True;dq.append((nx,ny))
    return comps
def place(word,x,y,h):
    dx,dy=(1,0) if h else (0,1)
    if x<0 or y<0 or x+dx*(len(word)-1)>14 or y+dy*(len(word)-1)>14:return None
    px,py=x-dx,y-dy
    if 0<=px<15 and 0<=py<15 and G[py][px]:return None
    ex,ey=x+dx*len(word),y+dy*len(word)
    if 0<=ex<15 and 0<=ey<15 and G[ey][ex]:return None
    new=[];need=Counter()
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if G[cy][cx]:
            if G[cy][cx]!=cba[ch]:return None
        else:
            if not(FREE(cy) or cy in(0,7,14)):return None
            if cy in(0,7,14):return None  # ankercellen niet vullen (die zijn al vol)
            new.append((cx,cy));need[chr(96+cba[ch])]+=1
    if not new:return None
    if any(need[c]>freebag[c] for c in need):return None
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if not G[cy][cx]:G[cy][cx]=cba[ch]
    if not(runs_valid_after(new) and mask_vert_ok()):
        for cx,cy in new:G[cy][cx]=0
        return None
    freebag.subtract(need)
    return new
def unplace(new,need):
    for cx,cy in new:G[cy][cx]=0
    freebag.update(need)
# kandidaat-verbindingswoorden: bruggen (up/dn op pre-kolommen) + rungs (horizontaal op tussenrij naast 2 componenten)
C8={}
for w in byl[8]: C8.setdefault((w[0],w[7]),[]).append(w)
def gen_moves():
    out=[]
    # up-bruggen op R0-pre-kolommen (verbindt rij0-pre naar rij7)
    for c in range(15):
        if c not in M0 and not G[1][c]:  # nog geen brug
            for w in C8.get((R0[c],R7[c]),[]): out.append((w,c,0,0))
    for c in range(15):
        if c not in M14 and not G[13][c]:
            for w in C8.get((R7[c],R14[c]),[]): out.append((w,c,7,0))
    # rungs: horizontaal woord op tussenrij dat 2 bezette cellen (brug-interieurs) verbindt
    for y in list(range(1,7))+list(range(8,14)):
        filled=[x for x in range(15) if G[y][x]]
        for a in filled:
            for b in filled:
                if not (2<=b-a<=7): continue
                # cellen a..b: endpoints bezet, tussen leeg?
                if any(G[y][k] for k in range(a+1,b)): continue
                la=chr(96+G[y][a]);lb=chr(96+G[y][b])
                for w in byl.get(b-a+1,[]):
                    if w[0]==la and w[-1]==lb: out.append((w,a,y,1))
    random.shuffle(out)
    random.shuffle(out); return out[:250]
t0=time.time();TL=float(os.environ.get('MGTL','150'))
target=[999]
BESTB=[None]
def dfs(depth):
    if time.time()-t0>TL: return False
    cm=comps_minus_mask()
    if cm<target[0]: target[0]=cm; BESTB[0]=[row[:] for row in G]
    if cm==1: return True
    if depth>22: return False
    for (w,x,y,h) in gen_moves():
        need=Counter(chr(96+cba[ch]) for ch in w if not G[y+(0 if h else 1)* (w.index(ch))][x])
        new=place(w,x,y,h)
        if new is None: continue
        nd=Counter()
        for cx,cy in new: nd[chr(96+G[cy][cx])]+=1
        if dfs(depth+1): return True
        unplace(new,nd)
    return False
ok=dfs(0)
print(f"solver2: 1-component={ok} beste-comps={target[0]} tegels={sum(1 for y in range(15) for x in range(15) if G[y][x])}",flush=True)
if target[0]<=1 and BESTB[0]:
    print("*** VERBONDEN (decomposable) BORD GEVONDEN ***",flush=True)
    import os as _os
    tag=_os.environ.get('MGTAG','x')
    json.dump({'grid':BESTB[0],'triple':[R0,R7,R14],'M0':sorted(M0),'M7':sorted(M7),'M14':sorted(M14)},open(f'experiments/results/mg_decomp_{tag}.json','w'))
