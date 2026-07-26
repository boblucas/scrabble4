"""WEAVE-GENERATOR v1 (doel >=4819): bovenhelft = 4435-recept (vast); onderhelft gegenereerd:
Vb (bottom-verticalen, 8-woorden F[c]......P[c] rijen 8-14 of razender-klasse rijen 7-13 voor kol
met (c,7) pre) x LANE (x4-laan: span dekt BEIDE DWS-cellen nieuw; kruisingen = verticalen) x
rij-14-bezorging (deliverable-DFS met atomaire blokken). CP-SAT score-max + score_game-arbiter."""
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
G='geschenkcheques';F='flexwerkstertje';P='polymelkzuurtje'
D=json.load(open('experiments/results/maxgame_BEST.json'))
grid0=D['grid'];moves0=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])
# bovenhelft-groepen uit 4435: alles met y<=7 behalve razender/woonnorm-klassen; onderhelft-groepen droppen
topg=[];fins=moves0[-3:]
gaskast=None
for m in moves0[:-3]:
    ys=[y for (_,y) in m]
    xs={x for (x,_) in m}
    if xs=={7} and len(m)==7: gaskast=m;continue
    if xs=={11} and (11,7) in m: topg.append([(11,7)]);continue   # razender -> alleen zijn (11,7), zelfde plek
    if max(ys)<=7: topg.append(m)
assert gaskast
# (4,7)/(9,7)-singles etc. zitten in topg; woonnorm(4), razender(11), indopend, uur, zuurt, z zijn bottom -> weg
def runs_ok(pl,word):
    cs=sorted(pl);i=0
    while i<len(cs):
        j=i
        while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
        if j>i and not isw(word[cs[i]:cs[j]+1]): return False
        i=j+1
    return True
def deliver14(heads,todo):
    def dfs(pl,td,seq):
        if not td: return seq
        for h in sorted(td&heads):
            np_=pl|{h}
            if runs_ok(np_,P):
                got=dfs(np_,td-{h},seq+[('H',h)])
                if got is not None: return got
        tl=sorted(td-heads)
        for size in (1,2,3):
            for blk in itertools.combinations(tl,size):
                span=set(range(min(blk),max(blk)+1))
                if not (span-set(blk)) <= pl: continue
                if not any((b-1 in pl or b+1 in pl) for b in blk): continue
                np_=pl|set(blk)
                if not runs_ok(np_,P): continue
                got=dfs(np_,td-set(blk),seq+[blk])
                if got is not None: return got
        return None
    return dfs(set(),todo|heads,[])
LANES={'L10':(10,3,11,{(4,10),(10,10)}),'L11':(11,3,11,{(3,11),(11,11)}),
       'L12a':(12,2,12,{(2,12),(12,12)}),'L12b':(12,1,11,{(2,12)}),'L13':(13,1,13,{(1,13),(13,13)}),'NONE':None}
BOTOK={c:len([w for w in bylen[8] if w[0]==cba[F[c]] and w[7]==cba[P[c]]]) for c in range(1,14) if c!=7}
def try_config(Vb,lane,tlim=240):
    g=[row[:] for row in grid0]
    for y in range(8,14):
        for x in range(15): g[y][x]=0
    for y in (8,9,10): g[y][7]=grid0[y][7]
    for x in range(15):
        if x not in {0,1,2,3,7,13,14}: pass
    # rij-14 pre: mask14 uit 4435 = {0,1,2,3,7,13,14} -> pre {4,5,6,8,9,10,11,12}
    pre14=set(Vb)
    singles14={4,5,6,8,9,10,11,12}-pre14
    if not (set(Vb)&{4,5,6}) or not (set(Vb)&{8,9,10,11,12}): return ('eiland',)
    seq=deliver14(set(Vb),singles14)
    if seq is None: return ('keten14',)
    groups=[]
    for c in Vb:
        groups.append([(c,y) for y in range(8,15)])
        for y in range(8,15): g[y][c]=1
    for item in []: pass
    lg=[]
    if lane:
        row,a,b,dws=LANES[lane]
        span=list(range(a,b+1))
        occ={(x,row) for x in span if g[row][x] or (x==7 and row in (8,9,10))}
        if any((x,row) in occ for x in [d[0] for d in dws if d[1]==row]): return ('dws-bezet',)
        newc=[(x,row) for x in span if (x,row) not in occ and not g[row][x] and not (x==7 and row in (8,9,10))]
        if len(newc)!=7: return ('laan-arith',len(newc))
        lg=[newc]
        for (x,y) in newc: g[y][x]=1
    mvpre=[gaskast]+list(topg)
    for item in seq:
        if len(item)==2 and item[0]=='H': mvpre.append([(item[1],y) for y in range(8,15)])
        else: mvpre.append([(c,14) for c in item])
    # verticalen die in seq als H voorkomen zijn al toegevoegd; groups-lijst hierboven diende alleen g
    mvpre=[m for m in mvpre]
    mv=[mvpre[0]];placed=set(mvpre[0]);rest=mvpre[1:]+lg
    while rest:
        pick=None
        for k,mm in enumerate(rest):
            if any((x+dx,y+dy) in placed for (x,y) in mm for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))):
                pick=k;break
        if pick is None: return ('order',len(rest))
        mv.append(rest.pop(pick));placed|=set(mv[-1])
    mv+=fins
    for y in (0,7,14):
        W={0:G,7:F,14:P}[y]
        for x in range(15):
            if g[y][x] or any((x,y) in m for m in mv): g[y][x]=cba[W[x]]
    occ=[(x,y) for y in range(15) for x in range(15) if g[y][x]]
    if len(occ)>101: return ('cap',len(occ))
    allmv=[c for m in mv for c in m]
    if len(allmv)!=len(set(allmv)): return ('dubbel',)
    if set(allmv)!=set(occ): return ('mismatch',len(allmv),len(occ))
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
    sol=cp_model.CpSolver();sol.parameters.max_time_in_seconds=tlim;sol.parameters.num_workers=8
    st=sol.solve(m_)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return ('infeas',sol.status_name(st))
    g2=[row[:] for row in g]
    for c in free: g2[c[1]][c[0]]=sol.value(L[c])
    tot,per,ok,msg=MG.score_game([row[:] for row in g2],mv,bl)
    return ('ok' if ok else 'rej',int(tot),sol.status_name(st),g2,mv,msg)
best=None;n=0
cands=[c for c,k in BOTOK.items() if k>=3]
for nb in (2,3,4):
    for Vb in itertools.combinations(cands,nb):
        for lane in LANES:
            key=f"Vb{Vb}-{lane}"
            res=try_config(list(Vb),None if lane=='NONE' else lane)
            n+=1
            if res[0]=='ok':
                print(f"OK {key} -> {res[1]} ({res[2]})",flush=True)
                if best is None or res[1]>best[0]:
                    best=(res[1],key)
                    json.dump({'grid':res[3],'moves':[[list(c) for c in m] for m in res[4]],'blanks':[list(b) for b in sorted(bl)],
                               'total':res[1],'triple':D['triple'],'plan':f'weave-gen v1 {key}'},
                              open('experiments/results/mg_weave_best.json','w'))
                    print(f"*** NIEUW BEST {res[1]} ***",flush=True)
            elif n%100==0: print(f"[{n}] {key} -> {res[0]}",flush=True)
print(f"KLAAR: {n} configs, best {best} (basis 4435)",flush=True)
