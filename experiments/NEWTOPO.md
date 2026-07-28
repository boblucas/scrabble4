# NIEUWE TOPOLOGIEEN — generator, meting en verdict (2026-07-28)

Motoren: `experiments/mg_newtopo.py` (topologiegenerator) en `experiments/mg_railtriplet.py`
(rail-filter op de tripletkeuze + volle-TWS-kolom-stelling), beide bovenop
`experiments/mg_mceiling.py`.
Uitvoer: `experiments/results/newtopo*.json`, `railtriplet*.json`, logs `newtopo_*.log`.
Referentie: record **4777/4778**; doel >= 4819.  `maxgame_BEST.json` is NIET aangeraakt.

**Samenvatting in drie regels.**  De rail-familie (rij 1 / rij 13 als steunrail) is de grootste
structurele sprong die ooit voor dit probleem is gemeten (+167..+401 plafond), maar is langs
twee onafhankelijke wegen weerlegd: het ankerwoord dat de rail toelaat is 837 punten minder
waard (de `q` van geschenkcheques heeft geen 2-letter-opvolger), en ladderloos levert de rail
op zichzelf nul op.  De volle TWS-kolom 14 bestaat wel (2-3 woorden, m-opbrengst 69-87 van
maximaal 126) maar kost 12 tegels en dus twee bingo's: netto **-133**.  Kolom 0 en kolom 7
bestaan als volle kolom helemaal niet.

    .venv/bin/python experiments/mg_newtopo.py                 # de hele tabel
    MINZET=1 .venv/bin/python experiments/mg_newtopo.py        # eerlijke (ladderloze) schema's
    FIT='<naam>' TLIM=900 .venv/bin/python experiments/mg_newtopo.py   # CP-SAT-vulling
    ONLY=rail,kol14 .venv/bin/python experiments/mg_newtopo.py         # deelselectie

De kolom `minzet` in de tabellen hieronder komt uit de MINZET=1-draai
(`experiments/results/newtopo_minzet.json`), de kolom `ladder` uit de gewone draai
(`newtopo.json` / `newtopo_final.log`).

---

## 0. Wat dit script toevoegt aan de bestaande motoren

`mg_classceiling.py` rangschikt klassen op het **vrije** plafond (pure geometrie).  Dat getal
misleidt: het gat tussen vrij (5757) en ankervast (4867) is bijna 900 punten en de ankerletters
liggen vast.  Alles hier wordt daarom gemeten op het **ankervaste** plafond, en er zijn drie
nieuwe filters bijgekomen die elk een hele familie ideeen wegsnijden:

| filter | functie | wat het weerlegt |
|---|---|---|
| **bezorgbaarheid** | `auto_schedule` bouwt zelf een legaal zetschema uit een bezetting; lukt dat niet, dan bestaat de topologie niet | 8 van de 26 ideeen ("onleverbaar") |
| **woordbaarheid per run** | `words_ok` / `table_nonempty`: elke gescoorde run moet minstens een woord van die lengte toelaten dat op de ankerletters past | rij-0-pre-groepen als `{8,9,10}` ("che") |
| **lijnconsistentie** (NIEUW) | `diagnose`: alle runs op DEZELFDE lijn moeten door EEN letterrij worden waargemaakt — elke tussenstand van een stapsgewijs gelegde lijn moet zelf een woord zijn | **volle kolom 14, volle kolom 5** — zie §3 |

De CP-SAT-vuller (`fit`) is geijkt: op de recordgeometrie geeft hij exact **4777, arbiter ok=True**.

---

## 1. Waar het record zijn punten vandaan haalt (de meetlat)

| deel | tegels | m-som | punten | punten/tegel |
|---|---:|---:|---:|---:|
| rij 0 (x27) | 15 | 452 | 1723 | 115 |
| rij 14 (x27) | 15 | 427 | 1521 | 101 |
| rij 7 (x9) | 15 | 173 | 523 | 35 |
| **vrije helft** | **56** | **~250** | **~460** | **8** |
| 11 bingo's | — | — | 550 | — |
| totaal | 101 | ~1355 | 4777 | |

De hele frontier zit in die vierde regel: 56 tegels leveren 8 punten per stuk, de 45
ankertegels 84.  Dat komt door twee harde plafonds:

* **een vrije cel kan geen hoge m krijgen.**  De enige wm > 4 in het spel zijn de x27 van
  rij 0/14 en de x9 van rij 7 — allemaal ankerrijen.  Een vrije cel haalt hoogstens
  x4 (DWS-paar in een laan), of 3 per slotzet als hij in kolom 0/7/14 ligt.
* **de vrije helft krijgt de slechte letters.**  Na de 45 ankerletters is er nog 95 punten
  letterwaarde over voor 54 tegels (gemiddeld 1,76); marginale m is daar ~1,5 punt waard.

Ankervast plafond record = **4867** (eigen schema) / **4877** (na schemazoektocht);
realisatiegraad 4777/4877 = **0,979**.  Een topologie moet dus ~4930 ankervast halen om
4819 te kunnen realiseren.

---

## 2. Gemeten lexicale randvoorwaarden van dit triplet

(`geschenkcheques` / `flexwerkstertje` / `polymelkzuurtje`; alles gemeten, geen aanname.)

**Volle 15-letterkolommen** bestaan er maar op vijf plaatsen:

| kolom | patroon | #woorden |
|---|---|---:|
| 14 | `s......e......e` | 600 |
| 5 | `e......e......e` | 104 |
| 2 | `s......e......l` | 27 |
| 12 | `u......t......t` | 3 |
| 7 | `k......k......k` | 2 |
| 0, 1, 3, 4, 6, 8, 9, 10, 11, 13 | o.a. `g..f..p`, `q..r..r` | **0** |

**2-letterwoorden onder rij 0 / boven rij 14** (bepalen of een rail op rij 1/13 kan bestaan):

| kolom | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| onder rij 0 (`g e s c h e n k c h e q u e s`) | aeo | 10 | ai | o | 6 | 10 | aou | asu | o | 6 | 10 | **—** | 6 | 10 | ai |
| boven rij 14 (`p o l y m e l k z u u r t j e`) | ou | 10 | ae | **—** | aho | 11 | ae | iu | **—** | 8 | 8 | abe | 4 | **—** | 11 |

Kolom 11 (`q`) heeft er geen; kolommen 3/8/13 (`y`/`z`/`j`) hebben er onderaan geen.
Kortste q-woord = 3 (`qat`, `qua`, `que`).

---

## 3. DE VONDST: rails op rij 1 en rij 13 — en waarom ze sneuvelen

**Idee.** Rij 1 en rij 13 hebben elk twee DWS op afstand 12 (`(1,1)/(13,1)` resp.
`(1,13)/(13,13)`) en twee TLS (`(5,y)/(9,y)`).  Een brugzet die BEIDE DWS nieuw dekt scoort de
hele rail **x4 over 13-15 cellen = 52-60 m**.  Belangrijker nog: zo'n rail ligt direct naast
een x27-rij en **draagt daardoor alle pre-cellen daarvan**, waardoor de vier klimkolommen van
de recordtopologie (24-28 tegels) vervallen — en hij maakt de randkolommen 0 en 14 bereikbaar,
wat zonder rail onmogelijk is (de bekende `(13,4)`-blokkade).

**Gemeten winst.** Dit is verreweg de grootste structurele sprong die tot nu toe voor dit
probleem is gemeten:

| topologie | ankervast (ladder) | ankervast (minzet) | delta t.o.v. record |
|---|---:|---:|---:|
| rail rij 1 + rij 13 + volle kolom 14 + kol 5 + kol 2 | **5278** | **5000** | +401 / +133 |
| rail rij 1 + rij 13 + volle kolom 14 | 5260 | 5002 | +383 / +135 |
| rail rij 1 + rij 13 (H-frame) | 5136 | 4858 | +259 / -9 |
| rail rij 13 alleen | 5065 | 4760 | +188 |
| rail rij 1 alleen | 5044 | 4800 | +167 |
| **record** | 4877 | 4867 | 0 |

**Waarom het toch niet kan (met DIT triplet).**  Een volle rail op rij 1 dwingt in elke kolom
een verticale 2-run met de vaste rij-0-letter erboven.  Gemeten over alle 118.709
15-letterwoorden:

* rij-1-rail cols 0..14: **het beste woord schendt 5 kolommen** (er is er precies 1);
* rij-13-rail cols 0..14: **het beste schendt 6 kolommen** (4 woorden);
* ingekorte rail cols 1..13 (nog steeds beide DWS): rij 1 schendt er minimaal 4, rij 13 minimaal 6.

Elke schending kost een extra tegel op rij 2 (resp. rij 12) om de verticaal naar een 3-run te
verlengen — 9 tot 11 extra tegels, en er blijven dan nog maar 1-3 kandidaatwoorden over.

CP-SAT bevestigt het onafhankelijk.  `rail1 (bovenrail)` is de scherpste test: die topologie
heeft **nul dode lijnen** volgens `diagnose` (elke lijn is op zichzelf consistent), en toch
meldt CP-SAT **INFEASIBLE** — de weerlegging komt dus precies uit de 15 verplichte verticale
2-letterwoorden, zoals de telling voorspelt.  Ook `rail1+13 (H-frame)` en
`rail+kol14+kol5+kol2` zijn INFEASIBLE (presolve, < 0,2 s).

**Dit is een opdracht voor de triplet-generator, geen dood spoor.**  De rail-familie is
+130 tot +400 ankervast waard.  Wat ervoor nodig is, is exact meetbaar en goedkoop te
scoren: *een tripletwoord voor rij 0 waarvan ELKE letter een 2-letterwoord begint, en voor
rij 14 waarvan elke letter er een afsluit.*  `geschenkcheques` faalt op de `q`,
`polymelkzuurtje` op `y`/`z`/`j`.  Dat is een filter van O(1) per kandidaat-triplet en zou in
`mg_triplet_rank3.py` moeten worden meegenomen.

---

## 4. De volle TWS-kolom: de bouwvolgorde-stelling

Een volle kolom op x = 0, 7 of 14 wordt drie keer x3 herscoord doordat de rij-7-, rij-0- en
rij-14-final elk een van de drie TWS-cellen nieuw leggen: maximaal 39 + 42 + 45 = **126
m-eenheden voor 12 tegels** — met afstand de beste tegel/m-verhouding van de hele vrije helft.
Dat maximum is echter alleen bereikbaar bij EEN bepaalde bouwvolgorde, en elke volgorde levert
andere tussenruns op die stuk voor stuk zelf woord moeten zijn.

De kolom wordt met vijf zetten gelegd: bovenstuk **U** (rijen 1..6), onderstuk **D**
(rijen 8..13) en de drie slotzetten **F0 / F7 / F14**.  `mg_railtriplet.column_profile()`
loopt alle 120 volgordes af, bepaalt per volgorde de tussenruns en de m-opbrengst, en zoekt het
beste woord.  Board-breed:

| m-opbrengst | volgorde | tussenruns | 15-letterwoorden |
|---:|---|---|---:|
| **126** (maximum) | U, D, F7, F14, F0 | (1,6) (8,13) (1,13) (0,14) | **17** van 118709 |
| 108 | U, F0, D, F7, F14 | (1,6) (0,6) (0,13) (0,14) (8,13) | 708 |
| 90 | U, F0, F7, D, F14 | (1,6) (0,6) (0,7) (0,13) (0,14) | 270 |

Board-breed zijn **48.596 van de 118.709** 15-letterwoorden als volle TWS-kolom realiseerbaar
via *enige* volgorde, verdeeld over 3.956 letter-signaturen.  De maximale opbrengst 126 is dus
lexicaal haalbaar — maar alleen voor 17 woorden.

### Voor ONS triplet

| kolom | signatuur | hoogst haalbare m-opbrengst | woorden |
|---|---|---:|---|
| 0 | `g . f . p` | **geen enkele volgorde** | — |
| 7 | `k . k . k` | **geen enkele volgorde** | — |
| 14 | `s . e . e` | **87** (van 126) | `schaamtelijkere`, `schaamtevollere` |
| 14 (zonder verbindingscel nodig) | `s . e . e` | **69** | + `schaamtelijkste` |

De 87-variant (volgorde D, F0, U, F7, F14) legt het ONDERstuk als eerste en heeft dus een
verbindingscel in kolom 13 nodig.  De 69-variant (volgorde **F0, U, F7, D, F14**) heeft er
géén nodig: U hangt aan de zojuist gelegde `(14,0)` en D aan `(14,7)`.  Dat is de praktische
uitvoering.

### En toch is het NETTO NEGATIEF

Kolom 14 kost 12 tegels, en het bord zit op de cap van 101.  Gemeten op het echte record
(greedy sloop van de goedkoopste cellen, legaal én woordbaar, daarna kolom 14 ingevoegd met de
juiste finalvolgorde):

| geofferde tegels | tegels | bingo's | ankervast plafond | delta |
|---:|---:|---:|---:|---:|
| record | 101 | 11 | **4867** | 0 |
| 12 | 101 | 9 | 4734 | **-133** |
| 13 | 100 | 9 | 4733 | -134 |
| 14 | 99 | 8 | 4664 | -203 |

Kolom 14 levert ~90 m-eenheden op voor 12 tegels (7,5 per tegel tegen een vrij-gemiddelde van
4,3), maar de 12 tegels die eruit moeten breken **twee bingo's** (kolom 4 en kolom 11) = -100,
en dat kantelt het saldo.  **Conclusie: de volle kolom 14 is lexicaal mogelijk maar economisch
verlieslatend op dit bord** — het lopende `mg_insert`-spoor (kolom 7 / 11 / 14) zal niets
vinden, wat overeenkomt met de infeasible-meldingen in `mg_col7_*.log`, `mg_col14*.log` en
`mg_col11.log`.

Wat wel bestaat maar te klein is:

* **kolom 14 bovenhelft** (rijen 0..7, `s??????e`): 73 woorden overleven de deelruns
  (`sturende`, `slentere`, ...).  Ankervast **4870** = 7 onder het record.
* **kolom 7 bovenhelft** (rijen 0..10, `k......k???`): 547 woorden, waarvan 5 ook de
  centrumbingo-run (rijen 4..10) en de samenvoegrun (rijen 1..10) overleven
  (`kwijtinkjes`, `koorstukjes`, `klemminkjes`, `kruilinkjes`).  Ankervast **4887** (+10) bij
  97 tegels — CP-SAT vindt de volledige geometrie infeasible.

---

## 4b. HET RAIL-TRIPLET: gezocht, gevonden, en te duur

Motor: `experiments/mg_railtriplet.py` (bitsets over de woordenlijst, hele filter in 6 s).
Uitvoer: `experiments/results/railtriplet*.json`.

    .venv/bin/python experiments/mg_railtriplet.py     # tellingen + zak-haalbare tripletten
    KOLOM=1 .venv/bin/python experiments/mg_railtriplet.py   # TWS-kolomprofiel van een triplet

### De 26x26-matrix

| relatie | letters ZONDER partner |
|---|---|
| opvolger (rail ONDER rij 0: `rij0[x] + rail1[x]` moet een woord zijn) | **q, x** |
| voorganger (rail BOVEN rij 14: `rail13[x] + rij14[x]`) | **c, j, q, v, y, z** |

### Hoeveel ankerwoorden laten een rail toe?

| eis | haalbare 15-letter ankerwoorden | beste woord | ankerwaarde (27/9/27-model) |
|---|---:|---|---:|
| rij 0, VOLLE rail1 (kol 0..14) | **16** van 118709 | `carrouselbankje` | 999 |
| rij 0, DWS-rail1 (kol 1..13) | **644** van 118709 | `babbelzuchtiger` | 1188 |
| rij 0, geen rail (huidig) | 118709 | `croquemboucheje` | 1701 |
| rij 0 = `geschenkcheques` | — | — | **1674** |
| rij 14, VOLLE rail13 | **16** | `positiebepaling` | 837 |
| rij 14, DWS-rail13 | **449** | `consulaatsbuurt` | 1161 |
| rij 14 = `polymelkzuurtje` | — | — | **1512** |

De rail-eis is dus inderdaad **het dominante selectiecriterium**: hij snijdt 99,5 % van het
lexicon weg (DWS-rail) of 99,99 % (volle rail).  Er zijn 1497 zak-haalbare combinaties
(3 ankerwoorden + 2 railwoorden = 75 van de 101 tegels); de top staat in
`experiments/results/railtriplet_dws-rail.json`.  De 12 beste met een VOLLE rail staan in
`railtriplet_volle.json`.

### De rekening

| post | waarde |
|---|---:|
| rij 0: `geschenkcheques` (1674) -> beste rail-woord (1188) | **-486** |
| rij 14: `polymelkzuurtje` (1512) -> beste rail-woord (1161) | **-351** |
| samen | **-837 ankerwaarde** |
| daartegenover: de rail-topologie zelf, ladderloos gemeten | **+135** |

Gemeten in plaats van geschat — het ankervaste plafond van de RECORDgeometrie met de letters
van een rail-triplet erin:

| triplet | ankervast plafond |
|---|---:|
| `geschenkcheques / flexwerkstertje / polymelkzuurtje` | **4867** |
| `babbelzuchtiger / croquemboucheje / consulaatsbuurt` | 4324 (-543) |
| `mottengewichtje / verzamelcheques / waskaarskleurig` | 4064 (-803) |
| `carrouselbankje / vluchtheuveltje / familiegoederen` (volle rail) | 3706 (-1161) |

De reden is één cel: de **`q` op (11,0)** is een DLS op de x27-rij, m = 54, waarde 10 =
**540 punten uit één tegel**.  De `q` heeft geen enkele 2-letter-opvolger, dus elke rail
verbiedt hem.  Hetzelfde geldt voor de `x` (8 punten) en, boven rij 14, voor `y`/`z`/`j`/`v`
(8/4/4/4 punten) — precies de letters die de x27-rijen waardevol maken.

**Er is nog een tweede, onafhankelijke reden.** Het ladderloze plafond van de rail-topologie
zonder kolom 14 is 4858 tegen 4867 voor het record: **de rail levert op zichzelf nul op.**
De hele +135 kwam van de volle kolom 14, en die is (sectie 4) op zijn beurt netto -133 vanwege
de bingo-breuk.  De rail-familie is dus langs twee onafhankelijke wegen weerlegd:

1. het ankerwoord dat de rail toelaat is 837 punten minder waard, en
2. de rail zelf voegt (ladderloos) niets toe; alleen de kolom die hij ontsluit deed dat, en die
   kost meer tegels dan hij oplevert.

Bovendien struikelen de rail-tripletten over het **fragment-lemma**: bij
`croquemboucheje` als rij-7-woord bestaat er geen enkele keuze van slotzetcellen waarbij alle
pre-groepen woorden zijn (`mg_newtopo.auto_finals` geeft `None`).  Van de vijf doorgerekende
rail-tripletten had er geen enkele een leverbare rij-7.

---

## 5. Volledige tabel van geprobeerde ideeen

`minzet` = plafond bij een schema zonder ladderstapjes (eerlijk); `ladder` = na schemazoektocht
(optimistisch, want elke extra tussenstap eist een extra woord); `schatting` = minzet x 0,979.

| # | idee | tegels | bingo | minzet | ladder | woordbaar | verdict |
|--:|---|---:|---:|---:|---:|:--:|---|
| 1 | **rail 1+13 + kol 14 + kol 5 + kol 2** | 101 | 8 | 5000 | 5278 | run-ja | **lijn-DOOD** (kol 5 + kol 14) + rail infeasible |
| 2 | **rail 1+13 + kol 14** | 101 | 8 | 5002 | 5260 | run-ja | lijn-DOOD (kol 14) + rail infeasible |
| 3 | rail 1+13 + kol 14 + kol 2 | 101 | 7 | 4976 | 5240 | run-ja | idem |
| 4 | rail 1+13 + kol 14 + laan 4 | 101 | 7 | 4967 | 5237 | run-ja | idem |
| 5 | rail 1+13 + kol 14 (99 tegels) | 99 | 7 | 4965 | 5235 | run-ja | idem |
| 6 | rail 1+13 (H-frame, geen kol 14) | 101 | 9 | 4858 | 5136 | run-ja | rail lexicaal infeasible |
| 7 | x4-stapel (rijen 1/4/10/13) | 101 | 7 | 4773 | 5083 | run-ja | rail lexicaal infeasible |
| 8 | rail rij 13 alleen | 101 | 8 | 4760 | 5065 | run-ja | rail lexicaal infeasible + lijn-DOOD (kol 7, 11-run) |
| 9 | rail rij 1 alleen | 101 | 10 | 4800 | 5044 | run-ja | rail lexicaal infeasible |
| 10 | **kolom 7 bovenhelft (rijen 1..3)** | 97 | 10 | 4682 | **4887 (+10)** | ja | lijn-OK, geometrie CP-SAT-infeasible |
| 11 | *record (referentie)* | 101 | 11 | 4867 | 4877 | ja | 4777 gerealiseerd |
| 12 | kolom 14 bovenhelft (rijen 1..6) | 101 | 10 | 4652 | 4870 (-7) | ja | netto negatief |
| 13 | volle kolom 5 (`e..e..e`) | 100 | 11 | 4683 | 4845 (-32) | run-ja | lijn-DOOD |
| 14 | 2 x4-lanen (rij 4 + rij 10) | 98 | 6 | 4425 | 4817 (-60) | ja | negatief: x4 = 4 m/cel < gemiddelde |
| 15 | x4-lanen rij 2 + rij 12 | 101 | 10 | 4709 | 4788 (-89) | ja | negatief |
| 16 | rij-4-laan pas laatst x4 gesloten | 101 | 9 | 4557 | 4767 (-110) | ja | negatief |
| 17 | kolom 0 onderhelft (rijen 8..13) | 103 | 10 | — | — | — | past niet in 101 tegels |
| 18 | kolom 14 onderhelft (rijen 8..13) | 102 | 10 | — | — | — | past niet; 1 kandidaatwoord |
| 19 | kolom-14-ladder, 4 klimmers | 108 | 10 | — | — | — | past niet in 101 tegels |
| 20 | kolom-14-ladder, 3 klimmers | — | — | — | — | — | onleverbaar: pre-groep `{8,9,10}` = "che" |
| 21 | x4-lanen rij 3 + rij 11 | — | — | — | — | — | onleverbaar (rij-14-pre onbereikbaar) |
| 22 | 2 lanen + kolom 14 | — | — | — | — | — | onleverbaar |
| 23 | rail rij 2 + rij 12 (lex-veilig) | — | — | — | — | — | onleverbaar (kolom 14 hangt los) |
| 24 | weefsel (lanen eerst, dan kruisen) | — | — | — | — | — | onleverbaar |
| 25 | kleine rij-0-final (5 tegels) | — | — | — | — | — | onleverbaar + verliest 2 x DLS-x27 |
| 26 | rail 1 + kol 14 / rail 13 + kol 14 | — | — | — | — | — | onleverbaar (halve rail draagt de andere helft niet) |

**Netto t.o.v. 4777: geen enkel idee levert een geverifieerd bord boven het record op.**
Er is dus GEEN nieuw json-bord opgeslagen en `experiments/results/maxgame_BEST.json` is
ongewijzigd.

---

## 6. Structurele lessen (deze gelden ook voor de volgende ronde)

1. **De ladder is een illusie op schema-niveau, niet alleen op tegelniveau.**  De
   m-plafondzoeker wint 200-400 punten door lijnen tegel-voor-tegel te leggen, maar elke
   tussenstand moet zelf een woord zijn.  De kolom `minzet` is het eerlijke getal; het verschil
   `ladder - minzet` is precies de lexicale schuld.  `mg_classceiling`'s `vrij`-kolom
   overschat om dezelfde reden.
2. **Lijnconsistentie is een sterker filter dan run-woordbaarheid.**  `table_nonempty` keurt
   elke run apart; `diagnose` eist dat alle runs op een lijn door EEN woord worden gedekt.
   Voor kolom 14 (`s..e..e`) is dat het verschil tussen 600 woorden en 2.
   **Aanbeveling: `diagnose` als standaardfilter in elke generator gebruiken vóór CP-SAT.**
   *Let op de valkuil die deze campagne zelf maakte:* `diagnose` beoordeelt EEN gegeven
   zetschema.  Om te bepalen of een LIJN uberhaupt bestaat moet je alle bouwvolgordes aflopen
   (`mg_railtriplet.column_profile`); een eerdere versie van dit verslag concludeerde uit vijf
   handmatig gekozen volgordes ten onrechte dat kolom 14 onmogelijk was.
3. **x4-lanen zijn structureel te zwak.**  4 m per cel tegen een vrij-gemiddelde van 4,3 en
   een bordgemiddelde van 13,4.  Rijen 2/3/4/10/11/12 leveren dus per definitie niets op; alle
   vier de lane-varianten zijn negatief gemeten.  Alleen de rij-4-laan uit het record loont, en
   die loont omdat hij door zes kolommen wordt gekruist (herscoring), niet om zijn x4.
4. **Alleen kolom 0, 7 en 14 zijn interessante kolommen** (wm = 3 bij een slotzet); alle andere
   kolommen krijgen wm = 1 van de finals, dus 15 m voor 13 tegels.  Kolom 0 is lexicaal nul
   (`g..f..p`), kolom 7 heeft 2 volle woorden en 5 halve, kolom 14 heeft 0 volle en 73 halve.
5. **De pre-groepen van een ankerrij moeten zelf woorden zijn.**  `{8,9,10}` van
   geschenkcheques is "che" en bestaat niet — dat legt de keuze van de final-cellen van rij 0
   vrijwel vast op iets als `{0,3,7,8,11,13,14}` (het record).  Combineer dat met het
   pre-groep-lemma (elke groep een eigen dalende kolom) en de recordtopologie is vrijwel de
   enige die met dit triplet bestaat.

---

## 7. Aanbeveling voor de volgende stap

| prioriteit | actie | verwachte winst |
|--:|---|---|
| 1 | **Rail-spoor SLUITEN.**  Uitgevoerd en langs twee onafhankelijke wegen weerlegd (sectie 4b): het rail-triplet kost 837 ankerpunten, en de rail zelf levert ladderloos nul op.  Niet opnieuw openen zonder een lexicon met een 2-letterwoord op `q`. | gesloten |
| 2 | **Kolom-14/7/11-inserts stoppen.**  De volle kolom 14 bestaat (69 of 87 m-opbrengst, 2-3 woorden) maar is netto **-133** op het record door de bingo-breuk; kolom 0 en 7 bestaan helemaal niet. | bespaart rekentijd |
| 3 | **De bingo-breuk is de echte rem, niet de m.**  Elke structurele toevoeging van 12 tegels sloopt twee 7-tegelzetten (-100).  Een topologie die 12 tegels vrijmaakt ZONDER bingo's te breken maakt kolom 14 (+90 m, ~+135 punten) meteen positief.  Dat is de scherpst geformuleerde open vraag. | +100 .. +135 |
| 4 | Kolom-7-bovenhelft (`kwijtinkjes`-klasse, 5 woorden) met een ANDERE omliggende geometrie dan het record — het enige lexicaal levende plus-signaal in de tabel. | +10 plafond |
| 5 | De frontier blijft verder het LEXICON op de 14 hoogste m-cellen (`CLASSCEILING.md` §6.3, ~700 punten), niet de geometrie. | — |
