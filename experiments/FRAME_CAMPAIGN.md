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

### 13-bingo fase B — voortgang 2026-07-27
- hypochlorigzuur x jacquardweefsel: DOOD op fragment-niveau (0 van 128.394 configs haalde CP-SAT; singles_options leeg). Positie-gefilterde woord-fragmenten: hypo links {po,poch,och} rechts ALLEEN {ri}; jacquard links {qua,ar} rechts {we,wee,weef}. Bevestigt fragment-exceptionaliteit van ankerwoorden op een derde onafhankelijke laag (na ranker-v3 en survivor-track).
- gymjuffrouwtjes: fragment-arm (2 links/2 rechts) — overgeslagen.
- cyberhuwelijkje x quizmasterschap: fragment-RIJK (cyber 4L/5R: be,er,erhu,hu | el,li,lij,lijk,ijk; quiz 4L/3R: ui,ma,mas,as | er,scha,ha) — fase-B-run gestart (104.412 configs, CAP 2500, ledger_13bingo_faseB_cyber.jsonl).

- cyberhuwelijkje x quizmasterschap: 10/104.412 configs bezorgbaar (alle V8H0), alle 10 CP-SAT-INFEASIBLE; V7H1/V6H2 volledig bezorg-gesnoeid. FASE-B-EINDSTAND: geen enkel top-triplet levert 13 bingo's (geschenk fase-A-infeasible; hypo/gym fragment-dood; cyber 10/10 infeasible). Kanttekening: OPTS=6/HSETS=40-truncatie => sterk bewijs, geen gesloten theorema. 13-bingo-spoor GEPARKEERD — waarde-argument: zelfs bij SAT zou het spel een zwakker triplet dragen (-50 op ankers) voor +50 bingo-bonus netto.

### Ladder-generator (mg_ladder.py) — NEGATIEF 2026-07-27
Gedecomposeerd zetplan + herlettering (stage-run-tabellen dwingen ladder-woorden af): basis-model valideerde exact 4531 (UB 5110); ronde 1 (alle multi-tegel-zetten x {volledige center-keten, partiele 2-groep-splits k in {1,2,3,n-2,n-1} x asc/desc}, 90s-probes met 4531-hint) accepteerde NUL splits; eindsolve ok 4531. Ook chainify (mg_chainify.py, exacte DP op VASTE letters) gaf +0. CONCLUSIE: op dit footprint weegt keten-herscoring niet op tegen ladder-tabel-restrictie + bingo-verlies; de winnende herscoringsvorm blijft post-final extensies (die zitten er al in, cap-vol). Praktische les: eerste oplossing op het 322k-var-model kost ~47s — hints verplicht, probes >=90s.
STAND SPOREN: 4531 = geconvergeerd record over ALLE actieve motoren (extgen/structsweep/extjoint/chainify/ladder). Gat naar 4819: 288. STERKSTE VERVOLG: bobs referentie-details (P-boven-spiegel; web-zoektocht leverde niets — aadvdw.nl kent alleen max-zet-records 2002/2005/2085-SBNL). Daarna: ruil-extensies via gerichte sloop, reftopo-laan-chirurgie.

### Ruil-extensies (mg_ruil.py) — NEGATIEF 2026-07-28, bord VERZADIGD
Machinerie: sloop een cel, greedy-touch-herordening van het pre-final-blok, volledige herlettering (CP-SAT + blanco + zak), arbiter-gate. Bevindingen:
- Structuur-argument: van alle 1-tegel-zetten ligt er precies EEN buiten de ankerrijen — (11,2), 2 punten — en die is DRAGEND: zonder hem heeft de kolom-12-bingo geen enkele aangrenzende buur (ordening faalt hard). Alle overige goedkope singles liggen op rij 0/7/14 en zijn maskergebonden (finals zijn exact 7 tegels).
- Vrije slots op het 4531-bord: alleen V7 'wankend' NA (7,11) en VOOR (7,3).
- 6 ruilen (blad (10,8)/(5,8)/(2,11) x slot (7,11)/(7,3)) leveren ALLE een legaal bord maar geen enkele wint: 4500/4496/4511/4517/4490/4489 (beste -14). De bladeren zijn 14-27 waard, de vrije slots ~2-6.
CONCLUSIE: het bord is verzadigd — geen sloopbare tegel met positieve ruilwaarde. Daarmee zijn ALLE rescoring-motoren uitgeput op dit footprint (extgen, structsweep, extjoint, chainify, ladder, ruil). 4531 staat.

## NA DE BORDCORRECTIE (2026-07-28): economie van de ingrepen, exact doorgerekend
Record 4777; plafond huidige geometrie 4867; bewezen globale bovengrens 13917 (GLOBALBOUND.md).

STRUCTURELE FEITEN (nieuw, en ze corrigeren de oude frame-analyse):
- Een zet legt max 7 tegels, dus een 15-letterlijn wordt ALTIJD door een slotzet voltooid. Alleen een
  RIJ-slotzet kan drie TWS-cellen tegelijk nieuw leggen => alleen rij 0 en rij 14 halen x27.
  Een KOLOM kan nooit x27 halen; hij wordt door een rij-slotzet gekruist en krijgt dan x3 per TWS-cel.
  Dat maakt het hele frame-idee structureel zwakker dan gedacht.
- Rij 7 haalt x9, niet x18: de DWS op (7,7) telt niet mee omdat het centrum in zet 1 ligt.
- De zak is UITGEPUT (alleen een 'i' over) en alle 20 hoogste m-cellen zijn ankercellen met vaste
  letters. Het restgat van 90 punten is dus puur HERSCHIKKING van dezelfde letters.
- Sloopkosten (mg_tradeoff.py): 9 cellen kosten samen 30 punten; vanaf de 10e kost elke sloop 50+
  omdat hij een bingo breekt. Dat verklaart waarom eerdere netto-schattingen te somber waren.

BRUTO-WAARDE per toevoeging (m-calculus, cap genegeerd): kolom 7 gaten +191/6 tegels (32/tegel,
lexicaal dood), kolom 14 volledig +211/12 (18/tegel), kolom 14 boven +65/6, kolom 14 onder +59/6,
kolom 0 boven/onder +83/6 (14/tegel). Superadditief: de volledige kolom is meer waard dan de som
van zijn helften, want hij wordt drie keer gekruist.

NEGATIEF, met arbiter geverifieerd (niet herhalen):
- kolom 14 boven ingevoegd als groep vóór de finals tegen 6 goedkope sloopcellen: 4735 (-42).
  De m-calculus voorspelde bruto +65; het woordenboek dwingt goedkope letters in het kolomwoord.
  LES: bruto-m-winst is een BOVENGRENS, geen voorspelling -- bij lange nieuwe lijnen is het
  woordenboekverlies veel groter dan de ~90 punten die we op de bestaande geometrie zien.
- kolom 11 x4 (3 tegels): beide sloopvarianten infeasible.
- lange herlettering (3000s, 14 workers) op de huidige geometrie: geen verbetering => 4777 is
  het praktische optimum van dit footprint.
- woordbare schema-alternatieven (plafond 4872) vullen naar 4776.

NIEUW GEREEDSCHAP: mg_mceiling.py (m-calculus + schemazoeker), mg_schedsearch.py (woordenboek-bewuste
schemazoeker), mg_schedfit_all.py, mg_tradeoff.py (sloopkosten incl. bingo-breuk), mg_insert.py
(groep invoegen VOOR de slotzetten), mg_globalbound.py (bovengrens 13917).

## BEWEZEN (2026-07-28): 4778 is optimaal voor dit footprint met deze zetvolgorde
CP-SAT op het footprint-model (322k variabelen, 14 workers): `STATUS OPTIMAL, obj 4778,
bovengrens 4778`. Het model is exact -- het reproduceert score_game tot op de punt -- dus dit is
een echt bewijs, geen 'we vinden niets beters'. De onderste bewijslaag is daarmee gesloten.

DE DRIE LAGEN, met hun bewijskracht:
1. VAST footprint + VASTE zetvolgorde -> beste letterinvulling: BEWEZEN (CP-SAT OPTIMAL, 4778).
2. VASTE bezetting + ALLE zetvolgordes: open; branch-and-bound met het m-plafond als toelaatbare
   grens is de aangewezen route (elk schema met plafond <= 4778 kan zonder solver weg).
3. Alle geometrieen bij een gegeven triplet+masker: een triplet+masker legt maar 45 van de 101
   cellen vast; de keuze van de overige 56 uit 180 niet-ankercellen plus de zetindeling is de
   eigenlijke zoekruimte en ligt ver boven max-turn-N=15 in omvang.

BEGRIPPEN (voor de duidelijkheid vastgelegd): een MASKER is per ankerrij welke 7 van de 15 kolommen
door de slotzet gelegd worden (en dus welke 8 pre-cellen zijn) -- drie keer zeven kolomnummers, geen
letters en geen bordindeling. Het FOOTPRINT is alle 101 bezette cellen plus de zetvolgorde.
Onze maskers: rij 0 {0,3,7,8,11,13,14}, rij 7 {0,1,2,3,12,13,14}, rij 14 {0,1,2,3,7,13,14}.

### Bingo-tak GESLOTEN (2026-07-28) — met stelling
- Samenvoegen van niet-bingo-tegels tot een 12e bingo: van de 24 losse tegels ligt er maar EEN lijn
  met 7 op een rij (rij 14, x=5,6,8..12) en die heeft een gat op x=7 dat pas door de x27-slotzet
  gelegd wordt => 0 legale kandidaten over alle 34 invoegposities. Zonder dat gat was de ruil +22
  waard (50 bonus - 28 herscoring); hij is dus gunstig maar puur geometrisch geblokkeerd.
- Splitsen van bestaande bingo's: alle 11 x 126 deelverzamelingen x beide volgordes x alle posities,
  beste -39 (je verliest 50 en wint ~12 herscoring).
- STELLING: een TWS-lijn waarvan de slotzet x=0,7,14 bevat draagt HOOGSTENS EEN bingo — de overige
  cellen vallen in twee blokken van 6 en een tweede 7-zet zou over x=7 moeten bruggen, wat er nog
  niet ligt. Prijs van een TWS-cel uit een slotzet halen: 1166 (rij 0), 1022 (rij 14), 344 (rij 7),
  tegenover 50 voor een bingo. Rij 14 echt in 2 bingo's splitsen kost 897.
- Rij 7 is de uitzondering ((7,7) ligt vanaf zet 1, dus daar mag een zet over x=7 bruggen). Via
  kruis-lijn-herverdeling bestaat er wel degelijk een 12-bingo-spel met DEZELFDE 101 tegels:
  4767 met dezelfde letters, 4773 na herlettering (arbiter OK, 28 zetten) — dus -5 t.o.v. 4778.
  Bestanden: experiments/results/bingo12_sched.json en bingo12_refit.json.
- BOVENGRENS: set-packing over 12.835 vormlegale 7-groepen geeft max 13 disjuncte bingo's, maar elke
  pakking van 13 splitst rij 0 EN rij 14 (~-2200 voor +100). **12 is het maximum dat de x27-structuur
  overleeft**, en 12 kost ons 5 punten.

## LAAG 2 BEWEZEN (2026-07-28): deze bezetting is uitgeput op 4847
DECOMPOSITIE-IDENTITEIT (de sleutel, numeriek geverifieerd tegen score_game):
    score = SOM over de 14 maximale EINDruns L van g_L(geschiedenis van L)
    g_L = alle woordscores op L + 50 * (aantal 7-tegelzetten met L als hoofdlijn)
Elke gescoorde run ligt in precies EEN maximale eindrun (span-vulregel) en elke bingo hoort bij
precies EEN hoofdlijn. Daarmee valt de score per lijn uiteen en geeft een exacte DP over
deelverzamelingen per lijn een TOELAATBARE staartgrens.

STELLING 1: bij de bezetting EN de letters van het record bestaat er geen legale zetvolgorde met
score > 4778. Uitputtend bewezen: wortelgrens 5225, met de centrumregel (de zet met (7,7) is globaal
zet 1, dus de centrale x2 kan nooit in een slotzet worden hergebruikt — dat kostte rij 7 alleen al
955->561) zakt hij naar 4831, en de branch-and-bound sluit in 0,2 s met 751 bezochte toestanden
terwijl de ruimte 9,55e72 combinaties van lijn-geschiedenissen telt.
Validatie: identiteit vs arbiter; 600 willekeurige volledige schema's 600x arbiter-identiek; met
LB=4777 vindt de zoeker zelf een 32-zets-getuige die de arbiter op 4778 zet (het record heeft er 33),
dus de zoektocht gaat diep genoeg en snoeit niets legaals weg.

STELLING 3 (CP-SAT, OPTIMAAL gesloten): over ALLE zetvolgordes EN ALLE herletteringen van de 56 vrije
cellen (zak 100 tegels + 2 blanco's, kruispuntconsistentie op de 24 gedeelde cellen) geldt
    score <= 3865 (ankerrijen, onvoorwaardelijk) + 982 = 4847.
Losse per-lijn-maxima sommeerden tot 1364; zak en kruispunten kosten daar 382 van.

GEVOLG VOOR DE CAMPAGNE: deze bezetting heeft hooguit 69 punten headroom over zetvolgorde EN
herlettering samen, en dat is een BOVENgrens. Winst moet uit een ANDERE BEZETTING komen.
Bobs 4819 ligt nog net onder 4847, dus deze bezetting sluit hem niet uit — maar 4819 halen zou
betekenen dat we 41 van de 69 bound-punten daadwerkelijk incasseren, terwijl per lijn zichtbaar is
dat de zak die combinatie niet toelaat (V11 145 vs plafond 221, V9 87/143, V8 100/141).

VOLGENDE STAP die hieruit volgt: de decompositie-identiteit is niet aan DEZE bezetting gebonden.
Per-lijn-grenzen maken het mogelijk om hele GEOMETRIEKLASSEN te begrenzen in plaats van losse borden
— dat is de aangewezen route naar laag 3 (alle geometrieen bij gegeven triplet+masker).

## KLASSEGRENS (2026-07-28): het triplet wordt hierlangs NIET gedood — en de diagnose wijst de weg
STELLING B: elke klassegrens uit de per-lijn-decompositie is >= 4847 > 4819. Bewijs: de klasse bevat
onze eigen bezetting; fixeer die en het klassemodel reduceert tot het stelling-3-model, waarvan
CP-SAT het optimum OPTIMAAL = 4847 bewees; een maximum over een grotere verzameling is niet kleiner.
Er bestaat dus geen versie van deze route die onder 4819 uitkomt. (De agent heeft de zware berekening
daarom NIET gedraaid — hij kon bewijsbaar niets beslissen.)

STELLING A (bewezen, sterk): de drie ankerrijen dragen onvoorwaardelijk hoogstens 3865 bij --
1743 + 561 + 1561 -- over ALLE bezettingen, maskers, vrije letters en zetvolgordes. Het eiland-,
fragment- en x27-maskerlemma zijn hierdoor overbodig gemaakt (niet genegeerd): ze beperken allemaal
de toegestane geschiedenissen van een ankerrij, en hier wordt over de volledige verzameling gemaximeerd.
Rekenkundig gevolg: record 3840 (ankers) + 938 (27 overige lijnen) = 4778; het ankerplafond laat nog
+25 toe, dus het HELE gat van +41 naar 4819 moet uit de NIET-ANKERLIJNEN komen (938 -> >=979).

FRAME-VRAAG DEFINITIEF BESLIST (en contra-intuitief): de 9 kruispunten geven hun x3 maar EEN keer --
of aan de rij-final, of aan de kolomzet.
  scenario A (rij-finals pakken de x3): ankerrijen 3865 + kolommen 0/7/14 samen 766 = 4631
  scenario B (zuivere FRAME, kolomzetten pakken de x3): 787 + 2422 = 3209
A wint met 1422. De zuivere frame-klasse is voor dit triplet aantoonbaar SLECHTER; geschenkcheques en
polymelkzuurtje als x27-rij-final zijn meer waard dan welk kolomwoord ook. Wat wel werkt is de
hybride: het kolomwoord x3-voltooid door de rij-final als LOSSE tegel -- dat zit in scenario A en
levert 766 op de framekolommen, waar ons bord er 74 haalt.

DE DIAGNOSE (per lijn, bij exact dezelfde tegelinzet als het record):
  kolommen        648 -> 1227   (kol 10 +111, kol 11 +94, kol 4 +86, kol 5 +69, kol 7 +62)
  niet-ankerrijen 290 ->  936   (rij 8 +90, rij 5 +76, rij 6 +69, rij 3 +68, rij 2 +65)
Grootste post: de rijen 1/3/5/6/9/10/11/12/13 leveren NUL punten terwijl ze elk 2-5 tegels
verbruiken. Oorzaak, visueel bevestigd: onze verticale woorden staan in de kolommen 2,4,5,7,10,11,12
en liggen te ver uit elkaar, dus de middenrijen bevatten losse niet-aangrenzende tegels die geen
horizontaal woord vormen. Alleen rij 2 ('aft') en rij 8 ('in','na') scoren, precies waar kolommen wel
naast elkaar liggen. Een tegel die in EN een verticaal EN een horizontaal woord ligt wordt twee keer
gescoord; onze verticale tegels worden nu maar een keer geteld.
=> VOLGENDE CONSTRUCTIE: dichte-blok-topologie met AANGRENZENDE kolommen, zodat de middenrijen zelf
lange horizontale woorden vormen. Spanningsveld: elke aangrenzende kolom maakt kruiswoorden met zijn
buur die allemaal geldig moeten zijn.
NB: de per-lijn-plafonds in de diagnose zijn gecertificeerde ONDERgrenzen op het lijnplafond en
negeren zak, kruispuntconsistentie en volgorde -- indicaties, geen grenzen.

### 12-bingo-familie GESLOTEN (2026-07-28)
De laatste levende bingo-lead is uitgeput. De woordenboek-bewuste schemazoeker vond binnen die
familie 7304 woordbare schema's met plafond 4873 (tegen 4881 voor de basis), maar de CP-SAT-vulling
van de drie beste geeft alle drie 4772 (arbiter ok) -- onder hun eigen basis van 4773 en 6 onder het
record. Het plafondgat van 8 punten bleek dus geen speelruimte maar juist een extra lexicale schuld.

## DICHTE BLOKKEN (2026-07-28): negatief, maar met de scherpste diagnose tot nu toe
Een dicht blok (aangrenzende kolommen, zodat de middenrijen zelf woorden vormen) is bij gelijke
tegelinzet +130 tot +230 ankervast m-plafond waard -- het idee klopt kwantitatief. Toch geen bord
boven 4778: elk zetschema met een plafond boven ~4680 is CP-SAT-INFEASIBLE. Wel drie geverifieerde
dichte-blok-borden: denseblock_board_E2.json 4540, _G 4476, _D 4412.
DRIE BEVINDINGEN:
1. DE EERSTE ZEEF IS LOGISTIEK, NIET LEXICAAL. Maskercellen worden pas in de slotzet gelegd, dus
   rij 0 valt tot dan uiteen in de eilanden {1,2} {4,5,6} {9,10} {12} en rij 14 in {4,5,6} {8..12}.
   Elk eiland heeft een eigen dragende kolom nodig die rij 1 resp. rij 13 haalt => vier bovendragers
   en twee onderdragers liggen GEDWONGEN uit elkaar. Dat onze verticalen ver uit elkaar staan is dus
   een GEVOLG VAN DE MASKERKEUZE, geen ontwerpfout. Alle acht vrij ontworpen blokken sneuvelden
   hierop voordat er een woord aan te pas kwam.
2. DE LEXICALE MUUR IS EXACT GEMETEN: het 8-letter kolomwoord met twee vaste ankerletters dwingt de
   blokbreedte af op max 4 boven (posities 5-8, 6-9, 7-10, 9-12) en 3 onder (4-6, 5-7, 10-12);
   breedte 5 bestaat nergens. Met bouwvolgorde blijft boven een breedte-4-positie over (kol 7-10) en
   onder een breedte-3 (4-6).
3. DE DOODSOORZAAK IS DE BOUWVOLGORDE, NIET HET EINDBORD. Nieuw filterpaar static_feasible (alleen
   eindbord-runs) vs lex_feasible (alle tussenruns): elke dichte-blok-bezetting is statisch JA en met
   zetschema NEE. Twee aangrenzende kolommen over zes rijen eisen zes horizontale minidwoorden
   (waarvan drie 2-letterwoorden) bovenop twee dubbel verankerde kolomwoorden.
GEREEDSCHAPSLES: mg_newtopo.auto_schedule hangt de slotzetten altijd achteraan en verwerpt daardoor
bezettingen die wel bestaan (het record zelf is er een van); mg_denseblock.schedule() doet dat niet.
En: de m-plafondzoeker mag niet zonder lexicale toets gebruikt worden -- boven ~4680 bestaat het niet.
De realisatiegraad is NIET het probleem (E2 haalt 4540 uit plafond 4580 = 99,1%).
=> VOLGENDE: masker en geometrie GEZAMENLIJK optimaliseren. Het masker is tot nu toe alleen
geoptimaliseerd op wat het voor de ankerrij zelf oplevert; wat het afdwingt aan dragende kolommen --
en dus aan productiviteit van de middenrijen -- zat in geen enkele maat.

## MASKER-GEOMETRIE (2026-07-28 nacht): de gedwongen spreiding is een VOORWAARDE, geen handicap
EILAND-LEMMA BEWEZEN: elk eiland van de pre-set eist minstens een dragende kolom BINNEN dat eiland
(de eerste zet die het eiland raakt kan op die rij niets anders raken en moet dus via de buurrij
binden). Omdat {0,7,14} altijd in het masker van rij 0/14 zit, valt de pre-set altijd in >=2 eilanden
uiteen: minimaal 2 dragers per x27-rij. Rij 7 krijgt het centrum-eiland gratis.
KERNVRAAG NEGATIEF MET BEWIJS: aangrenzende dragers BESTAAN NIET. Dragers uit verschillende eilanden
zijn per constructie door een maskercel gescheiden; binnen een eiland is er maar een nodig en een
tweede ernaast is precies het dichte blok dat al weerlegd was. Uitputtende sweep over 39/39/36
legbare maskers: ons recordmasker is niet alleen maximaal in ankerwaarde maar ook het ENIGE
rij-0-masker waarvan alle vier de gedwongen dragers een rijke 8-letter kolomtabel hebben
(kol 2:1242, 5:390, 10:390, 12:368). Minder dragers kost 120 (4->3) of 234 (4->2) ankerpunten tegen
~8 punten per vrijgekomen tegel. Alleen een rij-7-maskerwissel is positief (+37 tegen -10).
DE INVERSIE (de vondst): de vier gedwongen rij-0-dragers (kol 2/5/10/12) kruisen elke bovenrij op
vier plaatsen -- precies wat een x4-LAAN nodig heeft om in EEN bingo-zet gelegd te worden. De
maskergedwongen spreiding is voor een laan dus de VOORWAARDE. Daaruit volgt ook direct de boven/onder-
asymmetrie van het record: rij 14 heeft maar twee pijlers, dus de onderhelft is laan-arm.
GEMETEN op het 4778-bord: laan op rij 3 = +55 ankervast plafond (4889 -> 4944), 12 bingo's i.p.v. 11,
101 tegels, betaald met de zeven losse tegels van de kolom-2-extensieketen (geen bingo gebroken).
Laan-sweep: rij 3 +55, rij 4 +29, rij 1 +17, rij 6 +14, al het andere <= 0.
LEXICAAL: invoegpositie 6 (plafond 4944) is NEE (de rij-3-run wordt eerst 10 en dan 11 letters, dus
rij 3 zou tegelijk een 10-letterwoord en diens 1-letter-uitbreiding moeten zijn); posities
7/10/14/18/22 (plafond 4925) zijn JA en het eindbord is CP-SAT OPTIMAL (bodeverhaal/isolatieglas).
De recordletters op rij 3 geven patroon r??d????d?a met 0 woorden, terwijl 35.216 pijlersignaturen
wel een 11-letterwoord toelaten -- de bovenhelft MOET dus herletterd worden.
LET OP (gemeten na de LNS-vondsten): op het 4790-bord is de beste laan nog maar +8, want de vloot
heeft juist de losse tegels opgesoupeerd die het betaalmiddel voor de laan waren. Laan en LNS
concurreren om dezelfde voorraad; MODE=laan moet dus na elke recordverbetering opnieuw draaien.

## DE ZAK IS DE GRENS (2026-07-29, gemeten): TOEVOEGEN kan niet meer, RUILEN wel
Alle laan-varianten op het 4790-bord zijn CP-SAT-INFEASIBLE, en het scherpste datapunt is dat EEN
extra tegel aan de al bestaande rij-4-laan -- geometrisch de goedkoopst denkbare toevoeging -- al
zak-infeasible is (plafond 4915, +30). Het record gebruikt 99 van de 100 lettertegels plus beide
blanco's; elke TOEVOEGING dwingt het lexicon tot letters die de zak niet meer heeft.
SYNTHESE MET DE LNS-VONDSTEN: de nachtvloot tilde het record in dezelfde uren van 4778 naar 4793 --
maar uitsluitend met RUILEN (sloop een cel, bouw er een andere), waarbij het tegelaantal en dus het
lettermultiset-budget gelijk blijft. Toevoegingen zijn zak-geblokkeerd, ruilen niet. Dat verklaart
in een klap waarom elke gerichte structurele ingreep van deze campagne sneuvelde (kolommen, rail,
dichte blokken, bruggen, lanen -- allemaal TOEVOEGINGEN) terwijl een blinde ruil-zoeker drie
verbeteringen op rij vond. De zoekruimte die nog leeft is die van de PERMUTATIES van hetzelfde
tegelbudget, niet die van de uitbreidingen.

### Zak-uitputting exact gemeten (2026-07-29)
Op het 4793-bord is van de 100 lettertegels er nog precies EEN over (een 'n'), plus beide blanco's
liggen op het bord. Verbruik van de goedkope letters: e 18/18, a 6/6, o 6/6, d 5/5, r 5/5, s 5/5,
t 5/5, i 4/4, n 9/10. Alle vier de laan-varianten op het 4790-bord zijn CP-SAT-INFEASIBLE
(rij 1 +21, rij 4 +30, rij 4 +21, rij 3 +59), net als de 4787-tegenhangers. Formeel blijft alleen
de rij-3-laan op invoegpositie >=7 van het 4790-bord ongetoetst; de vloot-lijst bevat per laan maar
een positie. Model B (schema-onafhankelijke zaktoets) draait nog.
CONSEQUENTIE VOOR DE CAMPAGNE: verbetering moet uit een ander LETTERMULTISET komen, niet uit meer
structuur. Het ankertriplet eist 45 tegels op, en juist de goedkope bindletters (e/n/a/o/d/r/s/t/i)
zijn daarna volledig vergeven -- terwijl precies die letters nodig zijn om verderop nog woorden te
kunnen vormen. De triplet-ranker weegt tot nu toe alleen wat een triplet ZELF oplevert, niet wat het
voor de overige 56 cellen OVERLAAT. En de m-plafondmaat is zak-BEWUST maar niet zak-LEXICAAL: hij
telt tegels, niet of de resterende letters nog woorden kunnen vormen. Dat verschil kostte hier vier
veelbelovende kandidaten.

### Laan-verificatie definitief (2026-07-29) + de mooiste bevestiging van het ruil-lemma
Zes laan-varianten getoetst op het 4790-bord: rij 3 (kol 2..11, +59) INFEASIBLE, rij 4 (+30)
INFEASIBLE, rij 1 (+21) INFEASIBLE, rij 4 (+21) INFEASIBLE, rij 6 (+11) UNKNOWN, en precies EEN
overlevende: rij 3 met alleen de cel (11,3), plafond 4896. Die levert een geverifieerd spel op
(maskgeom_board_laan3.json, 4744 arbiter-ok) maar ruim onder het record: om die ene tegel kwijt te
kunnen moet CP-SAT het hele bord herletteren, en dat kost elders meer dan de toevoeging opbrengt.
BEVESTIGING VAN HET RUIL-LEMMA: diezelfde cel (11,3) is precies wat de LNS-vloot een uur eerder
gebruikte -- maar als RUIL tegen (11,2), en dat gaf 4793. Dezelfde cel, 49 punten verschil, alleen
omdat de ruil binnen het tegelbudget past en de toevoeging niet.

### Model B: UNKNOWN (2026-07-29, 5400s)
De schema-onafhankelijke zaktoets voor de rij-3-laan-bezetting liep af zonder oordeel
(MODEL_B_UITSLAG: UNKNOWN). De rij-3-bezetting is dus niet formeel gesloten, maar de praktische
uitkomst staat wel vast: alle zes de laan-varianten op het actuele bord zijn los getoetst en op een
na CP-SAT-weerlegd, en de overlevende (enkele cel (11,3), als TOEVOEGING) levert 4744 -- onder het
record. Losse draad, geen open kans.

## LETTERBUDGET (2026-07-29): de triplet-deur is DICHT, met een gemeten wisselkoers
Vraag was: bestaat er een triplet dat ankerwaarde inlevert maar zoveel meer bindletters overlaat dat
de 56 vrije cellen productiever worden? Antwoord: NEE, en nu kwantitatief.
MULTIPLIER-ASYMMETRIELEMMA (de kern): de 45 ankercellen hebben m-som 1115 (gemiddeld 24,8) en de 56
vrije cellen m-som 238 (gemiddeld 4,25). De ankerrijen dragen dus 82,4% van al het scoringsgewicht.
Een tegel die je 'voor de zak bewaart' landt op een cel die gemiddeld 5,83x minder waard is. Voor
rij 0 en 14 is dat HARD: hun laagste m is 27 en de hoogste vrije m is 11, dus elke letterwaarde die
je daar weghaalt levert hoogstens 11/27 = 0,41 terug. Alleen rij 7 (min m 9) kan theoretisch boven 1.
GEMETEN WISSELKOERS: 0,31 restpunt per ingeleverd ankerpunt (regressie over 476 kandidaten), beste
enkele geval 0,44, bovengrens 0,66 -- break-even vereist 1,00. Het triplet zet 134 punten letterwaarde
om in 3763 (28,1x); de restzak zet 96 punten om in 480 (5,0x).
RESTZAK van ons triplet: 55 tegels, 17-letterig alfabet, c/h/j/k/l/q/u/x/y VOLLEDIG op, nog 21,9% van
de 8-letterwoorden bouwbaar. Arm dus -- maar dat is een GEVOLG van waar de punten zitten, geen oorzaak.
Ons triplet is rang 1 op beide sporen (ankerrijpools onder de fragmenteis, en voetafdruk-vrij).
WAT ER NOG WEL LIGT: 96 punten op DIT voetafdruk, in de LETTERING. De restzak haalt 480 van de 576 die
de zakgrens toelaat (83% realisatiegraad). De harde bovengrens van dit voetafdruk met ons triplet is
3763 + 576 + 550 = 4889, en 4819 ligt daaronder -- 4819 is dus NIET uitgesloten op deze bezetting,
alleen niet bereikbaar via een ander triplet.
=> LOPENDE BINDENDE TOETS: exact_fill in beslissingsvorm op het huidige voetafdruk, target = record+1
(experiments/results/mg_decide.log, 5400s). INFEASIBLE bewijst dat 4793 optimaal is voor deze
bezetting; FEASIBLE levert direct een beter bord.

### BEWEZEN (2026-07-29): 4793 is optimaal voor ZIJN EIGEN voetafdruk
exact_fill(target=4794) op de 4793-bezetting: **INFEASIBLE na 2964s**. Er bestaat geen enkele andere
lettering van de 56 vrije cellen -- met blanco's vrij plaatsbaar op ELKE cel -- die deze bezetting
plus zetvolgorde boven 4793 brengt. 'Invulling optimaliseren' is op dit bord dus uitgeput; winst moet
uit een ANDER voetafdruk komen. Daarmee is voor de tweede keer deze campagne een volledige
voetafdruk-laag gesloten (eerder 4778, nu 4793) -- en beide keren tilde de LNS het record er
vervolgens overheen door de BEZETTING te muteren.
TRIPLET-TOETS UITPUTTEND: van de 476 tripletten die de harde bovengrens halen zijn er 35 dood bij
constructie, 291 bewezen INFEASIBLE op '>= 4794', 149 onbeslist (allemaal schatting <=4742) en 0
boven het record. Opvallend: de meeste rivalen zijn niet 'te laag' maar HELEMAAL infeasible -- de
bezetting is letter-vergrendeld.
BIJVANGST (reproduceerbaarheidsbug, gefixt): r.words_str is een SET, dus de BYLEN-volgorde was
hash-afhankelijk en gelijkspel-keuzes verschilden per proces (+/-5 punten in schattingen, en
overlappende shards). Nu gesorteerd en deterministisch.

### Waarom de LNS na drie vondsten stilviel (gemeten, 2026-07-29 ochtend)
Diagnose over 24 willekeurige mutaties op het 4793-bord: 13 stranden bij de BOUW (het slopen van een
cel verbreekt de aanraakketen van een latere zet -- maar dat is pure Python en kost dus niets), 11
komen leeg terug uit de SOLVER, en NUL halen de arbiter. Per-cel is dat niet te verhelpen: van de 12
goedkoopste sloopcellen is er maar EEN die de bouw breekt en zijn er 56 van de 56 vrije cellen
lexicaal sloopbaar. De bouwfouten komen dus van COMBINATIES, en de solver-fouten van de
zak-vergrendeling die we los al bewezen hadden.
CONCLUSIE: de lage trefkans van de LNS is inherent aan het probleem, geen instelfout. De drie vondsten
van vannacht (4787/4790/4793) waren het laaghangend fruit van een bord dat daarna aantoonbaar
letter-vergrendeld is. Toegevoegde zeven (lexicale sloopzeef, bouwzeef, krimp-modus, simulated
annealing) verhogen de doorvoer maar veranderen die grens niet.

## CONFIGURATIE-GENERATOR (2026-07-29): 337,8 M structuurparameters, NUL bord boven 4793
Volledig verslag: `experiments/CONFIGGEN.md`, gereedschap `experiments/mg_configgen.py`.
In plaats van celverzamelingen te muteren (waar de LNS-vloot in vastliep: 0 van 24 mutaties haalt
de arbiter) somt deze module de STRUCTUURPARAMETERS op: laan, kolom 7, de vier rij-0-dragers en
de twee rij-14-dragers met hun dieptes, extra kolommen, laanhangers en de peel. Het record is
aantoonbaar een punt van die opsomming (skelet van 54 tegels + de hangers (11,3) en (13,5)).
TELLINGEN (twee volle draaien van 337.798.080 parameterpunten, samen 26,4 CPU-uur):
  tegelbudget != 56 vrije cellen  311.821.416 weg (92,3%)
  eiland/bezorging                     38.220 weg
  ZAK-LEXICALE runtoets            16.001.620 weg (61,6% van de rest) <- de ontbrekende zeef
  schema gebouwd                    9.936.824
  plafond in de band 4830-4980      8.156.685
Daarna 8.916 gespreide configuraties verfijnd met een NIEUWE ketenbewuste bouwer: 1.285
lijnconsistent (14,4%), beste plafond 5005 (record 4860 met dezelfde bouwer). fit_decide(4794):
2.350 NEE, 22 ONBEKEND, 0 JA. De negen hoogste ONBEKEND-gevallen zijn met de maximaliserende
solver nagelopen: ALLE NEGEN INFEASIBLE -- geen enkele lettering bestaat.
DE BINDENDE BEPERKING IS VERSCHOVEN: niet meer de geometrie, en niet meer de zak alleen, maar de
LEXICALE INVULBAARHEID VAN DE HELE BEZETTING. 85,6% van de verfijnde bezettingen is al
lijn-inconsistent en van de rest is elke geteste bezetting CP-SAT-infeasible, meestal via presolve
binnen twee seconden. Het m-plafond is daarmee als rangschikking uitgewerkt (correlatie met het
verfijnde plafond 0,35-0,47 binnen een familie; 0,70 over alle topologieen heen), en top-K erop
selecteert systematisch LADDERILLUSIES -- fase D draait daarom met een reservoirsteekproef binnen
een realistische plafondband.
TWEE CORRECTIES OP EERDERE INTUITIE, allebei gemeten:
 * 'bingo's domineren' is FOUT: op het record levert de kolom-2-verlengketen 16,0 punt/tegel tegen
   12,8 voor een gewone bingo. Wat betaalt is HERSCORINGSMASSA op lange runs, niet het aantal
   bingo's. Nieuw gereedschap: chain_len/sub_ok (is een keten lexicaal mogelijk?) en ext_potential.
 * het twee-lanen-spoor met korte (laan-gewortelde) dragers is NIET dood door gebrek aan bingo's;
   bij gelijke tegelinzet is het lexicaal juist kerngezond (400 van 401 lijnconsistent tegen 9,5%
   voor de enkellaans top) maar het plafond blijft op 4813 steken, en om daarvandaan boven 4793 te
   komen is 99,6% realisatiegraad nodig terwijl het record zelf 98,0% haalt.
STRUCTUURBEELD: het record staat op een smal optimum van een RUIL tussen plafond en lexicale
robuustheid (4860 plafond EN lijnconsistent); de sweep vond er geen tweede van.
SCHERPSTE OPENSTAANDE HEFBOOM die hieruit volgt: kolom 2 is lexicaal tot ketenlengte 8 verlengbaar
terwijl het record er maar 4 gebruikt -- daar is de BEZETTING de rem, niet het lexicon.
