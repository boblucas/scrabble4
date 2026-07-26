"""TRIPLET-RANKING v2: waarde (blanco-bewust 27/9/27) + hanger-potentieel (geneste tabellen op
premiekolommen, top en bodem) + fragment-bezorgbaarheid + werkster-analoog. Output top-30."""
import sys,os,json
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
hangT=defaultdict(int);hangB=defaultdict(int)
for w in ws:
    if len(w)==8:
        if w[1:] in w7set: hangT[(w[0],w[7])]+=1
        if w[:7] in w7set: hangB[(w[0],w[7])]+=1
col8=defaultdict(int)
for w in ws:
    if len(w)==8: col8[(w[0],w[7])]+=1
def frag(w):
    n=t=0
    for L in (2,3):
        for a in range(15-L+1):
            t+=1
            if isw(w[a:a+L]): n+=1
    return n/t
def wana(w):
    return any(1<=a and a+7<=13 and a<=7<=a+7 and isw(w[a:a+8]) for a in range(8))
PR={0:3,3:2,7:3,11:2,14:3}
def score(a,b,c):
    need=Counter(a)+Counter(b)+Counter(c)
    exc=[]
    for ch in sorted(need,key=lambda ch:-val[ch]):
        for _ in range(max(0,need[ch]-bag[cba[ch]])): exc.append(ch)
    if len(exc)>2: return None
    m=27*S(a)+9*S(b)+27*S(c)
    for ch in exc:
        w=min(27 if ch in a else 99,9 if ch in b else 99,27 if ch in c else 99)
        m-=w*val[ch]
    # hangers: per kolom beste van top/bodem, gewogen premie x ~geschat woord (25)
    h=0
    for col in range(1,14):
        if col==7: continue
        ht=hangT.get((a[col],b[col]),0);hb=hangB.get((b[col],c[col]),0)
        p=PR.get(col,1)
        if ht>=5: h+=25*p
        if hb>=5: h+=25*p
    # kolomtabellen binnen (bezorg-verticalen)
    ct=sum(1 for col in (4,5,6,8,9,10,11) if col8.get((a[col],b[col]),0)>=20)
    cb=sum(1 for col in (4,5,6,8,9,10,11) if col8.get((b[col],c[col]),0)>=20)
    fr=frag(a)+frag(c)
    return m+h+15*(ct+cb)+ (30 if wana(b) else 0) + int(100*fr), m,h,ct+cb,round(fr,2)
K=250
top=sorted(w15,key=S,reverse=True)
A=top[:K];C=top[:K]
B=[w for w in top if S(w)>=38][:400]
out=[]
for a in A:
    for b in B:
        if b==a: continue
        for c in C:
            if c==a or c==b: continue
            r=score(a,b,c)
            if r: out.append((r[0],r[1],r[2],r[3],r[4],a,b,c))
out.sort(reverse=True)
with open('experiments/results/triplet_rank2.jsonl','w') as f:
    for o in out[:30]:
        f.write(json.dumps({'tot':o[0],'M':o[1],'hang':o[2],'cols':o[3],'frag':o[4],'R':[o[5],o[6],o[7]]})+"\n")
print("kandidaten:",len(out))
for o in out[:8]: print("  ",o)
cur=score('geschenkcheques','flexwerkstertje','polymelkzuurtje')
print("HUIDIG:",cur)
