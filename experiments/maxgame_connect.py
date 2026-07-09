import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4'); sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ['N15_LANG'] = 'dutch2026'; os.environ['N15_HMAX'] = '15'
import n15_twolevel as T
r = T.r; cba = r.alphabet.cba
R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'
# index woorden op lengte + (pos->letter)
words = [w for w in r.words_str if 2 <= len(w) <= 15]
print(f"# {len(words)} woorden 2..15")
# VOLLE 15-verticaal in kol c: pos0=R0[c], pos7=R7[c], pos14=R14[c] -> verbindt alle 3 in 1 zet-kolom
print("\n=== 15-lange verticalen (verbinden rij0+7+14 in kolom c) ===")
n15 = 0
for c in range(15):
    hits = [w for w in words if len(w)==15 and w[0]==R0[c] and w[7]==R7[c] and w[14]==R14[c]]
    if hits:
        n15 += 1
        print(f"  kol {c:2d} (0={R0[c]},7={R7[c]},14={R14[c]}): {len(hits)} bv {hits[:2]}")
if n15==0: print("  (geen)")
# rij0<->rij7 brug: verticaal in kol c, top op rij0 (pos0=R0[c]), lengte>=8, pos7=R7[c]
print("\n=== rij0->rij7 bruggen (verticaal top rij0, raakt rij7) ===")
for c in range(15):
    hits = [w for w in words if len(w)>=8 and w[0]==R0[c] and w[7]==R7[c]]
    if hits: print(f"  kol {c:2d}: {len(hits)} bv {sorted(hits,key=len,reverse=True)[:2]}")
print("\n=== rij7->rij14 bruggen (verticaal raakt rij7 op pos p, rij14 op pos p+7, len>=8) ===")
for c in range(15):
    # verticaal die rij7 en rij14 dekt: begint op rij r<=7, lengte L, r+L-1>=14; pos (7-r)=R7[c], (14-r)=R14[c]
    hits = []
    for w in words:
        L = len(w)
        for rstart in range(max(0,15-L), 8):   # moet rij7 en rij14 raken: rstart<=7 en rstart+L-1>=14
            if rstart+L-1 < 14: continue
            if 7-rstart < L and 14-rstart < L and w[7-rstart]==R7[c] and w[14-rstart]==R14[c]:
                hits.append((w, rstart)); break
    if hits: print(f"  kol {c:2d}: {len(hits)} bv {hits[:2]}")
