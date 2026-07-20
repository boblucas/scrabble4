"""Sweep de algemene solver over top-viable triples (auto-maskers). Log welke SLUITEN."""
import sys, os, subprocess
sys.path.insert(0,'/home/bob/programming/scrabble4'); sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from itertools import combinations
import maxgame_score as MG
r=MG.r; cba=r.alphabet.cba; lk=MG.lk
def isw(s): return tuple(cba[c] for c in s) in lk
val={ch:r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
ALPH='abcdefghijklmnopqrstuvwxyz'
after_ok={ch for ch in ALPH if any(isw(ch+x) for x in ALPH)}
before_ok={ch for ch in ALPH if any(isw(x+ch) for x in ALPH)}
def prl_runs(w,m):
    pre=[c for c in range(15) if c not in m]; out=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1: j+=1
        out.append(list(range(pre[i],pre[j]+1))); i=j+1
    return out
def best_mask(w,ok):
    base=sum(val[c] for c in w); best=-1;bm=None
    for e in combinations([c for c in range(15) if c not in (0,7,14)],4):
        m=set((0,7,14))|set(e); runs=prl_runs(w,m)
        if not all(len(s)==1 or isw(w[s[0]:s[-1]+1]) for s in runs): continue
        if not all(len(s)>=2 or w[s[0]] in ok for s in runs): continue
        sc=27*(base+sum(val[w[cc]] for cc in (3,11) if cc in m))+50
        if sc>best: best=sc;bm=tuple(sorted(m))
    return best,bm
# top-viable triples uit de rank-tsv
rows=[l.rstrip('\n').split('\t') for l in open('experiments/results/maxgame_triplerank.tsv')][1:]
seen=set(); tried=0
for row in rows:
    rank,score,R0,R14,R7=row[0],row[1],row[2],row[3],row[4]
    if R7!='babyzwemmertjes': continue     # R7-machinerie is alleen voor babyzwemmertjes gevalideerd
    key=(R0,R14,R7)
    if key in seen: continue
    seen.add(key)
    _,m0=best_mask(R0,after_ok); _,m14=best_mask(R14,before_ok)
    if not m0 or not m14: continue
    env=dict(os.environ, MGR0=R0, MGR14=R14, MGR7=R7, MGM0=str(m0), MGM14=str(m14))
    try:
        out=subprocess.run(['.venv/bin/python','experiments/maxgame_solve.py'],env=env,
                           capture_output=True,text=True,timeout=120).stdout
    except Exception: continue
    line=[l for l in out.splitlines() if l.startswith('solve:')]
    tag=line[0] if line else out.strip()[:80]
    closed='SKELET SLUIT' in out
    print(f"#{rank} score{score} {R0}/{R14}: {tag} {'*** SLUIT ***' if closed else ''}",flush=True)
    tried+=1
    if tried>=40: break
print("sweep klaar",flush=True)
