# Globale bovengrens voor de score van elk legaal dutch2026-spel

Rekenscript: `experiments/mg_globalbound.py` (or-tools CP-SAT doet het rekenwerk;
Python bouwt alleen het model — geen pure-Python loops).
Multipliciteitsmotor: `experiments/mg_mceiling.py`.

## 0. Uitgangspunt: de multipliciteitsidentiteit

Voor een gespeeld spel geldt exact

```
score = SOM over cellen c van  m(c) * waarde(letter op c)   +   50 * #7-tegelzetten
```

met `m(c)` puur uit geometrie + zetvolgorde: voor elke scorende gebeurtenis
(maximale run van >= 2 cellen die minstens één nieuwe tegel bevat) met
woordmultiplier `wm` (= product van `word_multiplier` over de **nieuwe** cellen
van die zet in die run) draagt elke cel `c` van de run bij met
`wm * (letter_multiplier(c)` als `c` nieuw is in die zet, anders `1)`.

Op het huidige record (`experiments/results/maxgame_BEST.json`) klopt dat exact:
`SOM m*val = 4201`, `11` bingo's, `4201 + 550 = 4751 = score_game`.

Een globale bovengrens volgt dus uit een per-cel maximum `M(c)` van `m(c)` over
**alle** legale spellen, plus de herschikkingsongelijkheid (hoogste tegelwaarden
op hoogste `M`), plus de maximale bingo-bonus.

## 1. Aannames — en waarom ze mogen

| # | Aanname | Verdediging |
|---|---------|-------------|
| A1 | Bord = de arrays `r.letter_multiplier` / `r.word_multiplier` uit `maxgame_score` | Dat is de arbiter: `MG.score_game` rekent hiermee. Gecontroleerd: 8 TW, 17 DW (incl. centrum), 24 DL, 12 TL, transpositie-symmetrisch. Geen cel heeft tegelijk `lm>1` en `wm>1`. |
| A2 | Een zet legt 1..7 nieuwe tegels, alle in één lijn (rij of kolom) | Standaard-Scrabble-regel; `r.hand_size == 7` |
| A3 | Hoogstens 101 tegels op het bord | 102 in de zak (100 letters + 2 blanco's), tegenstander houdt er >= 1 |
| A4 | 50 bonus per zet die precies 7 tegels legt | `r.emptyhand_bonus == 50` |
| A5 | Scorende gebeurtenissen = maximale runs (>=2) met minstens één nieuwe tegel; per zet per cel hoogstens één horizontale en één verticale zulke run | Exact wat `MG.score_game` / `events_of` doen |
| A6 | Niets over woordenboek-legaliteit | De grens is dus zeker ook geldig voor spellen die het lexicon respecteren (relaxatie) |

Elke stap hieronder is een **relaxatie**: elk echt spel is een toegelaten punt
van het model, dus elk getal is een geldige bovengrens.

## 2. De lemma's

### L1 — per lijn: de partitie-grens

Fixeer een cel `c` en zijn rij `R`.

* Elke horizontale gebeurtenis die `c` bevat hoort bij precies **één** zet, en die
  zet legt minstens één tegel binnen `R` (de run ligt in `R`).
* Verschillende zetten leggen **disjuncte** celverzamelingen.
* De `wm` van zo'n gebeurtenis is het product van `word_multiplier` over de
  nieuwe cellen van die zet *binnen de run*, dus `<=` het product over álle
  cellen van die zet in `R` (want `word_multiplier >= 1`).
* De factor `letter_multiplier(c)` telt **alleen** in de gebeurtenis van de zet
  die `c` zelf legt — dat is precies het blok dat `c` bevat.

Met `w(B) = PROD_{p in B} wm(p)`:

```
m_rij(c) <= max over partities P van R in blokken van <= 7 cellen van
            SOM_{B in P} w(B)  +  (lm(c)-1) * w(B_c)
```

Volledige bedekking van `R` is optimaal (elk blok draagt `w(B) >= 1` bij), en
cellen met `wm = 1` (behalve `c`) zijn altijd het best als singleton: ze in een
blok stoppen verandert `w(B)` niet maar kost hun eigen `+1`. Analoog voor de
kolom; `m(c) <= m_rij(c) + m_kol(c)`.

Blokgrootte `<= 7` volgt uit A2. Blokken hoeven niet aaneengesloten te zijn
(een zet mag over al liggende tegels heen springen) — daarom laten we
willekeurige deelverzamelingen toe; dat is een relaxatie, dus veilig.

### L2 — oriëntatie-exclusiviteit

De zet die `c` legt ligt in één lijn. Ligt die in de rij, dan legt diezelfde zet
in de kolom van `c` alléén `c`, dus daar is `B_c = {c}`. Dus

```
M2(c) = max( Hb_vrij(c) + Vb_singleton(c) ,  Hb_singleton(c) + Vb_vrij(c) )
```

**Numerieke controle:** op het record is `max_c m(c) = 54` en zijn er **0**
schendingen van `M2` — het script test dit bij elke run (`selftest`).

### L3 — lijn-decompositie (W wordt gedeeld)

Met `W_L = SOM_{B in P_L} w(B)` en `V_L =` som van de tegelwaarden in lijn `L`:

```
SOM_{c in L} val(c) * m_L(c)  =  W_L * V_L  +  SOM_{c in L} val(c)*(lm(c)-1)*w(B_c)
```

De factor `W_L` wordt dus **gedeeld** door alle 15 cellen van de lijn. Daardoor
kan de tegelschaarste worden ingezet: `SOM over rijen van #tegels = SOM over
kolommen van #tegels = #tegels <= 101`, terwijl elke lijn maar 15 cellen heeft
(dus `V_L <= TOPSUM(k_L)`, de som van de `k_L` hoogste tegels in de zak).

### L4 — rij/kolom-koppeling van de woordpremies

Een cel met `wm > 1` zit in hoogstens één blok van grootte >= 2 (dat van zijn
eigen zet); in de loodrechte lijn is hij singleton en draagt daar los `wm(c)` bij
in plaats van in een product. Rij 0 haalt `w = 27` alleen als `(0,0)`, `(7,0)` en
`(14,0)` alle drie H-georiënteerd zijn — maar kolom 0 heeft voor zijn 27 juist
`(0,0)` V-georiënteerd nodig. Van `{rij 0, rij 14, kol 0, kol 14}` kunnen er
hoogstens twee tegelijk op `W = 39` staan.

### L5 — blok- en zetbudget (koppelt bingo's aan multipliciteit)

De blokken van de **rij**-partities zijn precies: de celverzameling `C_m` van
elke horizontale zet `m`, plus `{c}` voor elke cel `c` die door een verticale zet
is gelegd. Dus met `b_L` = aantal blokken in lijn `L`, `K_H`/`K_V` = aantal
horizontale/verticale zetten en `n_H`/`n_V` = aantal tegels met die oriëntatie:

```
SOM_rijen b_L = K_H + n_V ,   SOM_kolommen b_L = K_V + n_H
=>  SOM_rijen b_L <= T ,  SOM_kolommen b_L <= T ,  SOM_alle b_L = T + K
```

met `T` = aantal tegels (<= 101) en `K` = aantal zetten. Verder `7K >= T` en, met
`beta` = aantal 7-tegelzetten, `T >= 7*beta + (K - beta) = 6*beta + K`.
Ook geldt per lijn `k_L <= 7*b_L`.

**Numerieke controle op het record:** `T = 101`, `K = 33`,
`SOM_rijen b = 75`, `SOM_kolommen b = 59`, en `75 + 59 = 134 = T + K` — de
identiteit klopt exact. Het script `assert`t dit.

Dit is de scherpste structurele rem: **hoge `W_L` vraagt veel blokken, veel
blokken vraagt veel zetten, en veel zetten sluit bingo's uit.** Het model kiest
zelf de afruil (het optimum geeft vrijwel alle bingo's op).

### L6 — elke tegel zit in een woord

De openingszet vormt een woord van >= 2 letters; elke latere zet raakt het
bestaande bord; een zet van >= 2 tegels ligt zelf in een aaneengesloten run. Dus
elke bezette cel heeft een orthogonaal bezette buur. (Enige uitzondering: een
bord met precies één tegel — dat scoort 0.)

### L7 — bezettingskoppeling rijen/kolommen

De `k_r` bezette cellen van rij `r` liggen in `k_r` **verschillende** kolommen,
die dus niet leeg zijn: `k_r <= n_kol`, en analoog `k_x <= n_rij`. Dit is wat
verhindert dat rijen én kolommen tegelijk geconcentreerd zijn (7 volle rijen ⇒
alle 15 kolommen niet-leeg maar elk hoogstens 7 hoog).

## 3. Ingrediënten (numeriek)

Zak (dutch2026): 100 lettertegels + 2 blanco's, totale letterwaarde **230**;
de 15 hoogste tegels samen 78, de 7 hoogste samen 46.

Per lijn `Wmax` (bij 15 bezette cellen) en `G = max(W - b)`:

| lijn | Wmax | Wmax met mask=0 (L4) | G |
|---|---|---|---|
| rij 0 / rij 14 / kol 0 / kol 14 | 39 | 21 | 26 |
| rij 7 / kol 7 | 30 | 20 | 17 |
| de 16 DW-lijnen (rij/kol 1,2,3,4,10,11,12,13) | 17 | 17 | 3 |
| de 8 premievrije lijnen (rij/kol 5,6,8,9) | 15 | 15 | 0 |

Hoogste `M2(c)` = **83**, op de acht DL-cellen die op een TW-lijn liggen
(`(3,0) (11,0) (3,14) (11,14) (0,3) (0,11) (14,3) (14,11)`); daarna 65, 63,
56, 54, 53, 47, ...

Letterpremie-term `E = SOM_c val(c)*(lm(c)-1)*(w(B_rij)+w(B_kol)) <= 2216`
(36 cellen met `lm > 1`, herschikt met de hoogste tegelwaarden).

Bingo: `floor(101/7) = 14` zetten van 7 tegels ⇒ hoogstens **700** bonus
(vanaf stap 5 een variabele die tegen L5 wordt afgewogen).

## 4. Tussenstand per verscherpingsstap

| stap | inhoud | bovengrens |
|---|---|---|
| 1 | per-cel `M1 = Hb_vrij + Vb_vrij` (L1) + herschikking + 700 bingo | **15182** |
| 2 | + oriëntatie-exclusiviteit `M2` (L2) | **14649** |
| 6 | celmodel met alle 225 cellen: L1–L7, CP-SAT 1 uur / 32 workers | **13917** |

De stappen 1 en 2 zijn **analytisch** (geen solver-gap). Stap 6 rapporteert de
CP-SAT *objective bound*, die ook bij een time-out een geldige bovengrens is.
Het beste door de solver gevonden modelpunt lag op **10835**; dat is dus een
indicatie dat het echte optimum van déze relaxatie ergens in [10835, 13917]
ligt, maar 10835 is **geen bewezen grens**. Meer rekentijd op stap 6 drukt het
getal verder omlaag (60 s gaf 14828, 3600 s gaf 13917).

Ter referentie het (aantoonbaar lossere) aggregaatmodel, `--agg`:
stap 3 = 17296, stap 4 = 17296, stap 5 = 17292.

**Het antwoord: elk legaal dutch2026-spel scoort hoogstens 13917.**

## 5. Sanity

De grens moet minstens 4751 (huidig record `maxgame_BEST.json`,
`score_game`-geverifieerd) en minstens 4819 (extern record) zijn; het script
`assert`t dat expliciet. 13917 >= 4819: OK. De grens ligt dus een factor ~2,9
boven het record en een factor ~2,9 boven 4819 — 4819 is met deze analyse
**niet uitgesloten**, en er is ruim marge voor nog aanzienlijk hogere spellen.

## 6. Wat er NIET in zit (ruimte voor verdere verscherping)

* **Contiguïteit**: een blok van >= 2 cellen in een lijn moet in werkelijkheid
  samen met de al liggende tegels een aaneengesloten run vormen; het model staat
  willekeurige deelverzamelingen toe.
* **Run-lengte per gebeurtenis**: L3 rekent elk blok af alsof zijn run de hele
  lijn beslaat; in werkelijkheid is de run de maximale run op dat moment.
* **Samenhang**: het bord moet vanuit het centrum samenhangend groeien (alleen de
  zwakkere buur-eis L6 is gemodelleerd).
* **Woordenboek**: volledig genegeerd (A6). Dat is veruit de grootste bron van
  speling — het record haalt gewogen gemiddeld `m ~ 18,3`, terwijl de geometrie
  alleen al `m ~ 60` toestaat.

### Een doodlopend spoor dat het vermelden waard is

Een *aggregaatmodel* (alleen per-lijn-variabelen `k_L, b_L, W_L, V_L`, geen 225
celvariabelen) is klein en snel, maar **aantoonbaar losser** (~17300): daarin
mogen rij 0 én kolom 0 allebei de vijftien hoogste tegels claimen, wat in
werkelijkheid onmogelijk is (ze delen maar één cel). De rij/kolom-koppeling op
celniveau is dus onmisbaar. Het aggregaatmodel blijft beschikbaar via `--agg`.
