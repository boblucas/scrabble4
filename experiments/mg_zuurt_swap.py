"""ZUURT-swap (bob): (12,14)t pre ('zuurt'), mask14-swap 12<->1 (o in slotzet), asbo-keten (4 cellen)
weg; 4 vrije tegels herplaatsen. Varianten: V1 geen (97), V2 kol3 rijen10-13 (DWS 3,11 + slot-y 5-woord),
V4 kol9 rijen8-11 (TLS 9,9), V3 kol3(12,11)+kol9(8,9) mix, V2b kol3(10-12)+kol9(8)."""
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
D=json.load(open('/home/bob/.claude/jobs/da7ed622/tmp/base4373.json'))
grid0=D['grid'];moves0=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])

DEPLOY={
 'V2m':[[(3,10),(3,11),(3,12),(3,13)]],
 'V4m':[[(9,8),(9,9),(9,10),(9,11)]],
 'V4b':[[(9,8),(9,9)],[(6,8)],[(8,8)]],
 'V4c':[[(9,8),(9,9),(9,10)],[(6,8)]],
 'V6':[[(6,8)],[(8,8)],[(3,11),(3,12)]],
 'V7':[[(9,8),(9,9)],[(3,11),(3,12)]],
 'V8':[[(3,11),(3,12),(3,13)],[(6,8)]],
}
def try_variant(name,tlim=600):
    dep=DEPLOY[name]
    g=[row[:] for row in grid0]
    for (x,y) in [(1,12),(2,12),(3,12),(1,13)]: g[y][x]=0
    for grp in dep:
        for (x,y) in grp: g[y][x]=g[y][x] or 1
    dropcells={(1,12),(2,12),(3,12),(1,13),(1,14)}
    groups=[]
    for m in moves0:
        if all(c in dropcells for c in m): continue
        if len({y for (_,y) in m})==1 and list({y for (_,y) in m})[0]==14 and len(m)==7:
            m=[(0,14),(1,14),(2,14),(3,14),(7,14),(13,14),(14,14)]  # mask14-swap 12<->1
        groups.append(m)
    finals=groups[-3:];groups=groups[:-3]
    groups.append([(12,14)])
    groups+=dep
    mv=[groups[0]];placed=set(groups[0]);rest=groups[1:]
    while rest:
        pick=None
        for k,mm in enumerate(rest):
            if any((x+dx,y+dy) in placed for (x,y) in mm for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                pick=k;break
        if pick is None: return ('order',[tuple(mm) for mm in rest])
        mv.append(rest.pop(pick));placed|=set(mv[-1])
    mv+=finals
    occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ)>101: return ('cap',len(occ))
    fixed={(x,y):grid0[y][x] for (x,y) in occ if y in (0,7,14) or (x,y) in bl}
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
    for run in stage_runs:
        fx={i:fixed[c] for i,c in enumerate(run) if c in fixed}
        tab=[w for w in bylen.get(len(run),[]) if all(w[i]==v for i,v in fx.items())]
        if not tab: return ('nowords',run)
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
    sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=tlim;sol.parameters.num_workers=12
    st=sol.solve(m_)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return ('infeas',sol.status_name(st))
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,bl)
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,msg)

best=None
for name in DEPLOY:
    res=try_variant(name)
    print(name,"->",res[0],res[1] if len(res)>1 and not isinstance(res[1],(list,tuple)) else res[1:2],res[2] if res[0]=='ok' else '',flush=True)
    if res[0]=='ok' and (best is None or res[1]>best[1]):
        best=(name,res[1],res)
        json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b) for b in sorted(bl)],
                   'total':res[1],'triple':D['triple'],'plan':f'zuurt-swap mask14 12<->1 (bob) + herplaatsing {name}'},
                  open('/home/bob/.claude/jobs/da7ed622/tmp/mg_zuurt_best.json','w'))
print("BEST:",best[0] if best else None,best[1] if best else '-',"(basis 4373)")
if best:
    g2=best[2][3]
    for y in range(15):
        print(f"{y:2d} "+' '.join(chr(96+g2[y][x]) if g2[y][x] else '.' for x in range(15)))
