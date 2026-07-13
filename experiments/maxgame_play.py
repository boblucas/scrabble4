"""MAXGAME game-builder: construeer het spel ZET VOOR ZET (elke tussenstand legaal per constructie).
Fase A (script): myalgie door center; steunen; pre-runs; kolom-14-ladder; anker-slotzetten.
Fase B (greedy): vul met kruisende woorden (<=7 nieuw) op echte engine-score, tot zak op.
Output: volledig geldig spel + ECHTE totaalscore via maxgame_score."""
import sys, os, json, random
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
from collections import Counter
import maxgame_score as MG

r = MG.r; W = H = 15
cba = r.alphabet.cba; lk = MG.lk
val = {chr(96+i): r.scores[i] for i in range(1, 27)}
def isw(s): return tuple(cba[ch] for ch in s) in lk

grid = [[0]*W for _ in range(H)]         # evoluerende stand
moves = []                                # lijst zetten (elk: lijst (x,y))
bag = Counter({chr(96+c): r.counts[c] for c in r.counts})
blanks_left = r.blank_count
blankcells = set()
used = Counter()

def can_pay(need):
    global blanks_left
    short = 0
    for ch, n in need.items():
        short += max(0, used[ch] + n - bag[ch])
    return short <= blanks_left

def pay(need, cells_by_ch):
    """Trek tegels; overflow -> blanks (kies cel)."""
    global blanks_left
    for ch, n in need.items():
        over = max(0, used[ch] + n - bag[ch])
        used[ch] += n
        for k in range(over):
            blankcells.add(cells_by_ch[ch][k])
            blanks_left -= 1

def play(word, x, y, h, must_new_le=7):
    """Leg woord; bestaande passende letters zijn kruisingen. False bij illegale tussenstand."""
    dx, dy = (1,0) if h else (0,1)
    if x + dx*(len(word)-1) > 14 or y + dy*(len(word)-1) > 14: return False
    px, py = x-dx, y-dy
    if 0 <= px < W and 0 <= py < H and grid[py][px]: return False
    ex, ey = x+dx*len(word), y+dy*len(word)
    if 0 <= ex < W and 0 <= ey < H and grid[ey][ex]: return False
    new = []; need = Counter(); cells_by_ch = {}
    cross = False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if grid[cy][cx]:
            if grid[cy][cx] != cba[ch]: return False
            cross = True
        else:
            new.append((cx, cy)); need[ch] += 1
            cells_by_ch.setdefault(ch, []).append((cx, cy))
    if not new or len(new) > must_new_le: return False
    if moves and not cross:
        # raakt via buur?
        if not any(0<=nx+ddx<W and 0<=ny+ddy<H and grid[ny+ddy][nx+ddx]
                   for (nx,ny) in new for ddx,ddy in ((1,0),(-1,0),(0,1),(0,-1))):
            return False
    if not moves and (7,7) not in new: return False
    if not can_pay(need): return False
    for i, ch in enumerate(word):
        cx, cy = x+i*dx, y+i*dy
        if not grid[cy][cx]: grid[cy][cx] = cba[ch]
    # runs-check tussenstand
    ok = True
    for yy in range(H):
        xx = 0
        while xx < W:
            if not grid[yy][xx]: xx += 1; continue
            x2 = xx
            while x2 < W and grid[yy][x2]: x2 += 1
            if x2-xx >= 2 and not isw(''.join(chr(96+grid[yy][k]) for k in range(xx,x2))): ok = False
            xx = x2
    for xx in range(W):
        yy = 0
        while yy < H:
            if not grid[yy][xx]: yy += 1; continue
            y2 = yy
            while y2 < H and grid[y2][xx]: y2 += 1
            if y2-yy >= 2 and not isw(''.join(chr(96+grid[k][xx]) for k in range(yy,y2))): ok = False
            yy = y2
    if not ok:
        for (cx, cy) in new: grid[cy][cx] = 0
        return False
    pay(need, cells_by_ch)
    moves.append(new)
    return True

# ---------- FASE A: gescripte ruggengraat ----------
R0, R7, R14 = 'geschenkcheques', 'polymyalgietjes', 'bouwcuratrixjes'
script = [
    ('myalgie', 4, 7, 1),          # 1: door center, bingo
    ('na', 4, 6, 0),               # steun boven m? 'na' verticaal (4,6)-(4,7): n+a? grid(4,7)='m'!... skip
]
assert play('myalgie', 4, 7, 1), "opening faalt"
# steunen en pre-runs rond de ankers (uit de constructor, nu als echte zetten):
seq = [
    ('am', 4, 6, 0),      # (4,6)='a' boven m: 'am' verticaal
    ('es', 1, 0, 1),      # pre-run rij 0... zweeft; moet kruisen -> volgorde: eerst verticaal vanaf myalgie omhoog
]
# bouw verticale ladders van rij 7 omhoog/omlaag om rij 0/14 pre-runs aan te sluiten is complex;
# NACHTVERSIE: kolom 14 ladder via woorden: 'en'(13,14?)... we doen greedy fase B en meten hoe ver we komen.
print(f"na fase A: zetten={len(moves)} tegels={sum(1 for y in range(H) for x in range(W) if grid[y][x])}", flush=True)

# ---------- FASE B: greedy vullen ----------
wlist = [w for w in r.words_str if 2 <= len(w) <= 8]
random.seed(int(os.environ.get('SEED', '1')))
random.shuffle(wlist)
wlist = wlist[:250000]
progress = True
rounds = 0
while progress and rounds < 40:
    rounds += 1; progress = False
    anchors = [(x, y) for y in range(H) for x in range(W) if grid[y][x]]
    random.shuffle(anchors)
    for (ax, ay) in anchors[:60]:
        placed = False
        for w in wlist[:40000]:
            L = len(w)
            achr = chr(96+grid[ay][ax])
            if achr not in w: continue
            for i, ch in enumerate(w):
                if ch != achr: continue
                # horizontaal door (ax,ay)
                if play(w, ax-i, ay, 1): placed = True; break
                if play(w, ax, ay-i, 0): placed = True; break
            if placed: break
        if placed: progress = True
    nt = sum(1 for y in range(H) for x in range(W) if grid[y][x])
    print(f"  ronde {rounds}: zetten={len(moves)} tegels={nt} zak-rest={sum(bag.values())-sum(used.values())}", flush=True)
    if sum(bag.values()) - sum(used.values()) <= 0: break

# score
g2 = [row[:] for row in grid]
tot, per, ok, msg = MG.score_game(g2, moves, blankcells)
print(f"\nECHT SPEL: {len(moves)} zetten, score={tot} ok={ok} ({msg})", flush=True)
json.dump({'grid': grid, 'moves': [[list(c) for c in mv] for mv in moves],
           'blanks': [list(b) for b in blankcells], 'total': int(tot)},
          open(f'experiments/results/maxgame_play_{os.environ.get("SEED","1")}.json', 'w'))
