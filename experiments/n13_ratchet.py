"""Ratchet center-connected N=13 lower bound: for each (word, mask, lvec) candidate, build the
instance, run xfill --maxscore <floor-vert> --emit, and if it witnesses a board, verify the FULL
turn via witness_check and keep the best.  Left-edge contiguous block masks (incl. center col 6)
are connectivity-friendly (verified).  Prints VERIFIED totals; saves the best witness JSON.
"""
import sys,os,json,subprocess,itertools
from collections import Counter
sys.path.insert(0,'.'); sys.path.insert(0,'experiments')
import xtest, witness_check as wc
from scrabble import construct_rules, get_word_score
ROOT=os.getcwd()
XFILL=os.path.join(ROOT,'experiments/xfill_rs/target/release/xfill_lev3')
xtest.write_dict('13')
r0=construct_rules('dutch','13'); W,H=r0.W,r0.H
def has(w,c,length):
    L=w[c]; return any(v and v[0]==L and len(v)==length and (len(v)==1 or v[1:] in r0.words_lookup) for v in r0.words)
def main_score(word,scoring):
    r=construct_rules('dutch','13'); mt=r.alphabet.to_tup(word)
    f=(W*W)/(15*15); mc=Counter(mt)
    r.counts=Counter({c:max(round(n*f),mc[c],1) for c,n in r.counts.items()}); r.blank_count=round(r.blank_count*f)
    mask=[x in scoring for x in range(W)]
    v,_=get_word_score(r,mt,0,0,1,mask,[False]*W)
    return int(v)
def try_one(word,scoring,clen,others_len,wall=30):
    turn=''.join(c.upper() if i in scoring else c for i,c in enumerate(word))
    w=r0.alphabet.to_tup(word)
    Lvec={}
    for c in scoring:
        if c==6: Lvec[c]=clen; continue
        Lvec[c]=others_len if has(w,c,others_len) else (2 if has(w,c,2) else None)
        if Lvec[c] is None: return None
    inst,meta=xtest.build_instance('13',word,turn,Lvec,scale=True)
    if inst is None: return None
    tmp=os.path.join(ROOT,'experiments/xtests/n13_ratchet.txt')
    xtest.dump_simple(inst,None,tmp)
    env=dict(os.environ); env.pop('MAXNODES',None); env['WALL']=str(wall)
    rr=subprocess.run([XFILL,tmp,'--maxscore','0','--emit'],capture_output=True,text=True,env=env,cwd=ROOT)
    lines=(rr.stdout or '').splitlines()
    res=next((l for l in lines if l[:3] in ('MAX','LE ','TO ')),'')
    bl=next((l for l in lines if l.startswith('BOARD')),'')
    if not res.startswith('MAX') or not bl: return ('nowit',res, turn, Lvec)
    vmax=int(res.split()[1])
    codes=[int(t) for t in bl.split()[1:]]
    grid=[[int(codes[y*W+x]) for x in range(W)] for y in range(H)]
    mt=r0.alphabet.to_tup(word)
    for x in range(W): grid[0][x]=int(mt[x])
    r=construct_rules('dutch','13')
    f=(W*W)/(15*15); mc=Counter(mt)
    r.counts=Counter({c:max(round(n*f),mc[c],1) for c,n in r.counts.items()}); r.blank_count=round(r.blank_count*f)
    mask=[turn[x].isupper() for x in range(W)]
    blank,info=wc.derive_blanks(r,grid,mask,W,H)
    if blank is None: return ('blankfail',info,turn,Lvec)
    ok,rep=wc.check_witness(r,W,H,grid,blank,mask,claimed_total=None,require_center=True)
    if not ok: return ('reject',rep.get('fail'),turn,Lvec)
    return ('ok',int(rep['total']),int(rep['main_score']),int(rep['vertical_score']),turn,Lvec,grid,info)

if __name__=='__main__':
    words=sys.argv[1].split(',')
    scoring=[int(x) for x in sys.argv[2].split(',')]
    best=0; best_spec=None
    WALL=float(os.environ.get('RWALL','8'))
    CLENS=[int(x) for x in os.environ.get('CLENS','8,7').split(',')]
    OLS=[int(x) for x in os.environ.get('OLS','3,4,2').split(',')]
    for word in words:
        ms=main_score(word,scoring)
        for clen in CLENS:
            for ol in OLS:
                res=try_one(word,scoring,clen,ol,wall=WALL)
                if res and res[0]=='ok':
                    tot=res[1]
                    tag='***' if tot>best else ''
                    print(f"{word} sc={scoring} clen={clen} ol={ol} main={res[2]} vert={res[3]} TOTAL={tot} {tag}",flush=True)
                    if tot>best:
                        best=tot
                        grid=res[6]
                        best_spec={'board':'13','main_word':word,'turn_str':res[4],'scale':True,'blanks':True,
                                   'require_center':True,'grid':grid,'claimed_total':tot}
                else:
                    print(f"{word} sc={scoring} clen={clen} ol={ol} main={ms} -> {res[0] if res else 'none'} {res[1] if res else ''}",flush=True)
    if best_spec:
        out=os.path.join(ROOT,'experiments/results/turns/N13_ratchet_best.json')
        json.dump(best_spec,open(out,'w'),indent=1)
        print(f"BEST verified total={best} saved {out}",flush=True)
