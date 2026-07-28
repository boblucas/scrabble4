"""RAIL-FILTER OP DE TRIPLETKEUZE: welk ankerwoord laat een volle steunrail toe?

Achtergrond (zie NEWTOPO.md sectie 3).  Een rail op rij 1 (resp. rij 13) is de sterkste
structurele vondst van de campagne: +117..+163 ankervast plafond bij een ladderloos schema,
+167..+401 met schemazoektocht.  Hij scoort zelf x4 over 13-15 cellen (twee DWS op afstand 12),
hij DRAAGT alle pre-cellen van de x27-rij (de vier klimkolommen vervallen) en hij maakt de
randkolommen bereikbaar.  Met het huidige triplet is hij lexicaal onmogelijk: elke kolom eist
een verticaal 2-letterwoord en de 'q' van geschenkcheques heeft er geen.

Dit script draait die eis om tot een SELECTIECRITERIUM op de ankerwoorden:

    rij 0  + rail op rij 1  : voor elke kolom x moet  rij0[x] + rail1[x]  een woord zijn
    rij 14 + rail op rij 13 : voor elke kolom x moet  rail13[x] + rij14[x] een woord zijn

Dat is een 26x26-matrix (opvolgers / voorgangers uit de 2-letterwoorden) plus een zoektocht
"bestaat er een woord dat per positie in een toegestane letterverzameling past".  Die zoektocht
is met bitsets over de woordenlijst O(lengte) per kandidaat, dus de hele 15-letterlijst is in
seconden te filteren.

Varianten die worden gemeten:
  * VOLLE rail (kolommen 0..14): rail is een 15-letterwoord, alle 15 kolommen gebonden.
  * DWS-rail (kolommen 1..13): rail is een 13-letterwoord; de twee DWS (1,y)/(13,y) zitten er
    nog steeds in, dus de x4 blijft, maar de kolommen 0 en 14 zijn vrij.
  * GERELAXEERDE rail: een kolom mag een extra tegel op rij 2 (resp. rij 12) krijgen; de
    verticaal wordt dan een 3-run en de toegestane verzameling is veel groter.  Kost 1 tegel
    per gerelaxeerde kolom.

CLI:
    .venv/bin/python experiments/mg_railtriplet.py            # tellingen + top-N
    TOPN=40 .venv/bin/python experiments/mg_railtriplet.py
"""
import sys, os, json, time
from collections import Counter, defaultdict
sys.path.insert(0, '/home/bob/programming/scrabble4')
sys.path.insert(0, '/home/bob/programming/scrabble4/experiments')
os.environ.setdefault('N15_LANG', 'dutch2026')
import maxgame_score as MG

r = MG.r
cba = r.alphabet.cba
ABC = 'abcdefghijklmnopqrstuvwxyz'
VAL = {ch: r.scores[cba[ch]] for ch in ABC}
BAG = Counter({ch: r.counts[cba[ch]] for ch in ABC if cba[ch] in r.counts})
BLANKS = 2

BYLEN = defaultdict(list)
for w in r.words_str:
    BYLEN[len(w)].append(w)

# ---------------------------------------------------------------- 26x26-matrices
SUCC = {ch: set() for ch in ABC}          # L -> {M : LM is een woord}
PRED = {ch: set() for ch in ABC}          # L -> {M : ML is een woord}
for w in BYLEN[2]:
    SUCC[w[0]].add(w[1])
    PRED[w[1]].add(w[0])
# gerelaxeerde varianten: de verticaal is een 3-run
SUCC3 = {ch: set() for ch in ABC}         # L -> {M : er is een N met LMN een woord}
PRED3 = {ch: set() for ch in ABC}         # L -> {M : er is een N met NML een woord}
for w in BYLEN[3]:
    SUCC3[w[0]].add(w[1])
    PRED3[w[2]].add(w[1])


# ---------------------------------------------------------------- bitsets per lengte
def build_bits(L):
    """bit[i][ch] = bitmasker van alle woorden van lengte L met letter ch op positie i."""
    ws = BYLEN[L]
    bits = [dict() for _ in range(L)]
    for i in range(L):
        acc = {ch: 0 for ch in ABC}
        for k, w in enumerate(ws):
            acc[w[i]] |= 1 << k
        bits[i] = acc
    return ws, bits


def union_table(bits, L, rel):
    """U[i][L0] = bitmasker van woorden waarvan positie i in rel[L0] zit."""
    out = [dict() for _ in range(L)]
    for i in range(L):
        for L0 in ABC:
            m = 0
            for ch in rel[L0]:
                m |= bits[i][ch]
            out[i][L0] = m
    return out


def rail_for(anchor, offset, U, L):
    """Bestaat er een raiwoord van lengte L dat op posities offset..offset+L-1 onder/boven
    `anchor` past?  Geeft het bitmasker van alle passende railwoorden."""
    m = None
    for i in range(L):
        u = U[i][anchor[offset + i]]
        if not u:
            return 0
        m = u if m is None else (m & u)
        if not m:
            return 0
    return m


def first_word(mask, ws):
    k = (mask & -mask).bit_length() - 1
    return ws[k]


# ------------------------------------------------- volle-TWS-kolom-stelling
# Een volle kolom op x = 0, 7 of 14 wordt door alle drie de slotzetten x3 herscoord.  De
# opbrengst hangt af van de BOUWVOLGORDE van vijf zetten: het bovenstuk U (rijen 1..6), het
# onderstuk D (rijen 8..13) en de drie slotzetten F0/F7/F14 die elk een TWS-cel leggen.  Elke
# volgorde levert een andere verzameling tussenruns op, en ELKE tussenrun moet zelf een woord
# zijn.  Deze functie geeft per signatuur (rij0-letter, rij7-letter, rij14-letter) de HOOGST
# HAALBARE m-opbrengst plus de bijbehorende volgorde en woorden.
COLMOVES = {'U': list(range(1, 7)), 'D': list(range(8, 14)),
            'F0': [0], 'F7': [7], 'F14': [14]}


def col_plan(order):
    """tussenruns + m-opbrengst van de drie x3-gebeurtenissen voor deze bouwvolgorde."""
    placed, subs, pay = set(), [], 0
    for mv in order:
        cells = COLMOVES[mv]
        placed |= set(cells)
        a, b = min(cells), max(cells)
        while a - 1 in placed:
            a -= 1
        while b + 1 in placed:
            b += 1
        if b - a + 1 >= 2:
            subs.append((a, b))
            if mv in ('F0', 'F7', 'F14'):
                pay += 3 * (b - a + 1)
    return tuple(sorted(set(subs))), pay


def column_profile(c0, c7, c14, topn=4):
    """Hoogst haalbare m-opbrengst van een VOLLE TWS-kolom met deze drie vaste letters.
    Geeft (opbrengst, volgorde, tussenruns, woorden) of None als geen enkele volgorde werkt."""
    import itertools
    WS = {L: set(v) for L, v in BYLEN.items()}
    cand = [w for w in BYLEN[15] if w[0] == c0 and w[7] == c7 and w[14] == c14]
    if not cand:
        return None
    seen, uit = {}, []
    for order in itertools.permutations(COLMOVES):
        subs, pay = col_plan(order)
        if subs in seen:
            continue
        seen[subs] = 1
        hit = [w for w in cand
               if all(w[a:b + 1] in WS.get(b - a + 1, ()) for a, b in subs)]
        if hit:
            uit.append((pay, order, subs, hit))
    if not uit:
        return None
    uit.sort(key=lambda t: -t[0])
    p, o, s_, h = uit[0]
    return p, o, s_, h[:topn]


# ---------------------------------------------------------------- gewichten
def wrow(base):
    """m-profiel van een ankerrij: base per cel, 2x base op de DLS-cellen (3,y) en (11,y)."""
    return [base * (2 if x in (3, 11) else 1) for x in range(15)]


W_ROW0 = wrow(27)
W_ROW14 = wrow(27)
W_ROW7 = wrow(9)          # rij 7 is x9, NIET x18: de DWS op (7,7) ligt vanaf zet 1


def rowvalue(w, weights):
    return sum(weights[x] * VAL[w[x]] for x in range(15))


def fits_bag(*words):
    c = Counter()
    for w in words:
        c += Counter(w)
    tekort = sum(max(0, n - BAG.get(ch, 0)) for ch, n in c.items())
    return tekort <= BLANKS, tekort


# ---------------------------------------------------------------- hoofdmeting
def main():
    t0 = time.time()
    topn = int(os.environ.get('TOPN', '25'))
    W15 = BYLEN[15]
    print(f"lexicon: {len(W15)} 15-letterwoorden, {len(BYLEN[13])} 13-letterwoorden, "
          f"{len(BYLEN[2])} 2-letterwoorden", flush=True)
    dood_s = sorted(ch for ch in ABC if not SUCC[ch])
    dood_p = sorted(ch for ch in ABC if not PRED[ch])
    print(f"letters ZONDER opvolger (blokkeren een rail ONDER rij 0):  {dood_s}")
    print(f"letters ZONDER voorganger (blokkeren een rail BOVEN rij 14): {dood_p}", flush=True)

    ws15, bits15 = build_bits(15)
    ws13, bits13 = build_bits(13)
    U15s = union_table(bits15, 15, SUCC)
    U15p = union_table(bits15, 15, PRED)
    U13s = union_table(bits13, 13, SUCC)
    U13p = union_table(bits13, 13, PRED)
    print(f"bitsets gebouwd ({time.time()-t0:.1f}s)", flush=True)

    res = {}
    for naam, U, ws, L, off in (('rij0 + VOLLE rail1', U15s, ws15, 15, 0),
                                ('rij14 + VOLLE rail13', U15p, ws15, 15, 0),
                                ('rij0 + DWS-rail1 (kol 1..13)', U13s, ws13, 13, 1),
                                ('rij14 + DWS-rail13 (kol 1..13)', U13p, ws13, 13, 1)):
        hits = []
        snel = set(dood_s if 's' in naam.split()[0] or 'rail1' in naam else dood_p)
        snel = set(dood_s) if 'rail1' in naam else set(dood_p)
        for w in W15:
            if any(w[off + i] in snel for i in range(L)):
                continue
            m = rail_for(w, off, U, L)
            if m:
                hits.append((w, m))
        res[naam] = hits
        print(f"{naam:34s}: {len(hits):6d} van {len(W15)} ankerwoorden haalbaar"
              f"  ({time.time()-t0:.1f}s)", flush=True)
        for w, m in sorted(hits, key=lambda t: -rowvalue(t[0], W_ROW0))[:3]:
            print(f"      bv. {w} + rail {first_word(m, ws)}"
                  f"  (ankerwaarde {rowvalue(w, W_ROW0)})")

    json.dump({k: [[w, first_word(m, ws15 if len(w) == 15 and k.startswith('rij') and
                                  'VOLLE' in k else ws13)] for w, m in v[:2000]]
               for k, v in res.items()},
              open('/home/bob/programming/scrabble4/experiments/results/railtriplet.json', 'w'))

    # ------------------------------------------------ combineren tot tripletten
    print('\n=== TRIPLETTEN die BEIDE rails halen (volle rail) ===', flush=True)
    top0 = sorted(res['rij0 + VOLLE rail1'], key=lambda t: -rowvalue(t[0], W_ROW0))[:400]
    top14 = sorted(res['rij14 + VOLLE rail13'], key=lambda t: -rowvalue(t[0], W_ROW14))[:400]
    print(f"kandidaten: {len(top0)} x {len(top14)}", flush=True)
    combineer(top0, top14, ws15, ws15, topn, 'VOLLE rail')

    print('\n=== TRIPLETTEN die BEIDE DWS-rails halen (kolommen 1..13) ===', flush=True)
    top0b = sorted(res['rij0 + DWS-rail1 (kol 1..13)'],
                   key=lambda t: -rowvalue(t[0], W_ROW0))[:400]
    top14b = sorted(res['rij14 + DWS-rail13 (kol 1..13)'],
                    key=lambda t: -rowvalue(t[0], W_ROW14))[:400]
    print(f"kandidaten: {len(top0b)} x {len(top14b)}", flush=True)
    combineer(top0b, top14b, ws13, ws13, topn, 'DWS-rail')


def combineer(top0, top14, ws0, ws14, topn, tag):
    """Zoek (rij0, rij7, rij14) + de twee railwoorden die samen in de zak passen."""
    W15 = BYLEN[15]
    beste7 = sorted(W15, key=lambda w: -rowvalue(w, W_ROW7))[:600]
    uit = []
    for w0, m0 in top0[:120]:
        r1 = first_word(m0, ws0)
        for w14, m14 in top14[:120]:
            r13 = first_word(m14, ws14)
            for w7 in beste7[:120]:
                ok, tekort = fits_bag(w0, w7, w14, r1, r13)
                if not ok:
                    continue
                score = (rowvalue(w0, W_ROW0) + rowvalue(w7, W_ROW7)
                         + rowvalue(w14, W_ROW14))
                uit.append((score, w0, w7, w14, r1, r13, tekort))
                break
    uit.sort(reverse=True)
    if not uit:
        print(f"  GEEN enkele combinatie past in de zak ({tag}); "
              f"ankers+rails = 75 tegels van 100 letters + 2 blanco's", flush=True)
        # rapporteer het kleinste tekort
        best = None
        for w0, m0 in top0[:60]:
            r1 = first_word(m0, ws0)
            for w14, m14 in top14[:60]:
                r13 = first_word(m14, ws14)
                for w7 in sorted(W15, key=lambda w: -rowvalue(w, W_ROW7))[:60]:
                    _, tek = fits_bag(w0, w7, w14, r1, r13)
                    if best is None or tek < best[0]:
                        best = (tek, w0, w7, w14, r1, r13)
        print(f"  kleinste zaktekort: {best[0]} blanco's tekort bij {best[1:]}", flush=True)
        return
    print(f"  {len(uit)} zak-haalbare combinaties; top-{topn} op ankerwaarde:", flush=True)
    for t in uit[:topn]:
        print(f"   {t[0]:6d}  rij0={t[1]:15s} rij7={t[2]:15s} rij14={t[3]:15s} "
              f"| rail1={t[4]} rail13={t[5]}", flush=True)
    json.dump([{'ankerwaarde': t[0], 'rij0': t[1], 'rij7': t[2], 'rij14': t[3],
                'rail1': t[4], 'rail13': t[5]} for t in uit[:200]],
              open(f'/home/bob/programming/scrabble4/experiments/results/'
                   f'railtriplet_{tag.split()[0].lower()}.json', 'w'), indent=1)


def kolomtabel():
    """De drie TWS-kolommen van het HUIDIGE triplet doorrekenen."""
    trip = os.environ.get('TRIPLET',
                          'geschenkcheques,flexwerkstertje,polymelkzuurtje').split(',')
    print(f"\n=== VOLLE TWS-KOLOMMEN voor triplet {trip} ===")
    for x in (0, 7, 14):
        sig = (trip[0][x], trip[1][x], trip[2][x])
        pr = column_profile(*sig)
        if pr is None:
            print(f"  kolom {x:2d} ({'.'.join(sig)}): GEEN enkele bouwvolgorde haalbaar")
        else:
            p, o, s_, h = pr
            print(f"  kolom {x:2d} ({'.'.join(sig)}): hoogste m-opbrengst {p} van maximaal 126")
            print(f"      volgorde {o}, tussenruns {list(s_)}")
            print(f"      woorden {h}")


if __name__ == '__main__':
    if os.environ.get('KOLOM'):
        kolomtabel()
    else:
        main()
