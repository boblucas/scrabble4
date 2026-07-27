# FRAME-CAMPAGNE: doel >= 4819 (bob's externe record-referentie)

## De genegeerde klasse (bevestigd 2026-07-25)
Wij oogstten 3 premie-lijnen (rijen 0/7/14). De TWS-vakjes vormen een 3x3-ROOSTER: kolommen
0/7/14 zijn OOK triple-lijnen. Frame-klasse = 6 vijftien-letterwoorden (3 rijen + 3 kolommen),
snijdend op de 9 premiecellen. Kolom-interieurs (12 cellen/kolom) worden prep; de rij-slotzetten
completeren de kolommen op hun hoek-/middencellen => elk kolomwoord scoort x3 mee in een eindzet.
Geschatte winst: 3 kolomwoorden x ~45-55 punten x3 + herstructurering ~ +400-600.

## Census (bewijs van rijkdom)
- Huidige triplet: kol-0-patroon g..f..p = 0 woorden (frame onmogelijk!) — daarom zagen we het niet.
  kol 7 'k..k..k' = 2 (koekbakkerswerk, kleermakerswerk), kol 14 = 600.
- 1.230.618 rij-tripletten (uit top-400-waarde) hebben ALLE 3 kolompatronen bezet.
- Top (blanco-NAIEF): cultuurchequeje/textielcyclusje/alfahydroxyzuur M=3420 (huidig 2880).

## Campagne-stappen
1. Blanco-bewuste + zak-joint frame-ranker: (R0,R7,R14,C0,C7,C14) met 9 snijpunt-consistenties,
   maximaliseer M_rows + 3*(S(C0)+S(C14)) + 3*S(C7) (multiplier-toewijzing: hoeken aan rijen,
   kolommen completeren via rij-finals; alternatieve toewijzingen ook scoren) - blanco-degradatie.
   Verplicht: R7 heeft werkster-analoog (8-subwoord over kol 7) als bingo-optie; frag-dichtheid!
2. Choreografie: kolom-interieurs (rijen 1-6, 8-13 van kol 0/7/14) als prep; volgorde zodat
   kolommen compleet-minus-eindcel zijn voor de finals; corner-trigger-analyse (welke final
   completeert welke kolom; x3 per completering).
3. Constructie via bestaande machinerie: deliverable-DFS (fragmenten!), greedy-touch,
   footprint-CP-SAT, score_game-arbiter. Alle lemma's (tel/eiland/fragment) hergelden.
4. Vergelijk ook: partieel frame (1-2 kolommen) op waarde-sterke tripletten.
Referentie: extern record 4819 (niet-optimaal volgens bob) — doel: >= 4819.

## Choreografie-analyse (2026-07-25 avond)
- Zet 1 = 7-tegel-verticaal op kol 7 over center => C7[4:11] moet een geldig 8-fragment... NB: cellen
  rijen 4-10 = C7[4..10], 7-run moet woord zijn bij plaatsing (gaskast-klasse) => C7-selectie-eis.
- Finals-volgorde rij7 -> rij0 -> rij14: kol 0 completeert op (0,14), kol 7 op (7,14), kol 14 op
  (14,14) — ALLE DRIE in de rij-14-final => die zet scoort R14x27 + 3x(C0+C7+C14) + 50 (monsterzet
  ~1800+). Rijen behouden 27/9/27 (alle 8 TWS aan rijen).
- Kol-0/14-interieurs: 2 segmenten van 6 (rijen 1-6, 8-13), GEEN bingo's mogelijk op die kolommen
  (eindcellen zijn final-cellen); ankering via kol-1/13-buren of rij-runs => scaffold-analyse nodig.
- Budget: 45 rij-ankers + 36 kol-interieurs = 81; 20 tegels over voor bingo-verticalen elders +
  scaffold => ~2 extra prep-bingo's naast zet-1. Bingo-verlies (~-300) vs kol-winst (+400-500) +
  hogere M => netto richting 4819 mits sextet-M hoog genoeg.

## KOERSWIJZIGING (zelfde avond): de x4-LANEN zijn de echte gemiste klasse
Frame-narekening: top-sextet M=3150 maar kolomwoorden S~30 (zakdruk) => 3x3 kolommen ~ +276
minus bingo-verlies ~ -300 => netto ~0. Frame alleen haalt 4819 NIET.
DE echte miss: rijen 1,2,3,4 en 10,11,12,13 zijn x4-LANEN (elk 2 DWS-cellen: (1,1)&(13,1),
(2,2)&(12,2), (3,3)&(11,3), (4,4)&(10,4) en gespiegeld onder; rijen 1/13 hebben BOVENDIEN 2 TLS).
Een lang rijwoord (11-13 letters) dat BEIDE DWS nieuw dekt scoort x4: ~4x45+50 = 230-280 per laan.
Ons 4435-bord oogst er 1 (bovengang, x4 via (4,4)+(10,4)) — er zijn er ACHT (4 boven, 4 onder,
plus kolom-lanen 1,2,3,4/10,11,12,13 verticaal!). Record-klasse = LANE-WEAVE: verticalen die
systematisch rijen 1-3/11-13 bereiken als kruisletters, zodat 13-cel-spans slechts 7 nieuw hebben.
Architectuur: lane-woorden eerst (spans die DWS-paren dekken), verticalen als kruis-leveranciers,
3-lijnen-skelet blijft (2x27+x9 is multiplier-optimaal bewezen: 8 TWS = 3+3+2).
NEXT: lane-weave-generator (H-configs met DWS-paar-dekking verplicht, verticalen vol-hoogte).

## Stand 2026-07-26 ochtend
- Rand-oogst (kol-0-top) getest: BH1 (dubbele oogst) INFEASIBLE (geneste g..f-eis leeg);
  BH2 (enkele oogst) 4373 = -62. Rand-klasse vereist triplet-tabel-steun; hand-chirurgie op.
- CONCLUSIE: +384 naar 4819 komt niet uit enkelvoudige mutaties op 4435. Nodig: WEAVE-GENERATOR
  die per triplet JOINT optimaliseert: verticalen-posities (NIET op DWS-diagonaalcellen!),
  x4-laan-woorden, rand-kolom-halfwoorden, maskers, ketens — score-objectief (niet bingo-telling),
  CP-SAT sluit letters, arbiter verifieert. = generalisatie van de 13-bingo-prover-config-machinerie.
- Extra kandidaat-klasse genoteerd: lange geneste hook-ketens (letter-voor-letter opbouwen,
  driehoeks-herscoring ~20/tegel) — meenemen als generator-move-klasse.

## Weave-v1-uitslag + DE derde klasse-onthulling (2026-07-26)
- Weave-v1 (vaste 4435-top, onderhelft gegenereerd, 1476 configs): beste 4396 (pure verts) < 4435;
  L10/L11-lanen joint-INFEASIBLE (6/6), L12-lanen cap-113 (top te vol: 37/56 niet-anker).
  Laan-economie op deze triplet: ~+80 netto indien haalbaar — te dun voor +384.
- ONTHULLING: MASK-KOLOM-HANGVERTICALEN. Onze finals hebben ~nul kruisoogst omdat alle verticalen
  op PRE-kolommen staan. Hang onder elke maskercel van rij 0/14 (en boven/onder rij 7) een
  verticaal woord (rijen 1-7, 7 tegels = bingo, '??????F[c]'-klasse): bij de final scoort het
  x celpremie ((3,0)/(11,0) DLS x2, (0,0)/(7,0)/(14,0) TWS x3). Geen bezorgplicht (maskercellen!).
  ~125 punten per 7 tegels; 4-6 hangers per final-rij => +240 per rij => +500-750 totaal. DIT
  schaalt naar 4819. Generator-v2: menu = pre-verts (bezorging) + mask-hangers (oogst) + lanen +
  randen, beide helften vrij; ankering van hangers via buurkolommen = het echte ontwerpprobleem.

## Triplet-ranking-v2 (2026-07-26): waarde x hangers x kolommen x frag
126.462 kandidaten; HUIDIG = (3315: M2880, hang200, kol9, frag0.70). TOP:
1. gymjuffrouwtjes / schuldcomplexen / wetenschapsquiz = 3509 (M2952 +72, hang300, kol11, frag0.63)
   R7-werkster-analoog: 'complexe' (venster kol 6-13!).
2. quichebuffetjes / whiskyzuipsters / vuurwerkexcesje = 3494 (hang350!)
3. gymjuffrouwtjes / hyperexclusieve / wetenschapsquiz = 3470
GENERATOR-V2-SPEC: mg_13bingo_v2-machinerie als basis met (a) werkster-VENSTER geparametriseerd
([a,a+7] uit R7-analoog i.p.v. vast [4,11]; pre7-interval volgt venster), (b) V-tellingen vrij
(12-bingo-configs toegestaan: score-objectief beslist, niet de 13-eis), (c) hanger-groepen
(6-cel-verticalen rijen 1-6 op mask0-kolommen met geneste tabellen; oogst via finals),
(d) F/G/P uit env (al aanwezig). Draai op top-3 tripletten; elke SAT = compleet geverifieerd spel.

## Gym-triplet DOOD + les (2026-07-26 middag)
gymjuffrouwtjes is fataal fragment-arm op rij 0: pre-bezorging vereist rij-fragmenten OF verticale
stubs, maar aangrenzende stubs vormen zelf rij-runs ('mj','ym','ff' = dood) en 8 niet-aangrenzende
kolommen bestaan niet. LES voor de ranker: HARDE bezorgbaarheids-check per ankerwoord (bestaat een
geldige pre-bezorgings-architectuur: eiland-DFS incl. ministubs) i.p.v. zachte frag-dichtheid.
Bob-topo-plateau: 4116 (oude triplet). SPOREN NU: (a) hybridisatie 4435 + x4-verticalen,
(b) ranker-v3 met harde bezorg-check -> nieuwe tripletten, (c) bob's 4819-referentiestructuur
(gevraagd, nog geen antwoord).

## Ranker-v3 + royalty-triple (2026-07-26 middag)
Ranker-v3 (harde bezorg-check, x4-venster-eis): top = royaltywatchers/pulsoxymetertje/
quichebuffetjes (M=2970 +90, venster 'oxymeter' [4,11] — zelfde geometrie als werkster!).
Generator-fitting strandt op bezorg-worteling (6 iteraties: ministubs floaten, fragmenten
per-geval). BESLUIT: bouw UNIFORME BEZORG-SOLVER: input (ankerwoord, structuurkolommen met
kolom-wortels [verts/lane-adjacent], premie-voorkeuren) -> output (pre-set, blok-zetreeks,
stub-plaatsing) via runs_orderable-DFS + root-mechanismen {kolom-vert, laan-adjacentie(3-cel),
buur-keten(fragment-word)}. Die component sluit ALLE toekomstige triplet-fits.

## REFERENTIE-ORIENTATIE (bob, 2026-07-26): P boven / F midden / G onder!
Zelfde triplet, GESPIEGELD. Tabellen worden overal rijk: TOP P..F {2:589,10:443,12:408,9:368,...},
BOTTOM F..G {1:589,6:455,5:390,10:390,13:152} (onze oude bodem was 3/4/1!). G's rijke fragmenten
(es/he/hen) dienen de bezorg-intensieve BODEM; P's mel/uur/zuur de top. Analyse wijst naar:
DUBBEL-LAAN-ARCHITECTUUR: x4-verts kol 4/10 rijen 3-11 (9-woorden: 7-zet rijen 3-10 + (c,11)-
extensie) => kruisingen voor rij-3-laan EN rij-11-laan (beide x4); lanen = wortel-rails voor
3-cel-stubs naar rij 0 (boven) en rij 14 (onder) — lost het linksbodem-wortelprobleem op
(kol 1,2,3 waren onbereikbaar; q/u-cellen (11,14)/(12,14) gaan in mask14). TE BOUWEN in
mg_bob_topo: vspan-extensie, dubbele laan, stub-bezorging beide zijden, pre-sets per fragmentanalyse.

## Laan-11-poging + blanco-model (2026-07-26 avond)
Bezorg-solver (mg_delivery.py, unit-getest) WEERLEGDE de 7-max-hand-analyse: verticaal-vrije
bodem-bezorging bestaat ({1,2,4,5,6,9,10,12} via hen/en/he/es + laan-gewortelde stubs) => laan-11
x4 structureel mogelijk. MAAR: het resulterende voetafdruk (dubbele laan 11+12 + laan 3 + 2x
9-woord-verts) is ZAK-infeasible: bag-relaxatie toont 15-letter-overvraag (4413 fantoomscore);
blanco-model (nu permanent in mg_ref_topo: <=2 blanco's, waarde 0, zak-vrij) dekt maar 2.
LES: elke extra lange-woord-structuur trekt aan dezelfde schaarse letters — zak-druk is de
uiteindelijke begrenzer van structuur-dichtheid. Reftopo-lijn-plafond: 4224.

## HERSCORING-KLASSE: doorbraak + status (2026-07-26 avond)
RECORD 4457: post-finale 1-tegel-extensies (kolomwoord-herscoring na de betreffende final; ~35/tegel,
DLS-rij-8-bonus) — alle 4 varianten sloegen 4435. Ontleding 4435: 37,4% herscoring, 47/101 cellen
nooit herscoord. Oogst-2-sweep: ruilbronnen op (alleen (11,2) over, arbiter-nee) => enkelvoudig
plafond op deze basis. VOLGENDE NIVEAUS: (a) sloop-diepte (3+-cel-zetten inkorten — chirurgie),
(b) RESCORING-DICHTHEID ALS GENERATOR-OBJECTIEF: ontwerp borden waar elke kolom een post-finale
extensie heeft (8 kolommen x ~35 = +280 t.o.v. nul-extensie-ontwerp!) — vereist: 9-woord-tabellen
(kol-woord+1) niet-leeg per kolom + extensie-cellen vrijgehouden op rij 8/13 + ruil-budget in
ontwerp (101-N tegels prep, N extensies); dit hoort in de triplet/topologie-keuze vanaf het begin.

## ROYALTY-FIT v1-stand (2026-07-26 laat)
Census: tabellen 5-25x rijker dan geschenk-triplet (kol-8-top 1452 w.v. 1358 verlengbaar!;
x4-verts door 'o'/'e': 4608/10470; centrum 1657). Bezorg-solver-sets: rij-0 {2,3,4,5,8,9,11,12}
(mask0 {0,1,6,7,10,13,14}), rij-14 {1,2,4,5,6,8,9,11}. v1-bouw: 121 tegels (over-ontworpen:
3 top-verts + 3 bottom-verts + 2 x4 + laan + stubs + westketting = te veel) + fragment-conflicten:
(2,3)-stubs 'ya' dood, (8,9)-bottom-feet 'ff' dood, (3,13)-westketting vs mask.
V2-AANWIJZINGEN: kies 2 top-verts (8 + 12), 2 bottom (9 of 8, 11 — NIET beide 8+9: ff!),
pre0 zonder 2-3-adjacentie (3-stub + 4-'alt'-ketting maar 2 in mask), westketting alleen indien
(c,13)-cellen niet boven mask-letters eindigen (check '?+R14[c]'-2-woorden), budget <=101 streng
tellen VOOR de bouw. Machinerie: mg_roy_topo.py (blanco-model in tail aanwezig).

## ROYALTY-LIJN GESLOTEN (2026-07-26 nacht) + de grote conclusie
V2-budgettering: kern 29 cellen => max 4 bezorg-verts (56-budget); beide ankerrijen cappen dan op
7/8 pre-cellen (fragmenten ya/ff/tc/oy dood; geen kettingruimte). Royalty's rijke MIDDEN-tabellen
compenseren de ANKERRIJ-fragmentarmoede niet. CONCLUSIE VAN DE HELE TRIPLET-ZOEKTOCHT:
geschenkcheques/flexwerkstertje/polymelkzuurtje heeft UITZONDERLIJKE ankerrij-fragmenten
(es/hen/he + mel/uur/zuur-clusters) — precies waarom het onze recordhouder is EN waarom bob's
4819-referentie dezelfde triplet gebruikt (gespiegeld). De frontier is dus: de referentie-
orientatie (P-boven) dieper verfijnen met ALLE klassen (reftopo-lijn 4224 was gen-2; de
geschenk-lijn kreeg ~15 generaties tot 4457) OF referentie-details van bob.

## SURVIVOR-TRACK AFGEROND (2026-07-27 ochtend)
Survey compleet (40/40). Behandeling: benzoylperoxide-familie 4121-raw -> wave 4251 -> footprint-
OPTIMAL 4284 -> sweep leeg (653 kandidaten). Cheque-familie wave <= benzoyl-niveau. Families 3-5
(plafonds < 4400) overgeslagen. CONCLUSIE: geen familie nadert 4457 — de fragment-uitzonderlijkheid
van geschenkcheques/flexwerkstertje/polymelkzuurtje is definitief bevestigd als de kern van zowel
ons record als bob's 4819-referentie (gespiegeld). OPEN FRONTIERS: (a) bob's referentie-details
(zetten/verticalen van het 4819-bord), (b) reftopo-laan-chirurgie (P-boven 4268), (c) 13-bingo
fase B (volgorde-volledigheid), (d) rescoring-dichtheid-generator (ontwerp-vanaf-nul).

## Spoor 3 (rescoring-densiteit) — oogst 2026-07-26
Iteratieve keten-extensie-loop (mg_extgen.py + scan-na-herlettering): 4457 -> 4459 (indopend-ruil, 4 exts) -> 4515 (ketenpaar (2,11)+(13,4); rij-4 'overzweefden' 13 letters, kol-2 'smarotsenden' 12) -> **4531** ((5,8) 'erbarmden'). +74 totaal, zak-vrij (pure herscoring). Bord VOL: 101/101 tegels — verdere extensies vergen ruilen (sloop elders). Motor bevestigd: elke CP-SAT-herlettering opent nieuwe ketens; convergeert pas bij tegel-cap.
Volgende hefbomen richting 4819 (gat 288): (a) bob's referentie-details (P-boven-spiegel), (b) ruil-extensies (sloop laagwaardige tegel -> lange-keten-slot), (c) struct-sweep op 4531-basis (mask-swaps composeerden eerder additief).

### Joint-extensiemodel (mg_extjoint, scratchpad) — NEGATIEF 2026-07-27
CP-SAT die zelf 7 van 15 optionele extensie-cellen kiest (core-94, ketens<=2, beide uiteinden, blanco's): obj 4517 FEASIBLE na 600s, arbiter VERWERPT ('overzwevena'). Kernbug: brug-cellen ((11,4)-klasse) mergen twee runs — vaste-lengte-woordtabellen dekken de gefuseerde run niet, en juist brugslots dragen de waarde. Sound maken vergt conditionele aux-tabellen per activatiecombo (5/run) — geschatte winst marginaal (greedy benutte dezelfde 7 slots al, obj<record). CONCLUSIE: greedy-scan+extgen-met-arbiter is de sound en voldoende motor; spoor 3 op het 4531-bord geconvergeerd. Volgende: extensie-oogst op de reftopo-lijn (4268) — test of bobs spiegelorientatie hogere herscoringsdichtheid toelaat (pad naar 4819-begrip).
