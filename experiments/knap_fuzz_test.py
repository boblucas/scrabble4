# Independent brute-force/differential soundness test of the KNAP joint-knapsack UB pruning rule
# (xfill_rs main.rs::knap_ub, default-on in --maxscore mode; opt out NOKNAP=1).
#
# Method: generate random SMALL --maxscore instances (small alphabet so the per-letter tile budget
# binds, random word-domains + blanks + bridges), then run the Rust solver TWICE -- with the knapsack
# OFF (NOKNAP=1, the trusted baseline: decision-26/26 + CP-SAT score-check 26/32, 0 wrong) and ON
# (KNAPCOLS=7) -- and assert IDENTICAL MAX/LE results whenever BOTH terminate under a node cap. Any
# unsound knapsack prune would drop a feasible board and change the answer, so a disagreement flags it.
# This isolates the new pruning rule's effect (cf. the AC-3 agent's 3000-instance validation).
# RESULT (2026-06-08): 1600+ random instances across seeds 1-5, 0 disagreements. Run: `python
# experiments/knap_fuzz_test.py <seed> <n>`. Complements the CP-SAT-oracle scorecheck (xtest.py).
import random, subprocess, os, sys
BIN='experiments/xfill_rs/target/release/xfill'
DICTP='/tmp/fuzz_dict.txt'
random.seed(int(sys.argv[1]) if len(sys.argv)>1 else 0)
N=int(sys.argv[2]) if len(sys.argv)>2 else 400
ALPHA=6   # small alphabet so words/budget interact
def rword(L): return [random.randint(1,ALPHA) for _ in range(L)]
# build a small dict of <=hmax words: random subset of all short strings (so cross-words sometimes valid)
def make_dict():
    words=set()
    # all length-2..4 words over alpha with prob
    import itertools
    for L in range(1,5):
        for combo in itertools.product(range(1,ALPHA+1),repeat=L):
            if random.random()<0.4: words.add(combo)
    with open(DICTP,'w') as f:
        for wd in words: f.write(' '.join(map(str,wd))+'\n')
    return words
def make_inst(path):
    W=random.choice([5,6,7]); H=W
    hmax=4
    # scoring cols: pick a few non-overlapping-ish columns
    ncol=random.randint(2,4)
    cols=sorted(random.sample(range(W), ncol))
    pre=[x for x in range(W) if x not in cols]
    blanks=random.randint(0,2)
    counts={c:random.randint(0,4) for c in range(1,ALPHA+1)}
    scoring=[]
    for c in cols:
        L=random.randint(2,min(H, hmax+1))
        nw=random.randint(1,6)
        ws=[]
        for _ in range(nw):
            stub=rword(L-1)
            g=random.randint(0,30)
            ws.append((stub,g))
        # dedup stubs
        seen={}; 
        for s,g in ws:
            seen[tuple(s)]=max(seen.get(tuple(s),-1),g)
        scoring.append((c,L,[(list(s),g) for s,g in seen.items()]))
    scores={c:random.randint(0,5) for c in range(1,ALPHA+1)}
    L=[]
    L.append(f"DIMS {W} {H} {hmax} {ALPHA} {blanks}")
    L.append("COUNTS "+' '.join(f"{c}:{n}" for c,n in counts.items()))
    L.append("SCORES "+' '.join(f"{c}:{n}" for c,n in scores.items()))
    L.append("PREPLACED "+' '.join(f"{x},0,{random.randint(1,ALPHA)}" for x in pre))
    L.append("NONSCORING "+' '.join(map(str,pre)))
    L.append(f"DICT {DICTP}")
    L.append(f"NSCORING {len(scoring)}")
    for c,Lc,ws in scoring:
        L.append(f"SCOL {c} {Lc} {len(ws)}")
        for s,g in ws: L.append(f"WORDV {g} "+' '.join(map(str,s)))
    L.append("TRUTH UNKNOWN")
    open(path,'w').write('\n'.join(L)+'\n')
def run(path, knap):
    env=dict(os.environ); env['MAXNODES']='3000000'
    # KNAP is default-ON in --maxscore mode; the baseline ("off") run uses NOKNAP=1.
    env.pop('KNAP',None); env.pop('NOKNAP',None)
    if knap: env['KNAPCOLS']='7'
    else: env['NOKNAP']='1'
    try:
        out=subprocess.run([BIN,path,'--maxscore','-1'],capture_output=True,text=True,timeout=20,env=env).stdout
    except subprocess.TimeoutExpired:
        return 'TIMEOUT'
    t=out.split()
    if not t: return '?'
    if t[0]=='MAX': 
        # but if it hit node cap, result is unreliable -> check 'nodes' < cap? cap=3M; if nodes==cap it's incomplete
        nodes=int([x for x in t if x.startswith('nodes=')][0].split('=')[1])
        return ('MAX',int(t[1]), nodes>=3000000)
    if t[0]=='LE':
        nodes=int([x for x in t if x.startswith('nodes=')][0].split('=')[1])
        return ('LE', nodes>=3000000)
    return out
make_dict()
disagree=0; tested=0; both_term=0
for i in range(N):
    p=f'/tmp/fuzz_{i%4}.txt'; make_inst(p)
    a=run(p,False); b=run(p,True)
    tested+=1
    # only compare when neither hit node cap (incomplete)
    def incomplete(r): return r=='TIMEOUT' or (isinstance(r,tuple) and r[-1] is True)
    if incomplete(a) or incomplete(b): continue
    both_term+=1
    # normalize: MAX value must match; LE (no board) must match
    ka = a[:2] if isinstance(a,tuple) else a
    kb = b[:2] if isinstance(b,tuple) else b
    if ka!=kb:
        disagree+=1
        print(f"DISAGREE inst {i}: noknap={a} knap={b} (file {p})")
        if disagree>=5: break
print(f"\nfuzz: tested={tested} both-terminated={both_term} disagreements={disagree}")
sys.exit(1 if disagree else 0)
