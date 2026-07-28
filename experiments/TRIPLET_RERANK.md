# TRIPLET-HERRANGSCHIKKING OP HET GECORRIGEERDE BORD (2026-07-28)

Aanleiding: `data/boards.toml` miste 7 letterpremies in de rijen 11-14 — DL op (7,11), (6,12),
(8,12), (3,14), (11,14) en TL op (5,13), (9,13). Die zijn vandaag hersteld. Daarmee vervalt de
gewichtsbasis van de rij-14-rangschikking en dus van de tripletkeuze.

Machinerie: `experiments/mg_triplet_rerank.py` (draai: `.venv/bin/python experiments/mg_triplet_rerank.py`,
env `STRICT`/`TOP`/`OUT`). Uitvoer: `experiments/results/triplet_rerank{,_relaxed}.{log,jsonl}`.

## 0. Wat het bord nu zegt

Het 15x15-bord is nu volledig puntsymmetrisch. Gevolg voor de ankerrijen:

| rij | woordvermenigvuldiger | letterpremies |
|-----|----------------------|---------------|
| 0   | 3x3x3 = **27**       | DL op x=3 en x=11 |
| 7   | 3x2x3 = **18** (9 in onze architectuur: het middenvak ligt al na zet 1) | DL op x=3 en x=11 |
| 14  | 3x3x3 = **27**       | DL op x=3 en x=11 |

**Rijen 0, 7 en 14 hebben nu een identiek letterprofiel.** De waardering reduceert tot

    waarde(w, y) = wm(y) * ( S(w) + v(w[3]) + v(w[11]) )        S(w) = som van de letterwaarden

Op het defecte bord ontbraken juist die twee DL's op rij 14, dus rij 14 werd gewaardeerd met
`27 * S(w)` — precies de fout uit de opdracht.

## 1. Top-20 per ankerrij (correcte bord)

Rij 0 en rij 14 zijn nu identiek; rij 7 is dezelfde volgorde met factor 18/27.

```
 1. croquemboucheje 1701     8. croquetmatchjes 1647    15. jacquardmachine 1593
 2. geschenkcheques 1674     9. jacquardweefsel 1620    16. chequeformulier 1593
 3. jacquetkostuums 1674    10. cultuurchequeje 1620    17. playbackshowtje 1593
 4. flauwekulexcuus 1647    11. verzamelcheques 1620    18. luchtdrukmaxima 1566
 5. alfahydroxyzuur 1647    12. dyscalculicusje 1593    19. jezuscomplexjes 1566
 6. deuxchevauxtjes 1647    13. mytylschooltjes 1593    20. polysyllabische 1566
 7. vluchtreflexjes 1647    14. circuscomedytje 1593
```

Onze keuzes: **geschenkcheques 1674 (rang 2/118709)**, **flexwerkstertje 918 (rang 431)**,
**polymelkzuurtje 1512 (rang 46)**.

### Hoeveel liet rij 14 liggen?

Twee verschillende getallen, allebei relevant:

* **Waarderingsfout (winst, geen verlies).** polymelkzuurtje werd op het defecte bord op
  `27*46 = 1242` gewaardeerd, is op het correcte bord `27*(46+8+2) = 1512` waard (`y`=8 op (3,14),
  `r`=2 op (11,14)). De rangschikking zette het op plaats 166; het hoort op plaats 46.
* **Gemiste kans t.o.v. de nominale nr. 1**: 1701 - 1512 = **189 punten** — maar croquemboucheje
  is fragment-dood (zie §3), dus dit getal is niet inbaar.

**Rechtstreekse controle op het echte bord:** ons recordbord `mg_ext_best.json` (4457, scoring op
het defecte bord) scoort met exact dezelfde zetreeks op het gecorrigeerde bord **4683 (+226)`.
Per hersteld veld: **(3,14) = +216**, (6,12) +4, (11,14) +4, (8,12) +2, (7,11)/(5,13)/(9,13) +0.
Die +216 is precies de `y` van polymelkzuurtje op de DL binnen de x27-slotzet — de correctie
werkt volledig in ons voordeel en bevestigt het model.

## 2. Zak-toets en blanco-degradatie

De drie ankerwoorden zijn 45 tegels uit 100 letters + 2 blanco's. Per triplet:
`tekort = SOM_letter max(0, nodig - voorraad)`; `tekort > 2` = dood. Bij tekort 1 of 2 komt er een
blanco op de **goedkoopste** cel (kleinste `wm(y) * lm(y,x) * v(letter)`), waarde 0.

De zak is de bindende beperking, niet de woordwaarde: van de **120.399** tripletten die de
waarde-drempel halen sneuvelen er **117.979 (98%)** op de zak. Dit is de zak-druk-lemma uit het
dossier, nu kwantitatief op tripletniveau.

## 3. Bezorgbaarheid (fragment-lemma)

Harde check, identiek aan het criterium dat gymjuffrouwtjes doodde (`mg_delivery.solve_delivery`,
`FRAME_CAMPAIGN.md`): bestaat er een 8-kolom-pre-set uit `{1..6, 8..13}` waarvan elke maximale run
ofwel lengte 1 heeft, ofwel in blokken (<=3) legbaar is met **elk tussenstadium-fragment een geldig
woord**? Kolommen 0, 7 en 14 (de TW's) blijven altijd voor de slotzet.

Resultaat: van de 434 rij-0/14-kandidaten boven de waardevloer zijn er **376 bezorgbaar**.
**De nominale nr. 1, croquemboucheje (1701), is NIET bezorgbaar** — geen enkele 8-pre-set overleeft
de fragmenttoets (fragmentrijkdom 3). Rij 7 wordt bezorgd via een 8-letter-deelwoord `w[a:a+8]`;
strikt moet dat venster de beide x4-kolommen 4 en 10 dekken (a in {3,4}).

### Masker-bewuste waardering (de eerlijke waarde)

Een DL op x=3/11 telt alleen onder de x27 als die cel in de **slotzet** ligt; ligt hij in de
pre-set, dan verzilvert hij alleen zijn dubbel in het kleine bezorgzetje. De slotzet heeft 7 cellen:
{0, 7, 14} + 4 vrije middenkolommen. Dus:

    bezorgbare waarde(w, y) = wm(y) * ( S(w) + max over geldige pre-sets van de vrijgehouden DL's )

Structureel feit voor rij 7: het 8-venster loopt van a tot a+7 met 1 <= a <= 6, dus het **kan nooit
zowel kolom 3 als kolom 11 vrijlaten** — rij 7 verzilvert hoogstens een van de twee DL's.

Per woord (masker-bewust, architectuurmultipliers 27/9/27):

* geschenkcheques: bonus 15 (**beide** DL's vrij: c=5 + q=10) -> 1674 = zijn volle nominale waarde
* polymelkzuurtje: bonus 8 (alleen (3,14): y=8) -> 1458
* flexwerkstertje: venster [4,11], bonus 8 (x op kolom 3) -> 441

## 4. De twee ranglijsten

### A. Nominaal (taakformule, blanco-gedegradeerd) — top-10 van 14

| # | R0 / R7 / R14 | nominaal | tekort | blancoverlies | gedegr. | delta | masker-bewust |
|---|---------------|---------:|-------:|--------------:|--------:|------:|--------------:|
| 1 | vluchtreflexjes / babyzwemstertje / verzamelcheques | 4203 | 0 | 0 | 4203 | +99 | 3231 (-342) |
| 2 | vluchtreflexjes / babyzwemstertje / chequeformulier | 4176 | 0 | 0 | 4176 | +72 | 3474 (-99) |
| 3 | verzamelcheques / bouwcuratrixjes / playbackshowtje | 4257 | 1 | 90 | 4167 | +63 | 3213 (-360) |
| 4 | vluchtreflexjes / bodysurfstertje / verzamelcheques | 4167 | 0 | 0 | 4167 | +63 | 3213 (-360) |
| 5 | vluchtreflexjes / babyzwemstertje / jacquardweefsel | 4203 | 1 | 72 | 4131 | +27 | 3357 (-216) |
| 6 | verzamelcheques / flexwerkstertje / playbackshowtje | 4131 | 0 | 0 | 4131 | +27 | 3249 (-324) |
| 7 | vluchtreflexjes / babyzwemstertje / wetenschapsquiz | 4122 | 0 | 0 | 4122 | +18 | 3420 (-153) |
| 8 | vluchtreflexjes / babyzwemstertje / vormingscheques | 4122 | 0 | 0 | 4122 | +18 | 3150 (-423) |
| 9 | jacquardweefsel / babyzwemstertje / luchtdrukmaxima | 4122 | 0 | 0 | 4122 | +18 | 3312 (-261) |
| 10 | jacquetkostuums / flexwerkstertje / playbackshowtje | 4185 | 1 | 72 | 4113 | +9 | 3159 (-414) |
| .. | (11) vluchtreflexjes / babyzeepaardjes / verzamelcheques | 4113 | 0 | 0 | 4113 | +9 | 3186 (-387) |
| .. | (12) vluchtreflexjes / babyroofstertje / verzamelcheques | 4113 | 0 | 0 | 4113 | +9 | 3186 (-387) |
| **13** | **geschenkcheques / flexwerkstertje / polymelkzuurtje** | **4104** | **0** | **0** | **4104** | **+0** | **3573 (+0)** |
| 14 | chequeformulier / flexwerkstertje / playbackshowtje | 4104 | 0 | 0 | 4104 | +0 | 3492 (-81) |

De lijst is **volledig**, niet een top-K-steekproef: uit `MAXA = 1701` en `MAXB = 1044` volgen
bewijsbare vloeren (rij 0/14 >= 1359, rij 7 >= 702) waaronder geen triplet onze 4104 kan halen.
Rij 0 en rij 14 zijn waarde-identiek, dus de spiegeling (P boven / G onder) is gratis.

### B. Masker-bewust / bezorgbaar (de eerlijke ranglijst)

    tripletten met bezorgbare waarde >= 3573:  2      rang huidig triplet: 1

| # | R0 / R7 / R14 | bezorgbaar | nominaal | tekort |
|---|---------------|-----------:|---------:|-------:|
| **1** | **geschenkcheques / flexwerkstertje / polymelkzuurtje** | **3573** | 4104 | 0 |
| 2 | geschenkcheques / flexwerkstertje / papyruszuiltjes | 3573 | 4050 | 0 |

Met de losse rij-7-eis (elk 8-venster, geen x4-plicht; 31.029 kandidaten i.p.v. 9.703) verandert
er niets: nog steeds exact dezelfde twee, huidige op 1.

## 5. Conclusie

**Wij wisselen NIET van triplet.**

1. Nominaal (kale taakformule) staat ons triplet 13e van 14 en laat maximaal **+99** liggen
   (vluchtreflexjes / babyzwemstertje / verzamelcheques, 4203).
2. Zodra de bezorgbaarheid meetelt — welke DL's je feitelijk in de x27-slotzet kunt houden — draait
   dat volledig om: ons triplet is **globaal optimaal (3573)**, met 99 tot 423 punten voorsprong op
   elk van de nominale rivalen. De reden is geschenkcheques: het is het enige topwoord dat een
   fragment-geldige pre-set heeft die **beide** DL-kolommen (3 en 11) vrijhoudt, waardoor c=5 en
   q=10 allebei onder de x27 vallen (+405 t.o.v. nul-bonus).
3. Enige gelijke: **papyruszuiltjes** i.p.v. polymelkzuurtje op rij 14 (ook 3573, maar 54 lager
   nominaal, dus strikt slechter zodra een kolomwoord of herscoring de niet-verzilverde DL raakt).
   Geen reden om te wisselen.
4. De bordcorrectie is **pure winst**: ons bestaande recordbord gaat van 4457 naar **4683** met
   ongewijzigde zetreeks, waarvan +216 uit de herstelde DL (3,14) onder polymelkzuurtjes `y`.

Vervolgens relevant: alle scores/plafonds die op het defecte bord zijn berekend (records, klasse-
plafonds, footprint-optima) moeten worden herscoord — ze zijn stelselmatig te laag, met name daar
waar rij 14 en de rijen 11-13 in x-vermenigvuldigde slotzetten meedoen.
