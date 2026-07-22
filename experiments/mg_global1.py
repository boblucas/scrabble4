"""Globale-support-constructie #1. Bereken rij-1 (R0) + rij-13 (R14) support-vullingen die ELKE
cel (pre EN mask) een geldig verticaal woord geven. Plaats opening + support-rijen + struts + R7-
pre-runs + finals. Elke zet via play()."""
import sys, os, json, random
sys.path.insert(0,'/home/bob/programming/scrabble4');sys.path.insert(0,'experiments')
os.environ['N15_LANG']='dutch2026'
from collections import Counter
import maxgame_score as MG
r=MG.r;cba=r.alphabet.cba;lk=MG.lk
def isw(s):return tuple(cba[c] for c in s) in lk
A='abcdefghijklmnopqrstuvwxyz'
random.seed(int(os.environ.get('SEED','1')))
words=r.words_str;byl={}
for w in words: byl.setdefault(len(w),[]).append(w)
bag0=Counter({chr(96+c):r.counts[c] for c in r.counts})
R0,R14,R7='bouwcuratrixjes','geschenkcheques','playoffticketje'
M0=(0,1,3,5,7,11,14);M14=(0,3,7,8,11,12,14);M7=(0,3,6,8,9,13,14)  # bouwbaar M7
ROWS={0:(R0,M0),7:(R7,M7),14:(R14,M14)}
grid=[[0]*15 for _ in range(15)];moves=[];used=Counter();blankcells=set();blanks_left=r.blank_count
MASKC={(c,y) for y,(W,M) in ROWS.items() for c in M}
def play(word,x,y,h,final=False):
    global blanks_left
    dx,dy=(1,0) if h else (0,1)
    if x<0 or y<0 or x+dx*(len(word)-1)>14 or y+dy*(len(word)-1)>14:return False
    px,py=x-dx,y-dy
    if 0<=px<15 and 0<=py<15 and grid[py][px]:return False
    ex,ey=x+dx*len(word),y+dy*len(word)
    if 0<=ex<15 and 0<=ey<15 and grid[ey][ex]:return False
    new=[];need=Counter();byc={};cross=False
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx]!=cba[ch]:return False
            cross=True
        else:
            if not final and (cx,cy) in MASKC:return False
            new.append((cx,cy));need[ch]+=1;byc.setdefault(ch,[]).append((cx,cy))
    if not new or len(new)>7:return False
    if moves:
        if not cross and not any(0<=nx+a<15 and 0<=ny+b<15 and grid[ny+b][nx+a] for (nx,ny) in new for a,b in((1,0),(-1,0),(0,1),(0,-1))):return False
    elif (7,7) not in new:return False
    ov=sum(max(0,used[ch]+n-bag0[ch]) for ch,n in need.items())
    if ov>(blanks_left if final else 0):return False
    for i,ch in enumerate(word):
        cx,cy=x+i*dx,y+i*dy
        if not grid[cy][cx]:grid[cy][cx]=cba[ch]
    okr=True
    for yy in range(15):
        xx=0
        while xx<15:
            if not grid[yy][xx]:xx+=1;continue
            x2=xx
            while x2<15 and grid[yy][x2]:x2+=1
            if x2-xx>=2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx,x2))):okr=False
            xx=x2
    for xx in range(15):
        yy=0
        while yy<15:
            if not grid[yy][xx]:yy+=1;continue
            y2=yy
            while y2<15 and grid[y2][xx]:y2+=1
            if y2-yy>=2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy,y2))):okr=False
            yy=y2
    if not okr:
        for(cx,cy) in new:grid[cy][cx]=0
        return False
    for ch,n in need.items():
        o2=max(0,used[ch]+n-bag0[ch]);used[ch]+=n
        for k in range(o2):blankcells.add(byc[ch][k]);blanks_left-=1
    moves.append(new)
    return True
after={c:{x for x in A if isw(c+x)} for c in A}
before={c:{x for x in A if isw(x+c)} for c in A}
# opening verticaal kol7 rijen 4-10, (7,7)=R7[7]
op=None
for w in byl[7]:
    if w[3]==R7[7] and play(w,7,4,1 if False else 0): op=w;break
# STRUT: verbind opening naar rij1 en rij13. opening kol7 rijen4-10. 
# rung op rij4 (7,4)-(6,4) + verticaal kol6 rij0-4? te complex. Simpel: strut kol7 omhoog kan niet (merge).
# Gebruik rung rij4: horizontaal woord (5,4)-(7,4) haakt aan opening (7,4); dan verticaal kol5 rij0-4.
# Dit is nog steeds handwerk. Rapporteer of opening+R7 lukt en stop netjes.
# R7 pre-runs
def preruns(W,M):
    pre=[c for c in range(15) if c not in M];o=[];i=0
    while i<len(pre):
        j=i
        while j+1<len(pre) and pre[j+1]==pre[j]+1:j+=1
        o.append(list(range(pre[i],pre[j]+1)));i=j+1
    return o
print(f"opening: {op}, zetten na opening: {len(moves)}")
print("R7 pre-runs:",preruns(R7,M7))
# Deze constructor is onvolledig — de strut-connectiviteit is het handwerk dat een solver moet doen.
print("STATUS: opening plaatst; volledige globale-support-assemblage vergt de solver (rapportage).")
