"""FRAME-RANKER (campagne >=4819): zoek sextetten (R0,R7,R14,C0,C7,C14) van 15-woorden met
9 snijpunt-consistenties. Score = blanco-bewust: 27*S(R0)+9*S(R7)+27*S(R14) + 3*(S(C0)+S(C7)+S(C14))
+ segment-bonus (C[1:7]/C[8:14] zelf woorden = legbaarheid) + werkster-analoog-bonus R7.
Blanco's: overschot boven zak -> laagst-gewogen duplicaatcel (rij 27/9/27, kolom-interieur 3).
Output: top-sextetten naar experiments/results/frame_top.jsonl"""
import sys,os,json,time
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter,defaultdict
import maxgame_score as MG
cba=MG.r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
val={ch:MG.r.scores[cba[ch]] for ch in 'abcdefghijklmnopqrstuvwxyz'}
bag=Counter({c:MG.r.counts[c] for c in MG.r.counts})
ws=MG.r.words_str
w15=[w for w in ws if len(w)==15]
S=lambda w:sum(val[ch] for ch in w)
by_pat=defaultdict(list)
for w in w15: by_pat[(w[0],w[7],w[14])].append(w)
def wanalog(w):
    return any(1<=a and a+7<=13 and a<=7<=a+7 and isw(w[a:a+8]) for a in range(8))
def colscore(w):
    b=0
    if isw(w[1:7]): b+=15
    if isw(w[8:14]): b+=15
    return 3*S(w)+b
bylist={}
for pat,lst in by_pat.items():
    bylist[pat]=sorted(lst,key=colscore,reverse=True)[:60]
K=int(os.environ.get('K','300'))
top=sorted(w15,key=S,reverse=True)
R0s=top[:K];R14s=top[:K]
R7s=[w for w in sorted(w15,key=S,reverse=True) if wanalog(w)][:K]
print(f"kandidaten: R0/R14 {K}, R7-analoog {len(R7s)}",flush=True)
out=[];t0=time.time()
for i,a in enumerate(R0s):
    if i%50==0: print(f"[{i}/{K}] {time.time()-t0:.0f}s kept {len(out)}",flush=True)
    for c in R14s:
        if a==c: continue
        p0=(a[0],'?',c[0]);p14=(a[14],'?',c[14])
        for b in R7s:
            if b==a or b==c: continue
            k0=(a[0],b[0],c[0]);k7=(a[7],b[7],c[7]);k14=(a[14],b[14],c[14])
            if k0 not in bylist or k7 not in bylist or k14 not in bylist: continue
            base=Counter(a)+Counter(b)+Counter(c)
            for ch in (a[0],b[0],c[0],a[7],b[7],c[7],a[14],b[14],c[14]): base[ch]-=1
            if sum(max(0,base[ch]-bag[cba[ch]]) for ch in base)>2: continue
            pick=[];needc=base.copy();okk=True
            for key in (k0,k7,k14):
                bestw=None;bestex=99;bestsc=-1
                for w_ in bylist[key]:
                    if w_ in (a,b,c) or w_ in pick: continue
                    t=needc+Counter(w_)
                    ex=sum(max(0,t[ch]-bag[cba[ch]]) for ch in t)
                    sc=colscore(w_)
                    if ex<bestex or (ex==bestex and sc>bestsc):
                        bestw,bestex,bestsc=w_,ex,sc
                if bestw is None: okk=False;break
                pick.append(bestw);needc=needc+Counter(bestw)
            if not okk: continue
            C0,C7,C14=pick
            exc=[]
            for ch,n in needc.items():
                for _ in range(max(0,n-bag[cba[ch]])): exc.append((val[ch],ch))
            if len(exc)>2: continue
            m=27*S(a)+9*S(b)+27*S(c)+colscore(C0)+colscore(C7)+colscore(C14)
            for v,ch in exc:
                w_=3 if (ch in C0[1:7]+C0[8:14]+C7[1:7]+C7[8:14]+C14[1:7]+C14[8:14]) else 9
                m-=w_*v
            out.append((m,a,b,c,C0,C7,C14))
out.sort(reverse=True)
with open('experiments/results/frame_top.jsonl','w') as f:
    for o in out[:200]:
        f.write(json.dumps({'M':o[0],'R':[o[1],o[2],o[3]],'C':[o[4],o[5],o[6]]})+"\n")
print(f"KLAAR: {len(out)} sextetten; top-5:",flush=True)
for o in out[:5]: print("  ",o,flush=True)
