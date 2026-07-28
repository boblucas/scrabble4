# DICHTE BLOKKEN — verticale woorden in aangrenzende kolommen (2026-07-28)

Motor: `experiments/mg_denseblock.py` (bovenop `mg_mceiling.py` en `mg_newtopo.py`).
Uitvoer: `experiments/results/denseblock*.json`.
Triplet en maskers ongewijzigd: `geschenkcheques` / `flexwerkstertje` / `polymelkzuurtje`,
rij 0 `{0,3,7,8,11,13,14}`, rij 7 `{0,1,2,3,12,13,14}`, rij 14 `{0,1,2,3,7,13,14}`.
`experiments/results/maxgame_BEST.json` en `data/boards.toml` zijn **niet** aangeraakt.

```
COORD=1  LEX=20  .venv/bin/python experiments/mg_denseblock.py   # coordinaatzoektocht
RECT=1   TLIM=60 .venv/bin/python experiments/mg_denseblock.py   # woordrechthoek-muur
         LEX=25  .venv/bin/python experiments/mg_denseblock.py   # handmatige blokvormen
TOP=1 N=4 TLIM=900 .venv/bin/python experiments/mg_denseblock.py # CP-SAT + arbiter
```

## Uitkomst in drie regels

Het idee klopt kwantitatief — een dicht blok is bij gelijke tegelinzet en gelijk schema
**+130 tot +230 ankervast m-plafond** waard — maar het is met dit triplet **lexicaal onhaalbaar**, en de
weerlegging zit niet waar iedereen hem zoekt. Het eindbord van een dicht blok is prima
invulbaar; wat sneuvelt zijn de **tussenstanden**: elke bouwvolgorde van aangrenzende kolommen
maakt gedeeltelijke rij-runs (2-, 3-, 5-letterwoorden) die *bovenop* de eindwoorden moeten
bestaan. Elk schema met een plafond boven ~4680 is CP-SAT-INFEASIBLE; de schema's die wél
bestaan leveren geverifieerde borden van **4540**, **4476** en **4412** op.
**Er is geen bord boven 4778 gevonden; `maxgame_BEST.json` is ongewijzigd.**

---

## 1. De eerste zeef is niet lexicaal maar logistiek: BEZORGBAARHEID

De maskercellen van rij 0/7/14 worden pas in de slotzet gelegd. Daardoor valt rij 0 tot die
slotzet uiteen in vier **eilanden** en rij 14 in twee:

| rij | slotzet-masker | pre-groepen (eilanden) |
|---|---|---|
| 0 | `{0,3,7,8,11,13,14}` | `{1,2}` `{4,5,6}` `{9,10}` `{12}` |
| 7 | `{0,1,2,3,12,13,14}` | `{4,…,11}` (hangt aan het centrum) |
| 14 | `{0,1,2,3,7,13,14}` | `{4,5,6}` `{8,9,10,11,12}` |

Een eiland op rij 0 kan alleen door een **kolom** worden aangeraakt: er moet een tegel op
`(x,1)` liggen met `x` in die groep. Dus:

> **De bovenhelft heeft vier dragende kolommen nodig, één in elk van `{1,2}`, `{4,5,6}`,
> `{9,10}` en — als singleton gedwongen — kolom 12. De onderhelft heeft er twee nodig, één in
> `{4,5,6}` en één in `{8..12}`.**

Dat zijn precies de posities van de recordtopologie (2, 5, 10, 12 boven; 4 en 11 onder), en ze
liggen per constructie **uit elkaar**. De enige vrijheid voor een dicht blok is dus: *rond* zo'n
verplichte drager extra aangrenzende kolommen zetten. Een vrij gekozen blok (bv. kolommen 8-10
boven) laat drie eilanden onbereikbaar en bestaat niet als spel. In de eerste ronde sneuvelden
hierop **alle acht** vrij ontworpen blokvormen (`ONLEVERBAAR`), vóór er ook maar één woord bij te
pas kwam. In de definitieve sweep worden de dragers automatisch toegevoegd (`add_support`);
daar sneuvelen vervolgens 8 van de 33 vormen op de kolomtabel-zeef (`col_ok`).

**Nevenvondst (bouwtechnisch).** `mg_newtopo.auto_schedule` hangt de drie slotzetten altijd
achteraan en verwerpt daardoor bezettingen die wél bestaan — het record zelf is er één van (de
rij-7-slotzet is daar zet 23 van de 33, en `(2,8)/(2,9)/(2,10)` hangen daarna aan die net
gelegde rij 7). `mg_denseblock.schedule()` behandelt een slotzet als gewone kandidaat zodra de
rest van zijn rij ligt. Dat opent de hele familie "kolom die aan rij 7 hangt" en is nodig voor
elk blok in de kolommen 0-3 / 12-14.

---

## 2. DE MUUR, exact gemeten: de woordrechthoek (`RECT=1`)

Kernvraag van de opdracht: *bij welke blokbreedte slaat het om?* Dat is schema-onafhankelijk te
meten. Een blok van `W` aangrenzende kolommen over een rijenbereik eist:
elke **kolom** een woord over zijn volle verticale run (inclusief de vaste ankerletters), en
elke **rij** een woord over de volle blokbreedte. `rect_feasible()` legt dat als CP-SAT-model
voor. J = bestaat, N = bewezen onmogelijk (per positie `a..a+W-1`, van links naar rechts).

### 2a. statisch (alleen de volle blokbreedte)

| blok | W=2 | W=3 | W=4 | W=5 | W=6 |
|---|---|---|---|---|---|
| **boven rijen 1-6** (kolomwoord 8 lang, `rij0…rij7`) | 11/14 posities | 9/13 | **4/12** (5-8, 6-9, 7-10, 9-12) | **0/11** | 0/10 (1 onbeslist) |
| **onder rijen 8-13** (kolomwoord 8 lang, `rij7…rij14`) | 4/14 (4-5, 5-6, 6-7, 11-12) | **3/13** (4-6, 5-7, 10-12) | **0/12** | 0/11 | 0/10 |
| boven rijen 4-6 (kolomwoord 4 lang, hangt aan rij 7) | 14/14 | 13/13 | 12/12 | 11/11 | 10/10 |
| boven rijen 1-3 (kolomwoord 4 lang, `rij0…rij3`) | 14/14 | 13/13 | 12/12 | 11/11 | 10/10 |
| onder rijen 8-10 (kolomwoord 4 lang, hangt aan rij 7) | 12/14 | 10/13 | 8/12 | 7/11 | 6/10 |

> **De muur is het 8-letter kolomwoord met TWEE vaste ankerletters.** Een blok dat rij 1 of
> rij 13 haalt — en dat moet het, anders draagt het geen pre-groep — dwingt zo'n woord af in elke
> kolom van het blok. Boven houdt dat op bij breedte 4, onder al bij breedte 3.
> Een blok dat alleen aan rij 7 hangt heeft 4-letter kolomwoorden met één vaste letter en is
> lexicaal ruim; die blokken dragen alleen geen enkele pre-groep.

### 2b. dynamisch (de bouwvolgorde telt mee)

Een blok wordt kolom voor kolom gelegd, en elke tussenbreedte is zelf een gescoorde rij-run die
ook een woord moet zijn. Twee realistische volgordes:
*kam* = om en om, dan de gaten (tussenbreedtes 3,5,…); *lineair* = van links naar rechts
(tussenbreedtes 2,3,…,W-1). Aantal werkende posities:

| blok | W | statisch | kam | lineair |
|---|---:|---:|---:|---:|
| boven rijen 1-6 | 3 | 9 | 9 | 4 |
| boven rijen 1-6 | 4 | 4 | **1** (7-10) | **0** |
| boven rijen 1-6 | ≥5 | 0 | 0 | 0 |
| onder rijen 8-13 | 3 | 3 | 3 | **1** (4-6) |
| onder rijen 8-13 | ≥4 | 0 | 0 | 0 |
| boven rijen 4-6 (hangend) | 5 | 11 | 11 | 8 |
| boven rijen 4-6 (hangend) | 6 | 10 | 8 | 3 |
| boven rijen 4-6 (hangend) | 7 | 9 | 6 | 1 |
| onder rijen 8-10 (hangend) | 6 | 6 | 6 | 6 |

**Antwoord op de opdrachtvraag.** Voor een blok dat de ankerrij haalt slaat het om **tussen
breedte 3 en 4 boven, en tussen breedte 2 en 3 onder**; met een echte bouwvolgorde blijft er
boven precies één breedte-4-positie over (kolommen 7-10) en onder precies één breedte-3-positie
(kolommen 4-6). Voor hangende blokken ligt de omslag bij breedte 6-7.

---

## 3. Wat een dicht blok wél waard is (m-calculus)

Alle plafonds zijn ankervast (`SOM_c m(c)·waarde(c) + 50·#bingo's` met de tripletletters vast).
**IJking eerst**, want dat is waar de vorige ronde de mist in ging:

| bezetting | schema | tegels | bingo | m-plafond | lex | gerealiseerd |
|---|---|---:|---:|---:|:--:|---:|
| record | eigen schema (33 zetten, 42 runs) | 101 | 11 | **4881** | JA | **4778** |
| record | `schedule()` greedy | 101 | 10 | 4657 | JA | — |
| record | `schedule()` + ladderzoek | 101 | 10 | 4875 | — | — |

> De eigen greedy-bouwer is 150-220 plafondpunten zwakker dan het handgemaakte recordschema.
> **Elke delta hieronder is daarom gemeten met dezelfde bouwer op beide bezettingen**; absolute
> getallen tussen tabellen zijn niet vergelijkbaar.

### 3a. handmatige blokvormen (`LEX=25 .venv/bin/python experiments/mg_denseblock.py`)

25 van de 33 vormen overleefden de kolomtabel-zeef; alle 25 hebben een legaal zetschema. De
kolom *eerlijk* is het greedy-plafond, *ladder* het plafond na schemazoektocht (optimistisch),
*lex* het CP-SAT-oordeel over de kruiswoord-eisen van het greedy-schema.

| blokvorm | tegels | bingo | eerlijk | ladder | lijnen | lex |
|---|---:|---:|---:|---:|:--:|:--:|
| L5-8 + record-boven | 101 | 12 | **4888** | 4953 | dood | NEE |
| L4-7 + record-boven | 101 | 12 | 4876 | 4924 | dood | NEE |
| U8-10 + L5-7 | 101 | 12 | 4876 | 4909 | dood | NEE |
| U8-10 + L4-7 | 101 | 11 | 4834 | 4875 | dood | NEE |
| U7-10 + record-onder | 101 | 10 | 4816 | 4920 | dood | NEE |
| U8-11 + L4-7 | 101 | 10 | 4790 | 4928 | dood | NEE |
| U12-14 + record-onder | 100 | 8 | 4794 | 4942 | dood | NEE |
| U8-10 + L4-7 zonder laan | 101 | 12 | 4763 | 4834 | **OK** | NEE |
| U8-11 + L4-7 zonder laan | 101 | 11 | 4729 | 4855 | **OK** | NEE |
| U7-11 halfhoog + record-onder | 100 | 8 | 4767 | 4939 | **OK** | NEE |
| U4-8 halfhoog + record-onder | 100 | 9 | 4676 | 4871 | **OK** | ONBEKEND |
| **REF record (exacte bezetting)** | 101 | 10 | **4657** | 4875 | — | ONBEKEND |
| 8 vormen (U8-11, U4-6, U9-12, U2-5, L10-12, U5-8, …) | — | — | — | — | — | lege kolomtabel (kol 4 `h..w..m`, 6 `n..r..l`, 10 `e..e..u`, 11 `q..r..r` = 0 volle woorden) |

De beste dichte blokken staan **+175 tot +230 boven de recordbezetting bij dezelfde bouwer** —
het geometrische idee is dus bevestigd. Maar geen enkele overleeft de kruiswoordtest.

### 3b. coordinaatzoektocht over de blokvormen (`COORD=1`)

Omdat de bezorgbaarheidszeef de vier dragers vastlegt, is de zoekruimte geordend per pre-groep:
per groep een handvol lokale vormen (alleen de drager / drager + buurkolom / drie aangrenzende
kolommen / lage stukken). ~90 bezettingen doorgerekend, coordinaatstijging in 3-4 ronden.

| variant | eerlijk plafond | t.o.v. recordbezetting (zelfde bouwer, 4657) | oordeel |
|---|---:|---:|:--|
| `g1-2kort / g4-1112 / l2-alt12` (kolommen 11+12 boven, 12 onder) | 4908 | +251 | lijn-DOOD (kol 11 boven = `q..r`, 4 woorden) |
| `g1-2kort / g4-11k12+13k / l2-alt12` (blok 11-12-13 boven) | 4848 | +191 | lijn-OK, CP-SAT **INFEASIBLE** |
| **`g3-10+11k / l1-56`** (paar 10-11 boven, paar 5-6 onder) | **4788** | **+131** | lijn-OK, lex **NEE** |
| coord-BASIS: alleen de zes verplichte dragers (95 tegels) | 4579 | −78 | referentievorm zonder blokken |
| lanen weglaten (`LAAN=geen`), beste vorm | 4768 | +111 | lijn-OK, lex niet beslist |
| brede lage "planken" op rijen 5-6 en 8-9 (`p5-*`, `p8-*`) | nooit een verbetering | 0 | economisch afgewezen |

**De planken zijn de scherpste negatieve meting.** De woordrechthoek zegt dat lage hangende
blokken lexicaal vrij zijn tot breedte 6-7 — dat is precies de plek waar een dicht blok *wel*
zou mogen bestaan. Maar in de m-calculus levert zo'n plankcel ongeveer het vrije gemiddelde op
(~4,5 m) terwijl hij tegels kost die elders een bingo breken (-50 per 7 tegels). De
coordinaatzoeker koos **in geen enkele ronde een plank**. Dat sluit de enige lexicaal levende
dichte-blok-familie langs de economische kant.

---

## 4. Waar het precies breekt: de onvervulbare kernen

`lex_feasible()` toetst puur de kruiswoord-eisen (geen zak, geen blanco's, geen doel);
`lex_core()` zoekt daarna de minimale verzameling runs die elkaar uitsluiten. Ter controle:
de 42 runs van het echte recordschema zijn stuk voor stuk woorden, dus het model is correct.

**Beslissend onderscheid.** `static_feasible()` toetst alleen de maximale runs van het
**eindbord** — dus wat elk zetschema hoe dan ook moet waarmaken:

| bezetting | eindruns | statisch invulbaar? | met zetschema? |
|---|---:|:--:|:--:|
| record | 14 | **JA** | JA |
| `g3-10+11k / l1-56` (beste dichte blok) | 19 | **JA** | **NEE** |
| `g1-1kort / g3-10+11k / l1-56` | 19 | **JA** | **NEE** |
| `g2-4k+5 / g3-10+11k / l1-56` | 19 | **JA** | **NEE** |

> **Het eindbord van een dicht blok bestaat wél. Het spel dat ernaartoe leidt niet.**

De kern van de beste kandidaat (onderpaar kolommen 5 en 6, rijen 8-13), identiek bij twee
verschillende zetschema's:

```
  kol 5  [5,0]-[5,14]  len 15  e??????e??????e     (104 woorden)
  kol 5  [5,8]-[5,14]  len  7  ??????e
  kol 6  [6,7]-[6,14]  len  8  r??????l
  kol 6  [6,8]-[6,14]  len  7  ??????l
  rij 9  [5,9]-[7,9]   len  3  ???
  rij 11 [5,11]-[6,11] len  2  ??
  rij 12 [5,12]-[6,12] len  2  ??
  rij 13 [5,13]-[6,13] len  2  ??
```

Lees dat als het mechanisme van de hele familie: twee aangrenzende kolommen over zes rijen
eisen **zes horizontale mini-woorden** (hier drie 2-letterwoorden en een 3-letterwoord op de
rijen waar de kolommen ongelijk opgroeien) *bovenop* twee verticale woorden die aan beide
uiteinden op een ankerletter vastzitten. Er zijn maar 93 Nederlandse 2-letterwoorden; het
doorsnijden van drie van die eisen met `e??????e??????e` (104 woorden) en `r??????l` is leeg.
Bij de bovenkandidaten is de kern steevast `kol 12 = u??????t??????t` (3 woorden) samen met
`kol 13 = ??j` / `???j` (14 woorden) en de gedeeltelijke rij-runs van rij 4 resp. rij 6
(lengtes 12 en 13, resp. 5 en 7).

De boete-experimenten bevestigen dat het geen zoekfout is: `schedule(boete=k)` bestraft elke
run die géén eindrun is en drukt het aantal runs van 42 naar 33, maar de kandidaat blijft
lexicaal **NEE** bij boete 0, 15, 40 en 100 (het plafond zakt daarbij van 4805 naar 4612). Op de
recordbezetting geeft diezelfde bouwer bij boete 0 en 15 lexicaal **JA** (32 resp. 31 runs).

---

## 5. CP-SAT-eindoordeel en de wél gebouwde dichte-blok-borden

Vullingen met doelfunctie (`mg_newtopo.fit`: zak + hoogstens 2 blanco's + score maximaliseren),
gevolgd door de arbiter `MG.score_game`.

### 5a. schema's die uit de plafondzoeker komen — allemaal onvervulbaar

| topologie | plafond (schoon schema) | CP-SAT |
|---|---:|---|
| `g1-2kort/g2-rec/g3-rec/g4-11k12+13k/l1-rec/l2-alt12` | 4919 | **INFEASIBLE** |
| `g1-2kort/g2-rec/g3-10+11k/g4-11k12+13k/l1-rec/l2-alt12` | 4919 | **INFEASIBLE** |
| `g1-2kort/g2-rec/g3-89k+10/g4-11k12+13k/l1-rec/l2-alt12` | 4930 | **INFEASIBLE** |
| `g1-rec/g2-rec/g3-10+11k/g4-rec/l1-56/l2-rec` | 4890 | **INFEASIBLE** |

### 5b. schema's die de lexicale test eerst moesten doorstaan — die leveren wél borden op

Zelfde bezettingen, maar nu wordt uit ~12 schema's (boete 0/25/60 × 4 seeds) alleen het beste
gekozen dat `lex_feasible == JA` haalt. Dat kost plafond en levert een bord op:

| topologie | tegels | eindruns | beste lex-levende plafond | CP-SAT | **arbiter** |
|---|---:|---:|---:|---|---:|
| **E2** — dicht ONDERpaar kolommen 5-6 (rijen 8-13), centrumkolom, geen laan | 98 | 24 | 4580 | ok 4540 | **4540 ok=True** |
| **G** — dicht ONDERpaar kolommen 10-11 (kolom 10 kort), laan, centrum | 98 | 15 | 4592 | ok 4476 | **4476 ok=True** |
| **D** — onder 4/6/11 vol, boven record (geen blok) | 87 | 10 | 4421 | ok 4412 | **4412 ok=True** |
| E — zelfde onderpaar 5-6 mét de rij-4-laan | 101 | 18 | 4682 | **INFEASIBLE** | — |
| F — dicht BOVENpaar kolommen 9-10 (rijen 1-6) + laan | 100 | 17 | 4680 | **INFEASIBLE** | — |
| A — bovenblok kolommen 7-10 vol (de enige breedte-4-positie uit §2b) | 99 | 18 | — | — | **geen enkel lexicaal levend schema** (12 schema's, alle NEE) |

`experiments/results/denseblock_board_E2.json`, `..._G.json` en `..._D.json` zijn
geverifieerde spellen (`ok=True`), maar met **4540** / **4476** / **4412** ver onder het record. E2 laat wél precies zien wat
de opdracht vroeg — middenrijen die zelf een woord vormen:

```
    0 g e s c h e n k c h e q u e s     rij  8  vos      (kol 5-7)
    1 . . m . o . . . . e n . i . .     rij  9  aze
    2 . . a . u . . . . i d . t . .     rij 10  sen
    3 . . d . w . . . . d o . d . .     rij 11  in       (kol 5-6)
    4 . . e . t . . . . e g . a . .     rij 12  eg
    5 . . n . o . . f . r e . m . .     rij 13  va
    6 . . d . u . . o . i n . p . .
    7 f l e x w e r k s t e r t j e     98 tegels, 12 bingo's
    8 . . . . . v o s . . . a . . .     kolom 5 = 'vasieve' (rij 8-14)
    9 . . . . . a z e . . . b . . .     kolom 6 = 'ozengal'
   10 . . . . . s e n . . . a . . .     kolom 7 = 'ksen'   (rij 7-10)
   11 . . . . . i n . . . . r . . .
   12 . . . . . e g . . . . b . . .     arbiter 4540, ok=True
   13 . . . . . v a . . . . e . . .
   14 p o l y m e l k z u u r t j e
```

**Eerlijkheidsvoorbehoud bij de lex-kolom.** `lex_feasible` geeft drie antwoorden. **NEE** is een
bewijs (CP-SAT INFEASIBLE) en daar rust alle weerlegging hierboven op. **JA** en **ONBEKEND**
hangen van de rekentijd af, en niet elk model is even makkelijk: de recordbezetting zelf heeft
>60 s nodig voor een JA (bij `tlim=90` geeft `schedule(boete=0)` en `boete=15` op de
recordbezetting wél JA, met 32 resp. 31 runs), terwijl de dunnere blokborden binnen seconden
klaar zijn. De filter is dus *conservatief in de goede richting* — hij verwerpt alleen bewezen
onmogelijke schema's — maar hij is geen betrouwbare *rangschikking* van wat wél kan.

> **De realisatiegraad is niet het probleem.** E2 haalt 4540 uit een plafond van 4580 = **99,1 %**
> (het record: 4778 uit 4881 = 97,9 %). Het probleem is dat een dicht blok géén hoog plafond
> haalt zodra je het schema lexicaal levend houdt: de plafonds van 4850-4930 horen bij schema's
> die niet bestaan, en de schema's die wel bestaan komen niet boven ~4680.

**Er is geen bord boven 4778 geproduceerd. `maxgame_BEST.json` blijft ongewijzigd.**

---

## 6. Conclusie en wat dit voor de campagne betekent

1. **Het idee is geometrisch juist en economisch bevestigd**: dubbel gescoorde tegels zijn
   +130 tot +230 ankervast plafond waard bij gelijke tegelinzet. De diagnose in CLASSBOUND §4
   wees dus naar een echte post.
2. **De bezorgbaarheidszeef verklaart waarom het record eruitziet zoals het eruitziet.** De vier
   bovendragers en twee onderdragers liggen gedwongen uit elkaar; de "te ver uit elkaar staande
   kolommen" zijn geen ontwerpfout maar een gevolg van de maskerkeuze.
3. **De lexicale muur is scherp gelokaliseerd**: het 8-letter kolomwoord met twee vaste
   ankerletters. Blokbreedte ≤ 4 boven / ≤ 3 onder statisch, en met een echte bouwvolgorde
   1 positie boven (kolommen 7-10) en 1 onder (kolommen 4-6).
4. **De echte doodsoorzaak is de bouwvolgorde, niet het eindbord.** Elke doorgerekende
   dichte-blok-bezetting is *statisch* invulbaar; wat sneuvelt is het zetschema. Dat is een
   *nieuw* filter (`static_feasible` vs `lex_feasible`) dat elke volgende generator zou moeten
   draaien: het scheidt "deze bezetting bestaat niet" van "deze bezetting bestaat, maar dit
   schema niet". Praktisch gevolg: de plafondzoeker mag niet meer zonder lexicale toets
   worden gebruikt — elk schema dat hij boven ~4680 vindt, bestaat niet.
5. **De enige breedte-4-positie is apart uitgeprobeerd en valt om.** Variant A (bovenblok
   kolommen 7-10 vol, met de dragers 2/5/12 en onder 4/11, 99 tegels) is statisch invulbaar,
   maar geen van de twaalf gebouwde zetschema's (boete 0/25/60 × 4 seeds, 32-46 runs) overleeft
   de kruiswoordtest. De breedte-4-positie uit §2b bestaat dus wel als rechthoek en niet als
   spelonderdeel.
6. **Wat wél overeind blijft is klein en zit ~240 punten te laag.** Geverifieerd zijn de
   onderparen kolommen 5-6 (E2, **4540**, 98 tegels, 12 bingo's) en 10-11 (G, **4476**,
   98 tegels). De variant met blokpaar 5-6 *plus* de rij-4-laan (E, 101 tegels, plafond 4682)
   is INFEASIBLE, net als het bovenpaar 9-10 met laan (F, plafond 4680). Het patroon is
   consistent: een dicht paar is betaalbaar zolang het bord daaromheen dun blijft, en zodra je
   de tegels toevoegt die het plafond richting 4800 moeten duwen, verdwijnt de lexicale ruimte.
7. Voor >= 4819 blijft het beeld van NEWTOPO §6 staan: de rem is de **bingo-breuk** (elke
   structurele toevoeging van 7 tegels kost 50) en het **lexicon op de hoogste m-cellen**, niet
   de geometrie.

---

## 7. Gereedschap dat dit spoor achterlaat

| functie in `mg_denseblock.py` | wat het doet |
|---|---|
| `pre_groups` / `support_gaps` / `add_support` | de bezorgbaarheidszeef, expliciet |
| `schedule(cells, boete=)` | zetschema-bouwer die de slotzetten *niet* achteraan dwingt en tijdelijke runs mag bestraffen |
| `static_feasible(cells)` | schema-onafhankelijke weerlegging van een BEZETTING |
| `lex_feasible(mv)` / `lex_core(mv)` | weerlegging van een SCHEMA + minimale onvervulbare kern |
| `rect_feasible(cols, rows, tussen=)` | woordrechthoek met of zonder tussenbreedtes — de muurmeting |
| `coord_search` | coordinaatstijging over blokvormen per pre-groep |
| `refine(mv, lex=)` | ladderzoektocht die alleen lijn-consistente én niet-weerlegde schema's accepteert |
