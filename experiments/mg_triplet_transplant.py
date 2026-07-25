"""TRIPLET-TRANSPLANTATIE: het record-voetafdruk (maxgame_BEST) overzetten naar een nieuw
(rij0,rij14)-paar; rij 7 blijft flexwerkstertje. Ankerletters vervangen, rest vrij, blanco's:
(a) anker-overschot boven zak -> blanco op goedkoopste ankerrij (x9 voor x27), (b) 1 vrije-cel-
blanco (vrije letter, waarde 0, telt niet mee voor zak). CP-SAT + score_game."""
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
moves0=[[tuple(c) for c in m] for m in D['moves']]
F='flexwerkstertje'
def transplant(A,C,tlim=300):
    words={0:A,7:F,14:C}
    need=Counter(A)+Counter(F)+Counter(C)
    exc=[]
    for ch in sorted(need,key=lambda ch:val[cba[ch]],reverse=True):
        for _ in range(max(0,need[ch]-bag[cba[ch]])): exc.append(ch)
    if len(exc)>2: return ('zak',exc)
    bl=set()
    for ch in exc:  # blanco op ankerrij: liefst rij 7 (x9)
        rows=[7] if ch in F else [0,14]
        done=False
        for row in rows+[0,14,7]:
            for x in range(15):
                if words[row][x]==ch and (x,row) not in bl:
                    bl.add((x,row));done=True;break
            if done: break
        if not done: return ('bl-fail',ch)
    occ={(x,y) for m in moves0 for (x,y) in m}
    g=[[0]*15 for _ in range(15)]
    for (x,y) in occ:
        g[y][x]=cba[words[y][x]] if y in (0,7,14) else 1
    if len(exc)<2:  # vrije-cel-blanco (zoals (12,2) voorheen)
        for cand in [(12,2),(2,2),(5,3)]:
            if cand in occ and cand[1] not in (0,7,14): bl.add(cand);break
    mv=moves0
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
            if c in bl: continue
            b=m_.new_bool_var(f"i{c}_{ch}")
            m_.add(L[c]==ch).only_enforce_if(b);m_.add(L[c]!=ch).only_enforce_if(b.negated())
            cnt.append(b)
        base=sum(1 for c,v in fixed.items() if v==ch and c not in bl)
        m_.add(sum(cnt)+base<=bag[ch])
    VV=[0]+[val[i] for i in range(1,27)]
    valvar={}
    for c in set(sum(([cc for cc in run] for run,_ in events),[])):
        if c in bl: valvar[c]=m_.new_constant(0);continue
        v=m_.new_int_var(0,10,f"v{c}");m_.add_element(L[c],VV,v)
        valvar[c]=v
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
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,sorted(bl),msg)
if __name__=='__main__':
    best=None
    for (A,C) in [('hypochlorigzuur','jacquardweefsel'),('cyberhuwelijkje','quizmasterschap'),
                  ('gymjuffrouwtjes','quizmasterschap')]:
        res=transplant(A,C)
        print(A,'x',C,'->',res[0],res[1] if len(res)>1 and not isinstance(res[1],(list,tuple)) else res[1] if res[0]!='ok' else res[1],res[2] if res[0]=='ok' else '',flush=True)
        if res[0]=='ok' and (best is None or res[1]>best[0]):
            best=(res[1],A,C)
            json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b) for b in res[5]],
                       'total':res[1],'triple':[A,F,C],'plan':f'transplantatie 4435-voetafdruk -> {A}x{C}'},
                      open('experiments/results/mg_transplant_best.json','w'))
    print("BEST:",best,"(record 4435)")
