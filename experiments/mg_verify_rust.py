import sys,os,json
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
import maxgame_score as MG
line=sys.argv[1].split()
# format: SCORED total prep finals M0 M14 M7 board MV mv BL bl
total=int(line[1]); m0=list(map(int,line[4].split(','))); m14=list(map(int,line[5].split(','))); m7=list(map(int,line[6].split(',')))
bs=line[7]; mvi=line.index('MV'); bli=line.index('BL')
mvenc=line[mvi+1] if mvi+1<bli else ''
blenc=line[bli+1] if bli+1<len(line) else ''
R0,R7,R14='geschenkcheques','verzwaringswerk','polymelkzuurtje'
cba=MG.r.alphabet.cba
grid=[[ (0 if bs[y*15+x]=='`' else ord(bs[y*15+x])-96) for x in range(15)] for y in range(15)]
for y,W in ((0,R0),(7,R7),(14,R14)):
    for c in range(15): grid[y][c]=cba[W[c]]
def pcells(s): return [tuple(map(int,c.split('.'))) for c in s.split(',')] if s else []
prep=[pcells(seg) for seg in mvenc.split(';')] if mvenc else []
finals=[[(c,7) for c in sorted(m7)],[(c,0) for c in sorted(m0)],[(c,14) for c in sorted(m14)]]
moves=prep+finals
blanks=set(pcells(blenc))
tot,per,ok,msg=MG.score_game([r[:] for r in grid],moves,blanks)
print(f"RUST-VERIFY: rust_total={total} python_total={int(tot)} ok={ok} match={int(tot)==total} ({msg}) zetten={len(moves)}")
if ok and int(tot)>=int(os.environ.get('MINPROMOTE','999999')):
    D={'grid':grid,'moves':[[list(c) for c in mv] for mv in moves],'blanks':[list(b) for b in blanks],
       'total':int(tot),'triple':[R0,R7,R14],'plan':f'reachable record {int(tot)} via Rust full-pipeline (solve+score+beam), Python-geverifieerd'}
    json.dump(D,open('experiments/results/maxgame_BEST.json','w'));print("PROMOTED",int(tot))
