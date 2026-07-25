"""Variant B (bob's 7e bingo): kol-11 bingo rijen 7-13 ('r......'), mask7-swap 11<->12,
uur als 3-tegel-zet, pof+fond-steiger (6 cellen) verwijderd. Letters: footprint-CP-SAT."""
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
D=json.load(open('experiments/results/maxgame_BEST.json'))
grid0=D['grid'];moves0=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])
g=[row[:] for row in grid0]
for (x,y) in [(8,10),(9,10),(10,10),(9,11),(9,12),(9,13)]: g[y][x]=0
for y in range(8,14): g[y][11]=1  # dummy
g[7][11]=cba['r']  # ankerrij
mv=[]
for i,m in enumerate(moves0):
    if i in (16,19,20,21,22,23,24,38): continue
    if i==39: m=[(0,7),(1,7),(3,7),(8,7),(12,7),(13,7),(14,7)]  # mask7-swap
    if i==38 or i==39:
        pass
    mv.append(m)
# bingo + uur + z net voor de finals (na alle dribbles)
fin=mv[-3:];mv=mv[:-3]
mv.append([(11,y) for y in range(7,14)])
mv.append([(9,14),(10,14),(11,14)])
mv.append([(8,14)])
mv+=fin
occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
fixed={(x,y):grid0[y][x] for (x,y) in occ if y in (0,7,14) or (x,y) in bl}
fixed[(11,7)]=cba['r']
free=[c for c in occ if c not in fixed]
print(f"cellen: {len(occ)} bezet ({len(free)} vrij); zetten: {len(mv)}")
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
            k=('H',x0,y,x1-x0+1)
            if k not in seen:
                seen.add(k);run=[(xx,y) for xx in range(x0,x1+1)]
                if any(c in cset for c in run): events.append((run,cset));stage_runs.add(tuple(run))
        y0=y
        while y0>0 and (x,y0-1) in placed: y0-=1
        y1=y
        while y1<14 and (x,y1+1) in placed: y1+=1
        if y1>y0:
            k=('V',x,y0,y1-y0+1)
            if k not in seen:
                seen.add(k);run=[(x,yy) for yy in range(y0,y1+1)]
                if any(c in cset for c in run): events.append((run,cset));stage_runs.add(tuple(run))
for run in stage_runs:
    fx={i:fixed[c] for i,c in enumerate(run) if c in fixed}
    tab=[w for w in bylen.get(len(run),[]) if all(w[i]==v for i,v in fx.items())]
    if not tab: print("!! geen woorden voor run",run);sys.exit(1)
    m_.add_allowed_assignments([L[c] for c in run],tab)
for ch in range(1,27):
    cnt=[]
    for c in free:
        b=m_.new_bool_var(f"i{c}_{ch}")
        m_.add(L[c]==ch).only_enforce_if(b);m_.add(L[c]!=ch).only_enforce_if(b.negated())
        cnt.append(b)
    base=sum(1 for c,v in fixed.items() if v==ch and c not in bl)
    m_.add(sum(cnt)+base<=bag[ch])
VV=[0]+[val[i] for i in range(1,27)]
valvar={}
for c in set(sum(([cc for cc in run] for run,_ in events),[])):
    v=m_.new_int_var(0,10,f"v{c}");m_.add_element(L[c],VV,v)
    valvar[c]=m_.new_constant(0) if c in bl else v
obj=[];bingos=sum(50 for mm in mv if len(mm)==7)
for run,cset in events:
    wm=1
    for (x,y) in run:
        if (x,y) in cset: wm*=int(WM[y][x])
    obj.append(sum(valvar[(x,y)]*(int(LM[y][x]) if (x,y) in cset else 1) for (x,y) in run)*wm)
m_.maximize(sum(obj)+bingos)
print(f"bingo-50s: {bingos} ({bingos//50} zetten van 7)")
sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=600;sol.parameters.num_workers=12
sol.parameters.log_search_progress=False
st=sol.solve(m_)
print("status:",sol.status_name(st),"obj:",int(sol.objective_value) if st in (cp_model.OPTIMAL,cp_model.FEASIBLE) else '-',"bound:",int(sol.best_objective_bound))
if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,bl)
    print("score_game:",int(tot),"ok:",ok,msg if not ok else '')
    if ok:
        json.dump({'grid':g2,'moves':[[list(c) for c in m] for m in mv],'blanks':[list(b) for b in sorted(bl)],
                   'total':int(tot),'triple':D['triple'],'plan':'7e bingo kol11 rijen7-13 (bob), mask7-swap 11<->12, pof+fond weg, CP-SAT-herlettering'},
                  open('/home/bob/.claude/jobs/da7ed622/tmp/mg_variantB_best.json','w'))
        print("-> mg_variantB_best.json  (basis 4328)")
        for y in range(15):
            print(f"{y:2d} "+' '.join(chr(96+g2[y][x]) if g2[y][x] else '.' for x in range(15)))
