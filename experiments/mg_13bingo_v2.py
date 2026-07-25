"""13-BINGO-PROVER v2 (fase A, ontdekkingsmodus): fixes t.o.v. v1:
(a) singles-sets per kop-set GEENUMEREERD (memoized) met keten-woord-DFS,
(b) ATOMAIRE meer-tegel-ankerzetten (uur-cluster-klasse) in de keten-DFS,
(c) strata V=8/H=0, V=7/H=1, V=6/H=2 (huidig record is V6H2!),
(d) H-bingo-enumeratie: spans die verticaal-kolommen mijden; 7 nieuw (8-span door gaskast-kol).
Prioritering op census-product; cap per run. SAT => 13-bingo-witness. Ledger hervatbaar."""
import sys,os,json,itertools,time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
from functools import lru_cache
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
G='geschenkcheques';F='flexwerkstertje';P='polymelkzuurtje'
CNT8={}
for c in range(1,14):
    if c==7: continue
    CNT8[('T',c)]=len([w for w in bylen[8] if w[0]==cba[G[c]] and w[7]==cba[F[c]]])
    CNT8[('B',c)]=len([w for w in bylen[8] if w[0]==cba[F[c]] and w[7]==cba[P[c]]])
TOPOK=[c for c in range(1,14) if c!=7 and CNT8[('T',c)]>0]
BOTOK=[c for c in range(1,14) if c!=7 and CNT8[('B',c)]>0]
def runs_ok(pl,word):
    cs=sorted(pl);i=0
    while i<len(cs):
        j=i
        while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
        if j>i and not isw(word[cs[i]:cs[j]+1]): return False
        i=j+1
    return True
def deliverable(placed,word,todo,seq):
    """DFS: plaats atomaire blokken (1-3 kolommen, samen met bestaand aaneengesloten span,
    rakend aan placed), elke tussenstand run-geldig. Geeft zetreeks (lijst blokken) of None."""
    if not todo: return seq
    tl=sorted(todo)
    for size in (1,2,3):
        for blk in itertools.combinations(tl,size):
            span=set(range(min(blk),max(blk)+1))
            if not (span-set(blk)) <= placed: continue          # gaten in de zet gevuld door bestaand
            if not (set(blk)&placed or any((b-1 in placed or b+1 in placed) for b in blk)): continue
            np_=placed|set(blk)
            if not runs_ok(np_,word): continue
            got=deliverable(np_,word,todo-set(blk),seq+[blk])
            if got is not None: return got
    return None
@lru_cache(maxsize=None)
def singles_options(heads,word):
    """alle geldige singles-sets (grootte 8-|heads|) + bijbehorende blok-zetreeks."""
    H=set(heads);need=8-len(H)
    if need<0: return ()
    if need==0: return (((),()),)
    cand=set()
    for h in H: cand|={h-1,h+1}
    for _ in range(4): cand|={c+d for c in cand for d in (-1,1)}
    cand={c for c in cand if 1<=c<=13 and c not in (0,7,14) and c not in H}
    out=[]
    for S in itertools.combinations(sorted(cand),need):
        seq=deliverable(frozenset(H) and set(H),word,set(S),[])
        if seq is not None: out.append((S,tuple(tuple(b) for b in seq)))
    return tuple(out)
LEDGER='experiments/results/ledger_13bingo_v3.jsonl'
done=set()
if os.path.exists(LEDGER):
    for line in open(LEDGER):
        try: done.add(json.loads(line)['key'])
        except Exception: pass
led=open(LEDGER,'a')
def hspans(row,vcols):
    occ7 = (row in (4,5,6)) or (row in (8,9,10))
    out=[]
    for a in range(0,15):
        for L in (7,8):
            sp=list(range(a,a+L))
            if sp[-1]>14: continue
            if any(c in vcols for c in sp): continue
            inc7 = 7 in sp
            new = L - (1 if (inc7 and occ7) else 0)
            if new!=7: continue
            if inc7 and not occ7 and L==8: continue
            out.append((row,a,L))
    return out
def solve_config(Vt,Vb,S0,seq0,S14,seq14,Hs,tlim=90):
    g=[[0]*15 for _ in range(15)]
    groups=[[(7,y) for y in range(4,11)],[(c,7) for c in (4,5,6,8,9,10,11)]]
    for c in Vt: groups.append([(c,y) for y in range(7)])
    for c in Vb: groups.append([(c,y) for y in range(8,15)])
    for blk in seq0: groups.append([(c,0) for c in blk])
    for blk in seq14: groups.append([(c,14) for c in blk])
    for (row,a,L) in Hs:
        occ={7} if (row in (4,5,6) or row in (8,9,10)) else set()
        groups.append([(x,row) for x in range(a,a+L) if x not in occ])
    pre0=set(Vt)|set(S0);pre14=set(Vb)|set(S14)
    mask0=sorted(set(range(15))-pre0);mask14=sorted(set(range(15))-pre14)
    fins=[[(c,7) for c in (0,1,2,3,12,13,14)],[(c,0) for c in mask0],[(c,14) for c in mask14]]
    allc=[c for m in groups for c in m]
    if len(allc)!=len(set(allc)): return ('dubbel',)
    for (x,y) in allc+[c for m in fins for c in m]:
        g[y][x]=cba[{0:G,7:F,14:P}[y][x]] if y in (0,7,14) else 1
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
    if len(occ)>101: return ('cap',len(occ))
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
    sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=tlim;sol.parameters.num_workers=6
    st=sol.solve(m_)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return ('infeas',sol.status_name(st))
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,set())
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,msg)
# ---- enumeratie met prioritering
CAP=int(os.environ.get('CAP','2500'))
cands=[]
for (V,Hn) in ((6,2),(7,1),(8,0)):
    for nt in range(2,min(V,6)+1):
        nb=V-nt
        if nb<1 or nb>6: continue
        for Vt in itertools.combinations(TOPOK,nt):
            for Vb in itertools.combinations(BOTOK,nb):
                if set(Vt)&set(Vb): continue  # zelfde-kolom: fase B (15-woorden) — hier uitgesloten
                w=1.0
                for c in Vt: w*=min(CNT8[('T',c)],500)
                for c in Vb: w*=min(CNT8[('B',c)],500)
                cands.append((w,V,Hn,Vt,Vb))
cands.sort(reverse=True)
print(f"basis-configs: {len(cands)}; cap {CAP} CP-SATs",flush=True)
best=None;ncp=0;t0=time.time()
for (w,V,Hn,Vt,Vb) in cands:
    if ncp>=CAP: break
    opts0=singles_options(Vt,G);opts14=singles_options(Vb,P)
    if not opts0 or not opts14: continue
    vcols=set(Vt)|set(Vb)
    if Hn==0: Hsets=[()]
    else:
        h1=[h for row in (4,5,6,8,9,10) for h in hspans(row,vcols)]
        h2=[h for row in (1,2,3,11,12,13) for h in hspans(row,vcols)]
        allh=h1+h2
        Hsets=[(h,) for h in allh] if Hn==1 else [(a,b) for a,b in itertools.combinations(allh,2) if a[0]!=b[0]]
        Hsets=Hsets[:40]
    def islands_ok(V,S,inner):
        pre=sorted(set(V)|set(S))
        comps=[];cur=[pre[0]]
        for c in pre[1:]:
            if c==cur[-1]+1: cur.append(c)
            else: comps.append(cur);cur=[c]
        comps.append(cur)
        for comp in comps:
            if not any(c in inner and c in V for c in comp): return False
        return True
    for (S0,seq0) in opts0[:6]:
        if not islands_ok(Vt,S0,range(4,12)): continue
        for (S14,seq14) in opts14[:6]:
            if not islands_ok(Vb,S14,range(4,12)): continue
            for Hs in Hsets:
                key=json.dumps([V,Hn,Vt,Vb,S0,S14,Hs])
                if key in done: continue
                res=solve_config(Vt,Vb,S0,seq0,S14,seq14,list(Hs))
                led.write(json.dumps({'key':key,'res':res[0],'d':str(res[1])[:80] if len(res)>1 else ''})+"\n");led.flush()
                done.add(key)
                if res[0]=='infeas' or res[0]=='ok': ncp+=1
                if res[0]=='ok':
                    print(f"*** SAT *** V{V}H{Hn} Vt{Vt} Vb{Vb} S0{S0} S14{S14} H{Hs} -> {res[1]}",flush=True)
                    if best is None or res[1]>best[0]:
                        best=(res[1],)
                        json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[],
                                   'total':res[1],'triple':[G,F,P],'plan':f'13-BINGO V{V}H{Hn} Vt{Vt} Vb{Vb}'},
                                  open('experiments/results/mg_13bingo_witness.json','w'))
                if ncp>=CAP: break
            if ncp>=CAP: break
        if ncp>=CAP: break
    if ncp and ncp%100==0: print(f"cp-sats {ncp}, {time.time()-t0:.0f}s, best {best}",flush=True)
print(f"RONDE KLAAR: {ncp} CP-SATs, best {best}",flush=True)
