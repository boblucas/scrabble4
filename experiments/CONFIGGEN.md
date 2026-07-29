# CONFIGURATIE-GENERATOR — structuurparameters in plaats van celmutaties

Gereedschap: `experiments/mg_configgen.py`. Referentiepunten: record **4793**
(`experiments/results/maxgame_BEST.json`), doel **>= 4819**, harde bovengrens van het
recordvoetafdruk **4889**.

Aanleiding (zie `experiments/FRAME_CAMPAIGN.md`, laatste secties): de LNS-vloot muteert
celverzamelingen van 1-7 cellen en blijft daardoor in hetzelfde dal — gemeten over 24
willekeurige mutaties op het 4793-bord stranden er 13 bij de bouw, komen er 11 leeg uit de
solver en haalt er **nul** de arbiter. Die trefkans is inherent, geen instelfout. Deze module
somt daarom niet celverzamelingen op maar de **structuurparameters** waaruit het bord in
werkelijkheid is opgebouwd.

---

## 1. De parameterisering

### 1.1 Wat vastligt (bewezen, niet opnieuw opgesomd)

| vast | bewijs |
|---|---|
| triplet `geschenkcheques` / `flexwerkstertje` / `polymelkzuurtje` op rij 0 / 7 / 14 | LETTERBUDGET.md: 476 kandidaten getoetst, 291 bewezen infeasible, 0 boven het record; wisselkoers 0,31 restpunt per ingeleverd ankerpunt (break-even 1,00) |
| de drie slotmaskers `REC` = rij 0 {0,3,7,8,11,13,14}, rij 7 {0,1,2,3,12,13,14}, rij 14 {0,1,2,3,7,13,14} | MASKGEOM.md: uitputtende sweep over 39/39/36 legbare maskers; ons masker is het enige rij-0-masker waarvan alle vier de gedwongen dragers een rijke 8-letter-kolomtabel hebben |
| tegelcap 101 (45 ankercellen + 56 vrije cellen) | de zak: 100 lettertegels + 2 blanco's, waarvan het triplet er 45 opeist |

### 1.2 De vrije assen

Een configuratie is een **bezetting** (welke van de 225 cellen liggen er aan het eind), opgebouwd
uit onderdelen die elk een eigen rol in de bouwvolgorde hebben:

| as | domein | motivering |
|---|---|---|
| **laan** | geen, of (rij, x0, x1) met rij in 1..6 of 8..13, x0 in {0,2,4}, x1 in {10,12,14} | een horizontale laan is het enige dat de middenrijen laat scoren; MASKGEOM's laan-sweep vond alleen rij 1/3/4/6 positief. Hoogstens één laan per band: twee lanen kosten ~16 tegels en passen niet naast zes volle dragers. |
| **kolom 7** | boveninterval [a,6] (a in 1..6) en/of onderinterval [8,b] (b in 8..13); 48 combinaties | zet 1 moet (7,7) dekken en dat kan alleen met een verticaal door het centrum |
| **rij-0-dragers** | één kolom per pre-eiland {1,2} {4,5,6} {9,10} {12}: 2x3x2x1 = 12 keuzes | EILAND-LEMMA (MASKGEOM.md): de maskercellen komen pas in de slotzet, dus de pre-set van rij 0 valt in vier eilanden uiteen, en elk eiland kan alleen via een kolom worden aangeraakt — er moet dus een tegel op (x,1) liggen met x in dat eiland |
| **drager-dieptes (boven)** | per drager: `full` (rijen 1..6), `stub` (rijen 1..r-1, hangt aan de laan), `thru d` (rijen 1..6 + 8..d, d in 8..13) — 8 opties | de kolom-2-keten van het record is precies `thru11` |
| **rij-14-dragers** | één kolom per pre-eiland {4,5,6} {8..12}: 3x5 = 15 keuzes | idem, met (x,13) |
| **drager-dieptes (onder)** | `full` (8..13), `stub` (r+1..13), `thru a` (a..6 + 8..13) — 8 opties | |
| **extra kolommen** | 0 of 1 extra kolom met [a,6] of [8,b] | rij-7-hangers |
| **laanhangers** | 0-3 losse cellen direct boven/onder de laan | het (11,3)-mechanisme van het record |
| **peel** | 0..12 bladcellen die pas NA de slotzetten een voor een worden gelegd | de extensieketen: elke zo'n zet herscoort de hele run (kolom 2 groeide zo van 8 naar 12 letters) |

### 1.3 IJKING — het record is een punt van de opsomming

`MODE=calib` reconstrueert het recordbord uit de parameters:

```
record: 101 tegels; parameterisering geeft 101 (IDENTIEK)
  kolommen: {2:[(1,6),(8,11)], 3:[(4,4)], 4:[(4,4),(8,13)], 5:[(1,6)], 6:[(4,4)],
             7:[(4,6),(8,10)], 8:[(4,4)], 9:[(4,4)], 10:[(1,6)], 11:[(3,4),(8,13)],
             12:[(1,6)], 13:[(4,5)], 14:[(4,4)]}
  F1 OK  F2 OK  F3 OK
  plafond van het ECHTE recordschema : 4889 (gerealiseerd 4793)
  plafond van het GEBOUWDE schema    : 4860  (peel=0, 34 zetten, 11 bingo's)
  diagnose (lijnconsistentie): schoon
  IJKING skelet in de opsomming: JA
     laan (4,2,14) | c7 ((4,6),(8,10)) | sup0 (2,5,10,12) | sup14 (4,11)
     top ('thru11','full','full','full') | bot ('full','full')   -> 54 tegels
  IJKING record volledig (skelet + hangers): JA   hangers ((11,3),(13,5))
```

Het record is dus **skelet (54 tegels) + twee laanhangers**, en de eigen schemabouwer haalt op
die bezetting 4860 van de 4889 die het echte recordschema haalt. Die systematische
onderschatting van ~29 punten is de prijs van een greedy bouwer en is voor *rangschikken* geen
bezwaar.

---

## 2. De filterketen

Oplopend in kosten, met de zak **vroeg** (zie `FRAME_CAMPAIGN.md`: "de m-plafondmaat is
zak-BEWUST maar niet zak-LEXICAAL; dat verschil kostte vier veelbelovende kandidaten").

| # | filter | kosten | wat het test |
|---|---|---|---|
| F0 | tegelbudget | ~1 us | 45 + <=56 cellen; incrementeel bijgehouden met bitmaskers per kolom |
| F1 | vorm | 26 us | geen zwevende cel buiten de ankerrijen |
| F2 | eiland/bezorging | 32 us | elk pre-eiland van rij 0/14 heeft een drager; elke vrije cel hangt via vrije cellen aan rij 7 (rij 0 komt pas in de slotzet, dus daaraan hangen telt niet) |
| F3 | **zak-lexicaal per run** | 100 us | voor elke maximale run van het eindbord: bestaat er een woord dat op de vaste ankerletters past *en* waarvan de vrije posities uit de RESTZAK (55 tegels + 2 blanco's, na aftrek van de 45 ankerletters) te bouwen zijn. Strikt sterker dan `table_nonempty`, even duur (gecachet op (lengte, ankerpatroon)) |
| F4 | schema | 4,3 ms | greedy bouwer met de slotzetten als gewone kandidaten (zoals `mg_denseblock.schedule`; `mg_newtopo.auto_schedule` hangt ze altijd achteraan en verwerpt daarmee bezettingen die bestaan, waaronder het record zelf), twee peel-dieptes |
| F5 | m-plafond | in F4 begrepen | exacte zak-bovengrens van het m-profiel |
| F6 | lijnconsistentie | ~30 ms | `mg_newtopo.diagnose`: alle runs op één lijn moeten door EEN woord gedekt worden — de rem op de ladderillusie |
| F7 | CP-SAT + arbiter | minuten | `mg_newtopo.fit` + `MG.score_game`; alleen `ok=True` telt |

---

## 3. Wat de ijking meteen leerde: het m-plafond discrimineert niet meer

Het recordskelet (54 tegels) heeft binnen het tegelbudget **192 verschillende afrondingen tot 56
tegels** (extra kolom of laanhangers). Alle 192 zijn door de volle keten gehaald:

```
F3 zak-lexicaal   : 0 van de 192 gedood
F4 schema         : 192 van de 192 gebouwd
F6 lijnconsistent : 178 schoon, 14 vuil
verfijnd plafond  : 4880 .. 4909   (record zelf: 4904; gerealiseerd: 4793)
correlatie zeef-plafond ~ verfijnd plafond: 0,47
```

Dat is de belangrijkste meting van deze module, en ze is campagne-relevant:

> **Het m-plafond heeft in dit stadium zijn onderscheidend vermogen verloren.** 192 buren van het
> record liggen allemaal binnen 30 plafondpunten van elkaar, terwijl het record 110 punten
> ONDER zijn eigen plafond realiseert. Het plafond meet de geometrie; wat de score bepaalt is de
> lexicale/zak-invulbaarheid. Ranken op plafond is dus vrijwel ranken op ruis.

Nuance, gemeten over alle 40+ geverifieerde borden in `experiments/results/` (score 4482-4793):
over die volle breedte correleert het plafond wél sterk met de score (**0,70**), en het aantal
bingo's zwak (0,21); binnen de topband keert dat om. Het plafond is dus een goede GROVE zeef
tussen topologieën en een slechte FIJNE zeef binnen een topologie. Ook zichtbaar in diezelfde
tabel: elke score boven 4700 heeft precies 101 tegels — vandaar `TMIN=TMAX=56` in fase 1.

Twee consequenties voor de opzet:
1. de keuze van wat er naar CP-SAT gaat gebeurt op **structurele spreiding** (`pick_diverse`:
   hoogstens N configuraties per (laan, rij-0-dragers, rij-14-dragers)) in plaats van puur op
   plafond;
2. de beslissende toets is niet de maximaliserende `fit` maar de **beslissingsvorm**
   `fit_decide(schema, target=4794)`: bestaat er een lettering die BOVEN het record uitkomt?
   INFEASIBLE is dan een bewijs dat die bezetting met dat schema het record niet haalt, en het
   is veel sneller dan het optimum zoeken.

Als extra bevestiging: `mg_denseblock.static_feasible` op de recordbezetting (15 maximale runs)
komt in 30 s **niet** tot een oordeel — de zuiver lexicale vraag is op dit bord al hard. Een
goedkope lexicale zeef tussen F3 en CP-SAT bestaat dus niet.

### De beslissingsvorm werkt wél, en is snel

`fit_decide(schema, target)` legt `score >= target` op in plaats van te maximaliseren.
Geijkt op het recordschema zelf:

```
zonder hint, target 4793, 240 s  -> JA   (226 s; arbiter 4793, ok=True)
met    hint, target 4793, 180 s  -> JA   (170 s; arbiter 4793, ok=True)
        (150 s is te kort: dan ONBEKEND -- de tijdslimiet is de bindende parameter)
```

Op de vier best gerangschikte record-buren (plafond 4906-4909), elk met TWEE schema's
(geladderd en greedy), luidt het oordeel bij target 4794 acht van de acht keer **NEE** in
130-230 s. Dat is geen schatting maar een bewijs per (bezetting, schema): binnen die
bezetting en dat schema bestaat er geen lettering boven 4793.

### Wat er NIET knelt: het klinkerbudget

De restzak is `n9 e8 a6 d5 o5 i4 b2 g2 m2 r2 s2 t2 v2 f1 p1 w1 z1` = 55 tegels over een
17-letterig alfabet, waarvan 23 klinkers, plus 2 blanco's. De verticale runs zijn onderling
disjunct, dus hun minimale klinkerbehoefte telt op tot een geldige ondergrens (`f3b_vowels`).
Gemeten: de recordbezetting heeft er **10** van de 25 nodig, en over 1581 configuraties is de
kill-rate **0**. Het klinkerbudget is dus niet bindend; die zeef staat standaard uit
(`VOWEL=1` zet hem aan).

## 3a. Twee lanen met korte dragers — een EERSTE conclusie die is INGETROKKEN

De campagne heeft lanen altijd als TOEVOEGING op volle dragers geprobeerd, en die zijn allemaal
zak-infeasible. Deze parameterisering laat een variant toe die nooit geprobeerd is: **korte
(laan-gewortelde) dragers plus twee lanen**, dus verticale structuur RUILEN tegen horizontale bij
gelijk tegelaantal (`MENU=stub`, lanen op rij 4 en rij 10, dragers 2/5/10/12 en 4/11).

Een eerste meting gaf 4723 / 4784 / 4826 tegen 4860 voor het record, en daaruit werd geconcludeerd
dat het spoor dood was omdat het bingo's mist. **Die conclusie was fout en is ingetrokken.**

### De eerste fout: een oneerlijke tegelvergelijking

De drie stub-varianten gebruikten 93, 97 en 97 tegels; het record 101. Ze afgerond tot dezelfde
**56 vrije cellen** (met extra kolommen en laanhangers, 2500 varianten doorgerekend):

| configuratie | vrije cellen | plafond |
|---|---|---|
| twee lanen + stubs (eerste, oneerlijke meting) | 48 / 52 | 4723 / 4826 |
| **twee lanen + stubs, afgerond tot vol budget** | **56** | **4871** |
| record, met dezelfde bouwer gemeten | 56 | 4860 |

Bij gelijke tegelinzet is het twee-lanen-spoor dus **niet slechter maar iets beter** dan het
record. Het spoor is springlevend en krijgt een eigen sweep (fase C).

### De tweede fout: 'bingo's domineren' klopt niet

De per-zet-scores van het record (`MG.score_game`) weerleggen het rechtstreeks:

```
kolom-2-keten : bingo 'smarots'          106 punten / 7 tegels
                (2,8) 'smarotsen'         16
                (2,9) 'smarotsend'        17
                (2,10) 'smarotsende'      18
                (2,11) 'smarotsenden'     19
                --------------------------------------------
                samen                    176 punten / 11 tegels = 16,0 per tegel  (en OPLOPEND)

de zeven gewone bingo's  60 73 74 84 87 106 109 138 -> 625 / 49 tegels = 12,8 per tegel
de overige 31 losse tegels                          -> 415 / 31 tegels = 13,4 per tegel
de drie slotzetten       521 + 1724 + 1508          -> 3753 / 21 tegels = 179 per tegel (vast)
```

**Een verlengketen levert per tegel meer op dan een extra bingo**, want elke verlenging herscoort
de hele (steeds langere) run terwijl een bingo maar één keer scoort plus 50 bonus. De juiste
dominante grootheid is niet het aantal bingo's maar de **herscoringsmassa op lange, hoog-
vermenigvuldigde runs**.

### Wat de aanname WEL vraagt: lexicale ketenbaarheid

Een keten eist dat élke tussenstand een woord is (`smarots` -> `smarotse` -> `smarotsen` ->
`smarotsend` -> `smarotsende` -> `smarotsenden`), en dat is zeldzaam. Daarom is er nu een
goedkope voorzeef, `chain_len(run, kant, maxL)`: het grootste L waarvoor er een woord bestaat dat
op de ankerletters past én waarvan de L opeenvolgende afkappingen ook woorden zijn die op hún
ankerletters passen. Gecachet op (lengte, ankerpatroon, kant), dus enkele honderden patronen.

`ext_potential(bezetting)` telt dat per verticale run op, begrensd door het aantal cellen dat aan
die kant daadwerkelijk afpelbaar is. Gemeten:

```
record            : ext_potential 10  (kolom 2 tail L=4, kolom 7 tail L=3 en head L=3)
                    kolom 2 is lexicaal zelfs tot L=8 ketenbaar -- de bezetting is de rem, niet het lexicon
twee lanen + stubs: ext_potential 28-31
correlatie ext_potential ~ plafond binnen die familie: 0,35
```

De as zit nu in de generator (`RANKW=<gewicht>` telt hem mee in de rangschikking).

### Wat NIET de fout was

De eerste meting is wél met peel-varianten gedaan (`peels=(0,4,8)`), dus het verschil kwam niet
doordat de verlengketens waren uitgezet. Ter controle het plafond per peel-diepte:

```
record             : peel 0 -> 4860, 2 -> 4860, 4 -> 4796, 6 -> 4796, 8 -> 4792
twee lanen + stubs : peel 0 -> 4715, 2 -> 4723, 4 -> 4723, 6 -> 4723
```

De greedy bouwer maakt na de bingo's al vanzelf zo klein mogelijke zetten en legt de ketens dus
zelf; expliciet peelen voegt op het record niets toe. Het vermoeden dat peel=0 de oorzaak was, is
daarmee weerlegd — de oorzaak was de tegelvergelijking.

## 3b. Fase A — de volle enkellaans sweep (56 tegels), 16,2 CPU-uur

109 laan-opties, uitputtend over kolom 7 (48), de vier rij-0-dragers (12 keuzes x dieptes), de
twee rij-14-dragers (15 keuzes x dieptes), met precies 56 vrije cellen.

```
knopen (opgesomde parameterpunten)     337.798.080
F0 tegelbudget (!= 56 vrije cellen)    311.821.416   ( 92,3 % )
F2 onbereikbaar                             38.220
F3 zak-lexicaal (run zonder bouwbaar woord) 16.001.620   ( 61,6 % van wat F0 overlaat )
F4 schema gebouwd                        9.936.824
F5 plafond < 4800                          879.043
F5 door                                  9.057.781
bewaard (top-K per shard)                  120.000
```

De **zaktoets op runniveau is de zwaarste zeef na het budget**: 16,0 miljoen configuraties
sneuvelen omdat ergens een maximale run geen woord toelaat dat nog uit de restzak te bouwen is.
Dat is precies de zeef die in eerder werk ontbrak.

Plafond-histogram (zeef-plafond, bins van 20; totaal 9,06 M):

```
4800  564k   4880 1023k   4960  663k   5040 140k   5120  34k   5200  12k
4820  708k   4900 1007k   4980  503k   5060  79k   5140  29k   5220   6k
4840  850k   4920  943k   5000  356k   5080  48k   5160  22k   5240   2k
4860  967k   4940  808k   5020  234k   5100  40k   5180  18k   5260  <1k
```

## 3c. De valkuil die deze sweep blootlegde: de zeef selecteert de ladderillusie

De 120.000 bewaarde configuraties liggen **allemaal** in de plafondband 5050-5316, terwijl het
record op 4868 zit. De top-K-selectie op zeef-plafond kiest dus systematisch de staart, en die
staart bestaat uit ladderillusies: schema's die hun plafond halen door lijnen tegel voor tegel te
leggen, wat alleen mag als elke tussenstand zelf een woord is.

Twee ingrepen waren nodig:

1. **Ketenbewuste bouwer.** `sub_ok(eindrun, i, j)` toetst of er één woord voor de eindrun
   bestaat waarvan het deelstuk `[i:j]` ook een woord is (gecachet, de paarsgewijze versie van
   `diagnose`). Zonder die toets was **0 van 60** bezettingen lijnconsistent te plannen; met de
   toets lukt het wel. Ook nieuw: de bouwer kent nu twee regimes — `small=True` (zo klein
   mogelijke zetten, maximale herscoring) en `small=False` (zo groot mogelijk, minste lexicale
   schuld) — en `schedule_variants` probeert beide.
2. **Selectie op een realistische band** in plaats van op de top (`CEILMAX`), en een
   reservoirsteekproef (`SAMPLE=1`) zodat de bewaarde verzameling een onvertekende doorsnede is.

## 3d. Fase R+D — verfijning en beslissing over 5303 configuraties

Op een gespreide doorsnede van de 120.000 (hoogstens 2 per (laan, rij-0-dragers,
rij-14-dragers)):

```
verfijnd (ketenbewuste bouwer, beide regimes, peel 0-12)  5.302
daarvan LIJNCONSISTENT (mg_newtopo.diagnose leeg)           502   (9,5 %)
beste lijnconsistente plafond                              4908   (record: 4860 met dezelfde bouwer)
```

Daarna de beslissingsvorm `fit_decide(schema, 4794)` op alle 5303:

```
NEE (bewezen: geen lettering boven 4793)   5303
JA                                             0
ONBEKEND                                       0
mediane rekentijd                            1,2 s
```

**Alle 5303 zijn NEE, en de meeste binnen twee seconden.** Zo snel betekent dat de
onvervulbaarheid niet uit de scoregrens komt maar uit de woord- en zakbeperkingen zelf: deze
bezettingen zijn niet te LETTEREN, laat staan boven het record. Ter controle is dezelfde toets
op drie bekende borden gedraaid:

| bord | score | `fit_decide` op die score |
|---|---|---|
| `maxgame_BEST.json` (record) | 4793 | **JA** in 227 s (met hint 170 s) |
| `denseblock_board_E2.json` | 4540 | **JA** in 8 s |
| `maskgeom_board_laan3.json` | 4744 | ONBEKEND na 101 s |

De motor geeft dus JA waar hij dat hoort te doen; de 5303 NEE's zijn echte weerleggingen.

## 3e. De record-omgeving zelf: 192 afrondingen, 0 beter

Het recordskelet (54 tegels) heeft binnen het budget 192 afrondingen tot 56 tegels. Alle 192 zijn
door de keten gehaald: 0 gedood door F3, 178 lijnconsistent, verfijnde plafonds 4880-4909 (het
record zelf 4904). Van de 24 hoogst gerangschikte zijn beide schema's beslist:
**29 x NEE, 1 x ONBEKEND, 0 x JA**. De directe omgeving van het record is dus dicht.

## 3f. Twee lanen met korte dragers — het spoor eerlijk gemeten

Met de ketenbewuste bouwer en gelijke tegelinzet (56 vrije cellen), 401 afrondingen:

```
lijnconsistent      400 van 401   (99,8 % -- tegen 9,5 % voor de enkellaans top)
beste plafond       4813          (record met dezelfde bouwer: 4860)
fit_decide(4794)    ONBEKEND (90-100 s) -- niet weerlegd, maar ook niet gehaald
```

Het beeld is nu scherp en het is een ANDER beeld dan het eerste (foute) verhaal over bingo's:

> De twee sporen ruilen **plafond tegen lexicale robuustheid**. Lange kolommen geven hoge
> plafonds maar zijn lexicaal broos (9,5 % lijnconsistent, en van die 9,5 % is 100 % onvulbaar);
> korte stubs met twee lanen zijn lexicaal kerngezond (99,8 %) maar hun plafond blijft op 4813
> steken. Het record staat precies op het optimum van die ruil: 4860 plafond én
> lijnconsistent. Om vanaf 4813 boven 4793 te komen is 99,6 % realisatiegraad nodig, terwijl het
> record zelf 98,0 % haalt (4793 van 4889) — dat is geen marge maar een tekort.

---

## 3g. Fase D — dezelfde sweep, maar met een ONVERTEKENDE steekproef uit de realistische band

Fase A opnieuw gedraaid (identieke 337,8 M parameterpunten), nu met `CEILMAX=4980` en
`SAMPLE=1` (reservoirsteekproef) zodat de bewaarde 60.000 configuraties een echte doorsnede van
de band 4830-4980 zijn in plaats van de ladderstaart.

```
knopen                                 337.798.080
F0 tegelbudget                         311.821.416
F2 onbereikbaar                             38.220
F3 zak-lexicaal                         16.001.620
F4 schema gebouwd                        9.936.824
F5 plafond < 4830                        1.780.139
F5 plafond > 4980 (buiten de band)       1.495.090
F5 in de band                            8.156.685
reservoirsteekproef bewaard                 60.000        (10,24 CPU-uur)
```

Verfijning (ketenbewuste bouwer) van 8.916 gespreide configuraties uit die steekproef:

```
lijnconsistent                    1.285 van 8.916   (14,4 %; fase A haalde 9,5 %)
beste lijnconsistente plafond      5005              (record met dezelfde bouwer: 4860)
```

Beslissing `fit_decide(schema, 4794)` — loopt door, stand bij het schrijven:

```
NEE (bewezen)   2.196
ONBEKEND           22
JA                  0
mediane tijd      1,6 s
```

De 9 ONBEKEND-gevallen met het hoogste plafond (4911-4965) zijn apart met de MAXIMALISERENDE
solver (`mg_newtopo.fit`, 900 s) nagelopen: **alle negen INFEASIBLE in 83-142 s** — er bestaat
voor die bezettingen helemaal geen lettering, laat staan een betere. De ONBEKEND-uitslagen zijn
dus tijdslimiet-artefacten, geen open kansen.

---

## 4. Conclusie

**Geen enkel bord boven 4793.** Wat er wel ligt is een gemeten beeld van het landschap:

1. **De zak-lexicale runtoets is de zwaarste zeef na het tegelbudget**: 16,0 M van de 26,0 M
   budget-geldige configuraties sneuvelt omdat één maximale run geen woord toelaat dat nog uit de
   restzak (55 tegels, 17-letterig alfabet) te bouwen is. Dat is de zeef die in eerder werk
   ontbrak, en hij is goedkoop (100 us, gecachet).
2. **Het m-plafond is geen bruikbare rangschikking meer.** Binnen een familie correleert het
   nauwelijks (0,47 / 0,35), de 192 record-buren liggen binnen 30 punten van elkaar, en de
   top-K-selectie erop levert systematisch ladderillusies. Over alle topologieën heen is het wel
   informatief (0,70).
3. **De bindende beperking is de LEXICALE INVULBAARHEID van de hele bezetting**, niet de
   geometrie en niet meer de zak alleen. Van 8.916 verfijnde configuraties is 85,6 % al
   lijn-inconsistent, en van wat overblijft is elke geteste configuratie CP-SAT-infeasible —
   meestal binnen twee seconden, dus door presolve, dus structureel.
4. **Het record staat op een smal optimum van een RUIL.** Lange kolommen geven hoge plafonds maar
   zijn lexicaal broos (9,5-14,4 % lijnconsistent); korte stubs met twee lanen zijn lexicaal
   kerngezond (99,8 %) maar hun plafond blijft op 4813 steken. 4860 plafond én lijnconsistent —
   dat is de combinatie die het record maakt, en de sweep vond er geen tweede van.
5. **Verlengketens verslaan bingo's per tegel** (16,0 tegen 12,8 punt/tegel op het record), maar
   ze vragen dat elke tussenstand een woord is. `chain_len` / `sub_ok` maken dat vooraf toetsbaar;
   het record haalt ext_potential 10 terwijl kolom 2 lexicaal tot L=8 zou kunnen — de BEZETTING
   is daar de rem, niet het lexicon. Dat is de scherpste openstaande hefboom die deze module
   aanwijst: een bezetting die de kolom-2-keten dieper maakt zonder elders in te leveren.

### Wat NIET is uitgesloten

* De sweep is uitputtend over de **parameters** maar niet over alle bezettingen: hoogstens één
  niet-'full' drager (`MAXNF=1`), hoogstens één laan per band, laanspanwijdtes uit
  {0,2,4} x {10,12,14}, en de verfijning/beslissing draaide op een gespreide steekproef van
  8.916 van de 8,16 M configuraties in de band.
* De twee-lanen-familie is niet weerlegd (ONBEKEND, 90-100 s), alleen te laag bevonden (4813).
* Andere maskers en andere tripletten zijn hier niet opnieuw opgesomd; die zijn in
  `MASKGEOM.md` en `LETTERBUDGET.md` afgesloten.

## 5. Gebruik

```
MODE=calib                                     .venv/bin/python experiments/mg_configgen.py
MODE=enum SHARD=k NSHARD=10 TMIN=56 TMAX=56 TOPK=12000 OUT=... .venv/bin/python experiments/mg_configgen.py
MODE=expand IN=<dir> TOPN=4000 SHARD=k NSHARD=10               .venv/bin/python experiments/mg_configgen.py
MODE=refine IN=<dir> TOPN=3000 SHARD=k NSHARD=10               .venv/bin/python experiments/mg_configgen.py
MODE=fit    IN=<dir> TOPN=40 TLIM=600                          .venv/bin/python experiments/mg_configgen.py
```
