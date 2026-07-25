"""1-tegel-verplaatsings-polish (bob's poft-inzicht): neem het beste bord, enumereer ALLE legale
1-tegel-verplaatsingen (verwijderbaar = run-eindpunten op vrije rijen waarvan verwijdering alle
runs geldig laat; doel = lege niet-masker-cel waar plaatsing beide richtingen geldige runs vormt),
eis 1-component na de ruil, batch-evalueer kandidaten met de Rust-DP (DECOMP_ONLY), hill-climb.
Blanco-cel blijft vast (v1). Output: beste SCORED-regel + verloop."""
import sys, os, json, subprocess
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import deque
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
TMP='/home/bob/.claude/jobs/da7ed622/tmp'

D=json.load(open('experiments/results/maxgame_BEST.json'))
grid=[row[:] for row in D['grid']];moves=D['moves'];bl=set(tuple(b) for b in D.get('blanks',[]))
mask=set();rows={}
for m in moves[-3:]:
    for c in m: mask.add((c[0],c[1]));rows.setdefault(c[1],[]).append(c[0])
m0=sorted(rows[0]);m7=sorted(rows[7]);m14=sorted(rows[14])
R0,R7,R14=D['triple']
# pre-bord
pre=[[0]*15 for _ in range(15)]
for y in range(15):
    for x in range(15):
        if grid[y][x] and (x,y) not in mask: pre[y][x]=grid[y][x]

def runs_ok(g,cells):
    rows_=set(y for _,y in cells);cols=set(x for x,_ in cells)
    for y in rows_:
        x=0
        while x<15:
            if not g[y][x]:x+=1;continue
            x2=x
            while x2<15 and g[y][x2]:x2+=1
            if x2-x>=2 and not isw(''.join(chr(96+g[y][k]) for k in range(x,x2))):return False
            x=x2
    for x in cols:
        y=0
        while y<15:
            if not g[y][x]:y+=1;continue
            y2=y
            while y2<15 and g[y2][x]:y2+=1
            if y2-y>=2 and not isw(''.join(chr(96+g[k][x]) for k in range(y,y2))):return False
            y=y2
    return True
def mask_vert_ok(g):
    anch={0:R0,7:R7,14:R14}
    for (c,y) in mask:
        up=[];yy=y-1
        while yy>=0 and g[yy][c]:up.append(chr(96+g[yy][c]));yy-=1
        dn=[];yy=y+1
        while yy<15 and g[yy][c]:dn.append(chr(96+g[yy][c]));yy+=1
        if up or dn:
            if not isw(''.join(reversed(up))+anch[y][c]+''.join(dn)):return False
    return True
def ncomp(g):
    seen=[[False]*15 for _ in range(15)];n=0
    for y in range(15):
        for x in range(15):
            if g[y][x] and not seen[y][x]:
                n+=1;dq=deque([(x,y)]);seen[y][x]=True
                while dq:
                    cx,cy=dq.popleft()
                    for a,b in((1,0),(-1,0),(0,1),(0,-1)):
                        nx,ny=cx+a,cy+b
                        if 0<=nx<15 and 0<=ny<15 and g[ny][nx] and not seen[ny][nx]:seen[ny][nx]=True;dq.append((nx,ny))
    return n
def emit(g):
    return ''.join(('`' if g[y][x]==0 else chr(96+g[y][x])) for y in range(15) for x in range(15))

base_line=f"SCORED 0 0 0 {','.join(map(str,m0))} {','.join(map(str,m14))} {','.join(map(str,m7))} {emit(pre)} MV x BL {','.join(f'{b[0]}.{b[1]}' for b in sorted(bl))}"
cands=[base_line]
labels=[('BASIS',None,None)]
free_rows=set(range(1,7))|set(range(8,14))
for y in range(15):
    for x in range(15):
        if not pre[y][x] or y not in free_rows or (x,y) in bl: continue
        L=pre[y][x]
        g2=[row[:] for row in pre];g2[y][x]=0
        if not runs_ok(g2,[(x,y)]) or not mask_vert_ok(g2): continue
        if ncomp(g2)!=1: continue
        for ty in range(15):
            for tx in range(15):
                if g2[ty][tx] or (tx,ty) in mask or ty in (0,7,14): continue
                # moet grenzen aan structuur (connectiviteit)
                if not any(0<=tx+a<15 and 0<=ty+b<15 and g2[ty+b][tx+a] for a,b in((1,0),(-1,0),(0,1),(0,-1))): continue
                g3=[row[:] for row in g2];g3[ty][tx]=L
                if not runs_ok(g3,[(tx,ty)]) or not mask_vert_ok(g3): continue
                if ncomp(g3)!=1: continue
                cands.append(f"SCORED 0 0 0 {','.join(map(str,m0))} {','.join(map(str,m14))} {','.join(map(str,m7))} {emit(g3)} MV x BL {','.join(f'{b[0]}.{b[1]}' for b in sorted(bl))}")
                labels.append((chr(96+L),(x,y),(tx,ty)))
print(f"kandidaten: {len(cands)-1} verplaatsingen",flush=True)
open(f'{TMP}/reloc_cands.txt','w').write('\n'.join(cands)+'\n')

env=dict(os.environ)
env.update(WORDS_ALL=f'{TMP}/wordsall.txt',WORDS_CONN=f'{TMP}/words2_8.txt',PREMIUM_FLAT=f'{TMP}/premium_flat.txt')
meta=json.load(open(f'{TMP}/meta.json'))
env['VALS']=','.join(map(str,meta['val']));env['BAG']=','.join(map(str,meta['bag']))
env['DECOMP_ONLY']='1';env['MGBEAMW']=os.environ.get('RELOC_BEAM','12')
inp='geschenkcheques flexwerkstertje polymelkzuurtje\n0 0\n'+'\n'.join(cands)+'\n'
out=subprocess.run(['experiments/mg_full_bin'],input=inp,capture_output=True,text=True,env=env).stdout
res=[l for l in out.splitlines() if l.startswith('SCORED')]
print(f"geëvalueerd: {len(res)}",flush=True)
scored=[]
for i,l in enumerate(res):
    p=l.split();scored.append((int(p[1]),i,l))
scored.sort(reverse=True)
print("top-8 (beam-12):")
for tot,i,l in scored[:8]:
    lab=labels[i] if i<len(labels) else ('?',)
    print(f"  {tot}  {lab}")
best=scored[0]
open(f'{TMP}/reloc_best.txt','w').write(best[2]+'\n')
print(f"BESTE: {best[0]} ({labels[best[1]]})")
