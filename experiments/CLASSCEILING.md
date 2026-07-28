# KLASSE-PLAFONDS op het HERSTELDE bord (2026-07-28, herrekend)

Motor: `experiments/mg_classceiling.py` bovenop `experiments/mg_mceiling.py`.
Per klasse is een representatieve BEZETTING + ZETSCHEMA geconstrueerd — cellen en zetten,
geen woorden — en daarvan is het exacte zak-plafond `SOM_c m(c)*waarde(c) + 50*#bingo's`
berekend.  Draaien: `ITERS=20000 SURGERY=1 .venv/bin/python experiments/mg_classceiling.py`
(~25 min, 12 processen).  Uitvoer: `experiments/results/classceiling.json` en
`classceiling_surgery.json`.  (`classceiling_repo.json` / `classceiling_std.json` zijn de
ONGELDIGE oude bestanden van het defecte bord en zijn leeggemaakt.)

> **Deze tabel vervangt de vorige volledig.**  De eerdere versie is berekend op het DEFECTE
> bord (`data/boards.toml` miste 7 letterpremies in de rijen 11-14) en is ongeldig.
> `board_check()` staat nu vooraan in het script en weigert te rekenen als het bord geen echt
> scrabblebord is (180-graden-symmetrisch, 24 DL / 12 TL / 17 DW / 8 TW).

## 0. Twee reparaties aan de meetlat

**(1) Zetvorm wordt nu wél gecontroleerd — in de motor zelf.**
`mg_mceiling.legal_schedule()` keurde vroeger elke celverzameling goed die het bord raakte.
Er zit nu `mg_mceiling.shape_ok()` in: elke zet ligt op ÉÉN lijn en de run tussen min en max
moet volledig gevuld zijn (door de zet zelf of door al liggende tegels).  Ook de
splits-operator in `best_schedule`/`search` snijdt nu LANGS de lijn, zodat beide deelzetten
weer een echte zetvorm hebben.  Regressie: het schema van ons record komt er ongeschonden
doorheen (`legal_schedule(record) == True`), en de m-calculus reproduceert de score exact.

**(2) De m-calculus rekent nu met blanco's.**  `ceiling(..., zero=blanks)` geeft blanco-cellen
waarde 0 en laat ze geen zaktegel kosten.  Daarmee geldt op ons record de identiteit exact:

```
SOM_c m(c)*waarde(c) + 50*11 bingo's = 4751 = MG.score_game(record)
```

Dat maakt een derde, veel hardere kolom mogelijk: **EXACT** = het plafond met álle 101 letters
vastgezet, dus de werkelijke score van deze tegelligging bij een gegeven zetvolgorde.

## 1. Wat de bordcorrectie met ons record deed

De 7 herstelde premiecellen zijn (7,11) (6,12) (8,12) (3,14) (11,14) DLS en (5,13) (9,13) TLS.
Ons record raakt er maar twee:

| cel | in het record | m | letter | winst door de correctie |
|---|---|---:|---|---:|
| (3,14) DLS | bezet, NIEUW in de x27-final | 54 | y (8) | +216 |
| (11,14) DLS | bezet, maar als PRE-cel | 33 | r (2) | +4 |
| (7,11) (6,12) (8,12) (5,13) (9,13) | **leeg** | 0 | — | 0 |

Samen +220: precies het verschil 4531 -> **4751**.  De hele winst komt uit één cel op de
x27-rij; de vijf herstelde premies in de rijen 11-13 leveren nul op, want daar staat vrijwel
niets (7 tegels, allemaal m <= 3).

## 2. IJking: wat moet een klasse halen?

| grootheid (record-voetafdruk) | waarde |
|---|---:|
| gerealiseerd (`score_game`, ok=True) | **4751** |
| EXACT-plafond, alle letters vast, eigen schema | 4751 |
| plafond met de ECHTE ankerletters (rij 0/7/14 vast, rest vrij) | **4839** |
| vrij plafond (pure geometrie, geen letters) | **5677** |
| realisatiegraad t.o.v. het ankervaste plafond | **0,982** |
| realisatiegraad t.o.v. het vrije plafond | **0,837** |

Klassen worden zonder woorden vergeleken, dus op het VRIJE plafond.  Bij dezelfde
realisatiegraad is nodig:

| doel | vrij plafond nodig | ankervast plafond nodig |
|---|---:|---:|
| 4819 (bobs referentie) | **5758** | 4908 |
| 5000 | **5974** | 5092 |

De drempel is 68 punten LAGER dan wat het defecte bord suggereerde (5826), en - dat is nieuw -
**hij is haalbaar**: klasse f (volle kolom 7) haalt 5876 en de kolom-7-chirurgie op ons eigen
bord 5917.  De conclusie van de vorige versie ("geen enkele klasse haalt 4819") is daarmee
ingetrokken.

## 3. Tabel (ITERS=20000, gesorteerd op vrij plafond)

| klasse | tegels | vrij | min2 | minzet | ladder | m-som |
|---|---:|---:|---:|---:|---:|---:|
| **f  anker3 + volle kolom 7** | 101 | **5876** | (a) 1911 | **5676** | 3965 | 1457 |
| j  kol 7 vol + onderlaan 12 | 101 (ruw 111) | 5841 | (a) | 5663 | 3973 | 1441 |
| a' anker3 = ons record 4751 | 101 | 5757 | (a) | 5748 | 4896 | 1376 |
| i  anker3 + onderlaan rij 11 | 101 (ruw 106) | 5755 | (a) | 5580 | 3752 | 1421 |
| g  anker3 + onderlaan rij 13 | 101 (ruw 108) | 5694 | (a) | 5562 | 3792 | 1367 |
| b2 FRAME 2/7/12 | 101 | 5693 | 5403 | 5272 | 290 | 1473 |
| a2 anker3 (min2-levering) | 99 | 5660 | **5415** | 5344 | 245 | 1453 |
| a  anker3 (synthetisch) | 100 | 5647 | (a) | 5503 | 3746 | 1346 |
| h  anker3 + onderlaan rij 12 | 101 (ruw 106) | 5631 | (a) | 5536 | 3794 | 1349 |
| e  herscoringszwaar | 101 | 5603 | (a) 1579 | 5534 | 4024 | 1450 |
| f2 f in min2-uitvoering | 101 | 5512 | 5313 | 5254 | 199 | 1458 |
| b3 FRAME 0/14 partieel | 99 | 5483 | 5114 | 5013 | 369 | 1480 |
| b  FRAME 0/7/14 | 101 (**ruw 105**) | 5472 | 5126 | 5049 | 346 | 1503 |
| d  hybride (ankers + 2 lanen) | 97 | 5306 | 5034 | 5052 | 272 | 1444 |
| c  x4-lanen puur | 95 | 3072 | 2499 | 2427 | 573 | 945 |

(a) = de levering stort in onder de min2-eis: deze schema's leveren hun pre-cellen met
1-tegel-haken (het record doet dat 20x).  Met een min2-choreografie bestaat de klasse wel —
dat zijn juist a2 en f2 — maar dat kost 3-4 bingo's.

Regimes: `vrij` = elke legale zet (ook 1-tegel-haken), `min2` = elke zet legt >= 2 tegels,
`minzet` = geen splitsingen.  `ladder` = vrij - min2.  Klassen die boven de 101 tegels
uitkomen worden door `trim_to_cap()` teruggesnoeid (steeds de cel met de laagste m die het
schema legaal laat), zodat alles op hetzelfde tegelbudget wordt vergeleken; het ruwe aantal
staat erbij.

## 4. Conclusies per spoor

### (f/j) VOLLE KOLOM 7 — de winnaar, en nu boven de drempel
Kolom 7 is een TWS-lijn: `(7,0)` en `(7,14)` zijn TWS.  Vul je rijen 1..13 van die kolom, dan
completeert de rij-14-final het kolomwoord tot een 14-run (wm = 3, want alleen de nieuwe cel
(7,14) telt) en de rij-0-final tot een 15-run (nog eens wm = 3).  Dat zijn twee gratis
x3-gebeurtenissen over 13 al bezette cellen: ~84 m-eenheden voor 6 tegels (14 per tegel,
tegen een bordgemiddelde van 1342/101 = 13,3).  Dit is de enige ingreep die het vrije plafond
boven de 4819-drempel tilt.

### De onderhelft (rijen 11-13) — hersteld maar structureel arm
De herstelde premies zijn allemaal LETTERpremies op lijnen zonder TWS.  Het beste dat een rij
daar kan doen is x4 (twee DWS nieuw gedekt in één brugzet):

| rij | DWS | run | letterpremies in de run | m-massa | tegels |
|---|---|---:|---|---:|---:|
| 11 | (3,11)+(11,11) | 9 | DLS (7,11) | 4*9 + 4 = 40 | 7-9 |
| 12 | (2,12)+(12,12) | 11 | DLS (6,12)+(8,12) | 4*11 + 8 = 52 | 9-11 |
| 13 | (1,13)+(13,13) | 13 | TLS (5,13)+(9,13) | 4*13 + 16 = 68 | 11-13 |

Dat is 4,4 tot 5,2 m-eenheden per tegel — een factor 3 onder het bordgemiddelde en een factor
10 onder wat dezelfde tegels in een klimkolom+final-constructie opleveren (een x27-final zet
405 m-eenheden neer met 7 tegels).  **De onderlanen verliezen dus altijd van de tegels die ze
moeten verdringen**, en de rij-13-laan (de beste van de drie, want die pakt de twee herstelde
TLS in een x4-zet mee: m = 12 per TLS-cel) haalt het net niet.  De bordcorrectie verandert de
rangorde van de klassen niet — ze verandert alleen de absolute hoogte (+40 à +200 per klasse)
en verlaagt de drempel.

### (b) FRAME — nog steeds tegel-infeasible (bord-onafhankelijk)
KLIMKOLOM-LEMMA, opnieuw nagerekend: elke ankerrij heeft 15 cellen en een final van hoogstens
7 tegels, dus >= 8 pre-cellen.  Die worden door de final-cel (7,rij) in een linker- en een
rechtergroep gesplitst, en elke groep heeft een eigen verticale klimmer nodig (rij 7 -> rij 1
= 6 tegels).  Rij 0 en rij 14 hebben dus 4 klimkolommen x 6 tegels = 24 tegels bovenop de 81
framecellen = **105 > 101**.  Het lemma telt alleen tegels en afstanden — geen premies — en is
dus bord-onafhankelijk; het script bevestigt het (klasse b bouwt 105 tegels en moet er 4
weggooien).  Ook na trimmen blijft het frame onder het record.

### (c) x4-lanen puur — onveranderd catastrofaal
Geen enkele TWS in het skelet.  Blijft rond de 2950, ver onder alles.

### (e) herscoringszwaar — ladder-illusie
Het vrije plafond is hoog, maar de winst zit volledig in 1-tegel-etappes; onder `min2` stort
het in.  `mg_ladder.py` had dat al empirisch bevestigd (nul geaccepteerde splitsingen).

## 5. CHIRURGIE: wat levert het het meeste op op ONS bord?

Het bord zit vol (101 tegels), dus elke toevoeging moet even veel tegels vrijmaken.
`surgery()` offert steeds de cellen met de LAAGSTE m waarvan het weghalen het schema legaal
laat (de centrumkolom is beschermd als ruggengraat) en herordent daarna het schema.
Alle delta's zijn t.o.v. de HERSCHEMA-basis, niet t.o.v. het huidige schema.

Basis (eigen schema): vrij 5677, ankervast 4839, EXACT 4751.
Herschema-basis (zelfde bezetting, beste vorm-legale volgorde): vrij **5757**, ankervast
**4924**, EXACT **4830** — maar dat laatste getal negeert het woordenboek (zie §6.1).

| ingreep | +tegels | vrij | Δvrij | ankervast | Δankervast | bingo's |
|---|---:|---:|---:|---:|---:|---:|
| **kolom 7 vol (rijen 1..13)** | 6 | **5917** | **+160** | **5162** | **+238** | 11 |
| kolom 7 vol + rij-10-x4-laan | 11 | 5818 | +61 | 5133 | +209 | 8 |
| **kolom 11 x4 (DWS rij 3 + rij 11)** | 3 | 5820 | +63 | 5064 | **+140** | 10 |
| kolom 7 onder (rijen 11..13) | 3 | 5795 | +38 | 4989 | +65 | 11 |
| kolom 3 x4 (DWS rij 3 + rij 11) | 7 | 5734 | -23 | 4961 | +37 | 11 |
| onderlaan rij 13 (x4, pakt beide TLS) | 11 | 5739 | -18 | 4933 | +9 | 10 |
| onderlaan rij 11 (x4) | 7 | 5711 | -46 | 4885 | -39 | 11 |
| rij-10 x4-laan | 5 | 5689 | -68 | 4874 | -50 | 10 |
| onderlaan rij 12 (x4) | 9 | 5654 | -103 | 4816 | -108 | 11 |
| kolom 7 vol + onderlaan 13 | 16 | — | — | — | — | past niet in 101 tegels |

Twee dingen springen eruit:

* **kolom 7 volmaken is de enige ingreep die het vrije plafond boven de 4819-drempel (5758)
  tilt**: 5917.  Voor 5000 (drempel 5974) komt hij 57 tekort — daar is dus nóg een ingreep of
  een betere realisatiegraad voor nodig.
* **kolom 11 x4 is spotgoedkoop**: 3 tegels voor +140 ankervast.  Kolom 11 heeft DWS op rij 3
  ÉN rij 11; als één brugzet ze allebei NIEUW dekt scoort de hele kolomrun (rijen 3..13) x4.
  In ons record ligt `(11,11)` al, dus die moet uit zijn huidige zet gesneden worden
  (`resect()`); de zet `[(11,3),(11,11)]` sluit dan de kolom.  Het kost wel een bingo
  (kolom 11 wordt in stukken gelegd) en dat is al in de +140 verrekend.
* Alle ONDERLANEN zijn negatief of marginaal, ook de rij-13-laan die de twee herstelde TLS
  in een x4-zet meepakt.  De bordcorrectie opent daar dus geen nieuw spoor.

## 6. AANBEVELING

**1. Gratis, al geverifieerd: speel de haak (11,4) meteen na de rij-4-laan.  +26.**
Zelfde tegels, zelfde letters, zelfde 33 zetten — alleen de volgorde verandert: de 1-tegel-zet
`(11,4)` schuift van positie 26 naar positie 2.  Daardoor is het rij-4-woord al 12 letters lang
als de verticalen (kolom 12, 5, 2) er doorheen kruisen, en herscoort elk van die kruisingen een
langer woord (+1 m op tien rij-4-cellen, +2 op (11,4)).
**`MG.score_game` zegt 4777, ok=True** — opgeslagen als
`experiments/results/mg_lexresched.json` (BEST.json is bewust NIET overschreven, er draaien
andere sporen op).  De m-motor zegt dat er zonder het lexicon +79 in zat (4830); de rest daarvan
is lexicaal onbereikbaar (de motor kiest volgordes die woorden als `rk` opleveren).

**2. De structurele ingreep met het hoogste rendement: KOLOM 7 VOLMAKEN (rijen 1..13).**
Zie §5.  Te offeren tegels: de vier onderste cellen van de kolom-2-staart `(2,8) (2,9) (2,10)
(2,11)` (m = 5,3,2,1) en de twee staartcellen van het rij-4-woord `(11,4)` en `(13,4)` (m = 2,1)
— samen 6 tegels met m-som 14, tegen ~84 nieuwe m-eenheden.  Geen bingo gaat verloren (11
blijft 11).
*Lexicale prijs, en die is stevig:* er moet een 15-letterwoord in kolom 7 staan dat
`(7,0)`-letter + rijen 1..13 + `(7,14)`-letter is, met de huidige ankerwoorden dus `k` ... `k`
en met `wankend` (rijen 4-10, uit het centrumwoord + de laan) er middenin.  Realistisch betekent
dit dat kolom 7 en de drie ankerwoorden SAMEN opnieuw gezocht moeten worden — dit is een
generator-taak, geen reparatie.
*Halve variant:* alleen rijen 11..13 (3 tegels, alleen `(2,9) (2,10) (2,11)` offeren) levert het
kleinere deel op (+65) en vraagt een 11-letterwoord rijen 4..14.

**2b. Als de kolom-7-woordeis te zwaar blijkt: KOLOM 11 x4 — 3 tegels voor +140.**
Kolom 11 heeft DWS op `(11,3)` én `(11,11)`.  Eén brugzet die ze allebei NIEUW dekt geeft de
hele kolomrun rijen 3..13 een x4.  Concreet: leg `(11,5)` en `(11,6)` (die twee cellen zijn nu
leeg, `(11,4)` ligt al), snijd `(11,11)` uit de huidige kolom-11-bingo, en sluit met de zet
`[(11,3),(11,11)]`.  Te offeren: `(2,9) (2,10) (2,11)`.  Kosten: de kolom-11-bingo valt uiteen
(-50, al verrekend).  Lexicaal veel makkelijker dan kolom 7: het vraagt een 11-letterwoord in
kolom 11 (rijen 3..13) in plaats van een 15-letterwoord met twee vastgezette eindletters.

**3. Waar de echte 800 punten liggen: het LEXICON, niet de geometrie.**
Het gat tussen het vrije plafond (5677) en het ankervaste plafond (4839) is 838 punten, en 729
daarvan zit op veertien cellen:

| cel | m | staat er | ideaal | verlies |
|---|---:|---|---:|---:|
| (3,0) DLS op x27 | 54 | c (5) | q (10) | 270 |
| (5,0) | 31 | e (1) | 5 | 124 |
| (2,0) | 35 | s (2) | 5 | 105 |
| (11,14) DLS op x27 | 33 | r (2) | 5 | 99 |
| (10,0) | 30 | e (1) | 4 | 90 |
| (5,14) | 29 | e (1) | 4 | 87 |
| (4,14) | 31 | m (3) | 5 | 62 |

`(11,14)` is bovendien half-geometrisch: hij is een PRE-cel (m = 33) terwijl hij in de x27-final
m = 56 zou hebben.  Maar dat kan NIET gratis — **pre-groep-lemma**: de 8 pre-cellen van een
ankerrij vormen aaneengesloten groepen, en elke groep heeft een eigen dalende kolom nodig om
aangehaakt te worden.  Onze twee groepen `{4,5,6}` en `{8..12}` hangen aan kolom 4 en kolom 11,
en juist dáárom is `(11,14)` een pre-cel.  Wil je hem in de final hebben, dan splitst de
rechtergroep in `{8,9,10}` en `{12}` en heb je een TWEEDE dalende kolom rechts nodig (kolom 10
én kolom 12): ~4 extra tegels en de kolom-11-bingo weg, voor +23 m op één cel (~+115 vrij
plafond).  Getest en te duur; opgeschreven zodat niemand het nog eens probeert.
De les die wél telt: **kies bij het genereren de dalende kolommen zó dat ze NIET onder een
DLS van de x27-rij staan** — dan is de DLS gratis final-cel.

**Prioriteit:**

| # | ingreep | winst | risico |
|---|---|---:|---|
| 1 | haak `(11,4)` naar voren | **+26 geverifieerd** | geen |
| 2b | kolom 11 x4 (3 tegels) | +140 plafond, schat +100 à +140 | 11-letterwoord kolom 11 |
| 2 | kolom 7 vol (6 tegels) | +238 plafond, schat +150 à +230 | 15-letterwoord kolom 7 met vaste eindletters -> generator-ronde |
| 3 | betere letters op de top-m-cellen | ~700 | puur lexicaal; dit IS de frontier |

De onderhelft-lanen (§4) zijn dood: ze kosten meer m dan ze opleveren.  Het frame (§4b) is en
blijft tegel-infeasible.

## 7. Ladder-afhankelijkheid (samenvatting)

Ons record verliest bij `minzet` vrijwel niets: de 4751-geometrie is eerlijk, niet opgeblazen
door tegel-voor-tegel-trucs.  De frame- en laanklassen leunen voor 250-500 punten op de ladder.
De `min2`-kolom stort in bij elke klasse die haar pre-cellen met 1-tegel-haken levert (het
record doet dat 20x); dat is geen zwakte maar een bingo-besparing — de min2-choreografieën
(a2/f2) kosten 3-4 bingo's = 150-200 punten.
