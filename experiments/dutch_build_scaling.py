import sys, time
sys.path.insert(0, '/home/bob/programming/scrabble4')
from scrabble import construct_rules
from dawg import position_independent_row_automaton
r = construct_rules('dutch','15')          # all dutch words <=15
allw = r.words
for L in [11,12,13,14,15]:
    w=[x for x in allw if len(x)<=L]
    t=time.time(); a=position_independent_row_automaton(w); dt=time.time()-t
    st={x for x,_,_ in a[2]}|{y for _,_,y in a[2]}
    print(f'dutch words<= {L:>2}: {len(w):>8} words  ->  row-DFA build={dt:8.2f}s  states={len(st)}  edges={len(a[2])}', flush=True)
print('DONE', flush=True)
