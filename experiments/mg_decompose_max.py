"""Score-MAXIMALISERENDE decompositie van een gesloten bord (mg_game_{TAG}.json of mg_decomp_{TAG}.json).
Zelfde bord/tegels, maar kies de zetvolgorde+groepering die de ECHTE score_game-score maximaliseert:
greedy op werkelijke marginale zetscore (per[-1]), zodat prep-zetten hoog-scorende bingo's worden.
De 3 slotzetten (masker-rijen ×27/×27/×9) blijven laatst. Env: MGTAG, MGSRC (game|decomp), MGBEAM."""
import sys, os, json, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ.setdefault('N15_LANG','dutch2026')
from collections import Counter
import maxgame_score as MG
r=MG.r;lk=MG.lk;cba=r.alphabet.cba
TAG=os.environ.get('MGTAG','x');SRC=os.environ.get('MGSRC','game')
W=H=15
if SRC=='game':
    D=json.load(open(f'experiments/results/mg_game_{TAG}.json'))
    grid=[row[:] for row in D['grid']]
    # afleiden masker-cellen uit de laatste 3 zetten
    mv=D['moves'];maskcells=set()
    for m in mv[-3:]:
        for c in m: maskcells.add(tuple(c))
    blanks=set(tuple(b) for b in D.get('blanks',[]))
    triple=D['triple']
else:
    D=json.load(open(f'experiments/results/mg_decomp_{TAG}.json'))
    grid=[row[:] for row in D['grid']];M0=set(D['M0']);M7=set(D['M7']);M14=set(D['M14'])
    R0,R7,R14=D['triple']
    for y,Wd in ((0,R0),(7,R7),(14,R14)):
        for c in range(15): grid[y][c]=cba[Wd[c]]
    maskcells={(c,0) for c in M0}|{(c,7) for c in M7}|{(c,14) for c in M14}
    blanks=set();triple=D['triple']
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
# pre-bord lijnen
pre=[[grid[y][x] if (x,y) not in maskcells else 0 for x in range(W)] for y in range(H)]
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
slotmoves=[]
# masker-slotzetten per rij
byrow={}
for (x,y) in maskcells: byrow.setdefault(y,[]).append((x,y))
for y in (7,0,14):
    if y in byrow: slotmoves.append(sorted(byrow[y]))

def marginal(prevmoves,cand):
    """echte marginale score van cand gegeven prevmoves = per[-1] van score_game.
    coverage-ok is False bij partiele reeks (verwacht), maar per-zet-scores kloppen wel;
    return None alleen als de laatste zet niet gescoord werd (illegaal/afbreking)."""
    mv=[[tuple(c) for c in m] for m in prevmoves]+[[tuple(c) for c in cand]]
    tot,per,ok,msg=MG.score_game([row[:] for row in grid],mv,blanks)
    if len(per)!=len(mv): return None
    return per[-1]
def candidates(pl):
    out=[]
    for line in lines:
        n=len(line)
        for i in range(n):
            for j in range(i,n):
                seg=line[i:j+1]
                new=[(x,y) for (x,y) in seg if not pl[y][x]]
                if not(1<=len(new)<=7): continue
                out.append((seg,new))
    return out
def solve_max():
    pl=[[False]*W for _ in range(H)];moves=[];t0=time.time()
    # eerste zet: door center (7,7)
    while sum(sum(r_) for r_ in pl)<npre:
        if time.time()-t0>500: return None,moves
        best=None
        for seg,new in candidates(pl):
            if not moves:
                if (7,7) not in new: continue
            else:
                touch=any(pl[y][x] for (x,y) in seg) or any(
                    0<=x+dx<W and 0<=y+dy<H and pl[y+dy][x+dx]
                    for (x,y) in new for dx,dy in((1,0),(-1,0),(0,1),(0,-1)))
                if not touch: continue
            for (x,y) in new: pl[y][x]=True
            leg=runs_legal(pl)
            for (x,y) in new: pl[y][x]=False
            if not leg: continue
            mg=marginal(moves,new)
            if mg is None: continue
            # voorkeur voor hoge marginale score; tie-break meer tegels
            key=(mg,len(new))
            if best is None or key>best[0]: best=(key,new)
        if best is None: return False,moves
        for (x,y) in best[1]: pl[y][x]=True
        moves.append(best[1])
    return True,moves
ok,moves=solve_max()
if not ok:
    print(f"MAXDECOMP {TAG}: pre-bord niet decomponeerbaar (ok={ok}, {len(moves)} zetten)",flush=True);sys.exit(0)
allmoves=[[tuple(c) for c in m] for m in moves]+[[tuple(c) for c in s] for s in slotmoves]
# blanks reeds bekend (uit game) of leeg (decomp) -> herbereken overflow-blanks als nodig
if SRC!='game':
    bag=Counter({chr(96+c):r.counts[c] for c in r.counts});cnt=Counter()
    for y in range(H):
        for x in range(W):
            if grid[y][x]: cnt[chr(96+grid[y][x])]+=1
    over=[ch for ch in cnt if cnt[ch]>bag[ch] for _ in range(cnt[ch]-bag[ch])]
    def cost(x,y,ch):
        lv=r.scores[ord(ch)-96];prem=1
        if y in(0,14) and x in(0,7,14):prem=27
        elif y==7 and x in(0,14):prem=9
        return lv*prem
    for ch in over:
        bestc=None
        for y in range(H):
            for x in range(W):
                if grid[y][x]==ord(ch)-96 and (x,y) not in blanks:
                    c=cost(x,y,ch)
                    if bestc is None or c<bestc[0]:bestc=(c,x,y)
        if bestc: blanks.add((bestc[1],bestc[2]))
tot,per,vok,msg=MG.score_game([row[:] for row in grid],allmoves,blanks)
prep=int(sum(sorted(per)[:-3]));fin=int(sum(sorted(per)[-3:]))
print(f"MAXDECOMP {TAG}: SCORE={int(tot)} (finals={fin} prep={prep}) zetten={len(allmoves)} ok={vok} ({msg})",flush=True)
if vok:
    out=f'experiments/results/mg_gamemax_{TAG}.json'
    json.dump({'grid':grid,'moves':[[list(c) for c in mv] for mv in allmoves],
               'blanks':[list(b) for b in blanks],'total':int(tot),'triple':triple},open(out,'w'))
    print(f"*** MAX game score={int(tot)} -> {out} ***",flush=True)
