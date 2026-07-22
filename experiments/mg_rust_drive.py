"""Driver: Python precompute (top-finals mask-combos) -> Rust solver (zware DFS, veel restarts) ->
Python decompose_max+score_game validatie. Zoekt de HOOGSTE bereikbare score, m.n. hoog-finals maskers
die Python niet kan sluiten. Env: MGR0/MGR7/MGR14, MGK (maskers/woord), MGCOMBOS (max combos),
MGNREST, MGTLMS, MGSHARD/MGNSHARD (combo-sharding), MGBEAM."""
import sys,os,json,subprocess,time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from itertools import combinations
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
ALPH='abcdefghijklmnopqrstuvwxyz';val={ch:r.scores[cba[ch]] for ch in ALPH}
after_ok={ch for ch in ALPH if any(isw(ch+x) for x in ALPH)}
before_ok={ch for ch in ALPH if any(isw(x+ch) for x in ALPH)}
R0=os.environ.get('MGR0','geschenkcheques');R7=os.environ.get('MGR7','verzwaringswerk');R14=os.environ.get('MGR14','polymelkzuurtje')
K=int(os.environ.get('MGK','12'));MAXCOMBOS=int(os.environ.get('MGCOMBOS','400'))
NREST=int(os.environ.get('MGNREST','120'));TLMS=int(os.environ.get('MGTLMS','120'))
SHARD=int(os.environ.get('MGSHARD','0'));NSHARD=int(os.environ.get('MGNSHARD','1'))
BEAM=os.environ.get('MGBEAM','10')
TMP='/home/bob/.claude/jobs/da7ed622/tmp'
def prl(w,m):
    pre=[c for c in range(15) if c not in m];out=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1:j+=1
        out.append(list(range(pre[i],pre[j]+1)));i=j+1
    return out
def topm(w,ok,forced,mult,k):
    base=sum(val[c] for c in w);cands=[];nf=7-len(forced);pool=[c for c in range(15) if c not in forced]
    for e in combinations(pool,nf):
        m=forced|set(e);runs=prl(w,m)
        if not all(len(s)==1 or isw(w[s[0]:s[-1]+1]) for s in runs):continue
        if not all(len(s)>=2 or w[s[0]] in ok for s in runs):continue
        sc=mult*(base+sum(val[w[cc]] for cc in (3,11) if cc in m))+50
        cands.append((sc,tuple(sorted(m))))
    cands.sort(reverse=True);return cands[:k]
m0s=topm(R0,after_ok,{0,7,14},27,K)
m14s=topm(R14,before_ok,{0,7,14},27,K)
m7s=topm(R7,after_ok,{0,14},9,K)
combos=[]
for s0,m0 in m0s:
    for s14,m14 in m14s:
        for s7,m7 in m7s:
            combos.append((s0+s14+s7,m0,m14,m7))
combos.sort(reverse=True)
combos=combos[:MAXCOMBOS]
# shard
mine=[c for i,c in enumerate(combos) if i%NSHARD==SHARD]
if not mine:
    print("geen combos",flush=True);sys.exit(0)
# stdin voor rust
inp=[f"{R0} {R7} {R14}", f"{NREST} {TLMS}"]
for sc,m0,m14,m7 in mine:
    inp.append(f"{','.join(map(str,m0))} {','.join(map(str,m14))} {','.join(map(str,m7))}")
env=dict(os.environ)
env['WORDS_ALL']=f'{TMP}/wordsall.txt';env['WORDS_CONN']=f'{TMP}/words2_8.txt'
meta=json.load(open(f'{TMP}/meta.json'))
env['VALS']=','.join(map(str,meta['val']));env['BAG']=','.join(map(str,meta['bag']))
t0=time.time()
proc=subprocess.run(['experiments/mg_solver_bin'],input='\n'.join(inp),capture_output=True,text=True,env=env)
closed=[l for l in proc.stdout.splitlines() if l.startswith('CLOSED')]
print(f"[shard{SHARD}] rust: {len(closed)} gesloten borden uit {len(mine)} combos in {time.time()-t0:.1f}s",flush=True)
best=0;bestinfo=None
for li in closed:
    parts=li.split()
    ci=parts[1];m0=list(map(int,parts[2].split(',')));m14=list(map(int,parts[3].split(',')));m7=list(map(int,parts[4].split(',')))
    bs=parts[5]
    grid=[[0]*15 for _ in range(15)]
    for y in range(15):
        for x in range(15):
            ch=bs[y*15+x]
            grid[y][x]= (ord(ch)-96) if ch!='`' else 0
    tag=f"RUST_{SHARD}_{ci}"
    json.dump({'grid':grid,'triple':[R0,R7,R14],'M0':sorted(m0),'M7':sorted(m7),'M14':sorted(m14)},
              open(f'experiments/results/mg_decomp_{tag}.json','w'))
    dec=subprocess.run(['.venv/bin/python','-u','experiments/mg_decompose_max.py'],
        env=dict(env,MGTAG=tag,MGSRC='decomp',MGBEAM=BEAM),capture_output=True,text=True).stdout
    line=[l for l in dec.splitlines() if l.startswith('MAXDECOMP')]
    if not line:
        os.remove(f'experiments/results/mg_decomp_{tag}.json');continue
    import re
    mm=re.search(r'SCORE=(\d+) \(finals=(\d+) prep=(\d+)\).*ok=(True|False)',line[0])
    if mm and mm.group(4)=='True':
        sc=int(mm.group(1));fin=int(mm.group(2));pr=int(mm.group(3))
        if sc>best:
            best=sc;bestinfo=(sc,fin,pr,tag)
            os.system(f'cp experiments/results/mg_gamemax_{tag}.json experiments/results/mg_rustbest_{SHARD}_{sc}.json')
            print(f"[shard{SHARD}] NEW BEST score={sc} finals={fin} prep={pr} (combo {ci})",flush=True)
    os.remove(f'experiments/results/mg_decomp_{tag}.json')
print(f"[shard{SHARD}] KLAAR best={best} {bestinfo}",flush=True)
