import sys,time,json; sys.path.insert(0,'.'); sys.path.insert(0,'experiments')
import xtest
from scrabble import construct_rules
word=sys.argv[1]; scoring=[int(x) for x in sys.argv[2].split(',')]
clen=int(sys.argv[3]) if len(sys.argv)>3 else 7
cap=float(sys.argv[4]) if len(sys.argv)>4 else 600
mode=sys.argv[5] if len(sys.argv)>5 else 'decide'
turn=''.join(c.upper() if i in scoring else c for i,c in enumerate(word))
r=construct_rules('dutch','13'); w=r.alphabet.to_tup(word)
def has(c,length):
    L=w[c]; return any(v and v[0]==L and len(v)==length and (len(v)==1 or v[1:] in r.words_lookup) for v in r.words)
Lvec={}
for c in scoring:
    if c==6: Lvec[c]=clen; continue
    for length in (2,3,4): 
        if has(c,length): Lvec[c]=length; break
    else: Lvec[c]=2
print('turn',turn,'Lvec',Lvec,'mode',mode,flush=True)
inst,meta=xtest.build_instance('13',word,turn,Lvec,scale=True)
if inst is None: print('NOCAND'); sys.exit()
t=time.time()
if mode=='decide':
    st=xtest.cpsat_decide(meta,cap=cap); print('DECIDE',st,'wall',round(time.time()-t,1),flush=True)
else:
    st,sc=xtest.cpsat_maxscore(meta,cap=cap); print('MAXSCORE',st,sc,'wall',round(time.time()-t,1),flush=True)
