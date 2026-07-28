# ANKERKETEN RIJ 0 EN RIJ 14: masker en woord gezamenlijk (2026-07-28)

Vervolg op `ROW7.md`. Daar bleek dat de waarde van een ankerwoord niet
`multiplier*(S+DL-bonus)` is maar `multiplier*(S+DL-bonus) + KETEN(w, masker)`, omdat elke
bezorgzet elke maximale run herscoort die hij raakt. Voor rij 7 was die keten 45 punten. Hier
voor rij 0 en rij 14, waar de multiplier 27 is en het masker vier vrije binnencellen heeft.

Machinerie: `experiments/mg_anchorchain.py` (delen 0-3; env `MAXROOTS`, `MB`, `TOP`, `PART`).
Uitvoer: `experiments/results/anchorchain.json`. Basisbord: het huidige record **4778**.

**Uitkomst: geen enkel triplet in het lexicon haalt onze waarde. Ons masker was al optimaal —
voor allebei de woorden. Er komen ook geen tegels vrij, dus het kolom-14-spoor gaat hier NIET
mee open.**

---

## 1. Het eiland-decompositielemma

Rij 0 en rij 14 zijn geometrisch identiek (WM `3/1../3/1../3`, DL op x=3 en x=11). De slotzet
legt 7 cellen en moet (0,y), (7,y) en (14,y) bevatten voor x27 — er blijven dus **4 vrije
maskerplekken** over uit de 12 binnenkolommen `{1..6, 8..13}`, en de pre-set is de overige 8.

Omdat **(7,y) altijd een maskercel is**, kan geen enkele zet over kolom 7 heen reiken (de span
zou een lege cel bevatten). De pre-set valt daarmee uiteen in twee eilanden die elkaar nooit
raken, en de keten **decomponeert exact**:

```
keten(w, P) = keten_eiland(w, P n {1..6}) + keten_eiland(w, P n {8..13})
wortels(P)  = #runs links + #runs rechts        (altijd >= 2, want 8 > 6)
```

Anders dan bij rij 7 is er **geen gratis wortel**: rij 7 kreeg het centrum uit zet 1, maar op
rij 0/14 heeft elke run een verticale stub nodig ((c,1) resp. (c,13)). Dat maakt de DP klein
(2x64 toestanden) en exact.

### IJking — de DP reproduceert het bord

| rij | masker | pre-set | wortels | DP-keten | gemeten op het bord |
|-----|--------|---------|--------:|---------:|--------------------:|
| 0  | 0,3,7,8,11,13,14 | 1,2,4,5,6,9,10,12 | 4 | 14 + 5 = **19** | **19** |
| 14 | 0,1,2,3,7,13,14  | 4,5,6,8,9,10,11,12 | 2 | 11 + 42 = **53** | **53** |
| 7  | (zie ROW7.md) | 4..11 | — | **45** | **45** |

Alle drie exact. De ketens op het record zijn:

```
rij  0: "he"(+5) -> "hen"(+6), "es"(+3), "he"(+5)                     = 19
rij 14: "me"(+4) -> "mel"(+7), "uur"(+12) -> "zuur"(+14) -> "zuurt"(+16) = 53
rij  7: "we"(+6) -> "werk"(+11), "te"(+3) -> "ter"(+7) -> "werkster"(+18) = 45
```

Totaal 117 punten herscoring op de ankerrijen — 2,4% van het record, en volledig onzichtbaar in
elke eerdere waarderingsmaat.

---

## 2. De volledige maat: `27*(S + DL-bonus) + keten`, masker en woord samen

Snoeivloer bewijsbaar joint gekozen: `3690 - maxA(1693) - maxB(567) = 1430`, pool 2933 van
118.709, waarvan 2447 een legbaar masker hebben (wortelbudget <= 4).

| # | woord | maat | 27*lsum | keten | wtl | optimale pre-set |
|---|-------|-----:|--------:|------:|----:|------------------|
| **1** | **geschenkcheques** | **1693** | 1674 | 19 | 4 | 1,2,4,5,6,9,10,12 |
| 2 | flauwekulexcuus | 1687 | 1647 | 40 | 3 | 1,2,4,5,6,8,9,10 |
| 3 | jacquardmachine | 1611 | 1593 | 18 | 4 | 1,5,6,8,9,10,12,13 |
| 4 | cultuurchequeje | 1595 | 1620 | 29 | 4 | 1,3,4,5,6,8,9,12 |
| 5 | quichebuffetjes | 1562 | 1539 | 23 | 4 | 1,2,4,5,6,8,12,13 |
| .. | | | | | | |
| 11 | vluchtreflexjes | 1540 | 1647 | 28 | 3 | 1,2,3,4,5,8,12,13 |
| **18** | **polymelkzuurtje** | **1511** | 1512 | 53 | 2 | 4,5,6,8,9,10,11,12 |

### Twee dingen springen eruit

**(a) De optimale maskers zijn EXACT de maskers die het record al gebruikt.** Voor
geschenkcheques levert de gezamenlijke optimalisatie pre-set `{1,2,4,5,6,9,10,12}` — het
recordmasker. Voor polymelkzuurtje `{4,5,6,8,9,10,11,12}` — ook het recordmasker. Er is niets
te winnen met masker-chirurgie; vraag 4 is daarmee negatief beantwoord, maar wel *bewezen*
negatief in plaats van onbeproefd.

**(b) De keten werkt in ons VOORDEEL, niet in ons nadeel.** Op de kale maat `27*lsum` stond
geschenkcheques 2e en polymelkzuurtje 45e. Met de keten meegerekend: **1e** en **18e**. Anders
dan bij rij 7 (waar de kale maat ons te laag zette) corrigeert de keten hier in dezelfde
richting: onze woorden hebben uitzonderlijk rijke fragmentketens (`he/hen/es`, `me/mel`,
`uur/zuur/zuurt`), en dat is precies de "fragment-uitzonderlijkheid" uit FRAME_CAMPAIGN — nu
voor het eerst in punten uitgedrukt in plaats van als dichtheidsheuristiek.

De prijs die de rivalen betalen is zichtbaar in de kolom `27*lsum` versus `maat`:
vluchtreflexjes staat nominaal op 1647 maar haalt met een legbaar masker maar 1540 — **-107**.
cultuurchequeje -25, jacquardweefsel -77. Dat verschil *is* de bezorgbaarheidsbelasting.

**(c) polymelkzuurtje kan zijn tweede DL niet vrijspelen.** Zijn maat 1511 ligt 1 punt onder
`27*lsum = 1512`. Reden: er bestaat geen legbaar masker (ook niet met 6 wortels) dat zowel
kolom 3 als kolom 11 vrijhoudt — de pre-set zou dan 8 van de 10 kolommen
`{1,2,4,5,6,8,9,10,12,13}` moeten zijn, en geen daarvan overleeft de fragmenttoets. De 54
punten van `27*v(r)` zijn dus structureel onbereikbaar, niet weggegooid.

---

## 3. Wortelbudget: er komen GEEN tegels vrij (antwoord op het kolom-14-spoor)

Elke wortel is een verticale stub — dus tegels. Als de optimalisatie met minder wortels toe kon,
zou het kolom-14-spoor (+211 bruto, netto ~0 omdat er 12 tegels vrij moeten komen) alsnog
rendabel worden. Dat is niet zo:

| wortelbudget | geschenkcheques | polymelkzuurtje |
|---|---:|---:|
| <= 2 | 1459 (-234) | **1511** (gebruikt 2) |
| <= 3 | 1573 (-120) | 1511 |
| <= 4 | **1693** (gebruikt 4) | 1511 |
| <= 5/6 | 1693 | 1511 |

* geschenkcheques **heeft alle 4 zijn wortels nodig**: eentje inleveren kost 120 punten, twee
  kost 234. De stubs op kolom 2/5/10/12 zijn dragend.
* polymelkzuurtje draait al op het **minimum van 2** wortels (kolom 4 en 11), en extra wortels
  leveren niets op.

> **Melding aan de coördinator: dit spoor levert geen vrije tegels op.** De ankerrijen gebruiken
> precies het minimum aantal stubs dat hun keten- en DL-waarde nog draagt. Kolom 14 volledig
> opbouwen blijft dus de 12 tegels kosten die het al kostte; masker/keten-optimalisatie
> financiert dat niet.

---

## 4. Verschuift het triplet? Nee — en nu bewijsbaar

Triplet-enumeratie op de volledige maat voor alle drie de rijen (rij 0/14 met eilandketen, rij 7
met de keten uit ROW7.md), zak-bewust met blanco-degradatie, joint-vloer 1430:

```
HUIDIG: geschenkcheques 1693 + flexwerkstertje 486 + polymelkzuurtje 1511 = 3690
1 triplet haalt die waarde; rang huidig = 1 van 1
```

Naaste concurrenten (alle varieren alleen rij 7, en houden ons rij-0/14-paar):

| # | maat | triplet | delta |
|---|-----:|---------|------:|
| 1 | **3690** | geschenkcheques / flexwerkstertje / polymelkzuurtje | +0 |
| 2 | 3663 | geschenkcheques / flexwerkstertje / papyruszuiltjes | -27 |
| 3 | 3662 | geschenkcheques / flexkiezeresjes / polymelkzuurtje | -28 |
| 4 | 3658 | geschenkcheques / reflexweggetjes / polymelkzuurtje | -32 |
| 5 | 3653 | geschenkcheques / walvisexpertjes / polymelkzuurtje | -37 |

### Wat laten we op rij 14 liggen? Op papier tot +176, in werkelijkheid nul.

Zestien woorden staan boven polymelkzuurtje op de geisoleerde maat. Met geschenkcheques erbij
(en de blanco-degradatie eerlijk verrekend):

| rij-14-woord | maat14 | vs polymelk | volledig triplet | delta |
|---|---:|---:|---|---:|
| flauwekulexcuus | 1687 | +176 | **zaktekort > 2 — DOOD** | — |
| jacquardmachine | 1611 | +100 | zaktekort > 2 — DOOD | — |
| cultuurchequeje | 1595 | +84 | zaktekort > 2 — DOOD | — |
| quichebuffetjes | 1562 | +51 | zaktekort > 2 — DOOD | — |
| babyglimlachjes | 1556 | +45 | 3492 (2 blanco, verlies 243) | **-198** |
| jacquardweefsel | 1543 | +32 | 3065 (2 blanco, verlies 675) | -625 |
| vluchtreflexjes | 1540 | +29 | 3493 (2 blanco, verlies 243) | -197 |
| lewylichaampjes | 1539 | +28 | 3500 (2 blanco, verlies 243) | -190 |
| cliquetsystemen | 1537 | +26 | 3048 (2 blanco, verlies 675) | -642 |
| aliquotvleugels | 1528 | +17 | 3185 (1 blanco, verlies 540) | -505 |
| **polymelkzuurtje** | 1511 | +0 | **3690 (0 blanco)** | **+0** |

De vier grootste kandidaten zijn zak-dood (meer dan 2 blanco's nodig naast geschenkcheques); de
rest betaalt 190 tot 642 punten aan blanco-degradatie, want een blanco op een x27-cel kost
`27*LM*v` — tot 540 punten voor een enkele letter. **De nul-tekort-pasvorm van polymelkzuurtje
bij geschenkcheques is meer waard dan de +176 die flauwekulexcuus op papier biedt.**

Kolomtabel-filter (het criterium dat gymjuffrouwtjes doodde): ons triplet houdt **1** dode kolom
(bodem kolom 3), met som top 3542 / bodem 1531. Er was geen enkele rivaal om doorheen te halen.

---

## 5. Conclusie

1. **De keten voor rij 0 en 14 is berekend en geijkt** (19 en 53, exact gereproduceerd). De
   drie ankerketens samen zijn 117 punten — reeel, en tot nu toe in geen enkele maat aanwezig.
2. **Het triplet verschuift niet.** Op de volledige maat, met bewijsbaar volledige joint-vloer,
   is `geschenkcheques / flexwerkstertje / polymelkzuurtje` het **enige** triplet dat 3690 haalt;
   de runner-up staat op -27 en verandert alleen rij 7.
3. **Ons masker was al optimaal, voor beide woorden**, en de gezamenlijke masker/woord-
   optimalisatie geeft exact de pre-sets terug die het record gebruikt. Niets te bouwen.
4. **We laten op rij 0 nul liggen** (rang 1 van 2447) en **op rij 14 nul** zodra de zak meetelt
   (de +176 van flauwekulexcuus is zak-dood; de beste zak-haalbare rivaal verliest 190).
5. **Geen vrije tegels**, dus het kolom-14-spoor wordt hierdoor niet rendabel.

Anders dan bij rij 7 — waar de kale maat een artefact in ons *nadeel* was — corrigeert de keten
hier in ons *voordeel*: geschenkcheques 2e -> 1e, polymelkzuurtje 45e -> 18e. De maat die de
zaak sluit is `multiplier*(S + DL-bonus) + keten(w, masker)`, gemaximeerd over legbare maskers
en daarna zak-gekoppeld over het triplet. Die maat hoort vanaf nu in elke topologie- of
tripletranker; `island_table()`/`full_measure()` in `mg_anchorchain.py` en `chain_value()` in
`mg_row7.py` zijn de herbruikbare onderdelen.
