"""Module-polish v1 (bob's onafhankelijkheids-inzicht): per KOLOMKETTING-module exhaustief alle
lexicon-alternatieven proberen. Vast: het voetafdruk (celposities + zetstructuur), de
kruisingsletters (cellen die deel zijn van een horizontale run >=2), ankerletters, blanco-cellen.
Vrij: de overige letters van de kolomrun. Kandidaat = dict-woord dat op het kolompatroon past
(incl. tussenstadium-geldigheid: elke zet-prefix van de ketting moet een woord zijn) en waarvan de
letterwissel zak-haalbaar is. Evaluatie: EXACT — score_game op de ongewijzigde zetreeks.
Itereert over kolommen tot fixpoint. Daarna: draai de 1-tegel-reloc + letterruil opnieuw."""
import sys, os, json
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
bag=Counter({chr(96+c):r.counts[c] for c in r.counts})
words=r.words_str
bylen={}
for w in words: bylen.setdefault(len(w),[]).append(w)

D=json.load(open('experiments/results/maxgame_BEST.json'))
grid=[row[:] for row in D['grid']];moves=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D['blanks'])
def sc(g):
    tot,per,ok,msg=MG.score_game([row[:] for row in g],moves,bl)
    return int(tot) if ok else -1
cur=sc(grid)
print(f"start: {cur}",flush=True)

def col_runs(g):
    out=[]
    for x in range(15):
        y=0
        while y<15:
            if not g[y][x]: y+=1;continue
            y2=y
            while y2<15 and g[y2][x]: y2+=1
            if y2-y>=4: out.append((x,y,y2))  # modules: kolomruns >=4
            y=y2
    return out
def stage_sets(x,y0,y1):
    """welke zetten legden cellen van deze kolomrun, in volgorde -> lijst van cel-sets (stadia)."""
    cells={(x,yy) for yy in range(y0,y1)}
    st=[];placed=set()
    for m in moves:
        mm=[c for c in m if c in cells]
        if mm:
            placed|=set(mm);st.append(set(placed))
    return st

improved=True;rondes=0
while improved and rondes<6:
    improved=False;rondes+=1
    for (x,y0,y1) in col_runs(grid):
        L=y1-y0
        if L not in bylen: continue
        # vaste posities: kruisingscellen (deel van horiz run >=2), ankerrijen, blanco's
        fixed={};crossing={}
        for i,yy in enumerate(range(y0,y1)):
            horiz = (x>0 and grid[yy][x-1]) or (x<14 and grid[yy][x+1])
            if yy in (0,7,14) or (x,yy) in bl:
                fixed[i]=chr(96+grid[yy][x])
            elif horiz:
                if os.environ.get('MODV2','0')=='1':
                    crossing[i]=yy   # v2: letter mag wisselen mits horiz-run (alle stadia) geldig
                else:
                    fixed[i]=chr(96+grid[yy][x])
        freeidx=[i for i in range(L) if i not in fixed]   # incl. crossing-indices in v2
        if not freeidx: continue
        # zak-budget: huidige vrije letters komen terug in de zak
        used=Counter(chr(96+grid[y][xx]) for y in range(15) for xx in range(15) if grid[y][xx] and (xx,y) not in bl)
        avail=bag-used
        for i in freeidx: avail[chr(96+grid[y0+i][x])]+=1
        # stadium-structuur (welke deelverzamelingen moeten op elk moment woord zijn)
        stages=stage_sets(x,y0,y1)
        curword=''.join(chr(96+grid[y0+i][x]) for i in range(L))
        best_local=None
        for w in bylen[L]:
            if w==curword: continue
            if any(w[i]!=fixed[i] for i in fixed): continue
            # v2: valideer kruisingen — horizontale run + zijn zetstadia met de nieuwe letter
            if crossing:
                okc=True
                for i,yy in crossing.items():
                    xx0=x
                    while xx0>0 and grid[yy][xx0-1]: xx0-=1
                    xx1=x
                    while xx1<14 and grid[yy][xx1+1]: xx1+=1
                    hw=''.join((w[i] if xx==x else chr(96+grid[yy][xx])) for xx in range(xx0,xx1+1))
                    if len(hw)>=2 and not isw(hw): okc=False;break
                    # stadia van de horizontale run
                    hcells={(xx,yy) for xx in range(xx0,xx1+1)}
                    placed=set()
                    for m in moves:
                        mm=[c for c in m if c in hcells]
                        if not mm: continue
                        placed|=set(mm)
                        xs=sorted(cx for (cx,cy) in placed)
                        if xs[-1]-xs[0]+1!=len(xs): okc=False;break
                        if len(xs)>=2:
                            seg=''.join((w[i] if cx==x else chr(96+grid[yy][cx])) for cx in range(xs[0],xs[-1]+1))
                            if not isw(seg): okc=False;break
                    if not okc: break
                if not okc: continue
            need=Counter(w[i] for i in freeidx)
            if any(need[ch]>avail[ch] for ch in need): continue
            # stadium-geldigheid: elk stadium = aaneengesloten? bepaal per stadium het interval en check woord
            ok=True
            for stcells in stages:
                ys=sorted(yy for (xx,yy) in stcells)
                if not ys: continue
                if ys[-1]-ys[0]+1!=len(ys): ok=False;break   # (stadium moet aaneengesloten zijn)
                if len(ys)>=2:
                    seg=''.join(w[yy-y0] for yy in range(ys[0],ys[-1]+1))
                    if not isw(seg): ok=False;break
            if not ok: continue
            g2=[row[:] for row in grid]
            for i in freeidx: g2[y0+i][x]=cba[w[i]]
            s=sc(g2)
            if s>cur and (best_local is None or s>best_local[0]):
                best_local=(s,w,g2)
        if best_local:
            cur,w,grid=best_local[0],best_local[1],best_local[2]
            print(f"ronde {rondes}: kol {x} [{y0},{y1}) -> '{w}' = {cur}",flush=True)
            improved=True
print(f"EIND module-polish: {cur}")
if cur>int(D['total']):
    out={'grid':grid,'moves':[[list(c) for c in m] for m in moves],'blanks':[list(b) for b in sorted(bl)],
         'total':cur,'triple':D['triple'],'plan':f'module-polish (kolomketting-enumeratie) vanaf {D["total"]}'}
    json.dump(out,open('experiments/results/mg_module_best.json','w'))
    print("-> experiments/results/mg_module_best.json")
