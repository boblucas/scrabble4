# BINGO-HERGROEPERING — kan het record een 12e bingo dragen?

Script: `experiments/mg_bingoregroup.py` (modi: `lines,ub,merge,split,repart,anneal,legal,cross,refit12`).
Basis: `experiments/results/maxgame_BEST.json` — 101 tegels, 33 zetten,
**11 bingo's (550 bonus)**, zetmaten 21×1 + 1×3 + 11×7. Het record schoof tijdens dit onderzoek
van **4777** naar **4778** (een tegel verplaatst: (2,11) → (14,4), rij 4 wordt `overzwevenden`);
de structuur — en dus elke conclusie hieronder — is in beide identiek. Getallen zijn per meting
gelabeld met hun basis.

**Antwoord in één zin: een 12e bingo bestaat, is volledig geverifieerd, en kost 5 punten.**

## 0. Methode

De identiteit uit `mg_mceiling.py`

    score = SOM_c m(c)·waarde(c) + 50·#zetten-van-7

is bij **vaste bezetting én vaste letters geen plafond maar de score zelf** (geverifieerd:
m-calculus 4777 == arbiter 4777). Daarmee is elke herindeling van de 101 tegels over de zetten
in ~0,2 ms exact te evalueren, zonder solver en zonder woordenboek. Het woordenboek komt er in
twee stappen bij:

* `wordable()` / `badruns()` — noodzakelijke voorwaarde zonder solver: elke tussenrun moet een
  woord kúnnen zijn gegeven de vaste letters van rij 0/7/14 (harde filter, ~0,3 ms);
* `MG.score_game` — de arbiter, en `refit()` — CP-SAT-herlettering bij vast schema.

## 1. Waar kán een 12e bingo vandaan komen?

Een zet ligt altijd op één lijn. Tel per lijn de **eigen tegels** (tegels die door zetten van
die lijn worden gelegd); een lijn met n eigen tegels draagt hoogstens ⌊n/7⌋ bingo's.

| lijn | eigen tegels | bingo's | capaciteit |
|---|---|---|---|
| rij 0 | 11 | 1 | 1 |
| rij 4 | 9 | 1 | 1 |
| rij 7 | 11 | 1 | 1 |
| **rij 14** | **14** | **1** | **2** |
| kol 2 | 11 | 1 | 1 |
| kol 4/5/7/10/11/12 | 7–9 | 1 elk | 1 elk |

Alle 11 lijnen met ≥7 eigen tegels leveren al een bingo: **de geometrie is bingo-verzadigd op 11**
zolang je de zetten binnen hun huidige lijn houdt.

**Uitputtende scan (`MODE=merge`)** over alle collineaire 7-deelverzamelingen van de 24
niet-bingo-tegels × alle 34 invoegposities:

* alleen **rij 14** heeft 7 niet-bingo-tegels: x = 5,6,8,9,10,11,12;
* die hebben een **gat op x=7**, en (7,14) wordt pas door de slotzet gelegd → **0 legale kandidaten**.

Zonder de vormeis zou die samenvoeging **+22** waard zijn (50 bonus − 28 herscoring): de trade
is dus op zichzelf gunstig, hij is puur *geometrisch* geblokkeerd.

## 2. Stelling: een TWS-rij met een ×27-slotzet draagt hoogstens één bingo

De slotzet moet x = 0, 7 en 14 bevatten, anders zakt de woordfactor van 27 naar 9 of 3.
Een tweede 7-zet op die rij mag die drie cellen dus niet gebruiken en houdt over: x ∈ {1..6}
(6 cellen) en x ∈ {8..13} (6 cellen). Een zet moet een aaneengesloten span hebben, dus zou hij
over x=7 moeten bruggen — maar (7,14) ligt er nog niet. **Onmogelijk.** Zelfde argument voor rij 0.

Prijskaartje van een TWS-cel in de slotzet (gemeten met `get_word_score`):

| slotzet | woord | score | verlies als één TWS-cel eruit gaat |
|---|---|---|---|
| rij 0 | geschenkcheques ×27 | 1724 | **−1166** |
| rij 14 | polymelkzuurtje ×27 | 1508 | **−1022** |
| rij 7 | flexwerkstertje ×9 | 491 | −344 |

Een bingo is 50 punten. **Een TWS opgeven voor een bingo is 20–23× te duur.**

Gemeten bevestiging (`MODE=repart`): rij 14 daadwerkelijk in twee bingo's splitsen kost
**−897** (beste van 8 vormlegale 7/7-verdelingen × alle posities); de goedkoopste is
`x5,6,7,8,9,10,11 + x0,1,2,3,12,13,14` → 3880 met 12 bingo's.

## 3. Omgekeerde richting: een bingo splitsen

`MODE=split`, uitputtend: elke 7-zet × alle 126 deelverzamelingen × beide volgordes × alle
posities. Beste resultaat **−38/−39** (splits een kolombingo in 6+1): je verliest 50 bonus en wint
maar ~12 herscoring. **Alle 11 bingo's staan dus goed.**

Dat is meteen de sleutel tot het hele dossier: de marginale herscoringswaarde van een losse
tegel is in dit bord ~10–20 punten. Zeven losse tegels tot één bingo samenvoegen levert
50 − 7·(hun herscoring) op; dat is alleen positief als die herscoring gemiddeld < ~7 is.

## 4. De 12e bingo bestaat wél — via een KRUIS-LIJN-herverdeling

Rij 7 is de uitzondering op de stelling van §2: daar ligt (7,7) **al vanaf zet 1** (kolom 7 is de
openingszet). Een tweede rij-7-zet mag dus wél over x=7 bruggen. Rij 7 heeft echter maar
11 eigen tegels — (5,7), (10,7) en (11,7) horen bij kolom 5/10/11. Geef die drie aan rij 7 en
laat de kolommen hun 7e tegel elders halen:

| lijn | oud | nieuw |
|---|---|---|
| rij 7 | slotzet(7) + 4 losse | **voorgroep x4..11\\{7} = "werkster" (7)** + slotzet x0,1,2,3,12,13,14 (7) |
| kol 5 | rijen 0,1,2,3,5,6,7 + los (5,8) | rijen 0,1,2,3,5,6,**8** (9-letterwoord in één zet) |
| kol 10 | rijen 0,1,2,3,5,6,7 + los (10,8) | rijen 0,1,2,3,5,6,**8** (idem) |
| kol 11 | rijen 7..13 + (11,14) in de 3-zet | rijen **8..14** (8-letterwoord, (11,7) ligt er al) |

(op de 4777-basis waren dat `erbarmden`, `eindfasen` en `raspiger`; na herlettering
`epicrisen`, `enabelden` en `roggeaar`.)

Netto **+1 bingo zonder één ×27-slotzet te breken**, bij **exact dezelfde 101 cellen en dezelfde
letters**. De gaten op rij 4 en rij 7 in de nieuwe kolomzetten worden gevuld door tegels die er
al liggen, dus de vorm klopt.

De rij-7-voorgroep moet een woord zijn: van de 6 mogelijke vensters [a,a+7]\\{7} is alleen
a=4 lexicaal geldig (`werkster`); `lexwerks`, `exwerkst`, `xwerkste`, `erkstert`, `rkstertj`
bestaan niet.

**Resultaat (`MODE=cross`, harde woordfilter `badruns()` in de doelfunctie):**

| meting | basis 4777 | basis 4778 |
|---|---|---|
| 12-bingo-schema, **zelfde letters**, arbiter OK | 4763 (−14) | **4767 (−11)** |
| m-plafond van dat schema (rij 0/7/14 vast) | 4856 (basis 4867) | 4873 (basis 4881) |
| na **herlettering** (`MODE=refit12`, CP-SAT, rij 0/7/14 vast) | 4764 | **4773 (−5)** |
| controle: dezelfde herlettering op het BASIS-schema | 4777 (onveranderd) | — |

Het schema krimpt van 33 naar **28 zetten**. Geverifieerde borden:
`experiments/results/bingo12_sched.json` (4767, letters van het record) en
`experiments/results/bingo12_refit.json` (**4773**, herletterd: kolom 5 = `epicrisen`,
kolom 10 = `enabelden`, kolom 11 = `roggeaar`, kolom 4 = `windboom`, rij-7-voorgroep = `werkster`).

Waar de 5 punten blijven: de 50 bonus weegt niet op tegen het verlies van vier losse
herscoringszetten ((4,7)/(6,7)/(8,7)/(9,7) worden één zet), plus (5,8) en (10,8) die in hun
kolomzet verdwijnen en (11,14) die uit de rij-14-keten wordt getrokken.

Dit is het **dichtstbijzijnde alternatief** dat we kennen: −5 op 4778. Het plafondverschil is
−8, dus met een schema-zoektocht die dat gat dicht (of een sterkere herlettering) kan de
12-bingo-tak alsnog voorbij het record komen. Dat is de enige nog levende bingo-lead.

## 5. Bovengrens op het aantal bingo's

`MODE=ub` — set-packing (CP-SAT) over alle 12 373 vormlegale 7-groepen in deze bezetting,
zonder zetvolgorde-eis: **maximaal 13 disjuncte groepen** (101 tegels ⇒ absoluut plafond 14).
Zo'n pakking van 13 splitst echter zowel rij 0 als rij 14 in twee bingo's en offert daarmee
twee ×27-slotzetten: ruwweg **−2200 voor +100**. Met de stelling van §2 erbij is
**12 het maximum dat de ×27-structuur overleeft**, en dat is precies de constructie van §4.

Wat zou 12–13 *rendabele* bingo's toelaten? Niet het splitsen van lijnen, maar **meer lijnen**:
elke bingo vraagt een eigen woordlijn met ≥7 eigen tegels. Met 101 tegels zijn 14 zulke lijnen
denkbaar, maar dan zit ~91 van de 101 tegels vast in groepszetten en houd je ≤10 tegels over
voor losse herscoringszetten. In dit bord zijn de late losse tegels 14–27 punten per stuk waard
(zetten 27–32 scoren 16,18,14,19,27,16) — zeven daarvan opofferen voor 50 punten is structureel
verlies. **De bingo-bonus is in de x27-architectuur geen hefboom; herscoringsdichtheid wel.**

## 6. Overige scans (nul opbrengst)

* `MODE=anneal` (8×60 000 stappen, split/merge/verplaats, exacte doelfunctie): beste m-schema
  **4830 (+53)**, maar met de huidige letters woord-illegaal (zet 4 vormt `rk`). Herlettering
  vergt de volledige 101-cel-CP-SAT; met rij 0/7/14 vast is het schema-plafond niet hoger dan
  de basis. Zie `bingoregroup_best.json.anneal.json`.
* `MODE=legal` (arbiter als harde eis, 6×8 000 stappen): **+0**. Het huidige schema is een
  sterk lokaal optimum in de woordlegale schemaruimte.

## 7. Conclusie

1. Een 12e bingo uit *losse* tegels bestaat niet: geen enkele lijn heeft 7 niet-bingo-tegels met
   een vulbare span (rij 14 komt er met 7 tegels het dichtst bij, maar strandt op x=7).
2. Een 12e bingo bestaat wél via een kruis-lijn-herverdeling (rij 7 leent (5,7)/(10,7)/(11,7)),
   is volledig geverifieerd, en kost na herlettering nog maar **5 punten** (4773 vs 4778).
3. Elke andere route naar 12+ bingo's breekt een ×27-slotzet en kost 900–2200 punten.
4. **Geen record via de bingo-bonus, maar de 12-bingo-tak is niet dood**: het schema-plafond
   ligt maar 8 punten onder dat van het record, dus een betere zetvolgorde binnen deze familie
   of een langere herlettering kan er alsnog overheen. De hoofdhefboom in dit bord blijft
   herscoringsdichtheid, niet het aantal 7-tegelzetten.

## Reproductie

```bash
MODE=lines,ub,merge,split,repart  .venv/bin/python experiments/mg_bingoregroup.py
MODE=cross AWIN=4 OBJ=ceil ITERS=50000 SEEDS=30 TRIES=200 .venv/bin/python experiments/mg_bingoregroup.py
MODE=refit12 SCHED=<schema.json> FIX37=1 TLIM=900 .venv/bin/python experiments/mg_bingoregroup.py
```

Bestanden (niets bestaands overschreven; `maxgame_BEST.json` is niet aangeraakt):

* `experiments/results/bingo12_sched.json` — 12-bingo-schema met de letters van het record,
  arbiter **4767**, 101 tegels, 28 zetten.
* `experiments/results/bingo12_refit.json` — hetzelfde schema herletterd, arbiter **4773**.
