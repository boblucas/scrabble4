"""Pijler 3: per-FAMILIE sound finals-UB via de legale maskerruimte, gecached per (woord,rol).

rowUB(w,y) = max over LEGALE maskers (groottes 3-7; pre-runs dict-woorden; TWS geforceerd) van
  mainscore(w,mask,y) + Σ_{c in mask} crossmax(c,y,w[c])
met crossmax = max kruiswoordscore bij de slotzet over echte dict-woorden (per-woord zak-haalbaar,
doorloop door andere ankerrijen GERELAXEERD toegestaan -> sound).
F*(familie) = rowUB(R0,0)+rowUB(R14,14)+rowUB(R7,7).  Eliminatie: F* + P* < LB => familie weg.

Cache per (woord,rol) — woorden delen over families. Output: frontier-tabel + per-familie F*.
"""
import sys, os, json
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from itertools import combinations
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
ALPH='abcdefghijklmnopqrstuvwxyz'
val={ch:r.scores[cba[ch]] for ch in ALPH}
import numpy as np
LM=np.array(r.letter_multiplier);WM=np.array(r.word_multiplier)
bag={ch:r.counts[cba[ch]] for ch in ALPH}
words=r.words_str
def bagok_skip(w,skip):
    c=Counter(ch for i,ch in enumerate(w) if i!=skip)
    return all(c[ch]<=bag[ch] for ch in c)

# crossmax per (rol y, kolom c, letter a): onafhankelijk van de andere ankerwoorden (doorloop gerelaxeerd)
bypos={}
for w in words:
    for i,ch in enumerate(w):
        bypos.setdefault((ch,i),[]).append(w)
CMX={}
def crossmax(c,y,a):
    k=(c,y,a)
    if k in CMX: return CMX[k]
    best=0
    lm=int(LM[y][c]);wm=int(WM[y][c])
    for i in range(15):
        for w in bypos.get((a,i),[]):
            L=len(w);y0=y-i
            if L<2 or y0<0 or y0+L-1>14: continue
            if not bagok_skip(w,i): continue
            sc=(sum(val[ch] for ch in w)-val[a]+val[a]*lm)*wm
            if sc>best: best=sc
    CMX[k]=best
    return best

def prl(m):
    pre=[c for c in range(15) if c not in m];out=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1:j+=1
        out.append((pre[i],pre[j]));i=j+1
    return out
def mainscore(w,m,y):
    sc=0;wm=1
    for c in range(15):
        if c in m: sc+=val[w[c]]*int(LM[y][c]); wm*=int(WM[y][c])
        else: sc+=val[w[c]]
    return sc*wm+(50 if len(m)==7 else 0)

ROWCACHE={}
def rowUB(w,y):
    k=(w,y)
    if k in ROWCACHE: return ROWCACHE[k]
    forced={0,7,14} if y in (0,14) else {0,14}
    pool=[c for c in range(15) if c not in forced]
    if y==7: pool=[c for c in pool if c!=7]  # center-lemma: (7,7) is altijd al bezet voor de slotzet
    best=-1
    for size in (3,4,5,6,7):
        nf=size-len(forced)
        if nf<0: continue
        for e in combinations(pool,nf):
            m=set(forced)|set(e)
            ok=True
            for (a,b) in prl(m):
                if b>a and not isw(w[a:b+1]): ok=False;break
            if not ok: continue
            tot=mainscore(w,m,y)
            if os.environ.get('MGCROSS','1')=='1': tot+=sum(crossmax(c,y,w[c]) for c in m)
            if tot>best: best=tot
    ROWCACHE[k]=best
    return best

if __name__=='__main__':
    LB=4321
    rows=[l.split('\t') for l in open('experiments/results/maxgame_triplerank.tsv')][1:]
    fams=[]
    seen=set()
    for rr in rows:
        try: R0,R14,R7=rr[2],rr[3],rr[4]
        except: continue
        key=(R0,R7,R14)
        if key in seen: continue
        seen.add(key)
        fams.append(key)
    SH=int(os.environ.get('SHARD','0'));NSH=int(os.environ.get('NSHARD','1'))
    out=open(f'experiments/results/mg_family_ub_{SH}.tsv','w')
    n=0
    for i,(R0,R7,R14) in enumerate(fams):
        if i%NSH!=SH: continue
        f=rowUB(R0,0)+rowUB(R14,14)+rowUB(R7,7)
        out.write(f"{f}\t{R0}\t{R7}\t{R14}\n")
        n+=1
        if n%500==0: print(f"[{SH}] {n} families, cache={len(ROWCACHE)}",flush=True)
    out.close()
    print(f"[{SH}] klaar: {n} families",flush=True)
