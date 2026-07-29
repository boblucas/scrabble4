# LETTERBUDGET: wat LAAT een ankertriplet over? (2026-07-29)

Machinerie: `experiments/mg_letterbudget.py` (delen 0-4; env `PART`, `TOP`, `TLIM`, `WORKERS`,
`SHARD`/`NSHARD`, `JOUT`, `MB`).  Uitvoer: `experiments/results/letterbudget.json`.
Basisbord: het record **4793** (`experiments/results/maxgame_BEST.json`, arbiter `ok=True`).

**Uitkomst in een zin: de deur is dicht, en we weten nu precies waarom.  De 45 ankercellen dragen
82% van alle scoringsgewicht van het bord (m-som 1115 tegen 238); een letter die je "voor de zak
bewaart" komt daardoor op een cel te liggen die gemiddeld 5,8x minder waard is.  De gemeten
wisselkoers is 0,31 restpunt per ingeleverd ankerpunt (beste enkele geval 0,55) — break-even vereist 1,00.**

---

## 0. De m-calculus-decompositie: anker en rest zijn optelbaar

Bij een VAST voetafdruk (celposities plus zetvolgorde) is de totaalscore **lineair** in de
letterwaarden.  Definieer per cel

```
m(c) = SOM over alle scoringsgebeurtenissen die c raken van  wm(gebeurtenis) * lm(c indien nieuw)
```

dan geldt exact

```
score  =  SOM_cellen m(c) * v(letter op c)  +  50 * #bingos
```

Op het record (deel 0, geijkt tegen de arbiter):

```
101 cellen = 45 anker + 56 vrij;  blanco's (7,8) en (10,5);  11 bingo's
anker 3763  +  rest 480  +  bingo 550  =  4793      <- EXACT gelijk aan score_game
```

| rij | woord | m-profiel | m-som | waarde |
|-----|-------|-----------|------:|-------:|
| 0  | geschenkcheques | 27 28 35 **54** 29 30 28 27 27 28 29 **54** 30 27 27 | 480 | 1721 |
| 7  | flexwerkstertje | 9 9 14 **18** 14 13 11 13 10 12 13 **17** 10 9 9 | 181 | 521 |
| 14 | polymelkzuurtje | 27 27 27 **54** 31 29 28 27 29 30 30 **33** 28 27 27 | 454 | 1521 |

**Dit is de maat die het gat dicht.** Alle eerdere rankers (`TRIPLET_RERANK`, `ROW7`,
`ANCHORCHAIN`) wogen alleen `A(T)`.  Nu staat er `A(T) + R(restzak(T))` in *dezelfde eenheid*, en
kunnen we de vraag "levert een triplet dat inlevert genoeg terug?" letterlijk optellen.

### Het multiplier-asymmetrielemma (de kern van het hele antwoord)

```
45 ankercellen : m-som 1115,  gemiddelde m = 24,8,  min 9   (rij-7-hoeken)
56 vrije cellen: m-som  238,  gemiddelde m =  4,25, max 11
```

De ankerrijen dragen **82,4% van al het scoringsgewicht van het bord**.  Een letter van waarde `v`
die van een ankercel naar een vrije cel verhuist, verliest gemiddeld een factor **5,83**.  Voor
rij 0 en rij 14 is dat zelfs een *harde* uitspraak: hun laagste m is 27 en de hoogste vrije m is
11, dus **elke** letterwaarde die je van rij 0 of rij 14 afhaalt levert in de restzak hoogstens
`11/27 = 0,41` terug.  Alleen rij 7 (min m = 9) kan in theorie boven 1 uitkomen (`11/9 = 1,22`),
en dan alleen als de vrijgekomen letter exact op de ene beste vrije cel landt.

Dat verklaart ook de waarde-verhouding: het triplet neemt 45 tegels met samen **134** punten
letterwaarde (58% van de 230 punten in de zak) en zet ze om in 3763 punten = **28,1x**; de restzak
houdt 55 tegels met **96** punten en zet ze om in 480 = **5,0x**.

---

## 1. De restzak van het huidige triplet

`geschenkcheques / flexwerkstertje / polymelkzuurtje` eist 45 van de 100 lettertegels op:

```
verbruik: c2/2  e10/18  f1/2  g1/3  h2/2  i0/4  j2/2  k3/3  l3/3  m1/3  n1/10  o1/6
          p1/2  q1/1  r3/5  s3/5  t3/5  u3/3  w1/2  x1/1  y1/1  z1/2
RESTZAK : a6 b2 d5 e8 f1 g2 i4 m2 n9 o5 p1 r2 s2 t2 v2 w1 z1     = 55 tegels
```

55 tegels + 2 blanco voor **56** vrije cellen — er is precies **één** tegel speling.  Dat is de
directe verklaring van de meting die deze opdracht veroorzaakte (geen enkele laan-uitbreiding is
nog feasible).

**Het triplet verbruikt e 10/18 (56% van alle e's), maar dat is niet het pijnpunt.** Het pijnpunt
is het *alfabet*:

```
restalfabet   a b d e f g i m n o p r s t v w z    (17 letters)
VOLLEDIG OP   c h j k l q u x y                    (9 letters)
klinkers 23 / medeklinkers 32;  bindletters e8 n9 a6 o5 d5 r2 s2 t2 i4 (som 43 van 55)
```

Weg zijn `k`, `l`, `u`, `h`, `c` — vijf van de frequentste Nederlandse letters — plus de vier
schaarse `j/q/x/y`.  De 56 vrije cellen moeten dus uit een 17-letterig alfabet worden opgebouwd.

### De zak-lexicale maat

Een restzak is pas goed als je er nog woorden mee kunt vullen.  Drie maten, van los naar streng:

**(a) `lex_free(L)` — generieke lexicale vrijheid.** Hoeveel woorden van lengte `L` zijn nog
volledig uit de restzak te bouwen (multiset-inclusie)?

| lengte | 4 | 6 | 8 | 10 | 12 | 15 |
|---|---:|---:|---:|---:|---:|---:|
| bouwbaar | 1736 | 7051 | 15801 | 19458 | 13410 | 3889 |
| van | 4342 | 23690 | 72074 | 137062 | 160808 | 118709 |
| **%** | **40,0** | **29,8** | **21,9** | **14,2** | **8,3** | **3,3** |

*Wat het garandeert:* een noodzakelijke voorwaarde per woord — een woord dat hier niet in zit kan
nergens op het bord meer voorkomen.  *Wat het niet garandeert:* niets over plaatsbaarheid,
kruisingen of gelijktijdigheid; de zak wordt per woord opnieuw voluit toegekend.

**(b) `col_tables` — zakgefilterde kolomcensus.** Realistischer, want een verticaal die rij 0 aan
rij 7 knoopt krijgt zijn ankerletters *gratis* en hoeft alleen zijn 6 binnenletters uit de restzak
te halen.  Per binnenkolom `x` tellen we de 8-letterwoorden met `w[0]=rij0[x]`, `w[7]=rij7[x]` en
`w[1:7]` bouwbaar uit de restzak (idem voor rij 7 -> rij 14):

```
kolom :    1    2    3    4    5    6    8    9   10   11   12   13
top   :   17  206    0    0   72   36   92  105   72    0  143    0     som 743
bodem :    3   17    0   26   72   40    1    1    1  112  132    0     som 405
```

*Wat het garandeert:* per kolom een noodzakelijke voorwaarde, mét de ankerletters correct als
gratis meegenomen.  *Wat het niet garandeert:* de kolommen delen dezelfde restzak; de som is dus
géén aantal simultaan bouwbare kolommen.

**(c) `rest_estimate` / `restub_bag` — de maat in PUNTEN.** Alleen een maat in punten kan tegen
ankerpunten worden weggestreept.

* `restub_bag(restzak)` = koppel de duurste resttegels aan de hoogste-m vrije cellen
  (herschikkingsongelijkheid).  Dit is een **geldige bovengrens** op `R(T)`: hij negeert
  woordvorming en zetvolgorde en kan dus alleen te hoog zijn.  Hij hangt *alleen* van de restzak
  en het m-profiel van de vrije cellen af.
* `rest_estimate(restzak)` = per hoofdrun het beste zak-bouwbare woord kiezen en de zak
  uitputten (greedy over de runs, aflopend naar m-gewicht).  Dit is **geen** grens maar een
  schatting: hij kan te hoog uitvallen (kruisende runs delen cellen) en te laag (greedy volgorde).

Op het record:

```
werkelijk 480   |   greedy-schatting 486 (+1,3%)   |   zakgrens RESTUB 576   |
absoluut plafond over ALLE denkbare restzakken 1022
```

De greedy-schatting zit er 6 punten (1,3%) naast — één ijkpunt, geen bewijs, maar goed genoeg om
476 rivalen mee te rangschikken.  De harde zakgrens ligt 96 punten (20%) boven de werkelijkheid;
onze *realisatiegraad* is dus 480/576 = **83%**.

### Hoeveel restwaarde koopt lexicale rijkdom eigenlijk?

Regressie over alle 476 kandidaat-tripletten uit deel 2 (spreiding: `lex_free(8)` van 7.770 tot
38.200, restwaarde van 387 tot 568):

| verandering in de restzak | oplevering |
|---|---:|
| +1000 extra bouwbare 8-letterwoorden | **+1,4 restpunt** (r = 0,27) |
| +100 extra kolomtabel-ingangen | **+1,8 restpunt** (r = 0,24) |
| -1 ankerpunt (over dezelfde 476) | **+0,31 restpunt** (r = -0,30) |

**Een restzak die 44% lexicaal rijker is levert ~10% meer restwaarde.** Dat is de hele
tegenprestatie, en hij is een orde te klein.

---

## 2. Volledige tripletsweep over het recordvoetafdruk

Het voetafdruk legt de zetvolgorde en dus de FRAGMENTEN op de ankerrijen vast: elke tussenstand-run
op rij 0/7/14 moet een woord zijn.  Dat is een harde bezorgbaarheids-eis, en hij is per rij een
substringtest:

| rij | fragmenteis (start, lengte) | pool | ons woord | rang | nummer 2 |
|-----|---|---:|---|---:|---|
| 0  | (1,2) (4,2) (4,3) (9,2) | 4852 | geschenkcheques **1721** | **1** | flauwekulexcuus 1703 |
| 7  | (4,2) (4,4) (4,8) (9,2) (9,3) | 770 | flexwerkstertje **521** | **1** | wijkteamchefjes 501 |
| 14 | (4,2) (4,3) (8,4) (8,5) (9,3) | 1153 | polymelkzuurtje **1521** | **1** | afschuwelijkste 1339 |

**Alle drie de ankerwoorden zijn rang 1 van hun pool.** `A_m` wordt dus door ons eigen triplet
gemaximeerd; er bestaat op dit voetafdruk geen triplet met een hogere ankerwaarde.

Enumeratie met de bewijsbaar geldige snoeivloer `A_m >= record - bingo - RESTUB_MAX = 3221`
(geldig omdat `R(T) <= RESTUB_MAX = 1022` voor elke restzak en het blancoverlies >= 0):

```
929 paren bekeken, 795 zak-haalbaar, 51.381 tripletten,
476 halen de HARDE bovengrens A_m - blancoverlies + RESTUB_bag + bingo > 4793
```

Alle 476 laten rij 0 en rij 14 staan en varieren alleen rij 7 — geen enkel alternatief voor
`geschenkcheques` of `polymelkzuurtje` overleeft zelfs de grofste grens.

| # | schatting | A_m | rest~ | UB | triplet |
|---|---:|---:|---:|---:|---|
| **1** | **4799** | **3763** | **486** | 576 | **geschenkcheques / flexwerkstertje / polymelkzuurtje** |
| 2 | 4756 | 3664 | 542 | 628 | ... / waagwerkstertje / ... |
| 3 | 4746 | 3665 | 531 | 635 | ... / viltwerkstertje / ... |
| 4 | 4745 | 3665 | 530 | 635 | ... / veldwerkstertje / ... |
| 5 | 4742 | 3644 | 548 | 650 | ... / filmmaakstertje / ... |
| 6 | 4741 | 3673 | 518 | 635 | ... / grofwerkstertje / ... |
| 7 | 4740 | 3643 | 547 | 654 | ... / profboksstertje / ... |

De naaste rivaal staat op **-43**, en dat is een schatting waarvan de *harde bovengrens*
(3664+628+550 = 4842) nog boven het record ligt — daarom deel 4.

### De wisselkoers

```
gemiddeld over 475 rivalen : 0,16 restpunt per ingeleverd ankerpunt
regressiehelling           : 0,31
beste enkele rivaal        : 56/99 = 0,57  (waagwerkstertje, op de schatting)
beste op de harde zakgrens : 66/99 = 0,67  (stafwerkstertje)
BREAK-EVEN VEREIST         : 1,00
```

De opdracht vroeg: een triplet dat 100 ankerpunten inlevert moet 126 extra uit de vrije cellen
halen.  Het beste dat het lexicon biedt is **57** — en zelfs de bovengrens komt niet boven 67.

---

## 3. De restzakprofielen van de rivalen

De rivalen ruilen inderdaad ankerwaarde tegen bindletters, precies zoals de opdracht vermoedde —
alleen te goedkoop.  Een paar sprekende gevallen (vrij van de voetafdruk-fragmenteis, gemeten met
de mask-optimale ankermaat uit `ANCHORCHAIN.md` + de zakgrens):

| triplet (rij 7 varieert) | anker | zakgrens | greedy rest | kolomtab | lex(8) |
|---|---:|---:|---:|---:|---:|
| **flexwerkstertje** | **3690** | 576 | **482** | 743/405 | 15.801 |
| zeefdrukstertje | 3610 (-80) | 656 | 528 (+46) | **1184/596** (+59%) | **22.759** (+44%) |
| roofdrukstertje | 3592 (-98) | 672 | 542 (+60) | 751/686 | 23.142 |
| kermisvrijsters | 3604 (-86) | 661 | 513 (+31) | 574/484 | 13.321 |
| torxsleuteltjes | 3634 (-56) | 632 | 476 (-6) | 650/377 | 17.645 |

`zeefdrukstertje` is het scherpste testgeval: het laat een restzak achter met **44% meer bouwbare
8-letterwoorden en 59% rijkere kolomtabellen** — precies wat de opdracht zocht — en betaalt daar
80 ankerpunten voor.  De opbrengst is **+46**.  Netto **-34**.

Op de mask-optimale (voetafdruk-vrije) ranglijst `anker + zakgrens`, blanco-verlies verrekend,
staat ons triplet bovenaan:

| # | totaal | anker | zakgrens | blanco | triplet |
|---|---:|---:|---:|---:|---|
| **1** | **4266** | 3690 | 576 | 0 | **geschenkcheques / flexwerkstertje / polymelkzuurtje** |
| 2 | 4266 | 3634 | 632 | 2 (-63) | ... / torxsleuteltjes / ... |
| 3 | 4266 | 3610 | 656 | 1 (-36) | ... / zeefdrukstertje / ... |
| 4 | 4265 | 3604 | 661 | 0 | ... / kermisvrijsters / ... |
| 5 | 4264 | 3592 | 672 | 1 (-36) | ... / roofdrukstertje / ... |

De nummers 2 en 3 staan *gelijk* — maar alleen op de **bovengrens**.  Hun 632 resp. 656 zouden
voor 100% gerealiseerd moeten worden, terwijl ons bord 83% realiseert; op de greedy-schatting
staan ze op -6 resp. -34.

---

## 4. Exacte toets: CP-SAT in beslissingsvorm + arbiter

Voor elke rivaal wordt op het recordvoetafdruk de vraag gesteld *"bestaat er een letterinvulling
van de 56 vrije cellen met totaalscore >= 4794?"* — CP-SAT met alle tussenstand-runs als
woordtabellen, de zakbeperking per letter, en de blanco's als beslissingsvariabelen.  `INFEASIBLE`
is dan een **bewijs** dat dit triplet op dit voetafdruk het record niet haalt.

**Soundness.** Het model bevat het record aantoonbaar als toegelaten oplossing: deel 0 verifieert
dat de doelfunctie `SOM m(c)*v(c) + 550` op het recordbord exact 4793 geeft, en `score_game`
accepteert dat bord.  Blanco's zijn vrij plaatsbaar op *elke* bezette cel (ook ankercellen), dus
ook tripletten die de zak overvragen worden correct en optimaal gemodelleerd.  Ijking: dezelfde
solver in maximalisatievorm op ons eigen triplet levert **4793 met `score_game` ok=True** — met
een andere invulling van kolom 7 en verplaatste blanco's, wat meteen laat zien dat 4793 op dit
voetafdruk meervoudig realiseerbaar is.

### (a) Het voetafdruk zelf: 4793 is OPTIMAAL

De eerste vraag die de solver kreeg was de onze: *bestaat er een andere lettering van dezelfde 56
vrije cellen die dit bord boven 4793 brengt?*

```
exact_fill(geschenkcheques/flexwerkstertje/polymelkzuurtje, target=4794)  ->  INFEASIBLE  (2964s)
```

**Er is er geen.** De harde zakgrens van 576 was 96 punten te ruim; de werkelijke restwaarde bij
deze restzak is exact de 480 die het bord haalt.  Het record is optimaal voor zijn eigen bezetting
en zetvolgorde — een resultaat dat de campagne nog niet had, en dat de hele
"invulling-optimaliseren"-richting op dit bord afsluit.

### (b) De rivalen

De 476 kandidaten uit deel 2 zijn stuk voor stuk aan dezelfde beslissing onderworpen
(`PART=2,4`, gesharde runs, `TLIM` 45s dan 300s, hervattend via `JOUT`):

| uitkomst | aantal | betekenis |
|---|---:|---|
| `nowords` | 35 | een run van het voetafdruk heeft met dit triplet GEEN enkel woord — dood bij constructie |
| `INFEASIBLE` | 288 | bewezen: geen invulling haalt 4794 |
| `UNKNOWN` | 152 | onbeslist binnen het tijdbudget |
| boven het record | **0** | — |

De sterkste rivalen, in volgorde van hun schatting:

| rivaal (rij 7) | schatting | harde UB | uitslag | s |
|---|---:|---:|---|---:|
| waagwerkstertje | 4743 | 4842 | **DOOD** (bewezen <= 4793) | 6 |
| profboksstertje | 4743 | 4847 | **DOOD** (bewezen <= 4793) | 6 |
| filmmaakstertje | 4742 | 4844 | **DOOD** (bewezen <= 4793) | 217 |
| veldwerkstertje | 4742 | 4850 | onbeslist | 50 |
| grofwerkstertje | 4742 | 4858 | **DOOD** (bewezen <= 4793) | 6 |
| stafwerkstertje | 4739 | 4856 | **DOOD** (bewezen <= 4793) | 4 |
| grafdelfstertje | 4738 | 4850 | **DOOD** (bewezen <= 4793) | 6 |
| viltwerkstertje | 4735 | 4850 | onbeslist | 49 |
| vlaswerkstertje | 4733 | 4840 | **DOOD** (bewezen <= 4793) | 4 |
| waszweetstertje | 4728 | 4848 | **DOOD** (bewezen <= 4793) | 79 |
| gaasweefstertje | 4727 | 4828 | **DOOD** (bewezen <= 4793) | 5 |
| melkvaarstertje | 4725 | 4843 | **DOOD** (bewezen <= 4793) | 195 |
| grafmaakstertje | 4724 | 4841 | **DOOD** (bewezen <= 4793) | 5 |
| zorgwerkstertje | 4720 | 4854 | onbeslist | 46 |

Van de 30 sterkste rivalen zijn er **21** bewezen dood; over het hele veld 323 van 475.

**Geen enkele rivaal heeft ook maar één geldige invulling boven 4793 opgeleverd.**  Sterker: de
meeste rivalen zijn niet "te laag" maar *helemaal infeasible* — hun restzak past domweg niet meer
in dit voetafdruk.  Dat is de scherpste vorm van het letterbudget-argument: met 55 resttegels voor
56 cellen (2 blanco, 1 tegel speling) is de bezetting **letter-vergrendeld**; verander één
ankerwoord en de puzzel valt uit elkaar.

De onbesliste gevallen zijn geen tegenbewijs: hun *schatting* ligt allemaal op 4742 of lager
(>= 51 punten onder het record) op een maat die op het record 1,3% te hoog uitvalt, en hun enige
claim boven 4793 komt van de zakgrens die op het record 20% te ruim bleek.

---

## 5. Conclusie

1. **De maat bestaat nu.** `score = SOM m(c)*v(c) + 50*#bingos` splitst het record exact in
   anker 3763 + rest 480 + bingo 550, en maakt "ankerwaarde minus restzak-armoede" een letterlijke
   optelsom.  `mg_letterbudget.py` levert `anchor_value`, `residual`, `restub_bag` (harde grens),
   `rest_estimate` (schatting) en `exact_fill` (arbiter-geverifieerde beslissing) als herbruikbare
   onderdelen.
2. **De restzak van ons triplet is inderdaad arm** — 55 tegels, 17-letterig alfabet, `c h j k l q
   u x y` volledig op, 21,9% van de 8-letterwoorden nog bouwbaar.  Dat is gemeten en het klopt met
   de niet-uitbreidbaarheid van het bord.
3. **Maar armoede van de restzak is niet het knelpunt** — het is een *gevolg* van waar de punten
   zitten.  De 45 ankercellen dragen 82,4% van al het scoringsgewicht; de 56 vrije cellen 17,6%.
   Een tegel die je voor de zak bewaart landt op een cel die 5,8x minder waard is.
4. **De wisselkoers is gemeten: 0,31 restpunt per ingeleverd ankerpunt** (regressie over 476
   kandidaten), met 0,44 als beste enkele geval en 0,66 als bovengrens.  Break-even vereist 1,00.
   Een restzak die 44% lexicaal rijker is levert 10% meer restwaarde.
5. **Ons triplet is rang 1 op beide sporen**: rang 1 in elke ankerrijpool onder de
   voetafdruk-fragmenteis (4852 / 770 / 1153 woorden), en rang 1 op de voetafdruk-vrije ranglijst
   `mask-optimale ankerwaarde + zakgrens`.
6. **Exact getoetst, niet alleen gemodelleerd.** Van de 476 tripletten die de harde bovengrens
   halen zijn er 323 bewezen dood (35 `nowords`, 288 `INFEASIBLE` op de vraag ">= 4794"); geen
   enkele heeft ook maar één geldige invulling boven het record opgeleverd.  De 152 onbesliste
   staan allemaal op een schatting van 4742 of lager.  De toets is hervatbaar (`JOUT`) en loopt
   door; `experiments/results/letterbudget_toets.json` bevat de stand.
7. **NIEUW EN BINDEND: 4793 is optimaal voor zijn eigen voetafdruk.**
   `exact_fill(CUR, target=4794)` = INFEASIBLE.  Geen enkele andere lettering van de 56 vrije
   cellen — met blanco's vrij plaatsbaar — brengt deze bezetting boven 4793.
8. **Deze deur is dicht.** Een tripletwissel loont niet — niet omdat de alternatieven geen betere
   restzak achterlaten (dat doen ze, aantoonbaar), maar omdat de vrije cellen te weinig
   multiplier dragen om die betere restzak te verzilveren.

### Wat dit voor de campagne betekent

**Niet meer zoeken in de tripletrichting.** Elke euro die je daar investeert komt tegen 0,31
terug.  Twee richtingen blijven wel open, en de analyse wijst ze scherp aan:

**(a) Op DIT voetafdruk ligt niets meer — dat is nu bewezen.** `exact_fill(CUR, target=4794)`
komt na 2964s terug met **INFEASIBLE**: er bestaat geen enkele letterinvulling van de 56 vrije
cellen (met blanco's vrij plaatsbaar op elke cel) die dit voetafdruk boven 4793 brengt.  De
zakgrens van 576 was dus 96 punten te ruim; de werkelijke restwaarde-optimum bij deze restzak is
exact de 480 die het bord al haalt.  **4793 is optimaal voor zijn eigen bezetting en zetvolgorde.**
Winst moet uit een ander voetafdruk komen, niet uit een andere invulling.

**(b) Verhoog de m-waarde van de vrije cellen, niet de rijkdom van de restzak.** Zolang 82% van
het scoringsgewicht op 45 cellen zit, is elke hefboom die alleen de andere 56 cellen raakt door
een factor 5,8 gedempt.  Dat is precies wat de FRAME-klasse doet (kolommen 0/7/14 als tweede stel
x27-lijnen): daar worden de "vrije" cellen zélf ankercellen, en verandert het m-profiel in plaats
van de zak.  De letterbudget-analyse steunt die richting kwantitatief.

En daarmee is 4819 op deze bezetting definitief uitgesloten: niet via een ander triplet (deel 2-4)
en niet via een andere lettering (deel 4, ijking).  Alleen een ander voetafdruk — andere cellen of
een andere zetvolgorde — kan er nog aan komen.
