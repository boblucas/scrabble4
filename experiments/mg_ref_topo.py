"""REFERENTIE-TOPOLOGIE (bob's orientatie: P boven/F midden/G onder) — expliciete constructie:
gaskast + werkster + 2x kol-x4-verts (rijen 3-10, exts naar rij 11 = 9-woorden) + rij-3-laan (x4)
+ rij-12-laan [7,13] (x2, wortel via (10,11)-ext) + kol-5-bottom-vert (werkster-geworteld)
+ top: uur-cluster op rij 0 (stubs 6/9 + mel/zuur/zuurt-kettingen)
+ bottom: ministubs 8/9/12/13 + he/en-kettingen; mask14 bevat q(11) en u?(nee: 12 pre).
95 tegels, 6 spare. CP-SAT letters + score_game."""
import sys,os,json
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
from ortools.sat.python import cp_model
import numpy as np
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba
val={i:r.scores[i] for i in range(1,27)}
LM=np.array(r.letter_multiplier);WM=np.array(r.word_multiplier)
bag=Counter({c:r.counts[c] for c in r.counts})
bylen={}
for w in r.words_str: bylen.setdefault(len(w),[]).append(tuple(cba[ch] for ch in w))
R0='polymelkzuurtje';R7='flexwerkstertje';R14='geschenkcheques'
mv=[
 [(7,y) for y in range(4,11)],                                  # gaskast
 [(c,7) for c in (4,5,6,8,9,10,11)],                            # werkster
 [(4,y) for y in (3,4,5,6,8,9,10)],                             # x4-vert kol 4 (door w)
 [(10,y) for y in (3,4,5,6,8,9,10)],                            # x4-vert kol 10 (door e)
 [(x,3) for x in (3,5,6,7,8,9,11)],                             # rij-3-laan (x4: 3,3+11,3)
 [(4,11)],[(10,11)],                                            # exts -> 9-woorden
 [(11,11)],                                                     # DWS-single aan ext+laan
]+ {'A':[[(12,1)],[(12,2)]],'B':[[(8,4)],[(3,2)]],'C':[[(8,4)],[(12,1)]],'':[]}[os.environ.get('MODS','')] + [
 [(6,0),(6,1),(6,2)],[(9,0),(9,1),(9,2)],                       # top-stubs (4-runs met laan)
 [(5,0)],[(4,0)],[(10,0),(11,0)],[(8,0)],[(12,0)],              # el/mel/uur/zuur/zuurt
 [(5,y) for y in range(8,15)],                                  # kol-5-bottom-vert (e......e)
 [(x,12) for x in (7,8,9,10,11,12,13)],                         # rij-12-laan [7,13] (x2 via 12,12)
 [(9,13),(9,14)],[(12,13),(12,14)],                             # ministubs 9/12
 [(3,10)],[(2,10)],[(2,11)],[(2,12)],[(2,13)],                  # westketting rij10 + kol2 zuid
 [(2,14)],[(1,14)],                                             # es-cluster
 [(4,14)],[(6,14)],[(10,14)],                                   # he/en/he-kettingen
 [(c,7) for c in (0,1,2,3,12,13,14)],                           # fin7
 [(c,0) for c in (0,1,2,3,7,13,14)],                            # fin0 (pre0={4,5,6,8,9,10,11,12})
 [(c,14) for c in (0,3,7,8,11,13,14)],                          # fin14 (pre14={1,2,4,5,6,9,10,12})
]
allc=[c for m in mv for c in m]
assert len(allc)==len(set(allc)), "dubbele cel"
g=[[0]*15 for _ in range(15)]
for (x,y) in allc:
    g[y][x]=cba[{0:R0,7:R7,14:R14}[y][x]] if y in (0,7,14) else 1
occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
print("tegels:",len(occ))
# touch-validatie
placed=set(mv[0]);okorder=True
for m in mv[1:]:
    if not any((x+dx,y+dy) in placed for (x,y) in m for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
        print("GEEN TOUCH:",m);okorder=False
    placed|=set(m)
print("volgorde ok:",okorder)
fixed={(x,y):g[y][x] for (x,y) in occ if y in (0,7,14)}
free=[c for c in occ if c not in fixed]
m_=cp_model.CpModel();L={}
for c in free: L[c]=m_.new_int_var(1,26,f"L{c}")
for c,v in fixed.items(): L[c]=m_.new_constant(v)
placed=set();events=[];stage_runs=set()
for t,cells in enumerate(mv):
    placed|=set(cells);cset=set(cells);seen=set()
    for (x,y) in cells:
        x0=x
        while x0>0 and (x0-1,y) in placed: x0-=1
        x1=x
        while x1<14 and (x1+1,y) in placed: x1+=1
        if x1>x0:
            k=('H',x0,y)
            if k not in seen:
                seen.add(k);run=[(xx,y) for xx in range(x0,x1+1)]
                if any(c in cset for c in run): events.append((run,cset));stage_runs.add(tuple(run))
        y0=y
        while y0>0 and (x,y0-1) in placed: y0-=1
        y1=y
        while y1<14 and (x,y1+1) in placed: y1+=1
        if y1>y0:
            k=('V',x,y0)
            if k not in seen:
                seen.add(k);run=[(x,yy) for yy in range(y0,y1+1)]
                if any(c in cset for c in run): events.append((run,cset));stage_runs.add(tuple(run))
bad=None
for run in stage_runs:
    fx={i:fixed[c] for i,c in enumerate(run) if c in fixed}
    tab=[w for w in bylen.get(len(run),[]) if all(w[i]==v for i,v in fx.items())]
    if not tab: print("LEEG:",run);bad=run;continue
    m_.add_allowed_assignments([L[c] for c in run],tab)
if bad: sys.exit(1)
for ch in range(1,27):
    cnt=[]
    for c in free:
        b=m_.new_bool_var(f"i{c}_{ch}")
        m_.add(L[c]==ch).only_enforce_if(b);m_.add(L[c]!=ch).only_enforce_if(b.negated())
        cnt.append(b)
    base=sum(1 for c,v in fixed.items() if v==ch)
    m_.add(sum(cnt)+base<=bag[ch])
VV=[0]+[val[i] for i in range(1,27)]
valvar={}
for c in set(sum(([cc for cc in run] for run,_ in events),[])):
    v=m_.new_int_var(0,10,f"v{c}");m_.add_element(L[c],VV,v);valvar[c]=v
obj=[];bingos=sum(50 for mm in mv if len(mm)==7)
for run,cset in events:
    wm=1
    for (x,y) in run:
        if (x,y) in cset: wm*=int(WM[y][x])
    obj.append(sum(valvar[(x,y)]*(int(LM[y][x]) if (x,y) in cset else 1) for (x,y) in run)*wm)
m_.maximize(sum(obj)+bingos)
print(f"bingo-zetten: {bingos//50}; events: {len(events)}; solven...",flush=True)
sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=float(os.environ.get('TLIM','900'))
sol.parameters.num_workers=10
st=sol.solve(m_)
print("status:",sol.status_name(st))
if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,set())
    print("score_game:",int(tot),"ok:",ok,msg if not ok else '')
    if ok:
        json.dump({'grid':g2,'moves':[[list(c) for c in m] for m in mv],'blanks':[],
                   'total':int(tot),'triple':[R0,R7,R14],'plan':'referentie-topologie P/F/G dubbel-laan v1'},
                  open('experiments/results/mg_reftopo_best.json','w'))
        for y in range(15):
            print(f"{y:2d} "+' '.join(chr(96+g2[y][x]) if g2[y][x] else '.' for x in range(15)))
