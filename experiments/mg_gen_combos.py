import sys,os
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from itertools import combinations
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
ALPH='abcdefghijklmnopqrstuvwxyz';val={ch:r.scores[cba[ch]] for ch in ALPH}
after_ok={ch for ch in ALPH if any(isw(ch+x) for x in ALPH)}
before_ok={ch for ch in ALPH if any(isw(x+ch) for x in ALPH)}
R0,R7,R14,MAXC=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
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
m0s=topm(R0,after_ok,{0,7,14},27,8);m14s=topm(R14,before_ok,{0,7,14},27,8);m7s=topm(R7,after_ok,{0,14},9,8)
combos=sorted([(s0+s14+s7,m0,m14,m7) for s0,m0 in m0s for s14,m14 in m14s for s7,m7 in m7s],reverse=True)[:MAXC]
for sc,m0,m14,m7 in combos:
    print(f"{','.join(map(str,m0))} {','.join(map(str,m14))} {','.join(map(str,m7))}")
