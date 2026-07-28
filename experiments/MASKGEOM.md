# MASKER x GEOMETRIE: de slotzet-maskers en de rest van het bord, gezamenlijk (2026-07-28)

Motor: `experiments/mg_maskgeom.py` (bovenop `mg_mceiling.py`, `mg_newtopo.py`, `mg_denseblock.py`).
Uitvoer: `experiments/results/maskgeom_*.json`, logs `maskgeom_*.log`.
Record bij aanvang **4778**; tijdens deze sessie tilde de nachtelijke LNS-vloot het naar **4787**
(`maxgame_BEST.json`, ankervast plafond 4889). Alle metingen hieronder staan op de basis die er
op dat moment lag; waar dat uitmaakt staat het erbij.
`maxgame_BEST.json`, `lns_best.json` en `data/boards.toml` zijn **niet** aangeraakt.

```
MODE=formal  .venv/bin/python experiments/mg_maskgeom.py  # eiland-lemma + ijking
MODE=sweep   ...                                          # alle legbare maskers per ankerrij
MODE=geo     ...                                          # ijking geometrie-evaluator
MODE=comb    NW=10 ...                                    # coordinaatstijging blokken x maskers
MODE=sa      NW=6  ...                                    # vrije SA over maskers EN bezetting
MODE=laan    NW=8  ...                                    # laan-invoeging in het recordschema
MODE=laanfit NW=6 TLIM=1800 ...                           # CP-SAT + arbiter
```

---

## 0. De vraag

`ANCHORCHAIN.md` optimaliseerde het masker uitsluitend op wat het voor de **ankerrij zelf**
oplevert (`mult*(S + DL-bonus) + keten`). `DENSEBLOCK.md` liet daarna zien dat datzelfde masker
de **rest van het bord** vastzet: de maskercellen liggen er pas na de slotzet, dus tot dan valt de
ankerrij uiteen in eilanden, en elk eiland eist een eigen dragende kolom. De opdracht was: die
koppeling formaliseren, maskers zoeken die wél aangrenzende dragers toelaten, en de winst in de
middenrijen afwegen tegen het verlies op de ankerrij.

**Uitkomst in drie regels.** Het eiland-lemma is bewezen en de maskers zijn uitputtend
doorgerekend: er zijn er maar 39 / 39 / 36 legbaar, en het recordmasker is niet alleen maximaal
in ankerwaarde maar ook **het enige rij-0-masker waarvan alle vier de gedwongen dragers een
rijke kolomtabel hebben**. Aangrenzende dragers bestaan niet — dragers uit verschillende
eilanden zijn per definitie door een maskercel gescheiden, en per eiland is er maar één nodig.
Maar de analyse legde wel bloot waar de middenrijen dan **wél** vandaan moeten komen, en dat
leverde een structuur op die alle eerdere generatoren hebben gemist.

---

## 1. Het eiland-lemma, nu als gereedschap

**Definitie.** Masker `M` = de 7 cellen die de slotzet van ankerrij `y` legt; pre-set `P = {0..14} \ M`;
de **eilanden** zijn de maximale aaneengesloten groepen van `P`.

**Lemma (dragers).** *Elk eiland eist minstens één dragende kolom, en die ligt binnen het eiland.*

> Bewijs. Alle cellen van `P` liggen op het bord vóór de slotzet. Beschouw de eerste zet die een
> cel van eiland `I` legt. Op rij `y` raakt die zet geen enkele andere tegel: de buren van `I`
> op die rij zijn maskercellen en dus leeg. Een zet moet het bord raken, dus er is een kolom
> `c in I` met een tegel op `(c, y±1)`. ∎

Voor rij 0 en rij 14 moet `{0,7,14}` in het masker zitten (anders geen ×27), dus **kolom 7 is
altijd een maskercel** en de pre-set valt altijd in ≥ 2 eilanden uiteen: het absolute minimum
is **2 dragers per ankerrij**. Voor rij 7 ligt `(7,7)` juist altijd in de pre-set (zet 1 dekt het
centrum), en dat eiland is gratis gedragen.

**Gevolg (de lexicale muur is een maskergevolg).** Een drager haalt rij 1 (resp. rij 13) en vormt
dus een verticale run over rij 0..7 (resp. 7..14): een **8-letterwoord met twee vaste
ankerletters**. Dat is precies de muur die DENSEBLOCK §2 mat. Het aantal van die woorden is dus
door de maskerkeuze bepaald, niet door de topologie.

### IJking (`MODE=formal`) — de DP reproduceert het record exact

| rij | woord | masker | eilanden | min dragers | maat = slotzet + keten |
|---|---|---|---|---:|---|
| 0 | geschenkcheques | `X..X...XX..X.XX` | `es` `hen` `he` `u` | **4** | 1693 = 1674 + 19 |
| 7 | flexwerkstertje | `XXXX........XXX` | `werkster` | **0** | 500 = 441 + 59* |
| 14 | polymelkzuurtje | `XXXX...X.....XX` | `mel` `zuurt` | **2** | 1511 = 1458 + 53 |

Rij 0 en rij 14 komen exact uit op de ANCHORCHAIN-waarden (1693 / 1511). \*Voor rij 7 geeft de
DP 59 als bovengrens bij een vrij wortelbudget; het record realiseert er 45 van (ROW7.md).

---

## 2. Alle legbare maskers, met hun geometrische rekening (`MODE=sweep`)

Uitvoer: `experiments/results/maskgeom_sweep.json`. Een masker is *legbaar* als elk eiland van
lengte ≥ 2 zelf een woord is en de eiland-DP een bouwvolgorde vindt. Dat laat er 39 (rij 0),
39 (rij 7) en 36 (rij 14) over van de 495 resp. 792 combinatorische maskers.

De kolom **arm** telt de gedwongen dragers waarvan de 8-letter kolomtabel bijna leeg is
(< 50 woorden); dat is de prijs die het masker in het lexicon betaalt. (Precisering: een drager
hoeft niet per se rij 7 te halen — een kort stuk rij 1..k met k < 6 geeft een run rij 0..k met
maar één vaste letter en is lexicaal ruim. Maar zo'n kort stuk kan zichzelf niet bezorgen: het
raakt het bord alleen via een buurkolom of een laan. Zelfdragend is alleen de volle kolom, en
daarvoor geldt de 8-letter-tabel.)

### Rij 0 (`geschenkcheques`) — de enige rij met echte vrijheid

| masker | maat | Δ rec | #dragers | arm | eilanden → beste drager (#woorden) |
|---|---:|---:|---:|---:|---|
| `X..X...XX..X.XX` **(record)** | **1693** | 0 | 4 | **0** | `[1,2]`→k2:1242 `[4,5,6]`→k5:390 `[9,10]`→k10:390 `[12]`→k12:368 |
| `X..X...XX..XX.X` (tweeling) | 1693 | 0 | 4 | 1 | … `[13]`→k13:**1** |
| `X..X...X.X.X.XX` | 1688 | −5 | 5 | 0 | `[1,2]` `[4,5,6]` `[8]` `[10]` `[12]` |
| `XX.....XX..X.XX` | 1573 | −120 | **3** | 0 | `[2..6]`→k2:1242 `[9,10]` `[12]` |
| `XX.....X.X.X.XX` | 1568 | −125 | 4 | 0 | `[2..6]` `[8]` `[10]` `[12]` |
| `XXXX..XX......X` | 1459 | −234 | **2** | 0 | `[4,5]`→k5:390 `[8..13]`→k8:450 |
| `X..XXXXX......X` | 1457 | −236 | 2 | 0 | `[1,2]`→k2:1242 `[8..13]`→k8:450 |
| `XXXXX..X......X` | 1456 | −237 | 2 | 0 | `[5,6]` `[8..13]` |

### Rij 14 (`polymelkzuurtje`) — geen vrijheid

| masker | maat | Δ rec | #dragers | arm |
|---|---:|---:|---:|---:|
| `XXXX...X.....XX` **(record)** | **1511** | 0 | **2** (het minimum) | **0** |
| `XX.XX..X.....XX` | 1504 | −7 | 3 | 1 |
| `XX....XX....XXX` | 1295 | −216 | 2 | 0 |

Het recordmasker haalt tegelijk de hoogste ankerwaarde, het minimum aantal dragers én arm 0.
Er is niets te ruilen.

### Rij 7 (`flexwerkstertje`)

| masker | maat | Δ rec | #dragers |
|---|---:|---:|---:|
| `XXXX........XXX` **(record)** | 500 | 0 | 0 |
| `XX.X....X..X.XX` | 490 | −10 | 3 |
| `XX.X....X..XX.X` | 490 | −10 | 3 |
| `XXXX....X...X.X` | 479 | −21 | 2 |

---

## 3. Het antwoord op de kernvraag: aangrenzende dragers bestaan niet

Twee dragers uit **verschillende** eilanden zijn per constructie door minstens één maskerkolom
gescheiden — ze kunnen dus nooit aangrenzend zijn. Binnen **hetzelfde** eiland is er maar één
drager nodig; een tweede kolom daarnaast is vrijwillig en is precies het "dichte blok" dat
DENSEBLOCK al lexicaal weerlegde (8-letterwoord × 8-letterwoord × zes horizontale mini-woorden,
en de bouwvolgorde sneuvelt).

Het masker biedt dus **geen** hefboom op aangrenzendheid. Wat het masker wél doet:

| mechanisme | wat het masker bepaalt | prijs |
|---|---|---|
| **drager** | hoeveel 8-letter dubbel-verankerde kolomwoorden er gedwongen zijn en in welke kolommen | verlaging kost 120 (4→3) of 234 (4→2) ankerpunten |
| **hanger** | staat een kolom onder een MASKERcel, dan herscoort de slotzet zijn hele verticale run (op x = 0/7/14 zelfs ×3) | zo'n kolom is 6 i.p.v. 7 tegels, dus geen eigen bingo (−50) |
| **keten** | de fragmentketen binnen de pre-set (`he→hen`, `uur→zuur→zuurt`) | zit al in de maat van §2 |

De maskeruitruil is daarmee **numeriek beslecht**: minder dragers kost 120–234 ankerpunten, en
de vrijgekomen 6–13 tegels leveren op het vrije halfrond ongeveer 4,2 m per cel op (gemeten
gemiddelde op het record) — bij marginale zaktegels van ~1,5 punt is dat ~8 punten per tegel,
dus 50–105 punten. Dat haalt de 120 niet, laat staan de 234.

---

## 4. Waar de middenrijen dan wél vandaan komen: de x4-LAAN OP RIJ 3

De diagnose van de opdracht klopt — de middenrijen leveren nul op — maar de oorzaak is niet de
drager-spreiding. Een tegel in een middenrij is alleen wat waard als hij in een woord met een
**woordvermenigvuldiger** ligt, en die liggen op de DWS-paren:

| rij | DWS-paar | spanwijdte | in het record |
|---|---|---:|---|
| 1 / 13 | (1,y) (13,y) | 13 | rail — weerlegd (NEWTOPO §3: de `q` van geschenkcheques heeft geen 2-letteropvolger) |
| 2 / 12 | (2,y) (12,y) | 11 | niet gebruikt |
| **3 / 11** | (3,y) (11,y) | **9** | **niet gebruikt** |
| 4 / 10 | (4,y) (10,y) | 7 | rij 4 = de bestaande x4-laan (`overzwevenden`), 217 punten |

De per-lijn-ontleding van het record laat zien hoe scheef dat is:

```
record 4787:
rij  0 1693   rij  4  217   rij  7  486   rij 14 1511
kol  2  114   kol 12   50   kol 11   47   kol  4   32   kol  7  32   kol  5  22   kol 10  21
rij  2   10   rij  8    2   alle overige rijen en kolommen: 0
```

Ankerrijen 3690 + 3 anker-bingo's 150 = **3840** (bewezen plafond 3865); alle overige lijnen
547 + 8 bingo's 400 = **947**. De negen middenrijen 1, 3, 5, 6, 9, 10, 11, 12, 13 leveren
**samen nul** — niet omdat er geen tegels liggen, maar omdat die tegels geen horizontaal woord
vormen én er geen woordvermenigvuldiger onder zit.

**De rij-3-laan is nooit op de RECORDtopologie gemeten.** De laan als idee bestaat: hij zit in de
alternatieve families `mg_ref_topo.py` / `mg_bob_topo.py` / `mg_roy_topo.py` (die op 4114-4268
bleven steken) en in `mg_newtopo.t_lanen_3_11`. Maar op de recordgeometrie meldde de oude bouwer
`auto_schedule` de topologie `ONLEVERBAAR` (hij hangt de drie slotzetten verplicht achteraan),
en de DENSEBLOCK-laanas kende alleen rij 4 en rij 10. Met de gerepareerde bouwer uit
`mg_denseblock.schedule()` — die een slotzet als gewone kandidaat behandelt zodra de rest van
zijn rij ligt — bestaat hij wél, en hij past bovendien in het *bestaande* recordschema (§6).

En hier komt het masker alsnog terug, maar **met omgekeerd teken**: de vier gedwongen dragers van
het rij-0-masker (kolommen 2, 5, 10, 12) zijn precies de **pijlers** waar een rij-3-laan aan kan
hangen. De laan raakt het bord op vier plaatsen tegelijk, dus hij is in één zet van 7 tegels
te leggen — een bingo — en hij dekt daarbij de DWS op (3,3); de run loopt van kolom 2 tot 12
(11 cellen) en herscoort onderweg elke pijlerkolom. De maskergedwongen spreiding, die
DENSEBLOCK als handicap las, is voor een laan juist de **voorwaarde**.

> **Boven/onder-asymmetrie, en die is puur maskerlogica.** Rij 0 heeft vier eilanden en dus vier
> pijlers; rij 14 heeft er twee. De bovenhelft is daarom laan-rijk en de onderhelft laan-arm.
> Gemeten: de spiegellaan op rij 11 (DWS (3,11)/(11,11), dezelfde spanwijdte 9) is los +38 waard
> en **verliest** 65 als je hem naast de rij-3-laan legt, want zonder pijlers kost hij zeven
> tegels aan opvulling die elders meer opbrachten. Een rij-14-masker met meer eilanden bestaat
> (−7 tot −11 ankerpunten voor 3 of 4 dragers, zie §2), maar elke extra onderpijler kost zes
> tegels (rijen 8..13, want hij moet rij 13 halen) en die zijn er niet: alle
> rij-14-maskervarianten scoren in `MODE=comb` 20 tot 135 plafondpunten lager.

### Gemeten (`MODE=comb`, greedy m-plafond, dezelfde bouwer op elke kandidaat)

| bezetting | m-plafond | Δ | tegels | bingo's | lijn-consistent |
|---|---:|---:|---:|---:|:--:|
| **record (referentie)** | **4657** | 0 | 101 | 10 | ja |
| + x4-laan rij 3 (kol 3..11) | **4791** | **+134** | 101 | 11 | ja |
| + laan rij 3, rij-7-masker `XX.X....X..X.XX` | **4828** | **+171** | 101 | 11 | ja |
| + laan rij 10 (kol 2..11) | 4699 | +42 | 101 | 11 | ja |
| + laan rij 11 (kol 3..11) | 4695 | +38 | 101 | 12 | ja |
| + kolom 1 boven (paar 1-2) | 4728 | +71 | 101 | 10 | ja |
| + kolom 5 onder doorgetrokken | 4721 | +64 | 101 | 12 | ja |
| + kolom 9 boven (paar 9-10) | 4720 | +63 | 101 | 12 | ja |
| + laan rij 2 (kol 2..12) | 4611 | −46 | 101 | 9 | ja |
| + kolom 0 boven | 4437 | −220 | 101 | 11 | nee |
| + kolom 13 boven | 4459 | −198 | 101 | 11 | nee |

De m-boekhouding wijst de winst exact aan (m-som van de vrije cellen per rij):

```
record :  rij1 14  rij2 15  rij3 12  rij4 68  rij5 16  rij6 18  rij8 19  rij9 10  ...
+laan3 :  rij1 10  rij2 15  rij3 69  rij4 84  rij5 10  rij6 11  rij8 14  rij9  6  ...
```

Rij 3 springt van 12 naar 69 m-eenheden en trekt rij 4 mee van 68 naar 84 (de nieuwe rij-3-cellen
verlengen de kolomrunnen die rij 4 kruist). Betaald wordt met zeven tegels uit de rijen 5, 6, 9
en 10, die daar 4,2 m per cel deden.

---

## 5. Wat het rij-7-masker doet (+37 bovenop de laan)

Het beste alternatief is `XX.X....X..X.XX` = `{0,1,3,8,11,13,14}` (maat 490, dus −10 op de
ankerrij). Het verschil met het recordmasker `{0,1,2,3,12,13,14}`:

* `(2,7)` en `(12,7)` verhuizen naar de **pre-set** — die kolommen worden dus vroeger doorgetrokken;
* `(8,7)` en `(11,7)` worden **maskercellen** — de rij-7-slotzet herscoort daardoor de verticale
  run van kolom 11 (rijen 7..13) én kolom 8, bovenop de ×9 van de rij zelf.

Netto op het greedy-plafond: **+37** tegen −10 ankerpunten. Dit is precies het *hanger*-mechanisme
uit §3, en het is de enige plaats waar een maskerwissel in dit onderzoek positief uitpakt.

Alle doorgerekende maskerwissels (greedy m-plafond, `maskgeom_comb.json`):

| maskerwissel | zonder laan | met laan (L3) | ankerkosten |
|---|---:|---:|---:|
| **geen (recordmaskers)** | **4657** | **4791** | 0 |
| rij 7 → `XX.X....X..X.XX` | 4699 | **4828** | −10 |
| rij 7 → `X.XX....X..X.XX` | **4745** | 4790 | −10 |
| rij 7 → `X.XX....X..XX.X` | 4711 | 4743 | −10 |
| rij 7 → `XX.X....X..XX.X` | 4661 | 4763 | −10 |
| rij 0 → `X..X...X.X.X.XX` (5 dragers) | 4708 | 4743 | −5 |
| rij 0 → `X..X...XX..XX.X` (tweeling) | 4696 | 4702 | 0 |
| rij 0 → `XX.....XX..X.XX` (3 dragers) | 4526 | 4686 | −120 |
| rij 0 → `XX.....X.X.X.XX` | 4582 | 4672 | −125 |
| rij 14 → `XX.X..XX.....XX` (3 dragers) | 4721 | 4750 | −7 |
| rij 14 → `X.XX..XX.....XX` | 4712 | 4693 | −7 |
| rij 14 → `XX.XX..X.....XX` | 4604 | 4629 | −7 |

**Elke rij-0-maskerwissel verliest**, ook de gratis tweeling. Rij 14 en rij 7 leveren kleine
winsten die de greedy-ruis (±40) nauwelijks overstijgen; alleen de rij-7-wissel is met de laan
erbij consistent positief. De maskerkeuze van het record blijft dus staan.

---

## 6. De laan in het RECORDSCHEMA invoegen — waar de winst echt zit

De greedy bouwer is op de recordbezetting 224 plafondpunten zwakker dan het handgemaakte
recordschema (4657 tegen 4881). Alle getallen in §4 zijn dus *relatieve* metingen; om er een
bord uit te halen moet de laan in het **bestaande** schema. Dat kan, want het tegelbudget heeft
precies genoeg speling: het record heeft **negen losse vrije tegels** (zetten van één tegel
buiten de ankerrijen) — `(11,4) (11,2) (2,8) (2,9) (2,10) (10,8) (13,4) (5,8) (14,4)` — en verder
alleen bingo's van 7. Zeven daarvan weghalen kost geen enkele bingo; de rij-3-laan legt er zeven
terug en is zelf een bingo (**12 bingo's** in plaats van 11).

Uitputtende sweep over alle verwijderings-deelverzamelingen × alle invoegposities
(`experiments/results/maskgeom_insert3.json`), met `T.legal` + `words_ok` + `diagnose` als eis:

| variant | plafond | Δ record | tegels | bingo's | lijn |
|---|---:|---:|---:|---:|:--:|
| **record 4787 + rij-3-laan `(3,3)(4,3)(6,3)(7,3)(8,3)(9,3)(11,3)` op positie 6** | **4944** | **+55** | 101 | **12** | schoon |
| record 4787 (referentie, plafond) | 4889 | 0 | 101 | 11 | schoon |
| record 4778 + dezelfde laan, positie 6 | 4944 | +63 | 101 | 12 | schoon |
| record 4778 (referentie) | 4881 | 0 | 101 | 11 | schoon |

Betaald wordt met `(2,8) (2,9) (2,10) (2,11) (10,8) (11,2) (14,4)` — dat is de hele
kolom-2-extensieketen. De laan verdient dat terug en meer.

**De invoegpositie is beslissend, en wel om precies één reden.** Op positie 6 ligt de laan
*vóór* kolom 2, dus de zet legt zowel `(3,3)` als `(11,3)` **nieuw** — de twee DWS — en de run
kolom 3..12 scoort dan **×4** over tien cellen. Wordt hij later gelegd (positie 7 of 8), dan is
een van de twee al bezet en blijft er ×2 over: 4925 in plaats van 4944. Zo scherp is het.

De laan-sweep over ALLE rijen en alle spanwijdtes (`maskgeom_laansweep.json`, per rij het
beste resultaat) laat zien hoe eenzaam die rij is:

| laan | plafond | Δ | bingo's |
|---|---:|---:|---:|
| **rij 3, kolommen 2..11** | **4944** | **+55** | 12 |
| rij 4, kolom 1 erbij (verlenging van de bestaande laan) | 4918 | +29 | 11 |
| rij 1, kolom 11 erbij | 4906 | +17 | 11 |
| rij 6, kolommen 2..4 | 4903 | +14 | 11 |
| alle overige rijen/spanwijdtes | ≤ 4889 | ≤ 0 | — |

Combineren helpt niet: rij-3-laan + `(1,4)` haalt 4925 (de achtste verwijderde tegel kost meer
dan de negende oplevert), en `maskgeom_laan3plus.json` vindt geen enkele combinatie boven 4944.

> **Het tegelbudget is aantoonbaar krap.** Geen enkele volle kolom kan weg om de laan te betalen:
> kolom 2/5/10/12 zijn de gedwongen rij-0-dragers, kolom 4/11 de gedwongen rij-14-dragers,
> kolom 7 is de centrumzet — en 2, 5, 10, 12 zijn bovendien precies de kolommen waar de rij-3-laan
> op steunt. Dat is het eiland-lemma dat zichzelf sluit: de dragers die het masker afdwingt zijn
> onmisbaar én dubbel nuttig.

## 6b. Realisatie: van plafond naar geverifieerd spel

De laatste stap is de dure: elke gescoorde run krijgt een `add_allowed_assignments`-tabel, de zak
is een telbeperking, hoogstens twee blanco's, doelfunctie = de score, en `MG.score_game` is de
arbiter. Twee praktische lessen uit deze ronde:

* **Het volle model is te groot.** Met een 11-letter rij-3-run en een 12-letter rij-4-run erbij
  loopt het model op tot 4-5·10⁵ variabelen en ~5·10⁶ clauses; CP-SAT is dan na 700 s nog steeds
  in presolve. Daarom `fit_hint` (warme start met het recordbord) en, beslissend, de **lokale**
  invulling: alle cellen buiten de runs die een nieuwe cel raken houden gewoon hun recordletter.
  Dat is legitiem omdat die lijnen ongewijzigd zijn en al geverifieerd waren.
* **`mg_newtopo.fit` gebruikt zijn `hint`-argument niet** (het staat in de signatuur en wordt
  nergens aangeroepen). Op modellen van deze omvang is dat de grootste enkele kostenpost.

### De laan dwingt een HERLETTERING van de hele bovenhelft af

De lokale invulling met `ring=1` (23 vrije cellen: rij 3, rij 4 en de cellen die daar direct aan
vastzitten) is **INFEASIBLE**, en de oorzaak is exact aan te wijzen. De vier pijlerkolommen
staan op rij 3 met de recordletters `kol 2 = r`, `kol 5 = d`, `kol 10 = d`, `kol 12 = a`, dus de
rij-3-run kolom 2..12 moet het patroon `r??d????d?a` waarmaken:

```
rij 3, kolommen 3..12  = ??d????d?a   ->      0 woorden
rij 3, kolommen 2..12  = r??d????d?a  ->      0 woorden
rij 3, volledig vrij   = ??????????? ->  155.658 woorden (11 letters)
```

Van de 35.216 pijlersignaturen `(kol2, kol5, kol10, kol12)` die wél een 11-letterwoord toelaten,
is de recordsignatuur `rdda` er geen. De laan is dus niet lokaal in te passen: hij eist dat de
vier pijlerkolommen zelf worden herletterd (elke pijler heeft honderden alternatieve
8-letterwoorden — kolom 2: 1242, kolom 5: 390, kolom 10: 390, kolom 12: 368 — dus de ruimte is
er ruimschoots). Daarmee wordt het een globaal invulprobleem: rij 3, rij 4 en de vier
pijlerkolommen tegelijk.

### Het eindbord van de rij-3-laan BESTAAT (CP-SAT OPTIMAL)

`static_feasible` op de 18 maximale eindruns van de laan-bezetting is **OPTIMAL** — er is dus een
letterinvulling waarin elk woord van het eindbord klopt. De getuige (zonder zak- of
scorebeperking, alleen het lexicon):

```
    0 g e s c h e n k c h e q u e s      rij  3  bodeverhaal   (kol 2..12)
    1 . . y . . d . . . . n . i . .      rij  4  isolatieglas  (kol 2..13)
    2 . . m . . i . . . . g . t . .      kol  2  symbiose      (rij 0..7)
    3 . . b o d e v e r h a a l . .      kol  5  editjes-achtig
    4 . . i s o l a t i e g l a s .      kol 10  engagere
    5 . . o . . t . t . . e . n . .      kol 12  uitlangt
    6 . . s . . j . e . . r . g . .      kol  7  everstsk?  (rij 3..10)
    7 f l e x w e r k s t e r t j e      kol  4  werpriem   (rij 7..14)
    8 . . . . e . . e . . . o . . .      kol 11  rookwaar   (rij 7..14)
    9 . . . . r . . n . . . o . . .
   10 . . . . p . . s . . . k . . .      de hele bovenhelft is HERLETTERD:
   11 . . . . r . . . . . . w . . .      'overzwevenden' wordt 'isolatieglas'
   12 . . . . i . . . . . . a . . .
   13 . . . . e . . . . . . a . . .
   14 p o l y m e l k z u u r t j e
```

Daarmee is de bezetting **niet** langs de weg van DENSEBLOCK weerlegd: het eindbord bestaat, en
in tegenstelling tot de dichte blokken is er ook een lijn-consistent zetschema (`diagnose` leeg)
met 12 bingo's. Wat overblijft zijn de twee laatste horden: de **tijdelijke runs** van het
zetschema en de **zak**.

### De hoogste variant sneuvelt op de tijdelijke runs — de op één na hoogste niet

| invoegpositie | plafond | runs | `lex_feasible` (zuiver lexicaal, geen zak) |
|---:|---:|---:|:--|
| 6 (vóór kolom 2) | **4944** | 41 | **NEE** (CP-SAT INFEASIBLE, 900 s) |
| 7, 10, 14, 18, 22 (ná kolom 2) | **4925** | 40 | **JA** |
| pos 7 + ladderverfijning | 4960 | — | ONBEKEND (niet weerlegd, 400 s) |

De oorzaak van dat verschil is precies het mechanisme dat positie 6 zo aantrekkelijk maakte. Daar
ligt de laan vóór kolom 2, dus de rij-3-run is op dat moment kolom 3..12 (**tien** letters) en
wordt daarna door de kolom-2-zet uitgebreid tot kolom 2..12 (**elf** letters) — twee
scoringsgebeurtenissen in plaats van één, +19 plafond. Maar dan moet rij 3 tegelijk een
10-letterwoord én diens 1-letter-uitbreiding zijn, en dát bestaat niet. Vanaf positie 7 ligt
kolom 2 er al: de laan maakt in één keer de run kolom 2..12, nog steeds met **beide** DWS nieuw
(dus ×4 over elf cellen), en de dubbele-woord-eis vervalt.

**Stand van zaken.** De bezetting is niet weerlegd en het zetschema evenmin: plafond **4925**
(+36 op het recordplafond 4889), 12 bingo's, `diagnose` leeg, `static_feasible` OPTIMAL,
`lex_feasible` **JA**. Wat rest is de zak plus de doelfunctie — en dat is precies de stap die
op dit model (4-5·10⁵ variabelen) urenwerk is. De realisatiegraad die nodig is om 4787 te
verslaan is 4788/4925 = **97,2 %**; het record zelf realiseert 4787/4889 = **97,9 %**.

### Wat er nog draaide bij het afsluiten

De laatste stap — zak + doelfunctie op het volle model — is niet afgerond binnen deze sessie.
Draaiende/afgeronde runs en hun logbestanden:

| run | wat | log |
|---|---|---|
| `witnessfit` | volle CP-SAT-vulling met de **eindbord-getuige** als warme start, posities 6/7/8 | `maskgeom_witnessfit.log` |
| `pos7ladder` | ladderverfijning van het pos-7-schema (plafond 4960) + lex-toets | `maskgeom_pos7ladder.log` |
| `scorebound` | lexicaal-bewuste BOVENGRENS op de score (eindruns + zak, tijdelijke runs gerelaxeerd), laan versus record | `maskgeom_scorebound.log` |
| `laanfitpos` | `MODE=laanfit` over de vijf levende posities | `maskgeom_laanfitpos.log` |

**Er is in deze sessie geen bord boven 4787 geproduceerd.** `maxgame_BEST.json` en `lns_best.json`
zijn ongewijzigd; alle uitvoer staat in `experiments/results/maskgeom_*`.

Reproduceren van de kandidaat in één regel:

```
MODE=laan    NW=8 .venv/bin/python experiments/mg_maskgeom.py        # -> maskgeom_laansweep.json
MODE=laanfit NW=5 TLIM=2400 LEX=1 IN=experiments/results/maskgeom_laanpos.json \
             .venv/bin/python experiments/mg_maskgeom.py             # -> arbiter
```

---

## 7. Conclusie

1. **Het eiland-lemma is bewezen en operationeel.** Elk eiland van de pre-set eist minstens één
   dragende kolom binnen dat eiland; kolom 7 ligt altijd in het masker van rij 0/14, dus er zijn
   altijd ≥ 2 dragers per x27-rij. `mg_maskgeom.islands / min_supports / support_domains /
   mask_value` maken dat berekenbaar, en de ketensom reproduceert de ANCHORCHAIN-waarden exact.
2. **De vraag "welk masker laat aangrenzende dragers toe" heeft een negatief antwoord met bewijs.**
   Dragers uit verschillende eilanden zijn per constructie door een maskercel gescheiden; binnen
   één eiland is er maar één nodig, en een tweede ernaast is exact het dichte blok dat DENSEBLOCK
   al lexicaal weerlegde. Er is geen masker dat hier iets aan verandert.
3. **Het recordmasker is ook geometrisch optimaal, niet alleen in ankerwaarde.** Van de 39
   legbare rij-0-maskers is het (samen met zijn tweeling) het enige dat 1693 haalt, en het enige
   waarvan **alle vier** de gedwongen dragers een rijke 8-letter kolomtabel hebben (kolom 2:1242,
   5:390, 10:390, 12:368; de tweeling zit vast aan kolom 13 met **één** woord). Rij 14 idem:
   maximale waarde, minimaal aantal dragers, arm 0. Minder dragers kost 120 (4→3) of 234 (4→2)
   ankerpunten en levert 6–13 tegels op die op het vrije halfrond ~8 punten per stuk doen — dat
   haalt het niet.
4. **Het masker stuurt de rest van het bord wél, maar via de PIJLERS, niet via aangrenzing.** De
   vier gedwongen rij-0-dragers staan op kolom 2, 5, 10 en 12 en kruisen daarmee elke bovenrij op
   vier plaatsen. Dat is precies wat een **x4-laan** nodig heeft om in één bingo-zet gelegd te
   kunnen worden. De rij-14-kant heeft maar twee pijlers en is daarom laan-arm — de boven/onder-
   asymmetrie van het record is een direct maskergevolg.
5. **De concrete opbrengst is de x4-laan op rij 3** (DWS `(3,3)` en `(11,3)`, spanwijdte 9), die
   in geen enkele eerdere generator kon bestaan omdat `mg_newtopo.auto_schedule` de slotzetten
   verplicht achteraan hangt en de topologie `ONLEVERBAAR` noemde. Met de gerepareerde bouwer is
   hij +134 waard op het greedy-plafond en **+55 op het ankervaste plafond van het echte
   recordschema** (4889 → 4944, 12 bingo's in plaats van 11), betaald met de zeven losse tegels
   van de kolom-2-extensieketen.

6. **Van die laan is de hoogste variant weerlegd en de op één na hoogste niet.** Invoegpositie 6
   (plafond 4944) eist dat rij 3 tegelijk een 10-letterwoord en diens 1-letter-uitbreiding is;
   `lex_feasible` zegt daar **NEE**. De posities 7 en later (plafond **4925**, +36 op het
   recordplafond, 12 bingo's) zeggen **JA**, en het eindbord is zelfs OPTIMAL invulbaar
   (`bodeverhaal` / `isolatieglas` over de herletterde bovenhelft). De laatste horde — zak plus
   doelfunctie op een model van 4-5·10⁵ variabelen — is binnen deze sessie niet genomen.
7. **Wat de volgende ronde moet doen.** (a) `MODE=laanfit` op `maskgeom_laanpos.json` afmaken met
   ruime tijd en de eindbord-getuige als hint; (b) de laan-invoeging combineren met de
   LNS-vloot in plaats van ernaast — de vloot herlettert, deze motor herstructureert, en dat zijn
   complementaire zetten; (c) `MODE=laan` na elke recordverbetering opnieuw draaien, want de
   losse-tegel-voorraad (de betaalmiddelen) verschuift mee.

> **Waarschuwing voor wie hierop doorbouwt.** Het m-plafond blijft misleidend: van de vier
> laan-varianten met plafond > 4900 is er één lexicaal dood (pos 6), één CP-SAT-infeasible
> (rij-4-verlenging, 4918) en één lex-dood (rij 1, 4906). Alleen de rij-3-laan vanaf positie 7
> overleeft beide toetsen. Draai `lex_feasible` vóór elke CP-SAT-vulling — hij is honderd keer
> goedkoper en weerlegt het merendeel.

---

## 8. Gereedschap dat dit spoor achterlaat

| functie in `mg_maskgeom.py` | wat het doet |
|---|---|
| `islands(mask)` / `min_supports(mask,y)` / `support_domains` | het eiland-lemma, expliciet en berekenbaar |
| `chain_island(w,y,cols,maxroots)` | exacte deelverzameling-DP: ketenwaarde én wortelkosten van één eiland |
| `mask_value(w,y,mask)` | `mult*(S + LM-bonus) + keten`, de volledige ankerrij-maat per masker |
| `all_masks(y)` / `sweep_row(y)` | uitputtende maskerenumeratie met legbaarheidsfilter |
| `gaps_of(cells,masks)` | bezorgbaarheidszeef, parametrisch in het masker (i.p.v. hard-coded) |
| `repair_supports` / `trim_cells` | een bezetting drager-compleet en cap-conform maken |
| `joint_search` | simulated annealing over MASKERS en BEZETTING tegelijk |
| `solo_cells` / `insert_group` | de losse tegels van een schema en het invoegen van een groep |
| `main_laan` (`MODE=laan`) | sweep over alle lanen × verwijderingen × invoegposities |
| `fit_hint` | CP-SAT-invulling **met warme start** (`mg_newtopo.fit` negeert zijn `hint`-argument) |

Twee dingen zijn breder bruikbaar dan dit spoor:

* **`MODE=laan` is een generieke laatste-loodjes-motor.** Hij vraagt niet "welke topologie is het
  beste" maar "welke aaneengesloten groep kan ik in het bestaande recordschema invoegen, betaald
  met de goedkoopste losse tegels, en op welke plek in de zetvolgorde?" Dat is precies de vraag
  die de LNS-vloot niet stelt (die permuteert letters en kleine zetten, niet structuren).
* **`fit_hint`.** Op modellen van 4-5·10^5 variabelen is de koude start van `mg_newtopo.fit` de
  belangrijkste kostenpost; hinten met het referentiebord is gratis en zou overal moeten worden
  gebruikt waar een verwante bezetting al ingevuld is.
