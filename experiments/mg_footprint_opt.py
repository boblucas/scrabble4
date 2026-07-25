"""FOOTPRINT-OPTIMALITEIT (bob): gegeven het exacte voetafdruk van het recordspel (celposities +
zetstructuur + blanco-cellen + ankerletters), bewijs de OPTIMALE letterinvulling met CP-SAT.

Waarom exact: multipliers hangen alleen af van (cel, zet)-structuur (vast) => totaalscore is
LINEAIR in de letterwaarden per cel. Constraints: (a) elke maximale run in ELK tussenstadium is
een dict-woord (AddAllowedAssignments-tabellen), (b) zak-tellingen per letter, (c) ankers/blanco's
vast. CP-SAT OPTIMAL => bewezen optimum-binnen-voetafdruk. (Modelbouw in Python; solven = CP-SAT.)
"""
import sys, os, json, time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
from ortools.sat.python import cp_model
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
val={i:r.scores[i] for i in range(1,27)}
import numpy as np
LM=np.array(r.letter_multiplier);WM=np.array(r.word_multiplier)
bag=Counter({c:r.counts[c] for c in r.counts})
words=r.words_str
bylen={}
for w in words: bylen.setdefault(len(w),[]).append(tuple(cba[ch] for ch in w))

D=json.load(open('experiments/results/maxgame_BEST.json'))
grid=[row[:] for row in D['grid']];moves=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])
tot0,per0,ok0,_=MG.score_game([row[:] for row in grid],moves,bl)
print(f"basis: {int(tot0)} ok={ok0}",flush=True)

# vaste cellen: ankerrijen (0/7/14) + blanco's; vrij: rest van de bezette cellen
occ=[(x,y) for y in range(15) for x in range(15) if grid[y][x]]
fixed={}
for (x,y) in occ:
    if y in (0,7,14) or (x,y) in bl: fixed[(x,y)]=grid[y][x]
free=[c for c in occ if c not in fixed]
print(f"cellen: {len(occ)} bezet, {len(free)} vrij, {len(fixed)} vast",flush=True)

m=cp_model.CpModel()
L={}
for c in free: L[c]=m.new_int_var(1,26,f"L{c}")
for c,v in fixed.items(): L[c]=m.new_constant(v)

# scoring-events + stadium-woorden: replay de zetten; per zet: alle runs door nieuwe cellen
placed=set();events=[];stage_runs=set()
for t,cells in enumerate(moves):
    placed|=set(cells)
    cset=set(cells)
    # runs op de tussenstand
    seen=set()
    for (x,y) in cells:
        # horizontaal
        x0=x
        while x0>0 and (x0-1,y) in placed: x0-=1
        x1=x
        while x1<14 and (x1+1,y) in placed: x1+=1
        if x1>x0:
            k=('H',x0,y,x1-x0+1)
            if k not in seen:
                seen.add(k)
                run=[(xx,y) for xx in range(x0,x1+1)]
                if any(c in cset for c in run):
                    events.append((run,cset));stage_runs.add(tuple(run))
        y0=y
        while y0>0 and (x,y0-1) in placed: y0-=1
        y1=y
        while y1<14 and (x,y1+1) in placed: y1+=1
        if y1>y0:
            k=('V',x,y0,y1-y0+1)
            if k not in seen:
                seen.add(k)
                run=[(x,yy) for yy in range(y0,y1+1)]
                if any(c in cset for c in run):
                    events.append((run,cset));stage_runs.add(tuple(run))
print(f"scoring-events: {len(events)}; unieke stadium-runs: {len(stage_runs)}",flush=True)

# woord-constraints per unieke stadium-run (tabel gefilterd op vaste letters)
nwords=0
for run in stage_runs:
    n=len(run)
    cand=bylen.get(n,[])
    fx={i:fixed[c] for i,c in enumerate(run) if c in fixed}
    tab=[w for w in cand if all(w[i]==v for i,v in fx.items())]
    if not tab:
        print(f"!! geen woorden voor run {run[:3]}...  (n={n}) — voetafdruk-inconsistentie");sys.exit(1)
    m.add_allowed_assignments([L[c] for c in run],tab)
    nwords+=len(tab)
print(f"tabellen: {len(stage_runs)} runs, {nwords} rijen totaal",flush=True)

# zak: per letter aantal gebruikte niet-blanco cellen <= bag
for ch in range(1,27):
    cnt=[]
    for c in free:
        b=m.new_bool_var(f"is{c}_{ch}")
        m.add(L[c]==ch).only_enforce_if(b)
        m.add(L[c]!=ch).only_enforce_if(b.negated())
        cnt.append(b)
    base=sum(1 for c,v in fixed.items() if v==ch and c not in bl)
    m.add(sum(cnt)+base<=bag[ch])

# objectief: som over events van wm_event * som(coef_cel * val(letter))  (+50-bingo's zijn vast)
# val als element-expressie
VV=[0]+[val[i] for i in range(1,27)]
valvar={}
for c in set(sum(([cc for cc in run] for run,_ in events),[])):
    v=m.new_int_var(0,10,f"v{c}")
    m.add_element(L[c],VV,v)
    if c in bl: valvar[c]=m.new_constant(0)
    else: valvar[c]=v
obj=[]
bingos=sum(50 for mv in moves if len(mv)==7)
for run,cset in events:
    wm=1
    for (x,y) in run:
        if (x,y) in cset: wm*=int(WM[y][x])
    terms=[]
    for (x,y) in run:
        lm=int(LM[y][x]) if (x,y) in cset else 1
        terms.append(valvar[(x,y)]*lm)
    obj.append(sum(terms)*wm)
m.maximize(sum(obj)+bingos)

sol=cp_model.CpSolver()
sol.parameters.max_time_in_seconds=1800
sol.parameters.num_workers=12
sol.parameters.log_search_progress=True
print("solven...",flush=True)
st=sol.solve(m)
print(f"status: {sol.status_name(st)}  objective: {int(sol.objective_value) if st in (cp_model.OPTIMAL,cp_model.FEASIBLE) else '-'}  bound: {int(sol.best_objective_bound)}",flush=True)
if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
    g2=[row[:] for row in grid]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],moves,bl)
    print(f"score_game-verificatie: {int(tot)} ok={ok}",flush=True)
    if ok and int(tot)>int(tot0):
        json.dump({'grid':g2,'moves':[[list(c) for c in mv] for mv in moves],'blanks':[list(b) for b in sorted(bl)],
                   'total':int(tot),'triple':D['triple'],'plan':f'footprint-opt CP-SAT ({sol.status_name(st)}) vanaf {int(tot0)}'},
                  open('experiments/results/mg_footprint_best.json','w'))
        print("-> mg_footprint_best.json")
    if st==cp_model.OPTIMAL and int(sol.objective_value)==int(tot0):
        print(f"*** BEWEZEN: {int(tot0)} is OPTIMAAL binnen dit voetafdruk ***")
