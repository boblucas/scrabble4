# KLASSEGRENS voor triplet + masker

Vervolg op `experiments/SCHEDULEPROOF.md`. Daar werd één bezetting afgesloten; hier gaat de
decompositie-identiteit een laag hoger, naar de hele geometrieklasse bij het triplet
**geschenkcheques / flexwerkstertje / polymelkzuurtje** op rijen 0/7/14.

Gereedschap: `experiments/mg_classbound.py`. Referentiepunten: eigen record **4778**, bewezen
grens voor de huidige bezetting **4847**, bobs externe referentie **4819**.

---

## 0. De identiteit op klasseniveau

Elke gescoorde run ligt in precies één rij of kolom, en elke bingo hoort bij precies één
hoofdlijn. Dus voor élk legaal spel, bij élke bezetting:

```
   score = SOM over de 15 rijen van (bijdrage van die rij)
         + SOM over de 15 kolommen van (bijdrage van die kolom)
```

Rijen 0/7/14 dragen het triplet en hebben daarmee **vaste letters**. Voor alle andere lijnen
varieert hier ook de bezetting van de lijn zelf. Per lijn is het maximum een DP over
deelverzamelingen (zelfde motor als in SCHEDULEPROOF), nu met een extra buitenlaag over de
bezetting van de lijn en over het woord op elke run.

---

## 1. STELLING A (bewezen) — de ankerrijen zijn hard gemaximeerd op 3865

```
   rij  0 'geschenkcheques' : 1743
   rij  7 'flexwerkstertje' :  561   (met de centrumregel; zonder die regel 955)
   rij 14 'polymelkzuurtje' : 1561
   ------------------------------------
   ANKERRIJ-PLAFOND         : 3865
```

Dit is een **exact maximum over alle bezettingen, alle maskers, alle vrije letters en alle
zetvolgordes**: de letters van die rijen liggen vast, de rijen zijn altijd volledig bezet, en de
DP maximeert over álle legale geschiedenissen van die 15 cellen.

> Gevolg: de door de coördinator genoemde extra lemma's zijn hier **overbodig, niet genegeerd**.
> Het eiland-lemma, het fragment-lemma en de x27-maskerstructuur beperken allemaal de
> verzameling toegestane geschiedenissen van een ankerrij. Wij maximeren over de *volledige*
> verzameling; elke deelverzameling geeft dus hoogstens hetzelfde. 3865 is een bovengrens die
> geen van die lemma's nodig heeft en die geen enkel masker kan overschrijden.

Reproduceren: `MODE=anchor .venv/bin/python experiments/mg_classbound.py`
(onafhankelijke implementatie; reproduceert 1743/561/1561 uit SCHEDULEPROOF exact.)

### Rekenkundig gevolg voor 4819

```
   record          : ankerrijen 3840  +  overige 27 lijnen 938  = 4778
   ankerrijplafond : 3865  -> op de ankerrijen is nog +25 te halen, meer niet
   voor 4819       : de 27 niet-ankerlijnen moeten >= 954 leveren   (nu 938, dus +16)
   idem, als de ankerrijen op 3840 blijven:            >= 979      (nu 938, dus +41)
```

Het hele gat naar bobs 4819 is dus **+41 punten in de niet-ankerlijnen** (of +16 als de
ankerrijen ook nog hun laatste 25 pakken).

---

## 2. STELLING B (bewezen) — deze route kán het triplet niet doden

> Elke klassegrens die met deze methode wordt berekend, is **>= 4847**, en dus **> 4819**.

*Bewijs.* De geometrieklasse bevat onze eigen bezetting. Fixeer in het klassemodel de bezetting
op die van `maxgame_BEST.json`; dan reduceert het klassemodel tot precies het model van
Stelling 3 in SCHEDULEPROOF (per-lijn-maxima + zak + kruispunten), waarvan het optimum met
CP-SAT **OPTIMAAL = 4847** is bewezen. Een maximum over een grotere verzameling is niet kleiner.
Dus klassegrens >= 4847 > 4819. ∎

**Antwoord op de beslissende vraag (3): NEE.** De klassegrens komt niet onder 4819, en dat is
bewezen in plaats van vermoed — er is geen versie van deze methode die hem er wel onder krijgt.
Het triplet wordt langs deze weg dus **niet** weerlegd, en de campagne is niet beslist.
Daarmee is punt 3 in de "zo nee"-tak beland: het verschil per lijn wijst de zoekrichting aan.

---

## 3. De FRAME-vraag, beslist

De 9 kruispunten (kolom 0/7/14 x rij 0/7/14) dragen alle drie een TWS. Ze kunnen maar één keer
een woordmultiplier opleveren: een cel telt alleen als ×3 in de zet waarin hij **nieuw** is, en
die zet ligt op één lijn. Dus **of** de rij-final pakt de ×3, **of** de kolomzet. Beide corners
zijn exact doorgerekend (`SINGLE=0,7,14` dwingt af dat de betreffende lijn die cellen alleen als
losse tegel mag leggen).

| scenario | ankerrijen | kolommen 0/7/14 | samen |
|---|---|---|---|
| **A — de rij-finals pakken de ×3** | 3865 | 228 + 224 + 314 = **766** | **4631** |
| **B — de kolomzetten pakken de ×3** (zuivere FRAME) | 787 | 493 + 508 + 1421 = 2422 | 3209 |

> **Scenario A wint met 1422 punten.** De zuivere FRAME-klasse — kolombingo's die zelf de TWS op
> rijen 0/7/14 aanslaan — is voor dít triplet aantoonbaar slechter: geschenkcheques en
> polymelkzuurtje als ×27-rij-final zijn samen meer waard dan welk kolomwoord ook.

Wat wél werkt is de hybride die in het geheugen staat als *"kolomwoorden ×3-gecompleteerd door
rij-finals"*: de rij-final legt de kruispuntcel, en in de kolom is dat één losse nieuwe tegel op
een TWS, dus het hele kolomwoord scoort ×3. Dat mechanisme zit volledig in scenario A en is daar
goed voor **766** op de drie framekolommen — waar ons bord er **74** haalt (alleen kolom 7).

---

## 4. Diagnose: waar zit de ruimte (de "zo nee"-tak)

Per lijn het plafond bij **exact dezelfde tegelinzet k als het record**, in scenario A
(`MODE=lines SINGLE=0,7,14`). Elk plafond is een *gecertificeerde ondergrens op het lijnplafond*:
het hoort bij een echt woord en een exact doorgerekende geschiedenis.

| kolom | k | record | plafond(k) | ruimte |   | rij | k | record | plafond(k) | ruimte |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | +0 |  | 1 | 4 | 0 | 56 | **+56** |
| 1 | 0 | 0 | 0 | +0 |  | 2 | 5 | 19 | 84 | **+65** |
| 2 | 9 | 145 | 184 | +39 |  | 3 | 4 | 0 | 68 | **+68** |
| 3 | 1 | 0 | 17 | +17 |  | 4 | 13 | 267 | 317 | +50 |
| 4 | 7 | 84 | 170 | **+86** |  | 5 | 5 | 0 | 76 | **+76** |
| 5 | 7 | 77 | 146 | +69 |  | 6 | 5 | 0 | 69 | **+69** |
| 6 | 1 | 0 | 8 | +8 |  | 8 | 6 | 4 | 94 | **+90** |
| 7 | 6 | 74 | 136 | +62 |  | 9 | 4 | 0 | 55 | +55 |
| 8 | 1 | 0 | 8 | +8 |  | 10 | 4 | 0 | 56 | +56 |
| 9 | 1 | 0 | 16 | +16 |  | 11 | 2 | 0 | 18 | +18 |
| 10 | 7 | 71 | 182 | **+111** |  | 12 | 2 | 0 | 18 | +18 |
| 11 | 8 | 97 | 191 | **+94** |  | 13 | 2 | 0 | 25 | +25 |
| 12 | 6 | 100 | 124 | +24 |  | | | | | |
| 13 | 1 | 0 | 18 | +18 |  | | | | | |
| 14 | 1 | 0 | 27 | +27 |  | | | | | |

```
kolommen        : record  648  ->  1227   (+579)
niet-ankerrijen : record  290  ->   936   (+646)
R (samen)       : record  938  ->  2163   bij dezelfde tegelverdeling
nodig voor 4819 :              >=  979
```

Losse tegelknapzak over de lijnen (`MODE=knap`, 56 vrije tegels per richting):
kolommen 1481, rijen 1549, indicatie max R **3030**.

**Lezing.** Er is geen enkele aanwijzing dat dit triplet op is. Er is +41 nodig; de per-lijn-
diagnose laat honderden punten liggen, en dat zonder één extra tegel te vragen. De concrete
zoekrichting, op volgorde van omvang:
1. **De niet-ankerrijen 1/3/5/6/8/9/10 doen nu vrijwel niets** (0 punten bij 4-6 tegels elk),
   terwijl elk van hen bij diezelfde inzet 55-94 kan. Dat is de grootste post: +646.
2. **Kolommen 10, 11, 4, 5, 7** dragen 71-100 waar 136-191 kan bij dezelfde inzet: +422.
3. **De framekolommen 0/1/13/14 staan leeg** (k = 0/0/1/1). Kolom 14 kan met 12 tegels tot 314
   in scenario A. Dat is de structurele post die het huidige bord volledig mist — maar dan als
   ×3-voltooiing door de rij-final, niet als kolombingo (zie §3).

---

## 5. Wat er wél en wat er niet in zit

**Wel afgedwongen, exact:**
* de decompositie-identiteit (numeriek geverifieerd tegen `MG.score_game`);
* volledige woordenboekcontrole per run: elk blok >= 2 moet op elk moment een woord zijn;
* <= 7 tegels per zet, bingo = precies 7 (+50), premie alleen op de zet waarin de cel nieuw is;
* de centrumregel (kolom 7 / rij 7);
* de koppeling *een cel kan in hoogstens één van zijn twee lijnen in een meer-tegelzet zitten*,
  op de 9 kruispunten van de frame-lijnen (§3, scenario's A en B);
* de vaste ankerletters van het triplet op elke kolom;
* eiland- en fragmentlemma: **overbodig gemaakt** door Stelling A (zie §1).

**Niet in de per-lijn-plafonds van §4 (dus: dat zijn géén bovengrenzen op de klasse):**
* de zak (letterschaarste) — per lijn mag elke lijn de beste tegels claimen;
* kruispuntconsistentie tussen een niet-ankerrij en haar kolom (dezelfde cel wordt in beide
  richtingen als meer-tegelcel geclaimd);
* globale volgorde-consistentie, aanraakregel en connectiviteit;
* de globale bingo-telling (per run wel meegeteld, niet globaal begrensd).
* de woordenlijst per interval is gesnoeid op een rangschikkingsheuristiek (top-N per lengte),
  dus de plafonds zijn *ondergrenzen* op het echte lijnplafond — precies de goede richting voor
  een diagnose van gemiste ruimte, en de verkeerde richting voor een bewijs.

De enige rigoureuze **bovengrenzen** in dit document zijn Stelling A (3865 op de ankerrijen) en
Stelling B (elke klassegrens uit deze methode >= 4847).

---

## 6. Gebruik

```
MODE=anchor                        .venv/bin/python experiments/mg_classbound.py
MODE=anchor SINGLE=0,7,14          .venv/bin/python experiments/mg_classbound.py   # scenario B
MODE=lines WHICH=col SHARD=k NSHARD=15 SINGLE=0,7,14 OUT=... .venv/bin/python experiments/mg_classbound.py
MODE=lines WHICH=row SHARD=k NSHARD=12 OUT=...               .venv/bin/python experiments/mg_classbound.py
MODE=knap  IN=a.json,b.json BUDGET=56                        .venv/bin/python experiments/mg_classbound.py
MODE=runs  KIND=col IDX=14                                   .venv/bin/python experiments/mg_classbound.py
```

Resultaattabellen: `experiments/results/classbound/` (`colA*` = scenario A, `col*`/`row*` = vrij).
