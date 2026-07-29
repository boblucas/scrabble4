# WEERLEGGINGSMOTOR — kan deze triplet+masker-klasse 4819 halen?

Vraag (opdracht): bewijs dat met

* `geschenkcheques` / `flexwerkstertje` / `polymelkzuurtje` op rij 0 / 7 / 14,
* slotmaskers rij 0 `{0,3,7,8,11,13,14}`, rij 7 `{0,1,2,3,12,13,14}`, rij 14 `{0,1,2,3,7,13,14}`,

**geen enkel legaal Nederlands Scrabble-spel de score 4819 haalt.**

Ons eigen record is 4793 (`experiments/results/maxgame_BEST.json`, arbiter `ok=True`); 4819 is
het externe referentierecord.

Gereedschap: `experiments/mg_refute.rs` (rekenwerk) + `experiments/mg_refute.py` (precompute,
ijking, CP-SAT-narekening).

---

## 0. Uitkomst in vijf regels

1. **De stelling is NIET bewezen, en waarschijnlijk niet waar.** De scherpste zetvolgorde-vrije
   én letter-vrije bovengrens op de bezetting van ons eigen record is **4867** (CP-SAT,
   bewezen optimaal) — 48 punten BOVEN de drempel 4819. Zelfs op de voetafdruk die we al
   hebben is 4819 dus niet uitgesloten.
2. De motor lokaliseert precies waar de ruimte zit: de **FRAME-klasse** — kolom 14 is een
   volle TWS-kolom (rijen 0, 7 en 14 zijn alle drie maskercellen) en draagt als ENKELE lijn
   tot **477** punten (416 na blanco-correctie), tegen 267 voor de beste vrije lijn van het
   record. De campagne heeft die klasse nooit gebouwd.
3. Wat wél bewezen is: uitputtende **stratificatie**. Elke bezetting zonder horizontale run in
   de vrije rijen en met alle verticalen ≤ 7 lang haalt hoogstens **4777** — dat weerlegt in
   één keer 3,57·10³⁶ bezettingen.
4. Doorvoer: de scherpe per-bezettings-grens kost **~13 µs** (≈ 73.000 bezettingen/seconde,
   één kern); de opsomming levert 200.000 overlevenden per 7 seconden.
5. De motor is geijkt (§6): de ontbindingsidentiteit reproduceert de arbiterscore exact, geen
   enkele gerealiseerde lijnbijdrage overschrijdt zijn per-lijn-DP, en op de recordbezetting is
   de grens 4993 ≥ 4793.

---

## 1. Het fundament: de lijn-ontbinding

Uit `experiments/SCHEDULEPROOF.md` (numeriek geijkt tegen `MG.score_game`):

```
score  =  SOM over de maximale EINDruns L van  g_L(geschiedenis van L)
g_L    =  alle woordscores op L  +  50 * (aantal 7-tegelzetten met L als hoofdlijn)
```

*Waarom.* Elke gescoorde run is een aaneengesloten run in één richting, en omdat de span van een
zet volledig gevuld moet zijn ligt zo'n run in precies één maximale eindrun. Elke bingo legt 7
tegels die per definitie op één lijn liggen, dus hoort bij precies één hoofdlijn. Geen
dubbeltelling, niets buiten de som. ∎

De *geschiedenis* van L is de geordende opdeling van L's cellen in groepen (één groep per zet die
cellen op L legt). g_L hangt alleen daarvan af, en van L's letters. Daarmee is

```
score  <=  SOM over de lijnen L van  U_L,        U_L = max over geschiedenissen h en letters W van g_L(h,W)
```

een geldige bovengrens: alle koppelingen tussen lijnen (globale zetvolgorde, de aanraakregel over
lijnen heen, gedeelde letters op kruispunten, de zak) worden weggelaten, en beperkingen weglaten
kan een maximum alleen verhogen.

De motor bestaat uit het scherp maken van die grens, plus drie koppelingen die er *wel* in gaan:
de **zak** (Lagrange), de **ankersteun** (aanraakregel) en de **kruispunten** (CP-SAT-narekening).

---

## 2. De per-lijn-DP (de kern)

Voor een lijn L van lengte n ≤ 15 met multiplier-profiel (wm, lm) en letters W is
`max_h g_L(h,W)` exact uit te rekenen met een DP over de 2^n deelverzamelingen van reeds gelegde
posities. Een overgang van toestand S is een **groep** g = [a..e] \ S met a,e nieuw en |g| ≤ 7
(precies de zetvorm: alle nieuwe tegels op één lijn, span volledig gevuld — al gelegde cellen
mogen worden overspannen). De opbrengst is

```
inc = (product van wm over de nieuwe cellen) * SOM over het gevormde blok [lo..hi] van
      (val * lm op nieuwe cellen, val op oude)      + 50 als |g| = 7
```

en de overgang bestaat alleen als het gevormde maximale blok `W[lo..hi+1]` een **woord** is.

Twee spelregels gaan er hard in:

* **centrumregel** (alleen rij 7): de groep die (7,7) bevat moet de eerste groep van die lijn
  zijn, want zet 1 van het spel dekt (7,7);
* **maskerregel** (ankerrijen): de 7 maskercellen vormen samen de laatste groep — dat is precies
  wat "slotmasker" betekent;
* **aanraakregel** (zie §4): een groep die geen loodrechte steun heeft moet binnen de lijn aan al
  gelegde cellen grenzen of eroverheen spannen.

De DP is in Rust geschreven (`maxg`) en onafhankelijk in Python geherimplementeerd
(`mg_refute.py: line_maxg`); beide geven op de gecontroleerde gevallen exact dezelfde waarden
(zie §6).

---

## 3. De drie ankerrijen zijn een constante

Rij 0, 7 en 14 zijn altijd volle runs van 15 met **vaste** letters. Hun bijdrage hangt dus alleen
van hun eigen geschiedenis af, en die is met de DP exact te maximaliseren:

| rij | woord | vrij | + maskerregel | + centrumregel |
|---|---|---:|---:|---:|
| 0 | geschenkcheques | 1743 | 1743 | **1743** |
| 7 | flexwerkstertje | 955 | 581 | **561** |
| 14 | polymelkzuurtje | 1561 | 1561 | **1561** |

```
ANCH = 1743 + 561 + 1561 = 3865
```

> **Lemma 1 (ankerplafond).** In elk legaal spel van deze klasse dragen de drie ankerrijen samen
> ten hoogste 3865 punten bij. Bijgevolg moet elk spel met score ≥ 4819 uit alle **overige**
> lijnen samen ten minste **4819 − 3865 = 954** punten halen.

Ter vergelijking: het record 4793 = 3840 (anker) + **953** (overige lijnen). De drempel ligt dus
precies één punt boven wat het record uit zijn vrije lijnen haalt, terwijl het record op de
ankerrijen nog 25 punten laat liggen.

---

## 4. Ankersteun, het eiland-lemma, en de aanraakregel

Elke zet moet het bord raken. Voor een groep g binnen lijn L betekent dat: óf g grenst binnen L
aan reeds gelegde cellen (of spant eroverheen), óf een van g's cellen heeft een **loodrechte**
buur die bezet is. Die loodrechte buur hoeft op dat moment nog niet te liggen — maar als hij in
het EINDbord leeg is, ligt hij zeker nooit. Dus:

> **Lemma 2 (steun).** `U_L` mag worden uitgerekend met de aanvullende eis dat elke groep
> aanraakt via een cel waarvan de loodrechte buur in het eindbord bezet is, of via aangrenzing
> binnen de lijn zelf. Dat is een noodzakelijke voorwaarde, dus de zo verkregen waarde blijft een
> bovengrens.

Toegepast op de ankerrijen geeft dat een tabel `A_y[steunpatroon]`: de 7 maskercellen komen in de
slotzet (die raakt sowieso aan, want de pre-cellen liggen dan al), dus alleen de 8 pre-cellen per
rij tellen — 256 patronen per rij, in twee seconden uitgerekend.

```
rij  0: 63/256 steunpatronen LEGBAAR, waarde 1740..1743
rij  7: 256/256 legbaar,               waarde 561
rij 14: 217/256 legbaar,               waarde 1551..1561
```

De 63 = 3·7·3·1 is precies het **eiland-lemma** van `MASKGEOM.md`: de pre-cellen van rij 0
vallen door het masker uiteen in de eilanden {1,2}, {4,5,6}, {9,10}, {12}, en elk eiland heeft
minstens één kolom nodig die (x,1) bezet — anders kan de eerste zet in dat eiland nergens
aanraken. Hier komt dat lemma er *automatisch* uit als "geen legale geschiedenis". Idem rij 14
met 217 = 7·31 en de eilanden {4,5,6}, {8..12}.

Toegepast op de **verticalen** is Lemma 2 nog veel harder, en dat is de belangrijkste enkele
meting van dit werk (§5).

---

## 5. De zak: Lagrange-relaxatie

De 45 ankercellen leggen 45 tegels vast. Wat overblijft is de **restzak**

```
a6 b2 d5 e8 f1 g2 i4 m2 n9 o5 p1 r2 s2 t2 v2 w1 z1  = 55 lettertegels  + 2 blanco
```

en de zak (100 letters + 2 blanco) minus de tegel die de tegenstander vasthoudt geeft ten hoogste
101 tegels op het bord, dus **ten hoogste 56 vrije cellen**. (Dat is een stelling, geen
waarneming: `RESERVE`-regel. Dat het in de praktijk altijd *exact* 56 zijn, is een waarneming en
wordt hier NIET gebruikt — de motor telt met ≤ 56.)

**Zak-lexicale runtoets.** Bij het bouwen van de per-lijn-tabellen wordt elk woord verworpen
waarvan de letters op de VRIJE posities niet uit de restzak te bouwen zijn (op ≤ 2 blanco's na).
Sound: in elk echt bord komen die letters uit precies die restzak. Blanco's houden in het model
hun volle letterwaarde — een overschatting, dus in de veilige richting.

**Eigendom.** Elke vrije cel ligt in ten hoogste één verticale en één horizontale run. We laten
de **verticaal** de zaktegel claimen; een cel die op geen enkele verticale run (≥2) ligt wordt
door zijn horizontale run geclaimd. Zo claimt elke vrije cel precies één lijn, dus

```
SOM over lijnen L van (letters van W_L op de door L geclaimde posities)  <=  restzak + 2 blanco
```

componentsgewijs. Voor elke λ ≥ 0 geldt dan

```
SOM_L U_L(W_L)  <=  SOM_L max_W [ U_L(W) - λ·cnt_claim,L(W) ]  +  λ·RESTZAK + 2·max λ
```

en de rechterkant is een som van **per-lijn-constanten** plus een globale constante: precies wat
een microseconde-weerlegger nodig heeft. λ wordt met subgradiënt-afdaling geoptimaliseerd
(`mg_refute_bin lamopt`); elke λ ≥ 0 geeft een geldige grens, dus optimaliseren mag vrij.

**Tabelafkapping.** Per lijn worden niet alle woorden bewaard maar de top-K op U plus de top-K op
U − λ₀·cnt. Voor de weggelaten woorden geldt `U ≤ tail` (de K+1-ste U-waarde) en λ·cnt ≥ 0, dus
`max over de rest van [U − λ·cnt] ≤ tail`. De afkapping is dus **sound**.

---

## 6. IJKING

`MODE=calib .venv/bin/python experiments/mg_refute.py` — drie harde eisen, alle drie groen:

```
(1) arbiter 4793 ok=True | lijn-ontbinding 4793 | identiek: True
(2) 15 lijnen, 0 schendingen van  g_L(gerealiseerd) <= per-lijn-DP met DEZELFDE letters
(3) ANCH-grens 3865 >= anker gerealiseerd 3840
```

Per lijn (record, eigen letters):

```
H15 geschenkcheques 1743 <= 1743      V12 smarotsenden 164 <= 164
H3  boa               10 <=   13      V8  efedrine      73 <=  73
H13 overzwevenden    267 <=  267      V8  enabelde      60 <=  87
H2  eg                10 <=   10      V8  uitademt     100 <= 100
H15 flexwerkstertje  536 <=  561      V2  on             4 <=   4
H15 polymelkzuurtje 1561 <= 1561      V7  waakton       74 <=  78
                                      V2  eg            10 <=  10
                                      V8  windboom      84 <=  84
                                      V8  raspiger      97 <=  97
```

Negen van de vijftien lijnen zitten **exact** op hun per-lijn-maximum. Met de eigen letters van
het record is de per-lijn-som 4852 — 59 boven de gerealiseerde 4793. Zo strak is de ontbinding.

Onafhankelijke kruiscontrole Rust ↔ Python: de zwaarste lijn van de hele klasse (kolom 14,
volledige TWS-kolom, 165 zak-bouwbare woorden) geeft in beide implementaties **1132**, en met de
aanraakregel in beide **477**.

---

## 7. Wat de motor eruit haalt

### 7.1 De opsomming: kolom-DP over ALLE bezettingen

Een bezetting is volledig bepaald door 15 kolommaskers van 12 bits (de vrije rijen 1..6, 8..13;
rijen 0/7/14 liggen altijd vol). De verticale runs van kolom *x* hangen **alleen** van masker *x*
af, dus de verticale bijdrage is per kolom separabel. De horizontale runs koppelen naburige
kolommen; die worden opgevangen met **paargewichten**

```
p(y,x) = max over runs r in rij y die het paar (x,x+1) bevatten van  Umax(r)/(|r|-1)
```

zodat `SOM over de |r|-1 paren van r van p >= Umax(r)` voor elke run — een verruiming, dus gezond,
en ze dekt élke runstructuur. Verder in de DP:

* het tegelbudget (≤ 56) als rugzakdimensie;
* het **eiland-lemma** als 2 toestandsbits (per ankerrij één "huidig eiland al gedragen"-vlag);
* een **isolatievlag** per kolom: een kolom mag verklaren dat geen van zijn vrije cellen een
  horizontale buur heeft (dan geldt `masker[x-1] & masker[x] = 0` én `masker[x] & masker[x+1] = 0`)
  en telt in ruil met de scherpe steunvariant. Beide richtingen zijn gezond.

De kolomovergang `B[pm] = max_m (A[m] + SOM_i w_i·[pm_i ∧ m_i])` gaat met een 12-staps
bit-transformatie in O(12·4096) in plaats van O(4096²); een hele DP kost daardoor ~1 s.

Uit de DP volgt (a) het **maximum over de hele deelfamilie** — is dat < 4819 dan is de hele
deelfamilie in één keer weerlegd — en (b) via een DFS met dezelfde grens als snoeier de
**overlevenden**, die daarna de scherpe per-bezettings-grens en tenslotte CP-SAT krijgen.

### 7.2 Stratificatie: wat is WEL weerlegd

`A` = de verzameling vrije rijen waarin überhaupt een horizontale run mag zitten; `MAXVLEN` = de
maximale lengte van een verticale run. Elke bezetting valt in precies één stratum (neem A = de
rijen waarin ze echt een horizontale run heeft), dus de stratificatie is uitputtend. λ wordt per
stratum geoptimaliseerd (`lamdp`); elke λ ≥ 0 blijft geldig.

| MAXVLEN | A = ∅ (geen horizontale run) | verdict |
|---:|---:|---|
| 6 | **4591** | WEERLEGD |
| 7 | **4777** | WEERLEGD |
| 8 | 4970 | open |
| 9 | 5094 | open |
| 10 | 5119 | open |
| 12 | 5159 | open |
| 15 | 5415 | open |

Het A = ∅, MAXVLEN ≤ 7 stratum telt (exacte telling met een zeta-transform)
**3,57 · 10³⁶ bezettingen**, allemaal in één DP van een seconde weerlegd.

Met **één** actieve rij (|A| = 1, alle 12 keuzes doorgerekend) springt de grens naar

```
MAXVLEN = 6 :  4871 .. 5011   (laagste bij rij 6, hoogste bij rij 1)
MAXVLEN = 7 :  5001 .. 5113
```

Geen daarvan komt onder 4819. De oorzaak is de **binaire steunvariant**: zodra een kolom één
cel in de actieve rij heeft, mag hij de ruime steunvariant gebruiken voor ál zijn runs, ook al
heeft de rest van de kolom geen enkele horizontale buur. Dat is de scherpste bekende zwakte van
de huidige relaxatie en tegelijk het duidelijkste verbeterpunt (zie §9).

### 7.3 De scherpe per-bezettings-grens

Voor een concrete bezetting kent de motor de exacte maximale runs, het exacte ankersteunpatroon
en het exacte steunmasker per lijn (`sharp`, die de per-lijn-DP met dat masker opnieuw draait).

```
bezetting                              vrije cellen   Lagrange   CP-SAT (kruispunten)
record (maxgame_BEST, 4793)                     56       4993     4867  (BEWEZEN OPTIMAAL)
F1  kolom 14 vol + 6 dragers                    54       4988     4950
F3  kolom 14 vol + kolom-2-keten                54       5024     4951
F4  kolom 14 vol + rij-4-fragmenten             54       4976     4914
R   record zonder de rij-4-laan                 51       4804     4729   <- WEERLEGD
```

> **Stelling A (bewezen).** Bij de bezetting van ons record 4793 haalt geen enkele legale
> zetvolgorde met welke lettering dan ook meer dan **4867**.

Dat is de scherpste uitspraak die dit werk oplevert, en ze is *negatief* voor de opdracht:
4867 ≥ 4819, dus zelfs onze eigen voetafdruk sluit 4819 niet uit. Er ligt daar 74 punten
headroom boven het gerealiseerde 4793.

### 7.4 De FRAME: waar de ruimte zit

De maskers maken van kolom 0, 7 en 14 **volledige TWS-kolommen**: hun cellen in rij 0, 7 én 14
zitten alle drie in het slotmasker. Een 15-letterig verticaal woord daar wordt door alle drie de
slotzetten opnieuw gescoord, elke keer met de ×3 van die TWS.

```
kolom  0 : patroon g......f......p   0 woorden        -> dood
kolom  7 : patroon k......k......k   2 woorden        (kleermakerswerk, koekbakkerswerk)
kolom 14 : patroon s......e......e   600 woorden, 165 zak-bouwbaar
```

Per-lijn-maxima voor de volle kolom 14:

```
zonder aanraakregel                       1132
met aanraakregel (steun alleen op 0/7/14)  477   ("stemgerechtigde")
+ blanco-correctie (blanco = waarde 0)     416   ("standsbewustere", 1 blanco)
zonder blanco's                            361   ("staatsgevangene")
```

Ter vergelijking: de beste vrije lijn van het record is de rij-4-laan `overzwevenden` met 267
voor 13 tegels; kolom 14 haalt 416 voor 12 tegels — **34,7 punt/tegel tegen 20,5**.

> Dit is de klasse die `FRAME_CAMPAIGN.md` aankondigde en die de generator
> (`mg_configgen.py`) niet kan produceren: daar zijn de "dragers" per definitie kolommen die
> een rij-0-**pre**-eiland dragen, en kolom 14 is een **masker**cel. De volle TWS-kolom komt in
> de parameterisering niet voor.

#### FRAME-borden bestaan ook echt — hier is er een

De CP-SAT-narekening levert bij een oplossing niet alleen een grens maar een **volledige
lettering**. Onafhankelijk nagerekend (elke maximale run is een `dutch2026`-woord, de zak klopt):

```
F1  (54 vrije cellen, 99 tegels, 2 blanco)      plafond 4950
geschenkcheques        kolom 14 = spreeuwennestje  (s..e..e door drie TWS)
..o..v....i.n.p
..g..i....n.f.r
..g..d....d.a.e
..e..e.b..e.i.e
..n..n.a..n.r.u
..d..t.n..d.s.w
flexwerkstertje
....a..m...e..n
....a..a...d..n
....i..n...z..e
....b......a..s
....o......m..t
....o......e..j
polymelkzuurtje

F2  (56 vrije cellen, 101 tegels, 2 blanco)     plafond (scherp) 5067
    kolom 14 = steviabedrijfje, kolom 13 draagt (13,4) en (13,5)
```

Dat is precies wat de campagne tot nu toe niet had: `CONFIGGEN.md` §4 concludeerde dat "de
bindende beperking de LEXICALE INVULBAARHEID van de hele bezetting is" en dat elke geteste
configuratie CP-SAT-infeasible was. Deze FRAME-bezettingen zijn wél volledig te letteren, met
101 tegels en precies 2 blanco's. Wat er nog ontbreekt is een zetvolgorde die de per-lijn-maxima
ook werkelijk haalt.

De aanraakregel doet er precies het goede mee: kolom 14 is horizontaal geïsoleerd, dus zijn
cellen kunnen alleen groeien vanaf (14,0), (14,7) en (14,14) — en die drie komen uit de
slotzetten. Dat is de reden dat 1132 naar 477 zakt, en het is ook meteen het **bouwrecept**:
rij-7-slotzet eerst, dan kolom 14 laag voor laag omhoog en omlaag laten groeien (elke tussenstand
moet een woord zijn — de DP heeft dat al afgedwongen), dan de slotzetten van rij 0 en rij 14.

### 7.5 Tellingen en doorvoer

```
precompute (Rust, 14 threads)
   2310 lijnsleutels x 2 steunvarianten -> 2243 unieke profielen -> 4620 tabellen   402 s
   tables.bin 377 MB (per lijn: alle zak-bouwbare woorden met hun exacte U)
ankersteuntabel (Python)                                                              2 s
weerleggen
   scherpe per-bezettings-grens          ~13 us   (73.000 bezettingen/s, 1 kern)
   DP per deelfamilie                    ~1 s     (weerlegt de HELE deelfamilie ineens)
   DFS overlevenden + scherpe grens      200.000 overlevenden per 7 s
   CP-SAT (kruispunten + zak, exact)     3-120 s per bezetting
voorbeeldsweep A = 0, MAXVLEN = 8 (grens 4970, dus niet in bulk te weerleggen)
   200.000 ruwe overlevenden -> 182.071 halen ook de scherpe grens (scherpe grenzen 4819..4832)
   gespreide steekproef van 60 naar CP-SAT ->  57 x NEE (bewezen weerlegd), 3 x JA, 0 ONBEKEND
```

De laatste regel is het belangrijkste getal van de pijplijn: van de bezettingen die de scherpe
Lagrange-grens overleven wordt **95 % alsnog weerlegd** zodra de kruispuntconsistentie erbij
komt, in 3–8 seconden per stuk. De weerlegging is daar dus goedkoop — maar de 5 % die overblijft
en de 10³⁶ die de DFS nooit bereikt maken het bewijs onhaalbaar.

---

## 8. Soundness per zeef

| # | zeef | sound? | argument |
|---|---|---|---|
| S1 | lijn-ontbinding | JA | §1, plus numerieke ijking tegen `MG.score_game` |
| S2 | per-lijn-DP (max over geschiedenissen) | JA | volledige opsomming van de zetvorm binnen de lijn; koppeling weggelaten = verruiming |
| S3 | maskerregel + centrumregel | JA | hypothese van de stelling resp. spelregel (zet 1 dekt (7,7)) |
| S4 | aanraakregel / steunmasker (Lemma 2) | JA | noodzakelijke voorwaarde: een lege eindcel is nooit bezet |
| S5 | eiland-lemma | JA | volgt uit S4; niet apart geprogrammeerd maar afgeleid |
| S6 | tegelbudget ≤ 56 vrije cellen | JA | 100 letters + 2 blanco − ≥1 tegel bij de tegenstander − 45 ankercellen |
| S7 | zak-lexicale runtoets per woord | JA | de vrije posities van elke lijn komen uit de restzak, ≤ 2 blanco's |
| S8 | blanco's houden volle letterwaarde | JA (verruiming) | overschatting, dus in de veilige richting |
| S9 | Lagrange-zakkoppeling | JA | elke λ ≥ 0 geeft een geldige grens; eigendom claimt elke vrije cel precies één keer |
| S10 | tabelafkapping (top-K + staartgrens) | JA | `max over de rest [U − λ·cnt] ≤ max over de rest U = tail` |
| S11 | paargewichten voor horizontale runs | JA (verruiming) | `SOM_paren p ≥ Umax(run)` per constructie |
| S12 | isolatievlag | JA | de vlag legt de eis op waaronder de scherpe steunvariant geldig is |
| S13 | CP-SAT-narekening (kruispunten + zak) | JA | zelfde model als `SCHEDULEPROOF` §5.1, plus per-lijn de exacte U-tabel |
| S14 | vaste-komma-rekenen (schaal 1/64) | JA | eindgrens naar beneden afgerond; de echte score is geheel |

**Aannames die expliciet blijven staan (geen van beide is in een grens gebruikt):**

* *De stratificatie is uitputtend, de opsomming binnen een stratum niet altijd.* Waar de DP een
  stratum niet in bulk weerlegt, somt de DFS de overlevenden op — maar het aantal loopt dan in
  de miljarden en er wordt afgekapt (`MAXSURV`). Zo'n stratum blijft dus OPEN, niet weerlegd.
* *De drie slotmaskers zijn een hypothese*, geen afgeleid feit: de stelling is over deze
  triplet+masker-klasse gesteld.

**Expliciet NIET overgenomen uit de bestaande generator** (de drie gaten uit de opdracht):

* de tegeltelling staat hier op **≤ 56** (stelling) in plaats van **= 56** (waarneming);
* er wordt **geen zetschema gebouwd** — de grens is over ALLE zetvolgordes tegelijk, dus de
  greedy-bouwer-onvolledigheid van `mg_configgen.F4` bestaat hier niet;
* er wordt **niet aan de bovenkant gesnoeid**: alleen "plafond < drempel ⇒ weerlegd" wordt
  gebruikt, nooit "plafond > band ⇒ weggooien".

---

## 9. Conclusie en wat er nog voor nodig is

**De stelling is niet bewezen.** De motor levert het tegendeel van een bewijs: op de bezetting van
ons eigen record is de exacte zetvolgorde- en letter-vrije bovengrens **4867 ≥ 4819**, en er is
minstens één structurele klasse (FRAME, volle TWS-kolom 14) waarvan de bovengrens 4914–4951
bedraagt terwijl de campagne haar nooit heeft gebouwd. Het externe record 4819 past ruimschoots
binnen die ruimte; het is waarschijnlijker dát het bestaat dan dat het niet bestaat.

Wat er wél ligt:

1. Een **geijkte, gezonde, snelle** weerlegger: ~13 µs per bezetting, en een DP die hele
   deelfamilies in één seconde afserveert.
2. Een **uitputtende stratificatie** met een echt bewezen brok: A = ∅ en verticalen ≤ 7 →
   ≤ 4777, dat is 3,57·10³⁶ bezettingen.
3. **Stelling A**: de recordvoetafdruk kan niet boven 4867 — met 74 punten headroom boven het
   gerealiseerde 4793 een concrete opdracht voor de LNS-vloot.
4. De **FRAME-lead** met getallen, woorden, een volledig geldige lettering en een bouwvolgorde:
   `experiments/results/refute/frame_grids.txt`.

Om de weerlegging alsnog rond te krijgen zou nodig zijn (in volgorde van hefboom):

* **Fijnere steungranulariteit.** Nu is er een binaire keuze (volle steun / alleen ankersteun).
  De juiste maat is het steunmasker `ankers ∪ (masker ∩ A)`; per stratum zijn dat 2^|A|
  varianten per lijnsleutel, met `sharp_line` in ~een minuut per stratum te berekenen. Dat haalt
  de sprong van 4777 naar 5100 bij één actieve rij grotendeels weg.
* **Kruispuntconsistentie in de DP.** Het CP-SAT-model wint 126 punten op de recordbezetting
  (4993 → 4867) puur door gedeelde cellen dezelfde letter te laten dragen. In de kolom-DP kan dat
  niet exact, maar wel als extra Lagrange-term.
* **Bingo-plafond.** `U_L` telt +50 per 7-groep zonder globaal maximum; met ≤ 101 tegels zijn er
  ten hoogste 14 bingo's, waarvan 3 de slotzetten. Een gezamenlijke grens op `SOM_L b_L` snijdt
  in de relaxatie mee.
* En bovenal: **de FRAME-klasse eerst uitrekenen**. Zolang daar 4951 staat, is er niets te
  weerleggen.

---

## 10. Gebruik

```bash
rustc -O -C target-cpu=native experiments/mg_refute.rs -o experiments/mg_refute_bin

# eenmalig: woordenboek, bord, lijnsleutels, ankersteuntabel
MODE=dump    .venv/bin/python experiments/mg_refute.py
MODE=anchtab .venv/bin/python experiments/mg_refute.py
MODE=calib   .venv/bin/python experiments/mg_refute.py     # IJKING (moet groen zijn)

# per-lijn-tabellen (14 threads, ~7 min, 377 MB)
TOPK=20000 THREADS=14 LAM=<lambda> ./experiments/mg_refute_bin tables

# een bezetting uit een bord-json halen
MODE=occ BOARD=experiments/results/maxgame_BEST.json .venv/bin/python experiments/mg_refute.py

LAM=<lambda> V=1 ./experiments/mg_refute_bin eval  <occfile>   # Lagrange-grens per bezetting
LAM=<lambda>       ./experiments/mg_refute_bin sharp <occfile>  # exacte steunmaskers
LAM=<lambda>       ./experiments/mg_refute_bin lamopt <occfile> # lambda voor een verzameling
MAXVLEN=7 ACT=000000000000 ./experiments/mg_refute_bin lamdp    # lambda per stratum
MAXVLEN=7 KACT=0 COUNT=1 ./experiments/mg_refute_bin gmax       # stratumgrens + familiegrootte
MAXVLEN=8 KACT=0 MAXSURV=200000 SURVOUT=... ./experiments/mg_refute_bin sweep   # overlevenden

# scherpste (zetvolgorde-vrije) narekening met CP-SAT
./experiments/mg_refute_bin dumptab <occfile>
MODE=refine TARGET=4819 IN=<occfile> .venv/bin/python experiments/mg_refute.py
MODE=refine MAXIMIZE=1 IN=<occfile>  .venv/bin/python experiments/mg_refute.py
```

`maxgame_BEST.json`, `lns_best.json` en `data/boards.toml` worden nergens aangeraakt.

