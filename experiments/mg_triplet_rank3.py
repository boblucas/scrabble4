"""RANKER-V3: harde bezorgbaarheids-check per ankerwoord (bestaat een 8-pre-subset waarvan elke
run len-1 is of een geldig, geordend-legbaar W-fragment) + waarde + hangers + x4-venster-compat.
R7: analoog-venster moet BEIDE x4-kolommen {4,10} of {desnoods 1} dekken. Top-15 output."""
import sys,os,json,itertools
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter,defaultdict
import maxgame_score as MG
cba=MG.r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
val={ch:MG.r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
bag=Counter({c:MG.r.counts[c] for c in MG.r.counts})
ws=MG.r.words_str;w15=[w for w in ws if len(w)==15]
S=lambda w:sum(val[ch] for ch in w)
w7set=set(w for w in ws if len(w)==7)
hangT=defaultdict(int)
for w in ws:
    if len(w)==8 and w[1:] in w7set: hangT[(w[0],w[7])]+=1
def runs_orderable(word,cols):
    """kan run 'cols' (contigu) in atomaire blokken geordend gelegd worden met alle tussenfragmenten geldig?"""
    def dfs(pl,td):
        if not td: return True
        tl=sorted(td)
        for size in (1,2,3):
            for blk in itertools.combinations(tl,size):
                sp=set(range(min(blk),max(blk)+1))
                if not (sp-set(blk))<=pl: continue
                if pl and not (set(blk)&pl or any((b-1 in pl or b+1 in pl) for b in blk)): continue
                np_=pl|set(blk)
                cs=sorted(np_);i=0;ok=True
                while i<len(cs):
                    j=i
                    while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
                    if j>i and not isw(word[cs[i]:cs[j]+1]): ok=False;break
                    i=j+1
                if ok and dfs(np_,td-set(blk)): return True
        return False
    return dfs(set(),set(cols))
from functools import lru_cache
@lru_cache(maxsize=None)
def deliverable_hard(word):
    """bestaat 8-subset van {1..6,8..13} waarvan elke maximale run len1 of orderbaar fragment is?"""
    cols=[c for c in range(1,14) if c!=7]
    for Ssub in itertools.combinations(cols,8):
        ok=True
        cs=sorted(Ssub);i=0
        while i<len(cs):
            j=i
            while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
            if j>i and not runs_orderable(word,list(range(cs[i],cs[j]+1))): ok=False;break
            i=j+1
        if ok: return True
    return False
def wanaWIN(w):
    outs=[]
    for a in range(1,7):
        if a+7<=13 and isw(w[a:a+8]): outs.append((a,a+7))
    return outs
K=int(os.environ.get('K','200'))
top=sorted(w15,key=S,reverse=True)
# harde check is duur -> cache per woord, alleen top-K
A=[w for w in top[:K] if deliverable_hard(w)]
print(f"R0/R14-kandidaten met harde bezorg-check: {len(A)}/{K}",flush=True)
B=[]
for w in top[:400]:
    wins=wanaWIN(w)
    for (a,b) in wins:
        if a<=4 and b>=10: B.append((w,(a,b)));break   # venster dekt beide x4-kolommen 4 en 10
print(f"R7-kandidaten met venster over kol 4+10: {len(B)}",flush=True)
out=[]
for a in A:
    for (b,win) in B:
        if b==a: continue
        for c in A:
            if c in (a,b): continue
            need=Counter(a)+Counter(b)+Counter(c)
            exc=sum(max(0,need[ch]-bag[cba[ch]]) for ch in need)
            if exc>2: continue
            m=27*S(a)+9*S(b)+27*S(c)-9*exc*3
            h=sum(25*(2 if col in (3,11) else 3 if col in (0,7,14) else 1) for col in range(1,14) if col!=7 and hangT.get((a[col],b[col]),0)>=5)
            out.append((m+h,m,h,a,b,c,win))
out.sort(reverse=True)
with open('experiments/results/triplet_rank3.jsonl','w') as f:
    for o in out[:15]:
        f.write(json.dumps({'tot':o[0],'M':o[1],'hang':o[2],'R':[o[3],o[4],o[5]],'win':o[6]})+"\n")
print("totaal:",len(out))
for o in out[:8]: print("  ",o,flush=True)
