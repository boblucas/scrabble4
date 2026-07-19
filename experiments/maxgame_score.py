"""MAXGAME scoring-engine: gegeven een FINAL board (grid) + een MOVE-SEQUENCE (per beurt de
nieuw-geplaatste cellen), bereken per beurt de score (hoofdwoord + alle kruiswoorden) en het
totaal.  Valideert: elke beurt legaal (verbonden, alle gevormde runs >=2 zijn woorden), tegels
komen uit de zak, center gedekt op zet 1.  N15_LANG kiest het lexicon.
"""
import sys, os
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
from collections import Counter
from scrabble import construct_rules, get_word_score
import numpy as np

LANG = os.environ.get('N15_LANG', 'dutch2026')
r = construct_rules(LANG, '15')
W = H = 15
cba = r.alphabet.cba
lk = r.words_lookup


def runs_through(grid, x, y, h):
    """De maximale run (>=1) door (x,y) in richting h (h=1 horizontaal)."""
    dx, dy = (1, 0) if h else (0, 1)
    x0, y0 = x, y
    while 0 <= x0-dx < W and 0 <= y0-dy < H and grid[y0-dy][x0-dx]:
        x0 -= dx; y0 -= dy
    cells = []
    xx, yy = x0, y0
    while 0 <= xx < W and 0 <= yy < H and grid[yy][xx]:
        cells.append((xx, yy)); xx += dx; yy += dy
    return cells


def score_game(grid, moves, blankcells=None):
    """grid: 15x15 codes (0=leeg).  moves: lijst van beurten, elke beurt = lijst van (x,y) NIEUW
    geplaatste cellen.  blankcells: set van (x,y) die blanks zijn.  Returns (totaal, per_move, ok, msg)."""
    blankcells = blankcells or set()
    placed_so_far = [[False]*W for _ in range(H)]
    curgrid = [[0]*W for _ in range(H)]   # bordstand NA elke zet — runs/legaliteit per tussenstand
    bagremain = Counter({c: r.counts[c] for c in r.counts}); blanksleft = r.blank_count
    total = 0; per = []
    for t, cells in enumerate(moves):
        # tegels uit zak
        for (x, y) in cells:
            if (x, y) in blankcells:
                blanksleft -= 1
            else:
                bagremain[grid[y][x]] -= 1
        # center op zet 1
        if t == 0 and (7, 7) not in cells:
            return 0, per, False, "zet 1 dekt center niet"
        # verbonden: elke nieuwe cel grenst aan bestaand OF andere nieuwe (behalve zet1)
        cset = set(cells)
        if t > 0:
            touch = any(any(0<=x+dx<W and 0<=y+dy<H and placed_so_far[y+dy][x+dx]
                            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) for (x,y) in cells)
            if not touch:
                return 0, per, False, f"zet {t+1} raakt bestaand bord niet"
        # markeer geplaatst
        for (x, y) in cells:
            placed_so_far[y][x] = True
            curgrid[y][x] = grid[y][x]
        # gevormde woorden: het hoofdwoord (langste run door de nieuwe cellen in de zet-richting)
        # + kruiswoorden loodrecht door elke nieuwe cel.  Verzamel unieke runs >=2 met >=1 nieuwe cel.
        seen = set(); mscore = 0
        for (x, y) in cells:
            for h in (1, 0):
                run = runs_through(curgrid, x, y, h)   # TUSSENSTAND, niet eindbord
                if len(run) < 2: continue
                key = (run[0], h, len(run))
                if key in seen: continue
                if not any(c in cset for c in run): continue   # geen nieuwe cel -> al bestaand woord
                seen.add(key)
                word = tuple(curgrid[cy][cx] for (cx, cy) in run)
                if word not in lk:
                    return 0, per, False, f"zet {t+1}: illegaal woord {''.join(chr(96+c) for c in word)}"
                placed = [ (cx,cy) in cset for (cx,cy) in run ]
                blanks = [ (cx,cy) in blankcells for (cx,cy) in run ]
                x0, y0 = run[0]
                sc, _ = get_word_score(r, list(word), x0, y0, h, placed, blanks)
                mscore += sc
        per.append(mscore); total += mscore
    # dekking: elke eindbord-cel moet door een zet geplaatst zijn
    for y in range(H):
        for x in range(W):
            if bool(grid[y][x]) != bool(curgrid[y][x]):
                return total, per, False, f"cel ({x},{y}) in eindbord maar niet in zetten (of andersom)"
    # zak-check
    if any(v < 0 for v in bagremain.values()) or blanksleft < 0:
        neg = {chr(96+c): v for c,v in bagremain.items() if v<0}
        return total, per, False, f"zak overschreden: {neg} blanksleft={blanksleft}"
    return total, per, True, "OK"


if __name__ == '__main__':
    # VALIDATIE: triviaal spel. zet1 'kat' horizontaal door center, zet2 'as' verticaal.
    grid = [[0]*15 for _ in range(15)]
    def put(word, x, y, h):
        for i, ch in enumerate(word):
            grid[y+i*(1-h)][x+i*h] = cba[ch]
    put('kater', 5, 7, 1)                 # rij7 kol5-9
    moves = [[(5,7),(6,7),(7,7),(8,7),(9,7)]]
    tot, per, ok, msg = score_game(grid, moves)
    print(f"validatie 'kater' door center: score={per} totaal={tot} ok={ok} ({msg})")
    # handmatig: k(3)a(1)t(2)e(1)r(2)=9, center kol7=('t') x2 word -> 18
    print("verwacht 18 (center DWS x2 op de t)")
