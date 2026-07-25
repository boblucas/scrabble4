# BEWIJSPLAN: 13-bingo-totaal met WERKSTER als zet 2 — mogelijk of onmogelijk?

Triplet vast: geschenkcheques (r0, ×27) / flexwerkstertje (r7, ×9) / polymelkzuurtje (r14, ×27).
Zet 1 = center-bingo kolom 7 (gaskast-klasse, rijen 4-10). Zet 2 = WERKSTER (rij 7, kol 4-11,
7 nieuw + de k). Vraag: bestaat een legaal spel met 13 zetten van 7 tegels (bingo's)?

## Tel-lemma (kern, bewezen door aftellen)
- 101 tegels = 45 anker (rijen 0/7/14) + 56 niet-anker. 13×7 = 91 bingo-tegels -> <=10 niet-bingo.
- Vast: gaskast (1 anker + 6 n-a), werkster (7 anker), 3 finals (21 anker) -> 8 overige bingo's.
- Na werkster is rij 7 VOL -> top-verticalen zijn EXACT rijen 0-6 (1 anker), bottom EXACT rijen
  8-14 (1 anker); horizontalen (rijen 1-6/8-13) absorberen 0 ankers.
- B_a = 29+V (V = #verticalen van de 8), niet-anker-behoefte B_n = 62-V <= 56 => **V >= 6**.
- Niet-anker-steiger S_n = V-6 (<=2!); anker-singles S_a = 16-V = precies de onbezorgde
  pre-cellen van rij 0+14 (8-V_top)+(8-V_bot). GEEN enkele andere niet-bingo-zet mogelijk.
- Zelfde kolom top+bottom => 15-run => 15-woord met G/F/P-letters op 0/7/14: apart te checken (~0).
- Verticaal + horizontaal delen GEEN kolom (vert kan niet meer uitwijken na werkster).

## Kolom-census (8-woord-tabellen, gedaan 2026-07-25)
TOP 'G[c]......F[c]': k1:38 k2:1242 k3:5 k4:19 k5:390 k6:99 k8:450 k9:301 k10:390 k11:4 k12:368 k13:1
BOT 'F[c]......P[c]': k1:12 k2:38 k3:0(DOOD) k4:74 k5:390 k6:103 k8:3 k9:4 k10:1 k11:261 k12:408 k13:2

## Prover-architectuur (mg_13bingo_prove.py, te bouwen)
1. Enumereer: V_top (kolommen, koppen in pre0), V_bot (pre14), H-configs (rijen+spans,
   H = 8-V <= 2; rij 4-6 door gaskast-kol / rij 1-3 onder rij-0-koppen / rij 8-13 aan werkster-rail),
   mask0/mask14 (pre-singles moeten via buur-adjacentie bezorgbaar; rij-0-stage-runs =
   G-substrings die woorden moeten zijn — "fragmenten in de 15-woorden"), steiger <= S_n cellen.
2. Per config: stabiele greedy-touch-ordening (compleet: touch is monotoon).
3. CP-SAT met stadium-run-tabellen + zak (bestaande machinerie 1:1); INFEASIBLE-certificaat per config.
4. Alle configs INFEASIBLE => STELLING: 13 onmogelijk. Anders: witness = nieuw record (12 bingo's
   bestaat: 4435 heeft er 12 incl finals; 13 = +1).
Pruning: censusdode kolommen, V>=6, adjacente verticalen alleen met 2-woord-tabellen, symmetrie.

## Eiland-lemma (ontdekt 2026-07-25, v3)
(7,0) en (7,14) zijn ALTIJD maskercellen (TWS in de slotzet) => rij 0 en rij 14 vallen elk uiteen
in twee bezorg-eilanden: kolommen 1-6 en 8-13. Elke samenhangende pre-component op een ankerrij
moet >=1 BINNEN-verticaal-kop bevatten (kolom 4-6 links, 8-11 rechts; binnen = werkster/rail-
geankerd). Buiten-verticalen (1-3, 12-13) wortelen alleen via een aaneengesloten pre-brug naar
zo'n kop op hetzelfde eiland. Dit verklaart de 73k order-fails van v2 (koppen zonder wortel) en
is een scherpe snoeiregel + bewijscomponent voor fase B.
