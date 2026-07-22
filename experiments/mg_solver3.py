"""Joint solver v3 (mask-pool): per triple genereert top-K score-maskers, en zoekt per masker met
twee-fase getargete DFS (fase1 brug-ruggengraat + fase2 korte verticale connectoren/rungs op geisoleerde
pre-cellen) naar een bord waar board-minus-mask = 1 component (=decomposeerbaar/bereikbaar).
Eerste sluiting -> mg_decomp_{tag}.json (arbiter score_game bevestigt later). Env: MGR0/MGR14/MGR7,
MGKMASK (masks per triple, def 6), MGSEEDS (def 3), MGTL (sec per masker-poging, def 20)."""
import sys, os, json, random, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter, deque
from itertools import combinations
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
words=r.words_str;byl={}
for w in words: byl.setdefault(len(w),[]).append(w)
ALPH='abcdefghijklmnopqrstuvwxyz'
val={ch:r.scores[cba[ch]] for ch in ALPH}
VALBIAS=os.environ.get('MGVALBIAS','0')=='1'
def wval(w): return sum(val[c] for c in w)
def biasshuf(lst):
    # hoog-waarde eerst met lichte randomisatie (behoud diversiteit): sorteer op -waarde, shuffle top helft
    if not VALBIAS:
        random.shuffle(lst); return lst
    lst.sort(key=lambda w:-wval(w))
    k=max(1,len(lst)//2); head=lst[:k]; random.shuffle(head); return head+lst[k:]
after_ok={ch for ch in ALPH if any(isw(ch+x) for x in ALPH)}
before_ok={ch for ch in ALPH if any(isw(x+ch) for x in ALPH)}
byfirst={}; bylast={}
for L,ws in byl.items():
    for w in ws:
        byfirst.setdefault((w[0],L),[]).append(w)
        bylast.setdefault((w[-1],L),[]).append(w)
C8={}
for w in byl.get(8,[]): C8.setdefault((w[0],w[7]),[]).append(w)
bag=Counter({chr(96+c):r.counts[c] for c in r.counts})

R0=os.environ.get('MGR0','bouwcuratrixjes');R14=os.environ.get('MGR14','geschenkcheques');R7=os.environ.get('MGR7','playoffticketje')
KMASK=int(os.environ.get('MGKMASK','6'));SEEDS=int(os.environ.get('MGSEEDS','3'));TL=float(os.environ.get('MGTL','20'))
MAXV=int(os.environ.get('MGMAXV','40'))
TAG=os.environ.get('MGTAG','x')

def prl_runs(w,m):
    pre=[c for c in range(15) if c not in m];out=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1: j+=1
        out.append(list(range(pre[i],pre[j]+1)));i=j+1
    return out
def top_masks(w,ok,forced,mult,k):
    """top-k maskers op ×mult score. forced = verplichte cellen (TWS). totale maskergrootte = 7."""
    base=sum(val[c] for c in w);cands=[]
    nfree=7-len(forced)
    pool=[c for c in range(15) if c not in forced]
    for e in combinations(pool,nfree):
        m=forced|set(e)
        runs=prl_runs(w,m)
        if not all(len(s)==1 or isw(w[s[0]:s[-1]+1]) for s in runs): continue
        if not all(len(s)>=2 or w[s[0]] in ok for s in runs): continue
        sc=mult*(base+sum(val[w[cc]] for cc in (3,11) if cc in m))+50
        cands.append((sc,tuple(sorted(m))))
    cands.sort(reverse=True)
    return [(sc,m) for sc,m in cands[:k]]

# ---- solver-state (reset per poging) ----
G=None;freebag=None;MASK=None;ANCH=None;target=None;BESTB=None;t0=0.0
def FREE(y): return 1<=y<=6 or 8<=y<=13
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
def components():
    # G bevat NU alleen pre-cellen + connectoren (masker-cellen zijn afwezig = pre-bord)
    seen=[[False]*15 for _ in range(15)];comps=[]
    for y in range(15):
        for x in range(15):
            if G[y][x] and not seen[y][x]:
                cells=[];dq=deque([(x,y)]);seen[y][x]=True
                while dq:
                    cx,cy=dq.popleft();cells.append((cx,cy))
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and G[ny][nx] and not seen[ny][nx]:seen[ny][nx]=True;dq.append((nx,ny))
                comps.append(cells)
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
            if cy in(0,7,14):return None
            if not FREE(cy):return None
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
def unplace(new):
    nd=Counter()
    for cx,cy in new: nd[chr(96+G[cy][cx])]+=1
    for cx,cy in new:G[cy][cx]=0
    freebag.update(nd)
def connectors_for(tx,ty,M0,M14):
    out=[]
    if ty==0:
        if not G[1][tx]:
            if tx not in M0:
                for w in C8.get((R0[tx],R7[tx]),[]): out.append((w,tx,0,0))
            for L in range(2,8):
                cand=byfirst.get((R0[tx],L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,0,0))
    elif ty==14:
        if not G[13][tx]:
            if tx not in M14:
                for w in C8.get((R7[tx],R14[tx]),[]): out.append((w,tx,7,0))
            for L in range(2,8):
                cand=bylast.get((R14[tx],L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,14-L+1,0))
    elif ty==7:
        if not G[6][tx]:
            for L in range(2,8):
                cand=bylast.get((R7[tx],L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,7-L+1,0))
        if not G[8][tx]:
            for L in range(2,8):
                cand=byfirst.get((R7[tx],L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,7,0))
    else:
        la=chr(96+G[ty][tx])
        for b in range(15):
            if b==tx or not G[ty][b]: continue
            a,c=(tx,b) if tx<b else (b,tx)
            if not(2<=c-a<=7): continue
            if any(G[ty][k] for k in range(a+1,c)): continue
            l0=chr(96+G[ty][a]);l1=chr(96+G[ty][c])
            for w in byl.get(c-a+1,[]):
                if w[0]==l0 and w[-1]==l1: out.append((w,a,ty,1))
        if ty>0 and not G[ty-1][tx]:
            for L in range(2,6):
                cand=bylast.get((la,L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,ty-L+1,0))
        if ty<14 and not G[ty+1][tx]:
            for L in range(2,6):
                cand=byfirst.get((la,L),[])
                for w in (cand if len(cand)<=MAXV else random.sample(cand,MAXV)): out.append((w,tx,ty,0))
    return out
def gen_moves(comps,M0,M14):
    if len(comps)<=1: return []
    main=max(comps,key=len)
    others=sorted((cc for cc in comps if cc is not main),key=len)
    out=[]
    for (tx,ty) in others[0]:
        out+=connectors_for(tx,ty,M0,M14)
    random.shuffle(out)
    return out[:500]
def stitch(free_row,mask):
    """verbind anker-segmenten die door mask-cellen zijn opgesplitst, via een rung op free_row
    tussen de dichtstbijzijnde bezette cellen links/rechts van elke mask-kolom."""
    for c in sorted(mask):
        if not(1<=c<=13): continue
        L=next((k for k in range(c-1,-1,-1) if G[free_row][k]),None)
        Rr=next((k for k in range(c+1,15) if G[free_row][k]),None)
        if L is None or Rr is None or not(2<=Rr-L<=7): continue
        if any(G[free_row][k] for k in range(L+1,Rr)): continue
        la=chr(96+G[free_row][L]);lb=chr(96+G[free_row][Rr])
        cs=[w for w in byl.get(Rr-L+1,[]) if w[0]==la and w[-1]==lb];cs=biasshuf(cs)
        for w in cs:
            if place(w,L,free_row,1): break
def build_backbone(M0,M14,M7):
    order=list(range(15));random.shuffle(order)
    for c in order:
        if c not in M0 and not G[1][c]:
            cs=biasshuf(C8.get((R0[c],R7[c]),[])[:])
            for w in cs:
                if place(w,c,0,0): break
    for c in order:
        if c not in M14 and not G[13][c]:
            cs=biasshuf(C8.get((R7[c],R14[c]),[])[:])
            for w in cs:
                if place(w,c,7,0): break
    # stitch de door-mask-opgesplitste ankersegmenten (optioneel; MGSTITCH=1)
    if os.environ.get('MGSTITCH','0')=='1':
        stitch(6,M7);stitch(8,M7);stitch(1,M0);stitch(13,M14)
def attempt(M0,M14,M7,seed):
    global G,freebag,MASK,ANCH,target,BESTB,t0
    random.seed(seed)
    MASK={0:set(M0),7:set(M7),14:set(M14)};ANCH={0:R0,7:R7,14:R14}
    G=[[0]*15 for _ in range(15)]
    # plaats ALLEEN pre-cellen (masker-cellen worden pas door de 3 slotzetten gelegd -> pre-bord)
    for y,W in ANCH.items():
        for c in range(15):
            if c not in MASK[y]: G[y][c]=cba[W[c]]
    freebag=Counter(bag)
    # reserveer echter tegels voor de VOLLEDIGE ankerrijen (masker-cellen worden later gelegd)
    for y,W in ANCH.items():
        for c in range(15): freebag[W[c]]-=1
    opcands=[w for w in byl[7] if w[3]==R7[7]];opcands=biasshuf(opcands)
    for w in opcands:
        nd=Counter(w);nd[R7[7]]-=1
        if all(freebag[c]>=nd[c] for c in nd):
            for i,ch in enumerate(w): G[4+i][7]=cba[ch]
            freebag.subtract(nd);break
    target=[999];BESTB=[None];t0=time.time()
    build_backbone(set(M0),set(M14),set(M7))
    def dfs(depth):
        if time.time()-t0>TL: return False
        comps=components();cm=len(comps)
        if cm<target[0]: target[0]=cm;BESTB[0]=[row[:] for row in G]
        if cm==1: return True
        if depth>30: return False
        for (w,x,y,h) in gen_moves(comps,set(M0),set(M14)):
            new=place(w,x,y,h)
            if new is None: continue
            if dfs(depth+1): return True
            unplace(new)
        return False
    ok=dfs(0)
    return ok,target[0],(BESTB[0] if ok else None)

# ---- driver: mask-pool over de drie woorden ----
# rijen 0/14: TWS op cols 0,7,14 verplicht in masker (×27). rij 7: TWS 0,14 verplicht, 7=center gespend (×9).
m0s=top_masks(R0,after_ok,{0,7,14},27,KMASK)
m14s=top_masks(R14,before_ok,{0,7,14},27,KMASK)
m7s=top_masks(R7,after_ok,{0,14},9,KMASK)
if not(m0s and m14s and m7s):
    print(f"HIT-DRIVER {TAG}: geen geldige maskers (m0={len(m0s)} m14={len(m14s)} m7={len(m7s)})",flush=True)
    sys.exit(0)
best_comp=999;tried=0;hit=None
# probeer combinaties in score-volgorde (product van top maskers), meerdere seeds
combos=[]
for s0,m0 in m0s:
    for s14,m14 in m14s:
        for s7,m7 in m7s:
            combos.append((s0+s14+s7,m0,m14,m7))
combos.sort(reverse=True)
T_ALL=float(os.environ.get('MGTALL','300'));tstart=time.time()
for sc,m0,m14,m7 in combos:
    if time.time()-tstart>T_ALL: break
    _sb=int(os.environ.get('MGSEEDBASE','0'))
    for seed in range(1+_sb,1+_sb+SEEDS):
        if time.time()-tstart>T_ALL: break
        ok,cm,board=attempt(m0,m14,m7,seed);tried+=1
        if cm<best_comp: best_comp=cm
        if ok and board:
            hit=(sc,m0,m14,m7,board);break
    if hit: break
if hit:
    sc,m0,m14,m7,board=hit
    print(f"*** HIT {TAG}: score~{sc} triple={R0}/{R7}/{R14} beste-comps=1 ***",flush=True)
    json.dump({'grid':board,'triple':[R0,R7,R14],'M0':sorted(m0),'M7':sorted(m7),'M14':sorted(m14),'score_est':sc},
              open(f'experiments/results/mg_decomp_{TAG}.json','w'))
else:
    print(f"HIT-DRIVER {TAG}: geen sluiting ({R0}/{R7}/{R14}) beste-comps={best_comp} pogingen={tried}",flush=True)

