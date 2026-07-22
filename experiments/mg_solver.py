"""Joint crossword-solver (component-geleid). Bord met rijen 0/7/14 = ankerwoorden (vol, statisch).
Vul vrije cellen met verbindingswoorden zodat: alle runs geldig (H+V), maskercel-verticalen geldig,
1 verbonden component, zak OK. Dan decompose -> zetreeks -> score_game. Component-geleide DFS +
volledige backtracking. Env: MGR0/MGR14/MGR7/MGM0/MGM14/MGM7."""
import sys, os, json, random, time, ast
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter, deque
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
A='abcdefghijklmnopqrstuvwxyz'
random.seed(int(os.environ.get('SEED','1')))
words=r.words_str;byl={}
for w in words: byl.setdefault(len(w),[]).append(w)
# prefix-set voor pruning
prefix=set()
for w in words:
    for i in range(1,len(w)): prefix.add(w[:i])
def isw_or_pref(s): return tuple(cba[c] for c in s) in lk
bag0=Counter({chr(96+c):r.counts[c] for c in r.counts})
R0=os.environ.get('MGR0','bouwcuratrixjes');R14=os.environ.get('MGR14','geschenkcheques');R7=os.environ.get('MGR7','playoffticketje')
M0=ast.literal_eval(os.environ.get('MGM0','(0,1,3,5,7,11,14)'))
M14=ast.literal_eval(os.environ.get('MGM14','(0,3,7,8,11,12,14)'))
M7=ast.literal_eval(os.environ.get('MGM7','(0,3,6,8,9,13,14)'))
ANCH={0:R0,7:R7,14:R14};MASK={0:set(M0),7:set(M7),14:set(M14)}
# STATISCH bord: rijen 0,7,14 vol met ankerletters
G=[[0]*15 for _ in range(15)]
for y,W in ANCH.items():
    for c in range(15): G[y][c]=cba[W[c]]
bagrem=Counter(bag0)
for y,W in ANCH.items():
    for c in range(15): bagrem[W[c]]-=1
BLANKS=r.blank_count
# pre-cellen (moeten uiteindelijk verbonden zijn); mask-cellen: hun verticaal moet geldig zijn
def vrun_valid(x,y):
    # verticale run door (x,y) op huidige G geldig?
    if not G[y][x]: return True
    y0=y
    while y0>0 and G[y0-1][x]: y0-=1
    y1=y
    while y1<14 and G[y1+1][x]: y1+=1
    if y1==y0: return True
    return isw(''.join(chr(96+G[k][x]) for k in range(y0,y1+1)))
def hrun_valid(x,y):
    if not G[y][x]: return True
    x0=x
    while x0>0 and G[y][x0-1]: x0-=1
    x1=x
    while x1<14 and G[y][x1+1]: x1+=1
    if x1==x0: return True
    return isw(''.join(chr(96+G[y][k]) for k in range(x0,x1+1)))
# plaats verticaal woord op vrije cellen (rijen 1-6 of 8-13), valideer H+V runs + zak
def place_vword(col,y0,word):
    cells=[]
    for i,ch in enumerate(word):
        y=y0+i
        if G[y][col]:
            if G[y][col]!=cba[ch]: return None
        else:
            if 1<=y<=6 or 8<=y<=13: cells.append((col,y,cba[ch]))
            elif y in(0,7,14): 
                if G[y][col]!=cba[ch]: return None  # anker vast
            else: return None
    # boven/onder rand leeg (anders langere run)
    if y0>0 and G[y0-1][col] and (y0-1 not in(0,7,14) or True): pass
    return cells
# ---- component-geleide DFS ----
def components():
    seen=[[False]*15 for _ in range(15)];comps=0;pre_comp={}
    for y in range(15):
        for x in range(15):
            if G[y][x] and not seen[y][x]:
                comps+=1;dq=deque([(x,y)]);seen[y][x]=True
                while dq:
                    cx,cy=dq.popleft()
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and G[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx]=True;dq.append((nx,ny))
    return comps
print(f"start: {R0}/{R7}/{R14} | componenten (3 volle rijen): {components()}",flush=True)
# de 3 volle rijen = 3 componenten. Doel: verbind tot 1 via verticale woorden, alle runs geldig.
# vind verticale woorden die 2 rijen verbinden (brug rij0-7 of rij7-14) of laddert.
def used_count():
    u=Counter()
    for y in range(15):
        for x in range(15):
            if G[y][x] and not(y in(0,7,14)): u[chr(96+G[y][x])]+=1
    return u
def bag_ok(extra):
    u=used_count()+extra
    over=sum(max(0,u[c]-bagrem_after(c)) for c in u)
    return over<=BLANKS
def bagrem_after(c): 
    # zak minus ankers al verrekend in bagrem; free tiles apart
    return bag0[c]-(Counter(R0)+Counter(R7)+Counter(R14))[c]
# eenvoud: verbind rij0-7 met 1 verticaal 8-woord (kol c), rij7-14 met 1 8-woord. Alle H-runs op
# rij1-6/8-13 = enkel (kol c) -> geldig. Dit maakt 1 component. Dan pre-cel-decompose check.
def try_two_bridges():
    C8u={};C8d={}
    for w in byl.get(8,[]):
        C8u.setdefault((w[0],w[7]),[]).append(w)
    best=None
    for uc in range(15):
        for uw in C8u.get((chr(96+G[0][uc]),chr(96+G[7][uc])),[]):
            # plaats up-brug kol uc
            need=Counter(uw[1:7])
            for dc in range(15):
                if dc==uc: continue
                for dw in C8u.get((chr(96+G[7][dc]),chr(96+G[14][dc])),[]):
                    need2=need+Counter(dw[1:7])
                    over=sum(max(0,need2[c]-bagrem_after(c)) for c in need2)
                    if over<=BLANKS:
                        return (uc,uw,dc,dw)
    return None
res=try_two_bridges()
print(f"2-brug-verbinding: {res}",flush=True)
if res:
    uc,uw,dc,dw=res
    for i,ch in enumerate(uw): G[i][uc]=cba[ch]
    for i,ch in enumerate(dw): G[7+i][dc]=cba[ch]
    print(f"componenten na 2 bruggen: {components()} (1 = verbonden)",flush=True)
    # nu: is dit DECOMPOSABLE tot zetreeks met x27/x9 finals? pre-cellen moeten verbindbaar zijn
    # zonder de mask-cellen. Check: bord minus mask-cellen nog verbonden?
    G2=[row[:] for row in G]
    for y,ms in MASK.items():
        for c in ms: G2[y][c]=0
    # tel componenten van G2 (pre-cellen + bruggen)
    seen=[[False]*15 for _ in range(15)];comps=0
    for y in range(15):
        for x in range(15):
            if G2[y][x] and not seen[y][x]:
                comps+=1;dq=deque([(x,y)]);seen[y][x]=True
                while dq:
                    cx,cy=dq.popleft()
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and G2[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx]=True;dq.append((nx,ny))
    print(f"bord-minus-maskcellen componenten: {comps} (1 = pre-cellen verbonden -> decomposable)",flush=True)
    isolated=[(x,y) for y in range(15) for x in range(15) if G2[y][x] and all(not(0<=x+a<15 and 0<=y+b<15 and G2[y+b][x+a]) for a,b in((1,0),(-1,0),(0,1),(0,-1)))]
    print(f"geisoleerde pre-cellen: {len(isolated)} {isolated[:8]}",flush=True)

# ---- support-struts voor geisoleerde pre-cellen + decompose ----
def full_valid():
    for y in range(15):
        for x in range(15):
            if G[y][x] and not hrun_valid(x,y): return False
            if G[y][x] and not vrun_valid(x,y): return False
    return True
def mask_verticals_ok():
    for y,ms in MASK.items():
        for c in ms:
            # (c,y) is mask (leeg in decompose). simuleer plaatsing: verticaal met buren geldig
            up=[];yy=y-1
            while yy>=0 and G[yy][c]: up.append(chr(96+G[yy][c]));yy-=1
            dn=[];yy=y+1
            while yy<15 and G[yy][c]: dn.append(chr(96+G[yy][c]));yy+=1
            if up or dn:
                if not isw(''.join(reversed(up))+ANCH[y][c]+''.join(dn)): return False
    return True
def board_minus_mask_comps():
    G2=[row[:] for row in G]
    for y,ms in MASK.items():
        for c in ms: G2[y][c]=0
    seen=[[False]*15 for _ in range(15)];comps=0;iso=[]
    for y in range(15):
        for x in range(15):
            if G2[y][x] and not seen[y][x]:
                comps+=1;dq=deque([(x,y)]);seen[y][x]=True;sz=1
                while dq:
                    cx,cy=dq.popleft()
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and G2[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx]=True;dq.append((nx,ny));sz+=1
                if sz==1: iso.append((x,y))
    return comps,iso
def free_bag():
    u=used_count();return {c:bagrem_after(c)-u[c] for c in A}
def add_strut(cell):
    """probeer (c,y) te verbinden via een korte verticale strut naar bestaande structuur (niet-mask),
    met alle cross-checks geldig. Retourneert True als geplaatst."""
    (c,y)=cell
    W=ANCH[y]
    fb=free_bag()
    for Ln in (2,3,4,5):
        cands=[]
        if y==0:  # omlaag
            for w in byl.get(Ln,[]):
                if w[0]==W[c]: cands.append((0,w))
        elif y==14:  # omhoog
            for w in byl.get(Ln,[]):
                if w[Ln-1]==W[c]: cands.append((14-Ln+1,w))
        else:  # rij7: omhoog of omlaag
            for w in byl.get(Ln,[]):
                if w[Ln-1]==W[c]: cands.append((7-Ln+1,w))
                if w[0]==W[c]: cands.append((7,w))
        random.shuffle(cands)
        for (y0,w) in cands[:300]:
            # cellen die nieuw zijn (vrije rijen)
            ok=True;placed=[]
            for i,ch in enumerate(w):
                yy=y0+i
                if G[yy][c]:
                    if G[yy][c]!=cba[ch]: ok=False;break
                elif 1<=yy<=6 or 8<=yy<=13: placed.append((yy,cba[ch]))
                elif yy in(0,7,14):
                    if G[yy][c]!=cba[ch]: ok=False;break
                else: ok=False;break
            if not ok or not placed: continue
            # rand-leeg check (geen langere V-run)
            if y0>0 and G[y0-1][c]: continue
            if y0+Ln<15 and G[y0+Ln][c]: continue
            # zak
            need=Counter(chr(96+v) for _,v in placed)
            if any(need[cc]>free_bag()[cc] for cc in need): continue
            # plaats
            for yy,v in placed: G[yy][c]=v
            # valideer alle nieuwe H+V runs
            good=full_valid() and mask_verticals_ok()
            # moet aan bestaande structuur raken (verbinden)
            if good:
                touch=any(0<=c+a<15 and 0<=yy+b<15 and G[yy+b][c+a] and (c+a,yy+b) not in [(c,p) for p,_ in placed]
                          for yy,_ in placed for a,b in((1,0),(-1,0)))
                # ook verticale buur boven/onder de strut telt als hij bestaand is (al gecheckt via run)
            if good and touch:
                return True
            for yy,v in placed: G[yy][c]=0
    return False

t0=time.time()
comps,iso=board_minus_mask_comps()
print(f"init geisoleerd: {len(iso)}",flush=True)
# greedy: verbind elke geisoleerde pre-cel
random.seed(int(os.environ.get('SEED','1')))
progress=True
while progress and time.time()-t0<120:
    comps,iso=board_minus_mask_comps()
    if not iso: break
    progress=False
    for cell in iso:
        if add_strut(cell): progress=True; break
comps,iso=board_minus_mask_comps()
print(f"na struts: componenten(minus mask)={comps} geisoleerd={len(iso)} {iso[:6]} tegels={sum(1 for y in range(15) for x in range(15) if G[y][x])}",flush=True)
if comps==1:
    print("*** DECOMPOSABLE: pre-cellen verbonden! Bord klaar voor zetreeks-decompositie ***",flush=True)
    json.dump({'grid':G,'triple':[R0,R7,R14],'M0':M0,'M7':M7,'M14':M14},open('experiments/results/mg_solver_board.json','w'))
