"""STRUCT-SWEEP (bob's 'veel onafhankelijke keuzes'-punt): systematische zoeker over de
STRUCTUURLAAG die tot nu toe handwerk was.
Dimensies per kandidaat: (1) mask-swap i<->j op rij 0/7/14 (slotcel <-> pre-cel);
(2) sloop van wees-geworden steigerzetten (subsets van 1-2-cel-zetten nabij j, greedy-touch-gecheckt);
(3) herplaatsing van vrijgekomen tegels uit een auto-catalogus (lege koppels/singles naast bezet,
premie-gerankt). Elke kandidaat: stabiele greedy-touch-ordening -> footprint-CP-SAT (alle letters
vrij behalve ankers/blanco's) -> score_game-arbiter. Basis: experiments/results/maxgame_BEST.json.
Gebruik: python experiments/mg_structsweep.py [tlim_per_solve] ; log: STRUCT-regels, best-dump naar
experiments/results/mg_struct_best.json"""
import sys,os,json,itertools,time
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
TLIM=float(sys.argv[1]) if len(sys.argv)>1 else 300
D=json.load(open('experiments/results/maxgame_BEST.json'))
grid0=D['grid'];moves0=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])
BASE=int(D['total'])
ANCH={0,7,14}

def greedy_order(groups,finals):
    mv=[groups[0]];placed=set(groups[0]);rest=list(groups[1:])
    while rest:
        pick=None
        for k,mm in enumerate(rest):
            if any((x+dx,y+dy) in placed for (x,y) in mm for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                pick=k;break
        if pick is None: return None
        mv.append(rest.pop(pick));placed|=set(mv[-1])
    return mv+finals

def solve_fp(g,mv,tlim):
    occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ)>101: return ('cap',len(occ))
    fixed={(x,y):grid0[y][x] for (x,y) in occ if y in ANCH or (x,y) in bl}
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
    sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=tlim;sol.parameters.num_workers=6
    st=sol.solve(m_)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return ('infeas',sol.status_name(st))
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,bl)
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,msg)

# --- catalogus: lege koppels/singles naast bezette cellen (geen 8+-run-extensies), premie-gerankt
occ0={(x,y) for y in range(15) for x in range(15) if grid0[y][x]}
def runlen_if(cell,extra):
    x,y=cell;tot=1
    for dx,dy in ((1,0),(0,1)):
        n=1
        for s in (1,-1):
            cx,cy=x+s*dx,y+s*dy
            while (cx,cy) in occ0 or (cx,cy) in extra: n+=1;cx+=s*dx;cy+=s*dy
        tot=max(tot,n)
    return tot
def prem(c):
    x,y=c
    return int(WM[y][x])*4+int(LM[y][x])
cands=[]
empty=[(x,y) for y in range(15) for x in range(15) if not grid0[y][x]]
occ_adj=lambda c,extra: any((c[0]+dx,c[1]+dy) in occ0 or (c[0]+dx,c[1]+dy) in extra for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))
for c in empty:
    if occ_adj(c,set()) and runlen_if(c,set())<=7:
        cands.append(([c],prem(c)))
    for d in ((1,0),(0,1)):
        c2=(c[0]+d[0],c[1]+d[1])
        if c2 in occ0 or c2[0]>14 or c2[1]>14 or grid0[c2[1]][c2[0]]: continue
        if (occ_adj(c,{c2}) or occ_adj(c2,{c})) and runlen_if(c,{c2})<=7 and runlen_if(c2,{c})<=7:
            cands.append(([c,c2],prem(c)+prem(c2)))
cands.sort(key=lambda t:-t[1])
CAT=[cells for cells,_ in cands[:40]]
print(f"catalogus: {len(cands)} kandidaten, top-40 in gebruik",flush=True)

# --- structuur: per rij mask (slotzet-cellen) en pre-cellen; 1/2-cel steigerzetten
finals=moves0[-3:];prep=moves0[:-3]
maskrow={m[0][1]:set(x for (x,_) in m) for m in finals}
small=[i for i,m in enumerate(prep) if len(m)<=2 and all((x,y) not in bl for (x,y) in m)]
best=BASE;cnt=0
def attempt(g,groups,fin,tag):
    global best,cnt
    mv=greedy_order(groups,fin)
    if mv is None: return
    res=solve_fp(g,mv,TLIM)
    cnt+=1
    if res[0]=='ok':
        print(f"STRUCT {tag} -> {res[1]} ({res[2]})",flush=True)
        if res[1]>best:
            best=res[1]
            json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b) for b in sorted(bl)],
                       'total':res[1],'triple':D['triple'],'plan':f'struct-sweep {tag}'},
                      open('experiments/results/mg_struct_best.json','w'))
            print(f"*** NIEUW BEST {res[1]} ({tag}) ***",flush=True)
    elif res[0] not in ('infeas','nowords','cap'):
        print(f"STRUCT {tag} -> {res[0]}",flush=True)

for row in (0,14,7):
    W={0:'geschenkcheques',7:'flexwerkstertje',14:'polymelkzuurtje'}[row]
    mask=maskrow[row];pre=set(range(15))-mask
    for i in sorted(mask-{0,7,14}):  # TWS-kolommen moeten in de slotzet blijven (x27)
        for j in sorted(pre):
            # j -> slot; i -> pre. i moet 1-tegel-plaatsbaar zijn (buurcel bezet, niet via j)
            nb=[(i+s,row) for s in (1,-1) if 0<=i+s<15]+[(i,row+s) for s in (1,-1) if 0<=row+s<15]
            if not any(c in occ0 and c!=(j,row) for c in nb): continue
            jmove=[k for k,m in enumerate(prep) if m==[(j,row)]]
            if not jmove: continue  # j door multi-zet gelegd: overslaan (v1)
            newfin=[m if m[0][1]!=row else sorted([(x,row) for x in (mask-{i})|{j}]) for m in finals]
            # wees-subsets: kleine zetten binnen afstand 3 van (j,row)
            nearby=[k for k in small if k not in jmove and all(abs(x-j)<=3 and abs(y-row)<=3 for (x,y) in prep[k])]
            for ns in range(0,3):
                for sub in itertools.combinations(nearby,ns):
                    dropped={k for k in jmove}|set(sub)
                    freed=sum(len(prep[k]) for k in sub)
                    g=[r0[:] for r0 in grid0]
                    for k in sub:
                        for (x,y) in prep[k]: g[y][x]=0
                    groups=[m for k,m in enumerate(prep) if k not in dropped]+[[(i,row)]]
                    tagb=f"r{row} {W[i]}{i}<->{W[j]}{j} sloop{[prep[k] for k in sub]}"
                    if freed==0:
                        attempt(g,groups,newfin,tagb)
                    else:
                        for dep in CAT:
                            if len(dep)!=freed: continue
                            if any(g[y][x] for (x,y) in dep): continue
                            g2=[r0[:] for r0 in g]
                            for (x,y) in dep: g2[y][x]=1
                            attempt(g2,groups+[dep],newfin,tagb+f"+dep{dep}")
print(f"KLAAR: {cnt} kandidaten, best {best} (basis {BASE})",flush=True)
