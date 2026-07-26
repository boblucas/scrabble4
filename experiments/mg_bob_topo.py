"""BOB-TOPOLOGIE: gaskast + WERKSTER + 2 verticale x4-bingo's door werkster (kol 4 via 'w',
kol 10 via 'e'; spans 3-10 of 4-11, beide DWS nieuw) + optionele x4-laan (rij 3 of 11, span [3,11],
kruisingen = de verts) + top-verts {2,12} (rij-0-bezorging) + bottom-verts (rij-14) + DFS-singles.
Deterministische volgorde + CP-SAT score-max + score_game."""
import sys,os,json,itertools
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
from ortools.sat.python import cp_model
import numpy as np
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
val={i:r.scores[i] for i in range(1,27)}
LM=np.array(r.letter_multiplier);WM=np.array(r.word_multiplier)
bag=Counter({c:r.counts[c] for c in r.counts})
bylen={}
for w in r.words_str: bylen.setdefault(len(w),[]).append(tuple(cba[ch] for ch in w))
import os as _os
G='geschenkcheques';F='flexwerkstertje';P='polymelkzuurtje'
if _os.environ.get('ORIENT')=='P': G,P=P,G
def runs_ok(pl,word):
    cs=sorted(pl);i=0
    while i<len(cs):
        j=i
        while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
        if j>i and not isw(word[cs[i]:cs[j]+1]): return False
        i=j+1
    return True
def deliver(word,heads,todo):
    def dfs(pl,td,seq):
        if not td: return seq
        for h in sorted(td&heads):
            np_=pl|{h}
            if runs_ok(np_,word):
                got=dfs(np_,td-{h},seq+[('H',h)])
                if got is not None: return got
        tl=sorted(td-heads)
        for size in (1,2,3):
            for blk in itertools.combinations(tl,size):
                span=set(range(min(blk),max(blk)+1))
                if not (span-set(blk)) <= pl: continue
                if not any((b-1 in pl or b+1 in pl) for b in blk): continue
                np_=pl|set(blk)
                if not runs_ok(np_,word): continue
                got=dfs(np_,td-set(blk),seq+[blk],)
                if got is not None: return got
        return None
    return dfs(set(),todo|heads,[])
def try_config(vspan,lane,Vb,tlim=600):
    # vspan: (r0,r1) voor beide x4-verts (3,10) of (4,11); lane: 3/11/None; Vb: bottom-verts
    g=[[0]*15 for _ in range(15)]
    gaskast=[(7,y) for y in range(4,11)]
    werk=[(c,7) for c in (4,5,6,8,9,10,11)]
    v4a=[(4,y) for y in range(vspan[0],vspan[1]+1) if y!=7]
    v4b=[(10,y) for y in range(vspan[0],vspan[1]+1) if y!=7]
    core=[gaskast,werk,v4a,v4b]
    lg=[]
    if lane is not None:
        occ={(x,lane) for x in (4,10)} if (vspan[0]<=lane<=vspan[1]) else set()
        newc=[(x,lane) for x in range(3,12) if (x,lane) not in occ]
        if len(newc)!=7: return ('laan-arith',len(newc))
        lg=[newc]
    topv=[[(c,y) for y in range(3)] for c in (2,12)]
    botv=[[(c,y) for y in range(8,15)] for c in Vb]
    # rij-0: pre0 = {2,12}-koppen + singles via DFS
    s0=deliver(G,{2,12},set())
    pre0={2,12}
    cand0=sorted({c for h in pre0 for c in (h-1,h+1)}|{c+d for c in {1,3,11,13} for d in (0,)} )
    # kies singles0: 6 nodig (8 pre - 2 koppen); DFS over kandidaten
    opts0=[]
    for S0 in itertools.combinations([c for c in range(1,14) if c not in (0,7,14) and c not in pre0],6):
        if not ({s for s in S0}|pre0)&{1,2,3,4,5,6} or not ({s for s in S0}|pre0)&{8,9,10,11,12,13}: continue
        seq=deliver(G,pre0,set(S0))
        if seq is not None:
            opts0.append((S0,seq))
            if len(opts0)>=4: break
    if not opts0: return ('keten0',)
    pre14=set(Vb)
    opts14=[]
    need14=8-len(Vb)
    for S14 in itertools.combinations([c for c in range(1,14) if c not in (0,7,14) and c not in pre14],need14):
        pp=set(S14)|pre14
        if not pp&{4,5,6} or not pp&{8,9,10,11,12}: continue
        seq=deliver(P,pre14,set(S14))
        if seq is not None:
            opts14.append((S14,seq))
            if len(opts14)>=4: break
    if not opts14: return ('keten14',)
    for (S0,seq0) in opts0:
     for (S14,seq14) in opts14:
      res=_inner(vspan,lane,Vb,S0,seq0,S14,seq14,tlim)
      if res[0]=='ok': return res
    return res
def _inner(vspan,lane,Vb,S0,seq0,S14,seq14,tlim):
    g=[[0]*15 for _ in range(15)]
    gaskast=[(7,y) for y in range(4,11)]
    werk=[(c,7) for c in (4,5,6,8,9,10,11)]
    v4a=[(4,y) for y in range(vspan[0],vspan[1]+1) if y!=7]
    v4b=[(10,y) for y in range(vspan[0],vspan[1]+1) if y!=7]
    lg=[]
    if lane is not None:
        occ={(x,lane) for x in (4,10)} if (vspan[0]<=lane<=vspan[1]) else set()
        newc=[(x,lane) for x in range(3,12) if (x,lane) not in occ]
        lg=[newc]
    topv=[[(c,y) for y in range(3)] for c in (2,12)]   # 3-cel-stubs: raken laan-rij-3 NIET
    botv=[[(c,y) for y in range(8,15)] for c in Vb]
    extra=[]
    if os.environ.get('EXTRA','1')=='1':
        extra=[[(8,y) for y in (1,2,4,5,6)]]             # kol-8-hanger; rij 3 = laan-cel (gat gevuld)
    botv+=extra
    scaf=[[(3,2)],[(11,2)]]   # diagonale ankers: laan-(3,3)/(11,3) -> stub-kolommen 2/12
    botv=scaf+botv
    pre0={2,12};pre14=set(Vb)
    groups=[gaskast,werk,v4a,v4b]+lg+topv
    for item in seq0:
        if len(item)==2 and item[0]=='H': continue
        groups.append([(c,0) for c in item])
    groups+=botv
    for item in seq14:
        if len(item)==2 and item[0]=='H': continue
        groups.append([(c,14) for c in item])
    mask0=sorted(set(range(15))-set(S0)-pre0)
    mask14=sorted(set(range(15))-set(S14)-pre14)
    if len(mask0)!=7 or len(mask14)!=7: return ('mask',)
    fins=[[(c,7) for c in (0,1,2,3,12,13,14)],[(c,0) for c in mask0],[(c,14) for c in mask14]]
    allc=[c for m in groups for c in m]
    if len(allc)!=len(set(allc)): return ('dubbel',)
    if len(allc)+21>101+  (21-21): pass
    for (x,y) in allc+[c for m in fins for c in m]:
        g[y][x]=cba[{0:G,7:F,14:P}[y][x]] if y in (0,7,14) else 1
    occn=sum(1 for y in range(15) for x in range(15) if g[y][x])
    if occn>101: return ('cap',occn)
    mv=[groups[0]];placed=set(groups[0]);rest=groups[1:]
    while rest:
        pick=None
        for k,mm in enumerate(rest):
            if any((x+dx,y+dy) in placed for (x,y) in mm for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                pick=k;break
        if pick is None: return ('order',len(rest))
        mv.append(rest.pop(pick));placed|=set(mv[-1])
    mv+=fins
    occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
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
        base=sum(1 for c,v in fixed.items() if v==ch)
        m_.add(sum(cnt)+base<=bag[ch])
    VV=[0]+[val[i] for i in range(1,27)]
    valvar={}
    for c in set(sum(([cc for cc in run] for run,_ in events),[])):
        v=m_.new_int_var(0,10,f"v{c}");m_.add_element(L[c],VV,v)
        valvar[c]=v
    obj=[];bingos=sum(50 for mm in mv if len(mm)==7)
    for run,cset in events:
        wm=1
        for (x,y) in run:
            if (x,y) in cset: wm*=int(WM[y][x])
        obj.append(sum(valvar[(x,y)]*(int(LM[y][x]) if (x,y) in cset else 1) for (x,y) in run)*wm)
    m_.maximize(sum(obj)+bingos)
    sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=tlim;sol.parameters.num_workers=10
    st=sol.solve(m_)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return ('infeas',sol.status_name(st))
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,set())
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,msg)
best=None
for vspan in ((3,10),(4,11)):
    for lane in (3,):
        if vspan!=(3,10): continue
        for Vb in (('5','9'),('5','11'),('6','9'),('6','11'),('6','8'),('5','8')):
            vb=[int(x) for x in Vb]
            if any(c in (4,10) for c in vb): continue
            res=try_config(vspan,lane,vb)
            tag=f"v{vspan}-L{lane}-Vb{vb}"
            print(tag,"->",res[0],res[1] if res[0]=='ok' else (str(res[1])[:50] if len(res)>1 else ''),flush=True)
            if res[0]=='ok' and (best is None or res[1]>best[0]):
                best=(res[1],tag)
                json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[],
                           'total':res[1],'triple':[G,F,P],'plan':f'bob-topologie {tag}'},
                          open('experiments/results/mg_bobtopo_best.json','w'))
                print(f"*** BEST {res[1]} ***",flush=True)
print("KLAAR:",best,flush=True)
