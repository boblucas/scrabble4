"""RIGOUREUZE sluitbaarheids-analyse van een triple via een NOODZAKELIJKE voorwaarde.

In elk pre-bord bestaan tegels alleen op vrije rijen + anker-pre-cellen. Een ankerrij-segment
(maximale pre-cel-reeks tussen maskercellen/randen) grenst horizontaal alleen aan lege maskercellen,
dus het kan UITSLUITEND verbinden via een tegel direct boven/onder een van zijn cellen — en dan is
de verticale maximale run door die ankercel een dict-woord dat alle gepasseerde ankerrij-letters
matcht. conn(c,y) = bestaat zo'n woord? Exhaustief uit het lexicon berekend.

Een maskercombo is sluitbaar => ELK segment (alle 3 rijen) heeft >=1 kolom met conn=True.
Tel de combo's die deze voorwaarde overleven. 0 overlevers = BEWEZEN onbouwbaar (onder de
volledige spelregels; dit is een relaxatie: overleven bewijst niets, falen weerlegt alles).

Env: MGR0/MGR7/MGR14, MGSIZES (maskergroottes, default '7'), MGFORCE0/14='0,7,14' MGFORCE7='0,14'.
"""
import sys, os
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from itertools import combinations
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
ALPH='abcdefghijklmnopqrstuvwxyz'
bag={ch:r.counts[cba[ch]] for ch in ALPH}
words=r.words_str
R0=os.environ.get('MGR0','bouwcuratrixjes');R7=os.environ.get('MGR7','playoffticketje');R14=os.environ.get('MGR14','geschenkcheques')
SIZES=[int(x) for x in os.environ.get('MGSIZES','7').split(',')]
anch={0:R0,7:R7,14:R14}
print(f"analyse: {R0} / {R7} / {R14}  maskergroottes {SIZES}",flush=True)

# index: (letter, positie) -> woorden
bypos={}
for w in words:
    for i,ch in enumerate(w):
        bypos.setdefault((ch,i),[]).append(w)

def conn(c,y):
    """Bestaat een verticaal dict-woord door (c,y) met >=1 cel op een vrije rij grenzend aan (c,y),
    dat alle gepasseerde ankerrijen letter-matcht en per-woord zakhaalbaar is?"""
    a=anch[y][c]
    for i in range(15):          # positie van (c,y) in het woord
        for w in bypos.get((a,i),[]):
            L=len(w);y0=y-i
            if y0<0 or y0+L-1>14 or L<2: continue
            # moet de cel direct boven of onder (c,y) bevatten
            if not((y>0 and y0<=y-1) or (y<14 and y0+L-1>=y+1)): continue
            ok=True
            for j,ch in enumerate(w):
                yy=y0+j
                if yy in (0,7,14) and yy!=y:
                    if ch!=anch[yy][c]: ok=False;break
            if not ok: continue
            cnt=Counter(w)
            # ankerrij-cellen in het woord verbruiken geen verse tegels (liggen er al / komen via slotzet)
            for j,ch in enumerate(w):
                if y0+j in (0,7,14): cnt[ch]-=1
            if any(cnt[ch]>bag[ch] for ch in cnt): continue
            return True
    return False

CONN={}
for y in (0,7,14):
    for c in range(15):
        CONN[(c,y)]=conn(c,y)
    row=''.join('1' if CONN[(c,y)] else '0' for c in range(15))
    print(f"conn rij {y:2d}: {row}   ({anch[y]})",flush=True)

def prl(m):
    pre=[c for c in range(15) if c not in m];out=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1:j+=1
        out.append((pre[i],pre[j]));i=j+1
    return out
def masks_for(w,y,forced,need_wordish):
    """alle maskers van gevraagde groottes: pre-runs moeten dict-woorden zijn (>=2) of los."""
    out=[]
    for size in SIZES:
        nf=size-len(forced)
        if nf<0: continue
        pool=[c for c in range(15) if c not in forced]
        for e in combinations(pool,nf):
            m=set(forced)|set(e)
            segs=prl(m)
            good=True
            for (a,b) in segs:
                if b>a and not isw(w[a:b+1]): good=False;break
            if good: out.append(tuple(sorted(m)))
    return out
F0={0,7,14};F7={0,14};F14={0,7,14}
M0s=masks_for(R0,0,F0,True);M7s=masks_for(R7,7,F7,True);M14s=masks_for(R14,14,F14,True)
print(f"geldige maskers: rij0={len(M0s)} rij7={len(M7s)} rij14={len(M14s)}",flush=True)

def row_ok(m,y):
    for (a,b) in prl(set(m)):
        if not any(CONN[(c,y)] for c in range(a,b+1)): return False
    return True
ok0=[m for m in M0s if row_ok(m,0)]
ok7=[m for m in M7s if row_ok(m,7)]
ok14=[m for m in M14s if row_ok(m,14)]
print(f"maskers met ALLE segmenten verbindbaar: rij0={len(ok0)}/{len(M0s)} rij7={len(ok7)}/{len(M7s)} rij14={len(ok14)}/{len(M14s)}",flush=True)
tot=len(ok0)*len(ok7)*len(ok14)
if tot==0:
    which=[y for y,o in ((0,ok0),(7,ok7),(14,ok14)) if not o]
    print(f"*** REFUTATIE: rij(en) {which} hebben GEEN masker waarvan alle segmenten verbindbaar zijn")
    print(f"*** => geen enkel pre-bord van dit triple kan 1 component zijn => triple BEWEZEN onbouwbaar")
else:
    print(f"noodzakelijke voorwaarde overleeft: {tot} combo's kandidaat (= geen refutatie op dit niveau)")
    # toon per rij de overlevende maskers (voor gerichte solver-aanval)
    for y,o in ((0,ok0),(7,ok7),(14,ok14)):
        print(f"  rij {y}: {o[:6]}{' ...' if len(o)>6 else ''}")
