# KLASSE-PLAFONDS: welke geometrie-klasse haalt >= 4819? (2026-07-28)

Motor: `experiments/mg_classceiling.py` (bovenop `mg_mceiling.py`).  Per klasse is een
representatieve BEZETTING + ZETSCHEMA geconstrueerd — cellen en zetten, geen woorden — en
daarvan is het exacte zak-plafond `SOM_c m(c)*waarde(c) + 50*#bingo's` berekend.
Draaien: `ITERS=100000 .venv/bin/python experiments/mg_classceiling.py` (15-75 s, 12 processen;
geen Rust nodig — de m-motor is licht, alleen de schema-zoektocht werd geparallelliseerd).

## 0. Twee correcties op de meetlat (lees dit eerst)

**(1) `mg_mceiling.legal_schedule` controleert de ZETVORM niet.**  Het checkt center/aanraking/
<=7 tegels, maar niet dat een zet op EEN lijn ligt en dat de run tussen min en max volledig
gevuld is.  `best_schedule` mag dus zetten verzinnen die geen enkel woord kunnen zijn.  Het
eerder gerapporteerde "4733 bij herordening van hetzelfde bord" is zo'n vorm-ILLEGAAL schema;
met de vorm-eis erbij is het **4684**.  `mg_classceiling.legal()` doet de strenge check (het
echte 4531-schema komt er ongeschonden doorheen).

**(2) `data/boards.toml` mist 7 letterpremies in de onderste bordhelft.**  De `15`-board-string
is asymmetrisch: rijen 11-14 missen premies die op een standaard scrabblebord wel de spiegeling
van rijen 3-0 zijn:

| cel | hoort te zijn | staat in de toml |
|-----|---------------|------------------|
| (7,11) | DLS (2) | 1 |
| (6,12), (8,12) | DLS (2) | 1 |
| (5,13), (9,13) | TLS (3) | 1 |
| (3,14), (11,14) | DLS (2) | 1 |

De woordmultiplicatoren zijn wel symmetrisch — het is dus een overschrijffout in de onderste
vier regels, geen bordvariant.  **Ons geverifieerde 4531-spel scoort op een standaardbord
exact 4751** (zelfde bord, zelfde letters, zelfde zetvolgorde; `score_game` ok=True, +220).
Het plafond van datzelfde bord bij herordening gaat van 4684 naar **4904**.
Dat verklaart 220 van de 288 punten die ons van bob's 4819 scheiden: als de referentie op een
echt scrabblebord is gespeeld, vergelijken we appels met peren.  *(Niet gewijzigd — dat zou
alle bestaande certificaten/records ongeldig maken; `BOARD=std` rekent de variant door.)*

## 1. IJking: wat moet een klasse halen?

| grootheid (4531-bord) | repo-bord | standaardbord |
|---|---|---|
| plafond met de ECHTE ankerletters, eigen schema | 4619 | 4839 |
| plafond met de echte ankerletters, best (vorm-legaal) herschema | 4684 | 4904 |
| plafond ZONDER letters (pure geometrie, "vrij") | 5478 | 5677 |
| gerealiseerd | 4531 | 4751 |
| realisatiegraad = gerealiseerd / vrij plafond | **0,827** | 0,798 |

Klassen worden zonder woorden vergeleken, dus met het VRIJE plafond.  Bij dezelfde
realisatiegraad moet een klasse ~**5826** vrij plafond halen om 4819 te kunnen worden
(op het standaardbord ~6037).

## 2. Tabel (repo-bord, ITERS=100000, gesorteerd op vrij plafond)

| klasse | tegels | vrij | min2 | minzet | ladder-winst |
|---|---:|---:|---:|---:|---:|
| **f  anker3 + volle kolom 7** | 101 | **5677** | (a) | 5469 | 3745 |
| b  FRAME 0/7/14 | **105 (ILLEGAAL)** | 5659 | 5249 | 5168 | 410 |
| f2 f in min2-uitvoering | 101 | 5587 | **5294** | 5239 | 293 |
| a' anker3 = ons record 4531 | 101 | 5559 | (a) | **5549** | 4706 |
| b2 FRAME 2/7/12 | 101 | 5493 | 5173 | 5063 | 320 |
| a2 anker3 (min2-levering) | 99 | 5489 | 5222 | 5138 | 267 |
| b3 FRAME 0/14 partieel | 99 | 5474 | 5142 | 5005 | 332 |
| a  anker3 (synthetisch) | 100 | 5439 | (a) | 5319 | 3522 |
| e  herscoringszwaar | 101 | 5376 | (a) | 5289 | 3769 |
| d  hybride (ankers + 2 lanen) | 97 | 5322 | 5057 | 5043 | 265 |
| c  x4-lanen puur | 95 | 2920 | 2449 | 2386 | 471 |

(a) = de levering stort in onder de min2-eis: deze schema's leveren hun pre-cellen met
1-tegel-haken (het record doet dat 20x).  Met een min2-choreografie bestaat de klasse wel —
dat zijn juist a2 en f2 — maar dat kost 3-4 bingo's.  Regimes: `vrij` = elke legale zet
(ook 1 tegel), `min2` = elke zet >=2 tegels, `minzet` = geen splitsingen (elke lijn in zo min
mogelijk zetten).  `ladder-winst` = vrij - min2.

Op het standaardbord verschuift alles ~+150 mee (f 5873, a' 5757, b 5692, b2 5689, a2 5642,
c 2962) — de rangorde blijft identiek.

## 3. Antwoord: GEEN ENKELE klasse haalt 4900/5826

* Het beste legale plafond is **5677** (klasse f) — **149 te weinig** voor 4819 bij onze
  realisatiegraad, en dat is nog vóór de ladder-korting.  Onder het realistische
  `minzet`-regime: 5549 (record) resp. 5469 (f).
* Reden: de multiplier-massa zit vast.  Er zijn 8 TWS-cellen; een woordmultiplicator telt
  alleen voor de cellen die IN DIE ZET nieuw zijn.  Een 15-cel-lijn met 3 nieuwe TWS levert
  27*15 = 405 m-eenheden; twee zulke lijnen + één lijn met 2 TWS (9*15) = **945**, en dat is
  precies wat de huidige klasse (rijen 0/7/14) al doet.  Elke andere verdeling van de 8 TWS
  is gelijk of slechter (bv. 2 rijen x27 + 2 kolommen x3 = 27+27+3+3 = 63 = hetzelfde
  multiplier-totaal als 27+27+9, maar met 24 tegels meer).
* Alle extra structuur legt m op cellen die niet in een x27-zet zitten; daar liggen de
  marginale tegels uit de zak, en die zijn 1 punt waard.  Frame b heeft 245 m-eenheden MEER
  dan het record (1592 vs 1347) en toch geen hoger realistisch plafond.  Dit is het
  zak-druk-lemma in zijn scherpste vorm: **plafond stijgt alleen als m stijgt op de ~20 cellen
  die de dure letters dragen**, niet door meer bezette cellen.

### (b) FRAME — negatief, en zelfs tegel-infeasible
KLIMKOLOM-LEMMA: elke ankerrij heeft 15 cellen en een final van hoogstens 7 tegels, dus >=8
pre-cellen.  Die pre-cellen worden door de final-cel (7,rij) in een linker- en een rechtergroep
gesplitst, en elke groep heeft een eigen verticale klimmer nodig (afstand rij 7 -> rij 1 = 6
tegels).  Rij 0 en rij 14 hebben dus 4 klimkolommen van 6 tegels = 24 tegels bovenop de 81
framecellen = **105 > 101**.  Het volle TWS-frame past niet op het bord.  De grootste legale
varianten (b2 = kolommen 2/7/12, b3 = kolommen 0/14) halen 5493 resp. 5474 — onder het record.
Extra verborgen kosten van het frame: (i) de kolommen 0/7/14 kunnen géén bingo-verticalen zijn
(hun eindcellen moeten leeg blijven tot de finals), (ii) met maar 2 klimmers per rij lukt het
niet om de DLS-cellen (3,0)/(11,0) in de final te houden — die twee cellen zijn in klasse (a)
juist de m=54-cellen.  De kolomcompletering levert per kolomcel maar +3 (of 2x +3 als je zowel
een 14-run als een 15-run laat scoren — en dat vraagt een 14-letterwoord dat verlengbaar is tot
een 15-letterwoord).

### (c) x4-LANEN puur — zwaar negatief (2920)
8 lanen x4 over 13/11/9/7 cellen = 4*80 = 320 m-eenheden voor 80 tegels, tegenover 945 voor de
45 ankercellen.  Een DWS-cel kan bovendien maar één zet bedienen (die zet die hem legt), dus
rij- en kolomlanen concurreren om dezelfde 16 diagonaalcellen.  Lanen zijn uitsluitend zinvol
als BIJVANGST op cellen die je toch al legt (zoals de rij-4-laan in ons record), nooit als
skelet.

### (d) HYBRIDE — 5322, geen winst
Lanen kosten precies de tegels die anders klimmers/bingo-verticalen zijn.  Elke laan-tegel die
je uit een verticaal haalt, kost een pre-levering of een bingo (50 punten) en levert ~4 m terug.

### (e) HERSCORINGSZWAAR — 5376, en het is een ladder-illusie
Trapsgewijs verlengen tilt het vrije plafond, maar de winst zit volledig in de 1-tegel-etappes:
vrij 5376 -> min2 stort in (35 cellen niet leverbaar) en `minzet` 5289.  De ladder-winst
(3769) is precies wat de woordenboek-eis (elke tussenstand moet een woord zijn) opvreet;
`mg_ladder.py` heeft dat empirisch al bevestigd (nul geaccepteerde splitsingen).
De herscoringsvorm die WEL werkt blijft de post-finale extensie — die zit al in 4531.

## 4. Goedkoopste structurele wijziging aan onze huidige klasse

**Maak kolom 7 helemaal vol (rijen 1..13) en laat beide x27-finals hem completeren.**
(klasse f; in het min2-regime f2.)

* Kost: 6 tegels (rijen 1-3 en 11-13 van kolom 7), weg te halen bij de onderste verticalen.
* Levert: de rij-14-final plaatst (7,14) en herscoort het kolom-7-woord met **x3** over 14
  cellen; de rij-0-final plaatst (7,0) en herscoort de volledige 15-run nóg eens **x3**.
  Dat zijn twee gratis x3-gebeurtenissen op cellen die al bezet zijn.
* Effect (zelfde bouwer, zelfde budget): vrij 5439 -> **5677** (+238), minzet 5319 -> 5469
  (+150).  In min2-uitvoering: 5489 -> 5587 (+98), min2 5222 -> 5294 (+72).
* Lexicale prijs: er moet een 13-letterwoord in kolom 7 staan dat met één letter erboven én
  één letter eronder tot 15 letters uitgroeit (de rij-0/rij-14-finals leveren die letters).
  Dat is dezelfde soort eis als onze bestaande post-finale extensies, maar dan op de duurste
  kolom van het bord.  Halve variant (alleen rijen 11-13, 2-3 tegels, alleen de rij-14-final
  completeert) levert al ~+70.

Daarna, op volgorde van rendement per tegel:
1. **bingo-dichtheid** — 11 bingo's nu; elke extra 7-tegelzet is +50 en kost niets extra's aan
   zakdruk.  De min2-choreografie (a2/f2) kost er juist 3-4: 1-tegel-haken zijn dus geen
   zwakte maar een bingo-besparing.
2. **letters op de top-m-cellen** — het gat tussen vrij (5478) en met-echte-letters (4619)
   is 859 punten; dat is 6x groter dan alles wat geometrie nog kan opleveren.  De frontier
   is lexicaal, niet geometrisch.
3. **het bord** — zie §0: 220 punten liggen in `data/boards.toml`.

## 5. Ladder-afhankelijkheid per klasse (samenvatting)

| klasse | vrij | min2 (>=2 tegels/zet) | minzet (lijn in één keer) | oordeel |
|---|---:|---:|---:|---|
| a' record | 5559 | choreografie-afhankelijk (a2: 5222) | 5549 | **niet ladder-afhankelijk** |
| f | 5677 | (f2: 5294) | 5469 | niet ladder-afhankelijk |
| b/b2/b3 frame | 5449-5659 | 5142-5249 | 5005-5168 | ~400 van het plafond is ladder |
| e herscoring | 5376 | 1607 (35 cellen onleverbaar) | 5289 | ladder-illusie |
| c lanen | 2920 | 2449 | 2386 | n.v.t. (te laag) |

Ons record verliest bij `minzet` maar 10 punten plafond: de 4531-geometrie is dus eerlijk,
niet opgeblazen door tegel-voor-tegel-trucs.
