"""UNIFORME BEZORG-SOLVER: gegeven een ankerwoord (rij 0/7/14), structurele kolommen (verticalen
die hun ankercel zelf leggen), stub-wortelbare kolommen (met stub-tabel), vind een geldige
pre-set van precies 8 kolommen + geordende blok-zetreeks. Kern: DFS met koppen (structureel,
vrij plaatsbaar), stubs (wortelbaar, tabel-gecheckt) en singles/blokken (rij-adjacent,
elk tussenfragment een woord). Eiland-regel en eindstand-runs impliciet via runs_ok."""
import sys,os,itertools
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG','dutch2026')
import maxgame_score as MG
cba=MG.r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
def _runs_ok(pl,word):
    cs=sorted(pl);i=0
    while i<len(cs):
        j=i
        while j+1<len(cs) and cs[j+1]==cs[j]+1: j+=1
        if j>i and not isw(word[cs[i]:cs[j]+1]): return False
        i=j+1
    return True
def solve_delivery(word,structural,stubable,maxblock=3,want=8,forbidden=()):
    """word: 15-str; structural: set kolommen met eigen structuur (kop, vrij plaatsbaar);
    stubable: dict kolom->True (stub-wortel beschikbaar; stub telt als kop);
    Geeft (pre_set, seq) of None. seq-items: ('H',c)=structuur/stub-kop, tuple=blok."""
    cols=[c for c in range(1,14) if c!=7 and c not in forbidden]
    structural=set(structural)&set(cols)
    heads=structural|{c for c in stubable if c in cols}
    for S in itertools.combinations(cols,want):
        Sset=set(S)
        if not structural<=Sset: continue
        # eindstand-runcheck (goedkoop)
        if not _runs_ok(Sset,word): continue
        Hs=heads&Sset
        todo=Sset
        def dfs(pl,td,seq):
            if not td: return seq
            for h in sorted(td&Hs):
                np_=pl|{h}
                if _runs_ok(np_,word):
                    got=dfs(np_,td-{h},seq+[('H',h)])
                    if got is not None: return got
            tl=sorted(td-Hs)
            for size in range(1,maxblock+1):
                for blk in itertools.combinations(tl,size):
                    sp=set(range(min(blk),max(blk)+1))
                    if not (sp-set(blk))<=pl: continue
                    if not any((b-1 in pl or b+1 in pl) for b in blk): continue
                    np_=pl|set(blk)
                    if not _runs_ok(np_,word): continue
                    got=dfs(np_,td-set(blk),seq+[blk])
                    if got is not None: return got
            return None
        seq=dfs(set(),todo,[])
        if seq is not None: return (tuple(sorted(Sset)),tuple(seq))
    return None
if __name__=='__main__':
    G='geschenkcheques';P='polymelkzuurtje';GY='gymjuffrouwtjes'
    # test 1: G onderaan (referentie): structureel kol 5 (essentie-vert), stubs 9,12,13 (lane12-geworteld) + westketen 1,2 (via kol-2: 'stubable')
    r=solve_delivery(G,structural={5},stubable={9:1,12:1,13:1,2:1})
    print("G-onder:",r[0] if r else None)
    # test 2: P bovenaan: stubs 6,9 (laan-3-geworteld)
    r2=solve_delivery(P,structural=set(),stubable={6:1,9:1})
    print("P-boven:",r2[0] if r2 else None)
    # test 3: gym (moet falen zonder overal-stubs)
    r3=solve_delivery(GY,structural=set(),stubable={5:1,9:1})
    print("gym:",r3[0] if r3 else None,"(verwacht None)")
