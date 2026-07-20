# Maxgame-optimaliteit: bewijsladder (dutch2026) — gestart 2026-07-19

**Status: LB = 3917 (maxgame_BEST.json, score_game-geverifieerd). Dit document bouwt de UB-kant.**
Arbiter: `maxgame_score.score_game` (state-aware sinds de impair-fix). Elke bewijslaag wordt
tegen de scorer gevalideerd.

## Stelling 1 (multiplierlijn-structuur) — BEWEZEN (numeriek geverifieerd)
Het bord heeft precies 8 TWS-cellen; precies 4 lijnen bevatten er 3: rij 0, rij 14, kol 0, kol 14.
Een zet scoort woordfactor 27 ⟺ hij dekt de 3 TWS van één zo'n lijn met NIEUWE tegels ⟹ het
hoofdwoord beslaat cel 0..14 van die lijn (15-woord). TWS-incidentie: rij-0∩kol-0={(0,0)} enz. —
elk paar {rij,kolom} deelt een TWS. Twee ×27-zetten vereisen disjuncte TWS-triples ⟹ alleen
{rij 0, rij 14} of {kol 0, kol 14}. **Gevolg: ≤ 2 ×27-zetten per spel.**

## Stelling 2 (center-uitputting) — BEWEZEN
Zet 1 dekt (7,7) (spelregel) en legt ≤7 tegels op een leeg bord ⟹ zet 1 is geen 15-woord ⟹ de
center-DWS is verbruikt vóór elk later rij-7/kol-7-15-woord. Rij 7 en kol 7 hebben elk exact 2 TWS
⟹ zulke zetten scoren ≤ ×9. Met het rijenpaar als ×27-frame verbruiken rij 0/7/14-15-woorden ALLE
8 TWS ⟹ daarna geen TWS-multiplier meer beschikbaar. (Bob's 2×27+×9-frame is dus de unieke
maximale multiplier-structuur.)

## Frame-componenten (UB's, alleen woordbestaan + zak; geen ketenbaarheid/setup-eisen)
- max enkele ×27-zet (hoofdwoord): **1751**
- max enkele ×9-zet (hoofdwoord): **617**
- max zak-haalbare (2×27 + ×9)-triple gezamenlijk: **3894** (jacquetkostuums/playbackshowtje/schrikreflexjes)

## Rest-UB V0: per-lijn stage-DP + gekoppelde budgetten (RELAXATIE — grof maar sound)
Totaalscore = Σ over (zet, gevormd woord) van woordscores + 50·#bingo's. Elk gevormd woord leeft op
één van de 30 lijnen; per lijn vormen de gescoorde intervallen een STIJGENDE keten (elke zet die
tegels aan de run toevoegt scoort het dan-actuele interval; multipliers alleen op de delta-cellen).
Per lijn ℓ: DP over intervallen [a,b] ⊂ [a',b'] met transitiescore
(Σ_delta v·LM + Σ_oud v)·Π_delta WM geeft frontier F_ℓ(#stages, #cellen) — een harde UB op wat lijn
ℓ ooit kan opleveren bij dat aantal stages/cellen, met tegelwaarden gerelaxeerd naar de beste
zak-toewijzing per lijn.
Koppeling (sound): (a) Σ_lijnen #cellen ≤ 2·101 (elke tegel ligt op 1 h- en 1 v-lijn, één keer
geplaatst); (b) Σ_lijnen #stages ≤ #zetten + 101 ≤ 202 (elke zet: 1 hoofdstage + ≤ #nieuwe
kruisstages); (c) bingo's ≤ ⌊101/7⌋·50 = 700. Knapsack over de frontiers ⟹ **U0**.
BEKENDE LOSHEID: letters per lijn onafhankelijk uit de volle zak (dubbeltelling), geen
woordbestaan-eis, geen volgorde-consistentie tussen lijnen. Aanscherpingsroute: exacte
letterkoppeling (multiset ≤ 2×zak), premium-both-directions-verfijning, woordbestaan per interval
(automaton), zet-consistentie (stage-gelijktijdigheid h+v).

## Ladder verder
1. U0 (dit script) → 2. letterkoppeling + stagebudget-verfijning → 3. frame-noodzakelijkheid:
spel met ≤1 ×27 ≤ 1751 + 617 + rest-UB' < LB ⟹ optimum gebruikt het frame → 4. klasse-sluiting
binnen het frame (triple exact, vulfase via CP-SAT + reachability-certificaat).

## Status UB-ladder (2026-07-19, avond)
V0 20243 → V1 (Lagrange+woordsom-caps) 13718 → V2 (st≤cellen, scherpere caps) 12633 →
**V3 (analytisch frontier + ketensom + zakwaarde/richting + TWS-cases) = 10806 — STAAND**.
V3b/c (gezamenlijk stagebudget 202 + delta≤7) verliezen per saldo door de waarde-bucketing
(verbruik afgerond omlaag): 11031/11141 — de fijnmazige 2D-V3 wint.

**Asymptoot-analyse:** de lijn-relaxatie bevat al: ketensom (Σ stage-bases ≤ 295/lijn),
woordsom-caps per lengte, cel- en waardebudget per richting, TWS-case-analyse, st≤cellen.
De resterende ~6.9k boven de LB zit in het ontbreken van GEOMETRISCHE consistentie
(kruis-stages verlangen echte loodrechte zetten op gedeelde cellen; niet elke lijn kan
tegelijk een diepe keten dragen). Dat is niet meer met budget-koppelingen te vangen.

**Routes naar scherper:**
(a) Begrensde exacte ILP: de 6 TWS-lijnen + hun kruisende lijnen celgewijs exact in CP-SAT,
    rest via V3-boekhouding — verwacht ~7-8k, onzeker.
(b) KLASSE-SLUITING (aanbevolen): conditioneel resultaat "gegeven het frame + anker-skelet is
    de vul+mop-up-fase ≤ X" via CP-SAT op het concrete bord (kleine ruimte!), plus
    triple-optimaliteit (al empirisch geveegd) ⟹ optimaliteit binnen de frame-klasse,
    analoog aan de ≤8-variant-2010 vóór de echte 2102.

## Klasse-sluiting: decompositie gemeten (2026-07-19)
Recordspel 3930 = **skelet 3728** (keten+slotzetten, deterministisch, score_game-geverifieerd)
+ **202 vulfase** (7 zetjes; slotzet-boost door vullercellen = 0 hier).  Klasse-optimum =
3728 + maxfill(skelet).  maxfill is een KLEIN probleem: ~15 resttegels op een vast bord van
~86 cellen; te begrenzen via exhaustieve zoektocht/CP-SAT incl. flank-kruisboost bij de
slotzetten (vullercel naast masker-TWS-cel telt x3 in de slotzet).  NB: klasse-bound moet ook
vullers vóór de slotzetten dekken (maskerdiscipline + kruisboost-term).

## Klasse-sluiting v1 (2026-07-19): skelet-klasse-bracket [3930, 4324]
maxgame_fillbound.py: elke vul/mop-up-stage = woord op één lijn passend op het skelet-patroon,
vulcellen uit de restzak (20 legbaar na reserve); per lijn g(m)-knapsack (herhaalbare stages,
elk >=1 verse vulcel), budgetten PER RICHTING <=20 (een vulcel is vers op rij- en kolomlijn);
slotzet-kruisboost gedekt (kolompatronen door maskercellen dragen WM mee).
maxfill-UB = 596 (rijen 262 + kolommen 334); skelet 3728 exact -> klasse-optimum <= 4324.
Bereikt: 3930.  Aanscherproute: kruis-hoofdstage-consistentie (kruisstage vergt loodrechte
hoofdzet), zetbudget (<=20 vulzetten is ruim: <=NREST), lijn-interacties.

## Eliminatieladder naar bewezen optimum (plan, 2026-07-19 avond — bob's voorstel)
Waarneming: alle top-spellen delen triple (flauwekulexcuus/babyzwemmertjes/zelfbeschikking) én
brugkolommen (6,8,5,10); skelet 3718-3733, vul 205-231.  Ladder:
1. **Skelet-optimum exact** gegeven (triple, kolommen): CP-SAT/B&B over brug/span/sp8-woorden
   met gedeeld zakbudget (kleine ruimte) -> hard getal S*.
2. **maxfill-UB op S*-skelet** (fillbound, aanscherpen met kruisstage-consistentie) -> klasse-
   optimum in [LB, S* + fillUB].
3. **Rival-eliminatie**: per rivaliserende (triple, kolommen)-klasse een sound UB =
   skelet-UB(rival, exact of analytisch) + generieke fillUB; alles < LB is BEWEZEN uitgesloten.
   Triviale drempel: backbone < LB - (keten+fill-UB ~1200) valt direct af; de 3400-3615-band
   krijgt per-rival exacte solves (zelfde machinerie, ~tientallen kleine problemen).
4. Herhaal over kolomkeuzes binnen de triple (klein aantal combinaties).
Eindresultaat: "LB = optimum binnen het 2x27+x9-frame" op stellingen 1+2 na volledig bewezen —
en het frame zelf is al de unieke maximale multiplierstructuur.

## Rival-eliminatie: drempel-analyse (2026-07-20 nacht)
Record 3963 op backbone 3516 ⟹ gerealiseerde EXTRA (ketens+slotzet-kruisen+vul) = 447.
Rival met backbone B verslaat de LB alleen bij extra > 3963−B: 3615-familie > 348 (niet
elimineerbaar zonder exacte solve), 3507 > 456, 3489 > 474, ..., 3345 > 618.
BENODIGD voor massa-eliminatie: universele extra-UB (~550-650) = keten-UB (skelet−backbone,
patroongebaseerd per rival zoals fillbound) + vul-UB. Sets uit de sweep haalden max 3734 TOTAAL
(= extra ≤ ~250 gerealiseerd); een extra-UB ≤ 600 elimineert alle backbones < 3363 direct en
reduceert de overlevers tot de 3400-3615-band (~14 sets) voor per-rival exacte behandeling.
Grove per-zet-bounds (brug ≤ 250 enz.) zijn TE los (extra-UB ~2200, elimineert niets) — de
patroon-machinerie van maxgame_fillbound.py is de juiste basis. BOUWEN: volgende cyclus.

## Universele extra-UB: TE LOS (2026-07-20)
Backbone-only fillbound (56 vrije tegels): extra-UB = 1872 ⟹ elimineert alleen backbone < 2091
(geen van de 22 planbare sets).  Massa-eliminatie via universele bound is DOOD; de route is
PER-RIVAL: (a) skelmax per rival-triple (S*_rival), (b) fillbound op dat skelet (~600), (c)
S*_rival + fillUB < record ⟹ uitgesloten.  Rivalen-sweep haalde totaal ≤ 3734; als per-rival
S*+fillUB ≤ ~3960 uitkomt sneuvelen ze allemaal behalve de eigen klasse.  Automatiseerbaar met
de bestaande machinerie (skelmax parametriseren op triple).

## CORRECTIE eliminatieplan (2026-07-20, zelf-gevangen): skelmax is een LB-tool, GEEN UB
skelmax(rival) vindt goede skeletten (stochastische ondergrens) en kan rivalen dus NIET
uitsluiten.  Sound per-rival UB binnen de choreografie-klasse = backbone + Σ per-SLOT-maxima
(elke van de 15 ketenslots heeft een eindige kandidatenlijst met statisch berekenbare
zetscore-maxima op vaste posities: bruggen via C8-lijsten, spans via SPAN-indexen) + fill-UB
(fillbound op backbone+slotcellen).  TE BOUWEN: slotmax-berekening in plan_for_triple-stijl
(maximaliseer per slot i.p.v. eerste-haalbare; negeer zakbudget voor UB = relaxatie, sound).
Eliminatie-claim wordt dan: "geen rival verslaat het record binnen de choreografie-klasse".

## Slotmax-haalbaarheidsanalyse (2026-07-20 ochtend): eliminatie op deze granulariteit ONHAALBAAR
Voorcalculatie per-slot-UB: bruggen 4x~110 + center ~130 + smalls-exact ~250 = keten-UB ~820;
+ fill-UB 596 = extra-UB ~1416.  Eliminatie vereist extra-UB < 3963−backbone: zwakste set
(3345) 618, sterkste rival (3615) 348.  Gat ~2-4x: per-slot-relaxatie kan dit NIET sluiten
(fill-UB 596 vs gerealiseerd 237 is de grootste post; slot-som 820 vs ~500 de tweede).
CONSEQUENTIE: bewijs-grade rival-eliminatie vergt per rival een EXHAUSTIEVE mini-campagne
(eindige planruimte + eindige vulruimte, zelfde machinerie als eigen klasse-sluiting) — doenbaar
maar ~uren per rival x 22.  PRAGMATISCHE stand: empirische dominantie (sweep: rivalen ≤ 3734,
eigen klasse 3963) + exacte sluiting van de EIGEN klasse eerst (skelet-B&B + snelle vul-DFS).

## Skelet-S* status (2026-07-20): stochastisch geconvergeerd op 3738; exacte enum vergt separabiliteit
Planruimte = up6(862) x up8(70) x dn5(573) x dn10(156) x span1(~28/brug) x span13 x sp8(9) ~ 10^12:
naïeve enumeratie ONHAALBAAR.  MAAR skelet-score is SEPARABEL per slot (elke brug/span/sp8 is een
eigen zet op disjuncte cellen; alleen koppelletter + zakbudget koppelen).  Drie onafhankelijke
stochastische rondes (250-3000s) convergeren alle op S*_lb = 3737-3738.  SOUND S*-UB (te bouwen):
per slot het exacte max-marginaal (replay 1 zet op leeg-plus-koppelbord) over zijn kandidatenlijst,
gesommeerd, zak-gerelaxeerd (loosе zak => bijna tight).  Verwachting: S*_UB in [3738, ~3770] =>
skelet nagenoeg gesloten.  Eigen-klasse-optimum = S* + maxfill; maxfill-DFS best 207 (niet
uitputtend); samen empirisch record 3963. Bracket eigen klasse ~ [3963, 3738+596=4334].

## CORRECTIE (2026-07-20, zelf-gevangen): separabele skelet-UB NIET rigoureus
De per-slot-max-som (slotub.py, "4024") is ONGELDIG als UB: bruggen kruisen de ankerrijen en
vormen kruiswoorden -> slots koppelen; losse maxima optellen onder-/dubbeltelt.  Zuivere skelet-
score = Σ maximale runs op het eind-skeletbord (score_game).  Aangescherpte losse componenten
(runs 43 EXACT want vaste anker-substrings wek/lex/bes/hik/la/el; span1 64, span13 34 met AF/BF)
zijn indicatief maar niet optelbaar tot een sound bound.  RIGOUREUZE skelet-sluiting = exacte
enum (10^12, separabiliteit gebroken door kruiswoorden) OF CP-SAT met kruiswoord-constraints.
STAND: skelet-waarde = 3738 (stochastisch, 3x geconvergeerd, betrouwbaar als LB; als UB
onbewezen).  Het beter-afsluitbare spoor blijft de mop-up-DFS (eindige ruimte, geen coupling-
subtiliteit).

## Consolidatie (2026-07-20): waar de proof-sporen stranden
Systematisch afgelopen; elk raakt een muur:
- **Mining-LB**: 3963, ~2000 spellen; extreme-value: ~7000 spellen/verbetering, +1-5 pt. UITGEPUT.
- **Globale UB**: lijn-relaxatie asymptoot 10806; geometrische consistentie niet met budget-
  koppelingen te vangen. -> [3963, 10806].
- **Skelet-UB**: separabiliteit gebroken door brug-kruiswoorden; per-slot-som ongeldig als UB.
  Skelet-LB 3738 (3x geconvergeerd). Rigoureus = 10^12-enum of CP-SAT-met-kruisconstraints.
- **Mop-up exact**: 892k voorberekende plaatsingen x diepte ~10 => niet uitputtend haalbaar;
  anytime-DFS best ~207 (fillexact), greedy 237. -> mop-up-subklasse niet gesloten.
- **Rival-eliminatie**: alle sound bounds te los (extra-UB 1416-1872 vs benodigd 348-618);
  bewijs-grade vergt per-rival exhaustieve mini-campagne (22x, uren elk).
VERDEDIGBAAR EINDRESULTAAT (analoog aan max-turn): LB 3963 (onvoorwaardelijk, score_game-OK) +
globale bracket [3963,10806] + 2 bewezen structuurstellingen + empirische dominantie eigen klasse
over rivalen (sweep: rivalen <=3734). Globaal BEWEZEN optimum: buiten praktisch bereik.
CPU: 4 mining-workers (staart) + 2 fillexact (anytime-LB) blijven laag doortikken.

## Empirische bevestiging: naïeve per-slot-UB ONGELDIG (2026-07-20, tegenvoorbeeld)
score_game decompositie-consistent: Σ per-zet = skelet-totaal (3721, geverifieerd). MAAR de 4
bruggen scoren in het echte skelet 65/70/71/78 (=284) door KRUISWOORDEN met de ankerrijen;
kruiswoordloze zetscore gaf 35-46 (=158). Naïeve slot-som choreografie ~387 < werkelijk 506 =>
GEEN bovengrens (concreet tegenvoorbeeld). Definitief: sound per-slot-UB vergt kruiswoord-termen
=> slots koppelen via buurletters => separabiliteit onbruikbaar. Skelet-UB blijft open; skelet-LB
3738 solide. Flip-flop gesloten met tegenvoorbeeld i.p.v. argument.

## Triplet-ranking (2026-07-20, Rust-kernel): anker+opening-potentieel != full-game
maxgame_precompute.py (per-woord beste x27/x9-completie + opening, gevalideerd als sound UB tegen
score_game) + triplerank.rs (volle enum, blanco-penalty, bag=2 blancos). KERNBEVINDING:
- Model-kern (A+B+C+D, beste masks, blanco-gecorrigeerd) van het RECORD-triplet
  (flauwekulexcuus/babyzwemmertjes/zelfbeschikking) = 3636, staat op rank >20000 op kern.
- Toch houdt het het record (3963) omdat de CHOREOGRAFIE (bruggen+subwoorden, +327..+660) sluit.
- Top-kern: geschenkcheques+bouwcuratrixjes (bob's ORIGINELE backbone!) + x9-woord = 3884.
CONCLUSIE (herkadering): anker+opening-potentieel is NIET de bottleneck — tienduizenden triplets
verslaan het record-triplet op ruwe potentie (band 3641-3884). De bottleneck is 2D-CHOREOGRAFIE-
prepareerbaarheid; geschenkcheques/bouwcuratrixjes zijn kern-optimaal maar choreografie-geblokkeerd
(che/ou/cur-prep faalt). Deze ranking ELIMINEERT geen triplets (kern bound niet de full-game) maar
levert LEADS: hoogste-kern-MET-sluitbare-choreografie. Concreet upgrade-lead: rank 13
chequeformulier/vluchtreflexjes/babyzwemmertjes kern 3852, 0 blancos, R7=babyzwemmertjes (BEWEZEN
sluitbaar) -> als chequeformulier/vluchtreflexjes-choreografie sluit: ~4100+ mogelijk.
Top-100 in maxgame_triplerank.tsv.

## CORRECTIE (2026-07-20, bob-caught): geschenkcheques IS prepareerbaar (es/hen/he/e)
Mijn "geschenkcheques/bouwcuratrixjes choreografie-geblokkeerd (che/ou/cur)" was FOUT — dat sloeg op
één specifiek masker. Beste x27-masker geschenkcheques = {0,3,7,8,11,12,14} met pre-runs es/hen/he/e
(alle woorden); bouwcuratrixjes = {0,1,3,5,7,11,14} met u/c/r/tri/je. Ranker s27=1724/1616 bevestigde
dit al. ANKER-BASIS geschenkcheques+bouwcuratrixjes = 3340 vs record-triplet flauwekulexcuus+
zelfbeschikking = 2989 (+351!). Beide per-rij prepareerbaar. ECHTE blocker = de builder
(maxgame_play5.py plan_for_triple) heeft een HARDGECODEERD masker M014=(0,3,7,11,12,13,14) dat NIET
matcht met geschenkcheques' masker (col 8 vers, 12/13 anders). Generalisatie van de builder naar
per-triple-maskers is de openstaande taak -> potentieel ~4200-4300 als de 2D-bruggen sluiten.

## geschenkcheques-triple: choreografie-HAALBAAR, connectiviteit resterend (2026-07-20)
maxgame_geschenk.py: opening zwemmer + bruggen up6=nadrukte/up9=hernoeme/dn8=mierzoet plaatsen
probleemloos; maskers M0={0,3,7,8,11,12,14} (es/hen/he/e) en M14={0,1,3,5,7,11,14} (u/c/r/tri/je)
legaal. RESTEREND: hoek-subwoorden (es@1-2, e@13, R14-randen) hebben verticale connector-woorden
nodig (span/ladder). = connectiviteitsprobleem, GEEN onmogelijkheid. Potentieel als skelet sluit:
anker-completes ~1724+1616+527-150blanco ~3700 (vs record 3215, +485); +opening+bruggen+fill(~660)
-> ~4360, sprong ~+400 over 3963. VOLGENDE: span/ladder-generalisatie (verbind hoek-subwoorden via
korte verticale woorden naar de brugkolommen) -> echte LB-doorbraak verwacht.

## Connectiviteit = gekoppelde zoektocht (2026-07-20) -> Rust gerechtvaardigd
maxgame_geschenk-analyse: hoek-subwoorden verbinden koppelt MASKER aan dict-muren. bouwcuratrixjes
mask {0,1,3,5,7,11,14}: cellen c@4 en j@12 NIET verticaal verbindbaar (before('c')=before('j')=∅,
zelfde muur als flauwekulexcuus-familie). Ze moeten VERS zijn (in de x27-completie) of in een
verbindbare horizontale run. => maskerkeuze gekoppeld aan {legale pre-runs, dict-before/after-muren,
brug-existentie, span-connectiviteit, zakbudget}. Dit is een CSP, niet triviale constructie ->
RUST-solver: per triple, zoek (mask_R0, mask_R14, mask_R7, brugkolommen, connector/span-woorden)
die een gesloten verbonden legaal skelet geven; anders bewijs geen. Rust hergebruikt DAWG uit
xfill_rs. Python valideert alleen de Rust-oplossing tegen score_game (1x). Compute-eerlijk.
NB: misschien vermijdt een ANDER top-core-R14 (bv vluchtreflexjes, rank 13) de c/j-muren -> eerst
per-triple een goedkope 'muur-check' (heeft elk pre-cel-nodige letter een niet-lege before/after?).

## Viability-gefilterde ranking (2026-07-20, Rust): rol-asymmetrie + eliminatie
Precompute v2: per woord beste MUUR-VEILIGE x27 voor rol R0 (after-∅-check: q,x) en R14 (before-∅:
c,j,q,v,y,z). ~2500 woorden NIET-viable als R14 (onfixbare before-muur). KERNCORRECTIE: bouwcuratrixjes
IS viable als R0 (boven; c@4/j@12 verbinden naar beneden) maar NIET als R14. Rol bepaalt de muur.
Top muur-veilige triples: #1 bouwcuratrixjes(R0)/geschenkcheques(R14)/playoffticketje (3884, 2 bl);
#15 vluchtreflexjes/chequeformulier/babyzwemmertjes (3852, 0 blancos, R7 bewezen sluitbaar) = veiligste
target. NB viability = NODZAKELIJK-heuristiek (losse pre-cel-connector), nog niet bewezen VOLDOENDE
(echte span/brug-geometrie moet sluiten). Volgende: de daadwerkelijke sluiting (span/brug-CSP) op de
top-viable target(s) -> echte LB-doorbraak richting ~4200-4300.

## Sluiting-route target vluchtreflexjes/chequeformulier/babyzwemmertjes: HAALBAAR (2026-07-20)
Strategie "R7-eerst + verticale brug per pre-run": babyzwemmertjes volledig leggen (record-choreografie
hergebruikbaar want zelfde R7-woord), dan elke pre-run van R0/R14 via 1 verticale brug verbinden.
Verifieerd: alle pre-runs hebben verbindende brug BEHALVE R14 u@4 (z..u ∄) -> kleine span nodig.
Tegelbudget ~83 (past in 100). Bruggen: R0 lucht@kol5(t..w,16)/e@kol10(e..r,128)/je@kol13(e..e,390);
R14 he@kol2(1371)/f@kol6(e..f,17)/mu@kol9(e..m,36)/ie@kol13(e..e,390) + u@4-span. TE BOUWEN:
maxgame_gen.py (R7-record-choreografie + R0/R14-bruggen + u@4-span + completes + fill), elke stap
score_game-gevalideerd. Verwacht: eerste echte skelet-sluiting van een hoge-kern-triple -> LB-sprong.

## Paper-lead erodeert onder geometrie (2026-07-20, eerlijk negatief)
Sleutelbevinding: met babyzwemmertjes-R7 (enige gevalideerde R7-choreografie) forceert de teee-connector
(cols 9-12 rij 8) dat teee-COMPATIBELE R14-woorden (pre-runs mijden 9-12) hooguit s27=1292 halen =
GELIJK aan record-zelfbeschikking. De "+400 kern-potentie" uit de viable-ranking overleeft de
geometrische compatibiliteit NIET voor babyzwemmertjes. Hoge-kern-triples (geschenkcheques/
bouwcuratrixjes) hebben andere R7-woorden nodig (playoffticketje etc.) -> vereist R7-connector-
machinerie generaliseren naar willekeurige middenwoorden (elk eigen zone-conflict) = substantieel,
onzekere opbrengst. STAND: LB 3963 bewezen; viable-ranking + muur-check + algemene solver = correcte
infrastructuur; realisatie van een LB-sprong vergt R7-generalisatie (open). Loop gestopt (bevestigt
anders hetzelfde). Mining-vloot draait parallel door op 3963.

## Top-down eliminatie: opening-window-check ONSOUND (2026-07-20, bob's idee getest+weerlegd)
Poging: R7 heeft geldige horizontale opening-window (7-substring door center) nodig -> elimineert
schijnbaar 18/38 top-triples. MAAR ONSOUND: opening mag VERTICAAL door center (kol 7), levert (7,7),
R7 eromheen gebouwd met prep. Dus geen horizontale window sluit niet uit. Geen goedkope sound
noodzakelijke vw. bestaat (alles al gefilterd; sound UB<3963 bestaat niet voor hoge-kern-triples;
bouwbaarheid weerleggen = enorme zoekruimte). Opening-window = sterk PRAKTISCH filter (~15/40 met
window makkelijker bouwbaar). Productieve zet: solver draaien op window-kandidaten (opening
generaliseren) om closing-triple te vinden = echte LB. Rigoureuze top-down-eliminatie niet haalbaar.

## Top-down solver-sweep (2026-07-20, bob's aanpak): top-38 viable, 0 sluiten
maxgame_solvesweep.py + gegeneraliseerde solver (opening-window + plank-backtracking R7, generieke
R0/R14-connector). Resultaat top-38: 0 sluiten. 35× R7-faalt (geen opening-window of R7-pre-cel
onverbindbaar), 3× R7-bouwt-maar-R0/R14-faalt (#15/16 vluchtreflexjes/chequeformulier mu-conflict;
#18 bouwcuratrixjes/geschenkcheques/citytrippertjes = hoogste-kern near-miss). CAVEAT: solver-fail =
bewijsMATERIAAL, geen bewijs (verticale opening niet geïmplementeerd; R0/R14-connector niet uitputtend).
PRAKTISCH: geen van top-38 verslaat 3963 constructief -> record staat. Near-misses (#15,16,18) =
plek voor uitputtender R0/R14-solver.

## Bingo-sweep VOLLEDIG (2026-07-20): top-500 viable, 0 sluiten (M7 gefixt)
Na M7-fix (x9-masker per R7-woord i.p.v. hardgecodeerd) volledige top-500-sweep met diepe backtracking-
solver: 499 getest, 0 sluiten. 482 R7-faalt (geen 7-window binnen masker), 17 R7-bouwt-maar-R0/R14-faalt
(hoogste #96 bouwcuratrixjes/geschenkcheques 3814). R0/R14-anker-pre-run-verbinding = universele muur
(17 verschillende triples, zelfde falen). nb-sweep (korte openingen, jouw idee) draait parallel voor de
482 zonder 7-window. CAVEAT blijft: solver-fail = bewijsmateriaal, niet bewijs. PRAKTISCH: geen van de
top-500 verslaat 3963 constructief -> record staat robuust.
