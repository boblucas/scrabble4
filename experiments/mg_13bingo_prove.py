"""13-BINGO-PROVER fase A (ontdekkingsmodus): gaskast + WERKSTER + 8 verticalen + 3 finals = 13.
Stratum V=8/H=0 (tel-lemma: S_n=2 steigercellen, S_a=16-8=8 anker-singles = precies pre-rest).
Enumereert (V_top,V_bot) met bezorgbaarheids- en keten-woord-filters (ankerrij-letters vast!),
dan greedy-touch + CP-SAT. SAT => 13-bingo-witness (RECORD); ledger voor hervatting.
LET OP: fase A is alleen-SAT-geldig; voor de onmogelijkheidsstelling volgt fase B
(volgorde-volledigheid). Zie experiments/THEOREM_13BINGO_PLAN.md."""
import sys,os,json,itertools,time
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
G='geschenkcheques';F='flexwerkstertje';P='polymelkzuurtje'
# 15-woord zelfde-kolom-check (top+bottom): patroon G[c]+6vrij+F[c]+6vrij+P[c]
w15={c:len([w for w in r.words_str if len(w)==15 and w[0]==G[c] and w[7]==F[c] and w[14]==P[c]]) for c in range(1,14) if c!=7}
TOPOK=[c for c in range(1,14) if c!=7 and len([w for w in bylen[8] if w[0]==cba[G[c]] and w[7]==cba[F[c]]])>0]
BOTOK=[c for c in range(1,14) if c!=7 and len([w for w in bylen[8] if w[0]==cba[F[c]] and w[7]==cba[P[c]]])>0]
print("topok:",TOPOK,"botok:",BOTOK,"15w-zelfde-kol:",{c:n for c,n in w15.items() if n},flush=True)
def chain_orders_ok(cols,heads,word):
    """singles (cols) + verthoofden (heads) op een ankerrij: bestaat een plaatsingsvolgorde van de
    singles (elk rakend aan al-geplaatst in de rij OF aan zijn kolom... hier: rij-adjacentie of
    verthoofd) zodat elke tussenrun (aaneengesloten, len>=2) een woord is? DFS, letters vast."""
    placed=set(heads)
    def runs_ok(pl):
        cs=sorted(pl);i=0
        while i<len(cs):
            j=i
            while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
            if j>i:
                seg=word[cs[i]:cs[j]+1]
                if not isw(seg): return False
            i=j+1
        return True
    todo=set(cols)
    def dfs(pl,td):
        if not td: return True
        for c in sorted(td):
            if (c-1 in pl) or (c+1 in pl):
                np_=pl|{c}
                if runs_ok(np_) and dfs(np_,td-{c}): return True
        return False
    return dfs(placed,todo)
LEDGER='experiments/results/ledger_13bingo_v8.jsonl'
done=set()
if os.path.exists(LEDGER):
    for line in open(LEDGER):
        try: done.add(tuple(json.loads(line)['key']))
        except Exception: pass
def solve_config(Vt,Vb,sc_cells,tlim=120):
    g=[[0]*15 for _ in range(15)]
    groups=[[(7,y) for y in range(4,11)],[(c,7) for c in (4,5,6,8,9,10,11)]]
    for c in Vt: groups.append([(c,y) for y in range(7)])
    for c in Vb: groups.append([(c,y) for y in range(8,15)])
    pre0=set(Vt);pre14=set(Vb)
    # singles: kies bezorgbare kolommen adjacënt aan koppen/elkaar tot 8, met keten-woord-check
    for pre,heads,word,row in ((pre0,set(Vt),G,0),(pre14,set(Vb),P,14)):
        cand=sorted({c for h in heads for c in (h-1,h+1) if 1<=c<=13 and c not in (0,7,14)}-heads)
        # breid uit met tweede-orde (buur van buur)
        for _ in range(3):
            cand=sorted(set(cand)|{c for s in cand for c in (s-1,s+1) if 1<=c<=13 and c not in (0,7,14)}-heads)
        for c in cand:
            if len(pre)>=8: break
            if c not in pre: pre.add(c)
        if len(pre)!=8: return ('pre-tekort',len(pre))
    s0=sorted(pre0-set(Vt));s14=sorted(pre14-set(Vb))
    if not chain_orders_ok(s0,set(Vt),G): return ('keten0',s0)
    if not chain_orders_ok(s14,set(Vb),P): return ('keten14',s14)
    for c in s0: groups.append([(c,0)])
    for c in s14: groups.append([(c,14)])
    for cell in sc_cells: groups.append([cell])
    mask0=sorted(set(range(15))-pre0-{c for c in Vt});mask0=sorted(set(range(15))-pre0)
    mask14=sorted(set(range(15))-pre14)
    if len(mask0)!=7 or len(mask14)!=7: return ('mask',len(mask0),len(mask14))
    fins=[[(c,7) for c in (0,1,2,3,12,13,14)],[(c,0) for c in mask0],[(c,14) for c in mask14]]
    allcells=[c for m in groups for c in m]
    if len(allcells)!=len(set(allcells)): return ('dubbel',)
    for (x,y) in allcells+[c for m in fins for c in m]:
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
    # blanco's: 1 op bord toegestaan -> zak+1 flexibiliteit NIET gemodelleerd in fase A (strenger = ok voor SAT)
    for ch in range(1,27):
        cnt=[]
        for c in free:
            b=m_.new_bool_var(f"i{c}_{ch}")
            m_.add(L[c]==ch).only_enforce_if(b);m_.add(L[c]!=ch).only_enforce_if(b.negated())
            cnt.append(b)
        base=sum(1 for c,v in fixed.items() if v==ch)
        m_.add(sum(cnt)+base<=bag[ch]+ (1 if ch==cba.get('e',5) and False else 0))
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
led=open(LEDGER,'a')
best=None;cnt=0
SC=[(3,3),(11,2),(3,11),(11,12),(2,2),(12,12)]
for nt in (4,5,3):
    nb=8-nt
    for Vt in itertools.combinations(TOPOK,nt):
        for Vb in itertools.combinations(BOTOK,nb):
            if set(Vt)&set(Vb) and any(w15.get(c,0)==0 for c in set(Vt)&set(Vb)): continue
            key=('V8',Vt,Vb)
            if tuple(map(str,key)) in done: continue
            # steiger: fase A simpel: geen (S_n=2 mag ook leeg — minder cellen = onder cap prima? NEE:
            # 13x7=91+8 singles+2 steiger=101; zonder steiger 99 -> mag (cap is bovengrens)
            res=solve_config(list(Vt),list(Vb),[])
            cnt+=1
            tag=f"Vt{Vt} Vb{Vb}"
            led.write(json.dumps({'key':list(map(str,key)),'res':res[0],'d':str(res[1]) if len(res)>1 else ''})+"\n");led.flush()
            if res[0]=='ok':
                print(f"*** SAT *** {tag} -> {res[1]} ({res[2]})",flush=True)
                if best is None or res[1]>best[0]:
                    best=(res[1],tag)
                    json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[],
                               'total':res[1],'triple':[G,F,P],'plan':f'13-BINGO {tag}'},
                              open('experiments/results/mg_13bingo_witness.json','w'))
            elif cnt%50==0:
                print(f"[{cnt}] {tag} -> {res[0]}",flush=True)
print(f"KLAAR V8-stratum: {cnt} configs, best: {best}",flush=True)
