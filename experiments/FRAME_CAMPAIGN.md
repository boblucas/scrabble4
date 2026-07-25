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
