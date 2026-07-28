# ZETVOLGORDE-BEWIJS bij VASTE BEZETTING

Onderwerp: het record `experiments/results/maxgame_BEST.json` — 101 bezette cellen, score **4778**.
De bezetting (welke cellen bezet zijn) staat vast. De vraag: **bestaat er een andere legale
zetvolgorde die bij dezelfde bezetting hoger uitkomt?**

Gereedschap: `experiments/mg_scheduleproof.py`.

---

## 1. Karakterisering van de zoekruimte

### 1.1 De bezetting bestaat uit 14 lijnen

Een *lijn* = een maximale aaneengesloten run van bezette cellen (lengte ≥ 2) in het EINDbord.
Voor deze bezetting zijn dat er precies 14:

| lijn | lengte | start | woord | ankerletters |
|---|---|---|---|---|
| H | 15 | (0,0)  | geschenkcheques | 15 (vast) |
| H |  3 | (10,2) | aft | 0 |
| H | 13 | (2,4)  | overzwevenden | 0 |
| H | 15 | (0,7)  | flexwerkstertje | 15 (vast) |
| H |  2 | (4,8)  | in | 0 |
| H |  2 | (10,8) | na | 0 |
| H | 15 | (0,14) | polymelkzuurtje | 15 (vast) |
| V | 11 | (2,0)  | smarotsende | 2 |
| V |  9 | (5,0)  | eenorigen | 2 |
| V |  9 | (10,0) | enabelden | 2 |
| V |  8 | (12,0) | uitademt | 2 |
| V |  7 | (7,4)  | waakton | 1 |
| V |  8 | (4,7)  | windboom | 2 |
| V |  8 | (11,7) | raspiger | 2 |

Som van de lengtes = 125; er zijn 101 cellen, dus precies 24 cellen liggen op twee lijnen
(een H- en een V-lijn), de overige 77 op één.

### 1.2 Elke zet ligt binnen één lijn

Een zet legt nieuwe tegels op één rij of kolom en de *span* tussen de buitenste nieuwe tegels
moet volledig gevuld zijn. Aan het eind zijn al die cellen dus bezet, en aaneengesloten, dus
**de hele zet ligt binnen één maximale eindrun**. Gevolg: een zet met k ≥ 2 tegels is een groep
binnen precies één lijn (zijn *hoofdlijn*); in elke kruisende lijn levert elk van zijn cellen
een losse (singleton-)groep. Een zet van 1 tegel is een singleton in beide lijnen van die cel.

Concreet: een zet vanuit toestand S op lijn L wordt volledig bepaald door een interval [a,e] op
L met a en e nog leeg; de nieuwe tegels zijn `[a..e] \ S`. Meer keuzes zijn er niet.

### 1.3 DE DECOMPOSITIE-IDENTITEIT

> **Stelling.** Voor elk legaal spel bij deze bezetting geldt
> ```
>       score  =  SOM over de 14 lijnen L van  g_L(geschiedenis van L)
> ```
> waarbij de *geschiedenis* van L de geordende opdeling van L's cellen in groepen is, en
> ```
>       g_L = (alle woordscores van gebeurtenissen op L) + 50 * (aantal groepen van precies 7 in L).
> ```

*Argument.* (a) Elke gescoorde woordrun (`event`) is een aaneengesloten run in één richting en
dus een deelinterval van precies één maximale eindrun L. De score van die run —
`(product van woordmultipliers van de NIEUWE cellen) × (som van letterwaarden, met
lettermultiplier alleen op de nieuwe cellen)` — hangt uitsluitend af van welke cellen van L al
lagen, welke nieuw zijn, en van L's letters. Dus van L's geschiedenis alleen.
(b) Een bingo-zet legt precies 7 tegels; die liggen alle in zijn hoofdlijn, dus telt de bingo
bij precies één lijn mee. Geen dubbeltelling, niets buiten de som. ∎

De identiteit wordt bij elke run numeriek gecontroleerd: `replay()` speelt het record na via de
lijndecompositie en vergelijkt met de arbiter `MG.score_game` → **4778 = 4778**.

Bijdragen van het record per lijn:

```
H15 (0,0)  geschenkcheques  1743     V11 (2,0)  smarotsende   145
H3  (10,2) aft                19     V9  (5,0)  eenorigen      77
H13 (2,4)  overzwevenden     267     V9  (10,0) enabelden      71
H15 (0,7)  flexwerkstertje   536     V8  (12,0) uitademt      100
H2  (4,8)  in                  2     V7  (7,4)  waakton        74
H2  (10,8) na                  2     V8  (4,7)  windboom       84
H15 (0,14) polymelkzuurtje  1561     V8  (11,7) raspiger       97   -> totaal 4778
```

### 1.4 Hoe groot is de ruimte?

Per lijn is de toestand de deelverzameling gelegde cellen (2^n, n ≤ 15). Niet elke deelverzameling
is bereikbaar: **elk maximaal blok van lengte ≥ 2 moet op elk moment een woord zijn.** Dat snijdt
de drie ankerrijen hard weg — van de 105 deelintervallen zijn er maar 17 (geschenkcheques),
18 (flexwerkstertje) resp. 22 (polymelkzuurtje) een woord:

```
geschenkcheques : ge ges geschenk geschenkcheque geschenkcheques es schen schenk he hen en enk
                  cheque cheques he que es
flexwerkstertje : flex flexwerk flexwerkster flexwerkstertje lex ex we werk werkster werkstertje
                  er ks kst ster te ter er je
polymelkzuurtje : po pol poly polymelkzuur polymelkzuurtje lyme me mel melk melkzuur melkzuurtje
                  el elk zuur zuurt zuurtje uur uurt uurtje urt urtje je
```

Daardoor zijn er van de 32768 deelverzamelingen maar 6218 / 6682 / 7000 woord-consistent.

Toch is de ruimte astronomisch. `MODE=count` telt exact het aantal legale *lijn-geschiedenissen*
per lijn (padtelling in dezelfde DP):

```
H15 geschenkcheques  1.151.884.557    V11 smarotsende  2.345.582
H3  aft                          9    V9  eenorigen       73.894
H13 overzwevenden      959.728.754    V9  enabelden      286.516
H15 flexwerkstertje  3.885.236.470    V8  uitademt        19.718
H2  in                           3    V7  waakton         2.492
H2  na                           3    V8  windboom        18.213
H15 polymelkzuurtje 22.737.680.062    V8  raspiger        27.164
                                   product = 9,55 x 10^72
```

Het werkelijke aantal schema's is nog gróter: die 9,55·10^72 lijn-geschiedenissen mogen ook nog
onderling verweven worden tot één globale volgorde. Opsommen is uitgesloten — vandaar de grens
hieronder. (De B&B bezoekt er uiteindelijk **751**.)

---

## 2. De gebruikte bovengrens en waarom hij toelaatbaar is

Per lijn L is een exacte DP over de 2^n deelverzamelingen mogelijk. Definieer

```
   suffix_L(S) = maximale toekomstige bijdrage van lijn L, over alle legale voortzettingen
                 van lijntoestand S tot de volle lijn (-oneindig als er geen is).
```

Berekening: achterwaartse DP, `suffix_L(vol)=0`, `suffix_L(S) = max over groepen g van
(inc(S,g) + suffix_L(S|g))`. Kosten: 2^n × O(n²), dus milliseconden.

> **Toelaatbaarheid.** Neem een willekeurige globale toestand met lijntoestanden (S_1..S_14) en
> een willekeurige legale voortzetting. Die voortzetting projecteert per lijn op een legale
> lijn-voortzetting van S_L naar vol. Volgens §1.3 is de toekomstige score de som van de
> toekomstige lijnbijdragen, en elk daarvan is ≤ suffix_L(S_L). Dus
> ```
>    toekomstige score  <=  SOM_L suffix_L(S_L).
> ```
> De grens negeert alleen koppelingen (globale volgorde-consistentie, aanraakregel, en het feit
> dat een cel in hoogstens één van zijn twee lijnen in een meer-tegelgroep kan zitten). Weglaten
> van beperkingen kan de grens alleen verhogen — hij blijft dus een geldige bovengrens. ∎

**Wortelwaarde.** `SOM_L suffix_L(0) = 5225`. Met één extra harde regel — de zet die het centrum
(7,7) legt is globaal zet 1, dus in de twee lijnen door (7,7) moet de groep met (7,7) de EERSTE
groep zijn — zakt hij naar **4831**. Die daling zit volledig in rij 7: het lijn-optimum 955 legt
`flexwerkstertje` af met een slotzet die de centrale ×2 nog eens meepakt, en dat mag niet; met de
centrumregel blijft 561 over.

Speling tussen wortelgrens en record: **4831 − 4778 = 53 punten**, verdeeld over drie lijnen
(rij 7: +25, kolom (5,0): +10, kolom (10,0): +18). Alle andere elf lijnen zitten in het record al
exact op hun lijn-maximum. Zó strak is de grens dat de branch-and-bound eronder in een fractie van
een seconde sluit.

---

## 3. De branch-and-bound

`Search.run()` is een exacte DP/B&B over **alle** legale zetvolgordes. Lagen zijn genummerd naar
het aantal gelegde cellen (monotoon stijgend), zodat elke bordtoestand in precies één laag valt en
`best[toestand] = maximale tot dan toe behaalde score` welgedefinieerd is.

Hard afgedwongen, precies zoals de arbiter ze kent:
* zet 1 bevat het centrum (7,7);
* elke volgende zet raakt een reeds gelegde tegel;
* ten hoogste 7 tegels per zet (bingo = precies 7, +50);
* alle nieuwe tegels op één lijn, span volledig gevuld;
* **elke gevormde run ≥ 2 — hoofdwoord én alle kruiswoorden — moet in `dutch2026` staan.**

Gesnoeid wordt op `acc + SOM_L suffix_L(S_L) <= huidige beste`.

### Validatie van de motor

1. **Identiteit.** Bij elke start: `MG.score_game` = 4778 en lijndecompositie = 4778.
2. **Arbiter-audit.** `MODE=audit N=600`: 600 willekeurig getrokken *volledige* schema's uit de
   zetgenerator; alle 600 worden door `MG.score_game` geaccepteerd (`ok=True`) en scoren exact
   wat de zoeker berekent. 0 afwijkingen.
3. **Vindt-het-record-test.** Met ondergrens 4777 (in plaats van 4778) moet de zoeker het optimum
   zelf terugvinden: hij doet dat — 61.268 toestanden, 8,5 s, en levert een getuige van **32
   zetten die de arbiter op 4778 zet** (het record zelf heeft er 33; er zijn dus meerdere
   4778-schema's). Dat bewijst dat de zoektocht diep genoeg gaat en niets legaals wegsnoeit.
4. **Volledigheid van de zetgenerator.** Zie §1.2: een meer-tegelzet is noodzakelijk
   `[a..e] \ S` binnen één lijn met a,e nieuw — precies wat tak (a) opsomt; een-tegelzetten zijn
   tak (b). De generator staat bovendien een openingszet van 1 tegel toe (in echte regels niet
   legaal): dat verruimt de zoekruimte en kan de bovengrens alleen maar verhogen.

### Resultaat

```
$ .venv/bin/python experiments/mg_scheduleproof.py
arbiter MG.score_game = 4778 (ok=True) | lijn-decompositie = 4778 | identiek: True
PER-LIJN-BOVENGRENS: vrij 5225, met centrumregel 4831
  ... bezochte toestanden: 751 (0,2 s)
B&B klaar=True beste score 4778
BEWEZEN: bij deze bezetting EN deze letters haalt GEEN ENKELE legale zetvolgorde meer dan 4778.
```

> ### STELLING 1 (bewezen, uitputtend)
> Bij de bezetting én de letters van `maxgame_BEST.json` bestaat er **geen** legale zetvolgorde
> met score > 4778. De 4778 van het record is optimaal over alle zetschema's.

Dit is een volledige opsomming (met gezonde snoei), geen heuristiek: elke tak die niet is
afgelopen, is aantoonbaar door de toelaatbare grens uitgesloten.

---

## 4. Wat er buiten Stelling 1 valt: vrije letters

De opdracht laat de 56 niet-anker-cellen vrij. Stelling 1 houdt de letters vast. Voor de vrije
variant geldt de decompositie onverkort, en levert ze meteen een deelresultaat:

> ### STELLING 2 (bewezen)
> De drie ankerrijen 0/7/14 dragen samen **hoogstens 3865** bij (1743 + 561 + 1561), ongeacht wat
> er met de 56 vrije letters of met het zetschema gebeurt. Hun letters liggen immers vast, dus
> g_L hangt daar alleen nog van de lijn-geschiedenis af, en de per-lijn-DP is exact (de 561 van
> rij 7 gebruikt de centrumregel).
> Gevolg: elke score bij deze bezetting is ≤ 3865 + SOM over de 11 vrije lijnen van g_L.

Het budget voor de elf vrije lijnen is dus 4778 − 3865 = 913 (het record gebruikt er 938 bij een
ankerbijdrage van 3840). Per vrije lijn is `U_L^vrij = max over alle woorden W van lengte n die op
de ankerletters passen, van max_h g_L(h,W)` exact uit te rekenen (`MODE=free`); die getallen staan
in §5. Ze sommeren ruim boven 913, dus **een bewijs voor de vrije-letter-klasse volgt hier niet
uit** — de per-lijn-grenzen zijn daarvoor te los, omdat ze de zak (100 lettertegels + 2 blanco's)
en de gedeelde letters op de 24 kruispunten negeren.

§5 sluit die klasse alsnog af met een zak- en kruispuntbewust CP-SAT-model: **STELLING 3, score
<= 4847 bij deze bezetting over zetvolgorde EN herlettering samen.**

Expliciet NIET afgedekt:
* **andere bezettingen** — dat is een andere vraag;
* de 69 punten tussen 4778 en de vrije-letter-grens 4847: daarvoor zou de koppeling tussen de
  lijnen (globale volgorde, aanraakregel, cel-in-hoogstens-een-meer-tegelzet) ook in het
  vrije-letter-model moeten zitten, zoals ze in Stelling 1 wel zit.

---

## 5. Vrije-letter-maxima per lijn (exact per lijn, koppeling genegeerd)

`MODE=free LI=<lijn>` somt alle kandidaat-woorden voor een lijn op en draait per woord de exacte
lijn-DP. Resultaten (`rec` = maximum met de huidige letters):

| lijn | woord in record | rec | U^vrij | best woord |
|---|---|---|---|---|
| H3 (10,2)  | aft | 19 | 34 | wax |
| H2 (4,8)   | in | 2 | 9 | uw |
| H2 (10,8)  | na | 2 | 9 | uw |
| V11 (2,0)  | smarotsende | 145 | 221 | skysurfende |
| V9 (5,0)   | eenorigen | 87 | 143 | effluxjes |
| V9 (10,0)  | enabelden | 89 | 141 | encrypten |
| V8 (12,0)  | uitademt | 100 | 141 | upcyclet |
| V7 (7,4)   | waakton | 74 | 104 | luckyst |
| V8 (4,7)   | windboom | 84 | 101 | weergalm |
| V8 (11,7)  | raspiger | 97 | 133 | recycler |
| H13 (2,4)  | overzwevenden | 267 | 328 | (153.033 kandidaten) |

Som = **1364**, ruim boven het budget van 913: per-lijn-grenzen alleen sluiten de vrije-letter-klasse
niet. Ze zijn ook onderling onverenigbaar — ze eisen allemaal dezelfde schaarse hoogwaardige
tegels (de zak heeft y×1, x×1, q×1, c×2, w×2, f×2, u×3), en de 24 kruispuntcellen moeten in beide
lijnen dezelfde letter dragen.

### 5.1 Zak- en kruispuntbewuste grens (CP-SAT)

`MODE=freebound` giet die koppeling wél in één model: per vrije lijn kiest CP-SAT een woord via
een tabelbeperking op de lettervariabelen van die lijn (met U_L(W) als objectiefkolom), de 24
gedeelde cellen delen één lettervariabele, en het totale lettergebruik over alle 101 cellen moet
in de zak passen op ten hoogste 2 blanco's na (die blanco's krijgen in het model tóch hun volle
waarde — overschatting, dus gezond).

CP-SAT sluit dit model **OPTIMAAL**: de elf vrije lijnen halen samen hoogstens **982** (de
letters van het record halen daar 966; het record zelf 938). De losse per-lijn-optima sommeerden
tot 1364 — de zak en de kruispunten kosten dus 382 van die 1364.

> ### STELLING 3 (bewezen)
> Bij deze bezetting geldt, over **alle** legale zetvolgordes **én alle** herletteringen van de 56
> vrije cellen (ankerletters vast, zak = 100 lettertegels + 2 blanco's, alle gevormde runs
> woorden):
> ```
>        score  <=  3865 (ankerrijen)  +  982 (vrije lijnen)  =  4847.
> ```
> Het record staat op 4778; er ligt bij deze bezetting dus **hooguit 69 punten** headroom, over
> zetvolgorde én herlettering samen.

Gebruikte verruimingen (alle in de veilige richting, dus de grens blijft geldig): de per-lijn-optima
worden onafhankelijk gekozen — dat laat de globale volgorde-consistentie, de aanraakregel en de
regel *een cel kan in hoogstens één van zijn twee lijnen in een meer-tegelzet zitten* vallen; en
blanco's krijgen in het model hun volle letterwaarde. Op de vaste-letter-instantie was precies die
weggelaten koppeling goed voor de laatste 53 punten (4831 → 4778); als ze hier vergelijkbaar bijt,
is de echte vrije-letter-top dicht bij het record.

---

## 6. Bestanden en gebruik

```
experiments/mg_scheduleproof.py            motor: decompositie, per-lijn-DP, staartgrens, B&B,
                                           vrije-letter-DP en zakbewuste CP-SAT-grens
experiments/SCHEDULEPROOF.md               dit document
experiments/results/scheduleproof/L*.json  per vrije lijn: alle kandidaat-woorden met hun exacte
                                           lijn-bovengrens U_L(W)  (11 lijnen, 157.807 woorden)

# hoofdbewijs (0,2 s)  -> STELLING 1
.venv/bin/python experiments/mg_scheduleproof.py
# validatie: moet het record zelf terugvinden (getuige 32 zetten, arbiter 4778)
LB=4777 .venv/bin/python experiments/mg_scheduleproof.py
# arbiter-audit van de zetgenerator
MODE=audit N=600 .venv/bin/python experiments/mg_scheduleproof.py
# omvang van de zoekruimte
MODE=count .venv/bin/python experiments/mg_scheduleproof.py
# vrije-letter-tabel van één lijn (LI = index uit de lijnlijst; SHARD/NSHARD voor parallel)
MODE=free LI=2 SHARD=0 NSHARD=16 OUT=/tmp/L2_0.json .venv/bin/python experiments/mg_scheduleproof.py
# zak- en kruispuntbewuste vrije-letter-grens (~5 min)  -> STELLING 3
MODE=freebound VALDIR=experiments/results/scheduleproof .venv/bin/python experiments/mg_scheduleproof.py
```

`WOUT=<pad>` schrijft een gevonden beter schema weg (alleen als de arbiter > 4778 bevestigt).
`maxgame_BEST.json` wordt nooit overschreven.
