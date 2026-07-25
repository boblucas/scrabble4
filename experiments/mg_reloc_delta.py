"""Delta-verplaatsings-polish (bob's poft-methode, exact): voor elke 1-tegel-zet in het recordspel,
probeer die tegel op elke andere legale lege cel (zet verplaatst naar het eind, net voor de
slotzetten, zodat aanhaak-eisen minimaal zijn), en scoor het VOLLEDIGE aangepaste spel exact met
score_game. Hill-climb tot geen verbetering. Alles blijft arbiter-geverifieerd per kandidaat."""
import sys, os, json, itertools
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG']='dutch2026'
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba

def game_score(grid,moves,bl):
    tot,per,ok,msg=MG.score_game([row[:] for row in grid],[[tuple(c) for c in m] for m in moves],set(bl))
    return int(tot) if ok else -1

D=json.load(open('experiments/results/maxgame_BEST.json'))
grid=[row[:] for row in D['grid']];moves=[[tuple(c) for c in m] for m in D['moves']];bl=set(tuple(b) for b in D.get('blanks',[]))
cur=game_score(grid,moves,bl)
print(f"start: {cur}",flush=True)

def try_all(grid,moves,bl):
    best=(game_score(grid,moves,bl),None)
    nfin=3
    occupied={(x,y) for y in range(15) for x in range(15) if grid[y][x]}
    for mi,mv in enumerate(moves[:-nfin]):
        if len(mv)!=1: continue
        (ox,oy)=mv[0]
        L=grid[oy][ox]
        if (ox,oy) in bl: continue
        for ty in range(15):
            if ty in (0,7,14): continue
            for tx in range(15):
                if (tx,ty) in occupied or (tx,ty)==(ox,oy): continue
                g2=[row[:] for row in grid]
                g2[oy][ox]=0;g2[ty][tx]=L
                m2=[list(m) for m in moves]
                del m2[mi]
                m2.insert(len(m2)-nfin,[(tx,ty)])
                s=game_score(g2,m2,bl)
                if s>best[0]:
                    best=(s,(g2,m2,chr(96+L),(ox,oy),(tx,ty)))
    return best

it=0
while True:
    it+=1
    s,payload=try_all(grid,moves,bl)
    if payload is None or s<=cur:
        print(f"iter {it}: geen verbetering (blijft {cur})",flush=True);break
    grid,moves,L,frm,to=payload[0],payload[1],payload[2],payload[3],payload[4]
    cur=s
    print(f"iter {it}: {cur}  ('{L}' {frm} -> {to})",flush=True)

print(f"EIND: {cur}")
if cur>int(D['total']):
    out={'grid':grid,'moves':[[list(c) for c in m] for m in moves],'blanks':[list(b) for b in sorted(bl)],
         'total':cur,'triple':D['triple'],'plan':f'reloc-delta-polish (1-tegel-verplaatsingen, exact score_game-geevalueerd) vanaf {D["total"]}'}
    json.dump(out,open('experiments/results/mg_reloc_best.json','w'))
    print("-> experiments/results/mg_reloc_best.json")
