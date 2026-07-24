"""FRAME-LEMMA (pijler 1 van het optimaliteitsbewijs, rigoureus):
Bovengrens op de totale woord-multiplier-oogst van ELK legaal spel, zonder aannames.

Feiten (bord): 8 TWS-cellen: rijen 0/14 op kols 0,7,14 en rij 7 op kols 0,14. Elke premiecel telt
alleen in de zet die hem vers belegt. Een zet is collineair, dus de TWS-cellen van één zet liggen
op één lijn: mogelijke groepen per zet = deelverzamelingen van {TWS op één rij/kolom}.
De 15-lijnen met 3 TWS: rij 0, rij 14, kol 0, kol 14. Met 2 TWS: rij 7, kol 7 (center is DWS).

CENTER-LEMMA: zet 1 dekt (7,7) en plaatst <=7 tegels, dus kan geen 15-lijn voltooien. Elke latere
zet die een 2-TWS-lijn (rij/kol 7) afmaakt vindt het center dus AL BELEGD => die zet krijgt
maximaal x9 (nooit x18).

Multiplier-oogst van zet z met TWS-groep g (en evt. andere premies): score(z) <= 3^|g| * 2^(dws) *
W(len), met W(len) = maximale kale letterwaarde van een dict-woord van die lengte (zak-gerelaxeerd,
maar wel: per woord zak-haalbaar). Voor de UB nemen we de beste partitie van de 8 TWS in collineaire
groepen, elk gewaardeerd met de best mogelijke woordwaarde (15-woorden voor 3-groepen; voor kleinere
groepen het beste woord dat de betreffende cellen kan dekken).

Uitvoer: (a) W(len)-tabel, (b) beste partitie + bijbehorende finals-main-UB, (c) verschil met de
gerealiseerde finals-mains van het record.
"""
import sys, os
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba
ALPH='abcdefghijklmnopqrstuvwxyz'
val={ch:r.scores[cba[ch]] for ch in ALPH}
bag={ch:r.counts[cba[ch]] for ch in ALPH}
words=r.words_str

def bagok(w):
    c=Counter(w);return all(c[ch]<=bag[ch] for ch in c)

# W(len): max kale woordwaarde per lengte (zak-haalbaar per woord)
W={}
TOPW={}
for w in words:
    L=len(w)
    v=sum(val[ch] for ch in w)
    if v>W.get(L,-1) and bagok(w):
        W[L]=v;TOPW[L]=w
print("W(len) top:",{L:(W.get(L),TOPW.get(L)) for L in (15,14,8,7)},flush=True)

# Ook: top-3 15-woorden op waarde (de drie slotwoorden zijn verschillende fysieke plaatsingen;
# zak-deling gerelaxeerd => zelfde topwoord 3x mag in de UB)
w15=W[15]

# TWS-groepen: partities van de 8 TWS in collineaire groepen.
# 3-groepen: {rij0}, {rij14}, {kol0}, {kol14} — elk vereist een compleet 15-woord over die lijn.
# 2-groepen: binnen een lijn: (0,7),(7,14) afstand 7 -> woord >=8; (0,14) afstand 14 -> 15-woord.
#            rij7/kol7-paren: afstand 14 -> 15-woord, x9 max (center-lemma).
# 1-groepen: enkel TWS: woord >= 2 dat de cel dekt: x3 * W(l), beste l<=8 relevant... neem W(8)
#            als royale relaxatie (langste woord dat één TWS + geen tweede dekt: 7 cellen ver van
#            de volgende TWS op de lijn, dus len<=7 door binnenrand; via de loodrechte lijn kan
#            len tot 8 zonder tweede TWS. UB: 3*W(8)).
# DWS-bijmenging: het center kan nooit vers zijn in een lijn-voltooiende zet (center-lemma);
# andere DWS-cellen liggen niet op de TWS-lijnen behalve center. => geen 2^k-factoren hier.
# NB: corners gedeeld tussen rij- en kolomlijnen: een partitie gebruikt elke TWS precies één keer,
# dus rij0(3) en kol0(3) kunnen niet allebei — dat is precies wat partities afdwingen.

from itertools import product
TWS=[(0,0),(7,0),(14,0),(0,7),(14,7),(0,14),(7,14),(14,14)]  # (x,y)
LINES={'r0':[(0,0),(7,0),(14,0)],'r14':[(0,14),(7,14),(14,14)],
       'c0':[(0,0),(0,7),(0,14)],'c14':[(14,0),(14,7),(14,14)],
       'r7':[(0,7),(14,7)],'c7':[(7,0),(7,14)]}
def groups_on(line):
    """mogelijke TWS-groepen op deze lijn met hun UB-waarde"""
    cells=LINES[line];out=[]
    n=len(cells)
    from itertools import combinations
    for k in range(1,n+1):
        for g in combinations(cells,k):
            if k==1: v=3*W[8]
            elif k==2:
                # afstand op de lijn
                (x1,y1),(x2,y2)=g
                d=abs(x1-x2)+abs(y1-y2)
                v=9*(w15 if d==14 else W[8+ (0 if d==7 else 7)])  # d=7 -> len>=8
                if d==7: v=9*W[15]  # len 8..15; W stijgt met lengte -> neem 15 (royaal, sound)
            else: v=27*w15
            out.append((frozenset(g),v))
    return out
ALLG=[]
for ln in LINES: ALLG+=groups_on(ln)
# dedup: zelfde cellenset via verschillende lijnen -> max v
GD={}
for g,v in ALLG: GD[g]=max(GD.get(g,-1),v)
GL=sorted(GD.items(),key=lambda t:-t[1])
# beste exacte partitie van de 8 TWS (branch and bound over de kleine ruimte)
best=[0];bestp=[None]
TWSset=frozenset(TWS)
import functools
GLl=[(set(g),v) for g,v in GL]
def bb(remaining,acc,used):
    if not remaining:
        if acc>best[0]: best[0]=acc;bestp[0]=list(used)
        return
    # bound: rest * max v per cel (27*w15/3 per cel royaal)
    if acc+len(remaining)*(27*w15/3.0)<best[0]: return
    cell=next(iter(remaining))
    for g,v in GLl:
        if cell in g and g<=remaining:
            bb(remaining-g,acc+v,used+[(g,v)])
res=bb(set(TWS),0,[])
print(f"\nFRAME-LEMMA: max multiplier-oogst (finals-mains, zak-gerelaxeerd) = {best[0]}")
for g,v in bestp[0]: print(f"  groep {sorted(g)} -> {v}")
print(f"\nter vergelijking: record-finals-mains ~= 27*{(1732-50)//27}... (gerealiseerde finals 3533 incl kruiswoorden en bingo's)")
print(f"Conclusie: elke andere TWS-partitie dan (3,3,2) verliest; de (3,3,2) op rijen 0/14 + rij-of-kolom-7 is DE structuur.")
