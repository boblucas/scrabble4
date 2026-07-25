"""BINGO-LIJN-HERROUTERING v1 (bob): bovenhelft-topologie als zoekdimensie.
Vast: onderhelft (woonnorm-4, razender-11, indopend, zuurt/uur, gaskast), blanco (12,2) => 12 in T,
pre7=[4,11]. Vrij: T = 2 in-span kolommen (8-woorden rijen 0-7, uit {5,6,8,9,10}) + 2 buiten-span
(7-woorden rijen 0-6 + ankercel, uit {1,2,3}+{12 verplicht}), H4-span a, mask0 (afgeleid:
pre-singles moeten aan T-koppen grenzen). Elke kandidaat: greedy-touch -> CP-SAT -> arbiter."""
import sys,os,json,itertools
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
BASE=int(D['total'])
G0='geschenkcheques';F7='flexwerkstertje'
# behoud: alles met alle cellen y>=8, plus gaskast (kol 7), plus rij-7-singles worden herbouwd
keep=[];gaskast=None
for m in moves0[:-3]:
    ys=[y for (_,y) in m]
    if all(y>=7 for y in ys) and len(m)>1: keep.append(m)  # incl. razender (rijen 7-13)
    elif {x for (x,_) in m}=={7} and len(m)==7: gaskast=m
fin7=[m for m in moves0[-3:] if m[0][1]==7][0]
fin14=[m for m in moves0[-3:] if m[0][1]==14][0]
assert gaskast
PRE7=set(range(4,12))  # (7,7) incl
def build(Tin,Tout,a):
    span=list(range(a,a+8))
    if 7 not in span or not all(c in span for c in Tin): return None
    if any(c in span for c in Tout if c!=12 and c>=a and c<=a+7): pass
    T=sorted(Tin+Tout)
    if any(T[i+1]-T[i]<2 for i in range(len(T)-1)): return None
    if 12 not in Tout: return None
    heads=set(T)
    D_adj={c for t in heads for c in (t-1,t+1) if 1<=c<=13 and c not in heads and c not in (0,7,14)}
    if len(D_adj)<4: return None
    singles0=sorted(D_adj,key=lambda c:-val[cba[G0[c]]])[:4]
    pre0=set(T)|set(singles0)
    if len(pre0)!=8: return None
    mask0=sorted(set(range(15))-pre0)
    if len(mask0)!=7 or not {0,7,14}<=set(mask0): return None
    g=[[0]*15 for _ in range(15)]
    for m in keep+[gaskast]:
        for (x,y) in m: g[y][x]=grid0[y][x] or 1
    for (x,y) in [c for m in (fin7,fin14) for c in m]: pass
    for y in (0,7,14):
        W={0:G0,7:F7,14:'polymelkzuurtje'}[y]
        for x in range(15): pass
    # bovenhelft-cellen
    newcells=[]
    H4=[(x,4) for x in span if x!=7]
    newcells+=H4
    verts=[]
    for c in Tin:
        mv=[(c,y) for y in range(8) if y!=4];verts.append(mv);newcells+=mv
    anchors=[]
    for c in Tout:
        mv=[(c,y) for y in range(7)];verts.append(mv);newcells+=mv
        # ankercel: (c+1,3) als (c+1,4) in span; anders tussencel naar dichtstbijzijnde T-kol op afstand 2
        if c+1 in span and c+1 not in heads: anc=(c+1,3)
        elif c-1 in span and c-1 not in heads: anc=(c-1,3)
        else:
            nb=[t for t in heads if abs(t-c)==2]
            if not nb: return None
            anc=((c+nb[0])//2,2)
        anchors.append([anc]);newcells.append(anc)
    for c in singles0: newcells.append((c,0))
    r7singles=[[(c,7)] for c in sorted(PRE7) if c!=7 and c not in Tin and c!=11]
    for m in r7singles: newcells+=m
    for (x,y) in newcells:
        g[y][x]=grid0[y][x] or 1
    for y in (0,7,14):
        W={0:G0,7:F7,14:'polymelkzuurtje'}[y]
        for x in range(15):
            if g[y][x]: g[y][x]=cba[W[x]]
    newfin0=sorted([(x,0) for x in mask0])
    groups=[gaskast,H4]+verts+anchors+[[ (c,0)] for c in singles0]+r7singles+keep
    mv=[groups[0]];placed=set(groups[0]);rest=groups[1:]
    while rest:
        pick=None
        for k,mm in enumerate(rest):
            if any((x+dx,y+dy) in placed for (x,y) in mm for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                pick=k;break
        if pick is None: return ('order',len(rest))
        mv.append(rest.pop(pick));placed|=set(mv[-1])
    mv+= [fin7,newfin0,fin14]
    n=sum(1 for y in range(15) for x in range(15) if g[y][x])
    return (g,mv,n)
def solve_fp(g,mv,tlim=180):
    occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ)>101: return ('cap',len(occ))
    fixed={(x,y):g[y][x] for (x,y) in occ if y in (0,7,14) or (x,y) in bl}
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
best=BASE;cnt=0
for Tin in itertools.combinations((5,6,8,9,10),2):
    if Tin[1]-Tin[0]<2: continue
    for Tout1 in (1,2,3):
        Tout=(Tout1,12)
        for a in (2,3,4):
            b=build(list(Tin),list(Tout),a)
            if b is None:
                print(f"skip Tin{Tin} Tout{Tout} a{a}: None",flush=True);continue
            if b[0]=='order':
                print(f"skip Tin{Tin} Tout{Tout} a{a}: order rest={b[1]}",flush=True);continue
            g,mv,n=b
            if n>101: continue
            res=solve_fp(g,mv)
            cnt+=1
            tag=f"Tin{Tin} Tout{Tout} a{a} n{n}"
            if res[0]=='ok':
                print(f"RER {tag} -> {res[1]} ({res[2]})",flush=True)
                if res[1]>best:
                    best=res[1]
                    json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b2) for b2 in sorted(bl)],
                               'total':res[1],'triple':D['triple'],'plan':f'herroutering {tag}'},
                              open('experiments/results/mg_reroute_best.json','w'))
                    print(f"*** NIEUW BEST {res[1]} ***",flush=True)
            else:
                print(f"RER {tag} -> {res[0]}",flush=True)
print(f"KLAAR: {cnt} kandidaten, best {best} (basis {BASE})",flush=True)
