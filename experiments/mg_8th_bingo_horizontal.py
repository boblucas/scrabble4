"""8e bingo (bob): horizontale bingo rij 4 kol a..a+7 door (7,4)w; kolommen die hij kruist
worden 8-woorden rijen 0-7 (leggen hun rij-7-pre-cel mee, blijven 7 nieuw = bingo).
Voetafdruk-chirurgie op maxgame_BEST (4362) + stabiele greedy-touch-ordening + footprint-CP-SAT."""
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

def try_variant(a,tlim=900):
    span=list(range(a,a+8))
    if 7 not in span: return None
    Hcells=[(x,4) for x in span if x!=7]
    crossed=[c for c in (2,5,10,12) if c in span]  # verticalen die 8-woord worden
    g=[row[:] for row in grid0]
    rm=[(4,3),(6,6)]
    if a==2: rm=[(3,3),(4,3),(6,6)]  # (3,3)-anker vervalt (kol2 kruist bingo zelf)
    for (x,y) in rm: g[y][x]=0
    for (x,y) in Hcells: g[y][x]=g[y][x] or 1
    for c in crossed: g[7][c]=grid0[7][c] or cba['flexwerkstertje'[c]]
    if 12 in crossed: return ('mask-conflict',)  # (12,7) is maskercel; niet ondersteund
    # zetgroepen opbouwen
    def is1(m,cell):return len(m)==1 and m[0]==cell
    dropcells={(8,4),(9,4),(4,4),(4,3),(6,6)}|set((c,7) for c in crossed)
    if a==2: dropcells|={(3,3)}
    groups=[];verts={2:[],5:[],10:[],12:[]}
    for m in moves0:
        xs={x for (x,y) in m};ys={y for (x,y) in m}
        if len(m)==1 and m[0] in dropcells: continue
        if len(xs)==1 and len(m)>=3 and list(xs)[0] in (2,5,10,12) and max(ys)<=7:
            c=list(xs)[0]
            if c in crossed:
                groups.append([(c,y) for y in range(0,8) if (c,y)!=(c,4)])  # 7 nieuw incl (c,7)
            else: groups.append(m)
            continue
        groups.append(m)
    finals=groups[-3:];groups=groups[:-3]
    groups.insert(1,Hcells)
    # stabiele greedy-touch
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
    print(f"a={a}: cellen {len(occ)}, zetten {len(mv)}, bingo-zetten {sum(1 for m in mv[:-3] if len(m)==7)}")
    if len(occ)>101: return ('cap',len(occ))
    fixed={(x,y):grid0[y][x] if y!=7 or grid0[y][x] else cba['flexwerkstertje'[x]] for (x,y) in occ if y in (0,7,14) or (x,y) in bl}
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
for a in (3,4,2):
    res=try_variant(a)
    print(f"a={a} ->",res[0],res[1] if len(res)>1 and not isinstance(res[1],list) else '',flush=True)
    if res[0]=='ok' and (best is None or res[1]>best[1]):
        best=(a,res[1],res)
        json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b) for b in sorted(bl)],
                   'total':res[1],'triple':D['triple'],'plan':f'8e bingo horizontaal rij4 kol{a}-{a+7} (bob) + 8-letter-verticalen, CP-SAT'},
                  open('/home/bob/.claude/jobs/da7ed622/tmp/mg_8bingo_best.json','w'))
print("BEST:",best[0] if best else None,best[1] if best else '-',"(basis 4362)")
if best:
    g2=best[2][3]
    for y in range(15):
        print(f"{y:2d} "+' '.join(chr(96+g2[y][x]) if g2[y][x] else '.' for x in range(15)))
