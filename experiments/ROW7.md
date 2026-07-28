# RIJ 7: HERWEGING (x9) EN DE BEZORGSTRUCTUUR (2026-07-28)

Machinerie: `experiments/mg_row7.py` (delen 0-7, env `PART`, `MAXROOTS`, `SCHEDITERS`, `TOP`).
Uitvoer: `experiments/results/row7.json`.  Basisbord: `experiments/results/maxgame_BEST.json`
(4777, 101 tegels, 33 zetten, 11 bingo's, arbiter `ok=True`).

**Uitkomst in een zin: de rij-7-eis is geen zelfmoord maar een ACTIEF VOORDEEL, en
flexwerkstertje is — gegeven geschenkcheques en polymelkzuurtje — het beste rij-7-woord van
alle 26.607 die de restzak toelaat.  Geen enkel alternatief haalt 4777.**

---

## 0. De x9 is bevestigd — en hij is een SPELREGEL, geen architectuurkeuze

Empirisch op het record (deel 0, product van `word_multiplier` over de nieuw gelegde cellen):

| rij | slotzet (kolommen) | wm-product | pre-set |
|-----|--------------------|-----------:|---------|
| 0   | 0,3,7,8,11,13,14   | **x27**    | 1,2,4,5,6,9,10,12 |
| 7   | 0,1,2,3,12,13,14   | **x9**     | 4,5,6,7,8,9,10,11 |
| 14  | 0,1,2,3,7,13,14    | **x27**    | 4,5,6,8,9,10,11,12 |

**Structureel lemma (x9 is afgedwongen).** Een zet legt hoogstens 7 tegels, dus een 15-letterrij
wordt altijd door een slotzet voltooid; die slotzet moet (0,y) en (14,y) bevatten om beide TWS te
pakken. Voor rij 0 en 14 kan ook (7,y) nieuw zijn -> 3x3x3 = 27. Voor rij 7 is (7,7) het
middenvak, en **zet 1 moet het centrum dekken** — (7,7) ligt er dus altijd al. De DWS op (7,7)
telt alleen bij nieuwe belegging, dus rij 7 haalt 3x3 = **9**. Dat is niet te repareren met een
andere architectuur. Alle rij-7-waarderingen in `TRIPLET_RERANK.md` (die x18 gebruikten) zijn
exact een factor 2 te hoog.

Ware m-profielen van de ankerrijen op het record (m-calculus, `mg_mceiling.py`):

```
rij  0 geschenkcheques  m=[27,28,35,54,29,31,28,27,27,28,30,54,30,27,27]  som 482  waarde 1723
rij  7 flexwerkstertje  m=[ 9, 9,14,18,14,14,11,13,10,12,14,17,10, 9, 9]  som 183  waarde  523
rij 14 polymelkzuurtje  m=[27,27,27,54,31,29,28,27,29,30,30,33,28,27,27]  som 454  waarde 1521
```

Ankers samen 3767 van 4777 (78,9%).

---

## 1. De gecorrigeerde ranglijsten

De drie ankerrijen hebben een identiek letterprofiel (DL op x=3 en x=11), dus de volgorde per rij
is identiek; alleen de schaal verschilt. `lsum(w) = S(w) + v(w[3]) + v(w[11])`.

```
 1. croquemboucheje 63   6. flauwekulexcuus 61   11. jacquardweefsel 60
 2. geschenkcheques 62   7. vluchtreflexjes 61   12. jacquardmachine 59
 3. jacquetkostuums 62   8. deuxchevauxtjes 61   13. chequeformulier 59
 4. croquetmatchjes 61   9. verzamelcheques 60   ...
 5. alfahydroxyzuur 61  10. cultuurchequeje 60
```

Onze keuzes: geschenkcheques 62 (rang 2), **flexwerkstertje 51 (rang 409)**, polymelkzuurtje 56
(rang 45). Rij-7-waarde: **459** met x9 (was 918 met x18).

### Verschuift het optimum door de herweging? NEE.

Volledige tripletenumeratie met bewijsbare vloeren, zak- en blanco-bewust:

| weging | huidig triplet | rang | beste alternatief | gat |
|--------|---------------:|-----:|-------------------|----:|
| **27/9/27 (correct)** | 3645 | 832 / 833 | vluchtreflexjes / babyzwemmertjes / verzamelcheques | **+99** |
| 27/18/27 (fout) | 4104 | 116 / 117 | vluchtreflexjes / babyzwemmertjes / verzamelcheques | +117 |

De koploper is onder beide wegingen hetzelfde woordentrio; de halvering van rij 7 verkleint het
gat van +117 naar +99 maar herschikt de lijst niet. Reden: rij 0 en rij 14 zijn waarde-identiek,
dus het triplet-optimum wordt gedomineerd door het rij-0/14-paar en rij 7 is de restpost.

### Correctie op TRIPLET_RERANK.md (tweede fout, belangrijker dan de x18)

Die analyse concludeerde dat ons triplet "masker-bewust globaal optimaal (3573)" is met "99 tot
423 punten voorsprong". Dat model waardeert een DL-cel in de PRE-set op **nul** extra. De
m-calculus weerlegt dat: `m(3,7)=18` (slotzet, DL) tegen `m(11,7)=17` (pre-set, DL) — een
pre-cel int zijn dubbel wel degelijk, in zijn bezorgzet en in elk kruiswoord. Het verschil is
~1-7 per letterpunt, niet 9. Daarmee vervalt de claim van 99-423 punten voorsprong; het eerlijke
gat naar het beste alternatief is +98 (deel 4b), niet negatief.

---

## 2. Het bezorglemma van rij 7 — de 'werkster'-eis is R=0

**Bezorglemma.** Rij 7 heeft een pre-set P van 8 kolommen met 7 in P. Een zet legt <= 7 tegels en
mag aan beide kanten van een bestaand blok aanleggen (de span moet gevuld zijn — `shape_ok`,
en `score_game` accepteert dat). Daarom is **elke maximale run van P in EEN zet te leggen** zodra
hij het bord raakt:

* de run die kolom 7 bevat groeit vanuit het centrum (hoogstens 7 nieuwe cellen — altijd waar);
* elke andere run heeft een **wortel** nodig: een kolom c in die run met een tegel op (c,6) of
  (c,8), d.w.z. een verticaal/stub die het bord raakt.

Enige woordenboekeis: elke maximale run van P met lengte >= 2 is een geldig woord. Tussenstadia
zijn te vermijden door de run in een zet te leggen.

> **bezorgkosten van rij 7 = aantal wortels = (#runs van P) - 1**

De 'werkster'-eis is dus precies het geval **R = 0**: P is een aaneengesloten 8-blok [a,a+7] om
kolom 7 en `w[a:a+8]` moet een woord zijn. Dat is geen spelregel maar ook geen willekeur — het is
de goedkoopste bezorging die er is.

### Hoeveel woorden laat elk model toe?

| R (wortels) | toegelaten rij-7-woorden | beste rij-7-waarde | woord | flexwerkstertje | rang |
|---:|---:|---:|---|---:|---:|
| 0 | 31.030 | 495 | quichebuffetjes | 441 | 36 |
| 1 | 93.213 | 549 | vluchtreflexjes | 441 | 148 |
| 2 | 114.059 | 549 | vluchtreflexjes | 441 | 277 |
| 3 | 117.552 | 558 | geschenkcheques | 459 | 154 |
| >=5 | 118.496 | 558 | geschenkcheques | 459 | 175 |

Per venster bij R=0: [1,8] 628, [2,9] 1171, [3,10] 2658, **[4,11] 7149 (het onze)**, [5,12] 6358,
[6,13] 14908 woorden. (De oude, strengere eis — venster moet ook de x4-kolommen 4 en 10 dekken —
sneed dit terug tot 9.703; die eis is architectuur, geen noodzaak.)

**Blok-lemma.** Bij R=0 is het voor GEEN ENKEL woord mogelijk beide DL-kolommen (3 en 11) in de
x9-slotzet te houden: een 8-blok om kolom 7 loopt van a tot a+7 met 1<=a<=6 en bevat dus altijd
kolom 3 (als a<=3) of kolom 11 (als a>=4). Vanaf R=1 kan het wel, voor 93.446 van de 118.709
woorden. flexwerkstertje heeft daar 3 wortels voor nodig.

### Wat levert de relaxatie nominaal op? Hooguit +18.

Joint tripletranglijst (masker-bewust, zak- en blancobewust, harde rij-0/14-fragmentcheck):

| wortelbudget | huidig | rang | beste alternatief | gat |
|---|---:|---:|---|---:|
| R=0 | 3573 | 1 / 2 | (geen) | +0 |
| R=1 | 3573 | 2 / 4 | geschenkcheques / bouwvakkersfuif / woestijnlynxjes | +18 |
| R=2 | 3573 | 4 / 7 | idem | +18 |
| R=3 | **3591** | 1 / 3 | wij zelf (kolom-11-DL vrijgemaakt) | +0 |

Het maximum van de hele relaxatie is dus **+18**, en dat pakken we met ons eigen triplet — geen
enkele bezorgstructuur laat een hoogwaardiger rij-7-woord toe dat ook wint.

---

## 3. En in de praktijk? De relaxatie is NEGATIEF: -22, met de arbiter gemeten

De +18 is gebouwd en geverifieerd (deel 6a). Constructie met **dezelfde letters** en **11
bingo's behouden**:

* pre-set rij 7 {4..11} -> {2,4,5,6,7,9,10,12}; slotzet {0,1,2,3,12,13,14} -> {0,1,3,8,11,13,14};
* (2,7) en (12,7) als gewortelde losse tegels ((2,6)='s', (12,6)='g');
* de kolom-11-bingo verhuist van rijen 7-13 ('raspige') naar rijen 8-14 en wordt NA de
  rij-7-slotzet gelegd, zodat de verticale run rijen 7-14 = 'raspiger' geldig blijft.

**Arbiter: 4755, ok=True — dat is 22 punten MINDER.**

```
 (11, 7)  17-> 20  r    +6     <- de vrijgemaakte DL, precies zoals voorspeld
 (11,14)  33-> 34  r    +2
 ( 4, 7)  14-> 13  w    -5     <- en hier gaat het mis
 ( 5, 7)  14-> 13  e    -1     ( 9, 7)  12-> 10  t    -4
 ( 6, 7)  11-> 10  r    -2     (10, 7)  14-> 12  e    -2
 ( 7, 7)  13-> 12  k    -3     (11, 8..13)                 -11
 ( 8, 7)  10->  9  s    -2
                                                    som   -22
```

**Herscoringslemma (de kern van het antwoord).** Elke zet herscoort ELKE maximale run die hij
raakt. Een aaneengesloten pre-run levert daardoor een geneste keten op; losse pre-cellen leveren
niets. Op ons bord is die keten exact:

```
zet  8: rij-7-run [4,5]  "we"        +6
zet 10: rij-7-run [4,7]  "werk"     +11
zet 16: rij-7-run [9,10] "te"        +3
zet 17: rij-7-run [9,11] "ter"       +7
zet 21: rij-7-run [4,11] "werkster" +18
                            TOTAAL   45
```

De 'werkster'-eis is dus geen kostenpost maar een **herscoringsmotor van 45 punten**. Wie de
pre-set uit elkaar trekt om een DL van 18 (nominaal) / 6 (echt) vrij te spelen, gooit die 45 weg.

---

## 4. De eerlijke ranglijst: herscorings-bewust en zak-bewust

Deel 7 waardeert rij 7 als `9*(S + DL-bonus) + max-bezorgketen`, waarbij de keten met een DP over
alle legvolgorden wordt gemaximaliseerd (eilanden toegestaan tegen wortelkosten).
**Validatie: de DP reproduceert de recordketen exact (45) en bewijst dat onze zetvolgorde
optimaal is** — met 2 wortels 45, met 3 wortels ook 45.

Zonder zakbeperking (31.030 legbare woorden):

| # | woord | totaal | keten | venster |
|---|-------|-------:|------:|---------|
| 1 | acrylschilderij | 567 | 99 | [5,12] |
| 2 | excuusvrouwtjes | 556 | 79 | [6,13] |
| 3 | quichebuffetjes | 553 | 58 | [6,13] |
| 4 | vluchtreflexjes | 552 | 75 | [6,13] |
| 5 | gymjuffrouwtjes | 550 | 73 | [3,10] |
| .. | **flexwerkstertje** | **486** | **45** | **[4,11]** | rang **101** |

Maar de zak is bindend. Met rijen 0/14 vast (geschenkcheques + polymelkzuurtje) blijft er een
restzak over, en daarin:

| # | woord | totaal | keten | blanco |
|---|-------|-------:|------:|-------:|
| **1** | **flexwerkstertje** | **486** | 45 | 0 |
| 2 | flexkiezeresjes | 458 | 44 | 0 |
| 3 | reflexweggetjes | 454 | 58 | 0 |
| 4 | walvisexpertjes | 449 | 53 | 0 |
| 5 | walvisvrouwtjes | 448 | 79 | 1 |

**flexwerkstertje is rang 1 van 26.607, met 28 punten voorsprong.**

Zelfde uitkomst met de rauwe m-calculus op de recordgeometrie (deel 4a, zonder ketenmodel):
flexwerkstertje = 523, **rang 1 van 99.467**. De reden is de `x` op kolom 3: dat is de enige `x`
in de zak, geschenkcheques en polymelkzuurtje gebruiken hem niet, en hij valt op de DL BINNEN de
x9-slotzet — `m=18`, `18*8 = 144` punten uit een enkele cel, 28% van heel rij 7.

---

## 5. Wat er dan wel te halen valt (en waarom het niet kan)

Ware m-calculus, hele tripletruimte vrij op deze geometrie (deel 4b): huidig 3767, beste **3865
(+98)** = vluchtreflexjes / babyzwemmertjes / chequeformulier; 118 tripletten halen onze waarde.
Dat is de harde bovengrens van de hele ankerwoord-discussie op dit voetafdruk.

Die +98 is niet inbaar. Kolomtabel-census (aantal 8-letterwoorden per kolom die rij 0 aan rij 7,
resp. rij 7 aan rij 14 knopen — deel 5):

| triplet | som top | som bodem | dode kolommen |
|---------|--------:|----------:|--------------:|
| **geschenkcheques / flexwerkstertje / polymelkzuurtje** | 3542 | 1531 | **1** |
| vluchtreflexjes / babyzwemmertjes / chequeformulier (+98) | 1892 | 2760 | 4 |
| vluchtreflexjes / babyzwemstertje / chequeformulier (+84) | 1815 | 2778 | 5 |
| vluchtreflexjes / whiskyzuipsters / jacquardweefsel (+60) | 1292 | 3323 | 2 |

Een dode kolom betekent: door die kolom is geen verticaal mogelijk die rij 7 kruist — precies
het mechanisme dat gymjuffrouwtjes, hypochlorigzuur en de royalty-lijn doodde. Vier dode
kolommen kosten veel meer dan 98 punten aan verticalen, wortels en bezorging.

Tenslotte: **exacte-score schemazoeker** op het vaste bord (letters onveranderd, `score_game` als
poort, splits/verplaats/samenvoeg met plateau-wandeling): 6 onafhankelijke runs over 5 seeds,
samen **ruim 6,6 miljoen perturbaties, nul verbeteringen**. De zetvolgorde van het record is
lokaal optimaal. (Dat sluit ook het losse voorstel "kolom-11-DL vrijmaken" definitief af: de
zoeker vindt hem, en hij scoort lager.)

---

## 6. Conclusie — eerlijk negatief, met de tellingen erbij

1. **De x9-correctie is bevestigd en doorgerekend.** Rij 7 weegt half zo zwaar als in
   `TRIPLET_RERANK.md`; het triplet-optimum verschuift daardoor NIET (dezelfde koploper, gat van
   +117 naar +99). Wel vervalt de daar getrokken conclusie dat wij "masker-bewust globaal
   optimaal met 99-423 punten voorsprong" zouden zijn: dat model waardeert pre-set-DL's op nul,
   wat de m-calculus weerlegt.
2. **De rij-7-eis is GEEN spelregel maar ook geen zelfmoord.** Het bezorglemma laat zien dat de
   eis het R=0-geval is en dat R>=1 wortels 79% van het lexicon openen. Maar:
   * nominaal levert de hele relaxatie hooguit **+18** op, en die pakken we met ons eigen triplet;
   * echt gebouwd en met de arbiter gemeten levert hij **-22** op, omdat het aaneengesloten
     8-blok een geneste herscoringsketen van **45 punten** genereert die een verspreide pre-set
     niet heeft (herscoringslemma);
   * en de x9 is bewijsbaar niet te verhogen (het centrum ligt vanaf zet 1).
3. **flexwerkstertje is niet gekozen ondanks maar dankzij de zak.** Gegeven geschenkcheques en
   polymelkzuurtje is het het beste van alle 26.607 toegelaten rij-7-woorden (herscorings- en
   zak-bewust), en het beste van 99.467 in de rauwe m-calculus. Zijn waarde-rang 409 op de kale
   `lsum` is een artefact van een maat die de zak en de herscoring negeert.
4. **Geen bord boven 4777 gevonden**; er is er ook geen te verwachten uit deze richting. Het
   eerlijke plafond van de hele ankerwoord-keuze op dit voetafdruk is +98, en dat vraagt
   tripletten met 4-5 dode kolomtabellen.

Wat hieruit wel volgt voor andere sporen: het **herscoringslemma** is generiek. Elke lange
pre-run op elke lijn is een geneste keten; de waarde van een ankerwoord is
`multiplier*(S+DL-bonus) + keten(w)`, en `keten` loopt in dit lexicon van 0 tot ~100 punten. De
ketencomponent hoort in elke toekomstige triplet- of topologieranker (`chain_value` in
`mg_row7.py` is herbruikbaar); hij is voor rij 0 en rij 14 nog niet berekend en daar zijn de
pre-sets groter en de multipliers drie keer zo hoog.
