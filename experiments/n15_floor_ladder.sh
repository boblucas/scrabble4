#!/bin/bash
# TOP-DOWN FLOOR-LADDER voor een fat mask (dutch2026, HMAX=15, LB 2100):
#   voor floor in 425 415 405 395 385 376: pinenum (Rust, snel) -> pinbatch (Rust) -> MAXes
#   naar witness. Elke LE-trede certificeert "geen bord met gross > floor" voor die trede;
#   de laagste all-LE-trede + hogere treden samen = certificaat tot floor 376 (= LB 2100).
#   Een geverifieerd bord > 2100 stopt de ladder (NEW LB -> alles herfloort).
# Usage: n15_floor_ladder.sh 0,3,7,8,11,12,14
set -u
cd /home/bob/programming/scrabble4
MASK="$1"
TAG=$(echo "$MASK" | tr ',' '_')
DTAG=$(echo "$MASK" | tr -d ',')
BASE=experiments/results/oracle_parallel/bases_2026/geschenkcheques/base_${TAG}.txt
D=experiments/results/oracle_parallel/ladder2026_${DTAG}
mkdir -p "$D"
ML=$(.venv/bin/python -c "w='geschenkcheques'; print(','.join(str(ord(w[c])-96) for c in [$MASK]))")
BIN=experiments/xfill_rs/target/release/xfill
for FLOOR in 425 415 405 395 385 376; do
  FREE=$(df --output=avail -BG / | tail -1 | tr -dc 0-9)
  [ "$FREE" -lt 30 ] && { echo "[$MASK] DISK LOW (${FREE}G) -- stop before floor $FLOOR"; exit 2; }
  SD="$D/f$FLOOR"; mkdir -p "$SD"
  echo "[$MASK] floor $FLOOR: pinenum ..."
  "$BIN" --pinenum "$BASE" --floor "$FLOOR" --mainletters "$ML" --shards 8 --outdir "$SD" 2>/dev/null | tee "$SD/pinenum.log"
  N=$(cat "$SD"/shard_*.txt | wc -l)
  if [ "$N" -gt 60000000 ]; then echo "[$MASK] floor $FLOOR band $N TE GROOT -- stop"; exit 3; fi
  echo "[$MASK] floor $FLOOR: solve $N combos ..."
  for i in $(seq 0 7); do
    PINWALL=5 "$BIN" --pinbatch "$BASE" --emit < "$SD/shard_0$i.txt" > "$SD/verdict_0$i.txt" 2>/dev/null &
  done
  wait
  NM=$(grep -hc '^RES .* MAX' "$SD"/verdict_*.txt | paste -sd+ | bc)
  NTO=$(grep -h '^RES' "$SD"/verdict_*.txt | grep -cE ' TO ')
  NRES=$(grep -hc '^RES' "$SD"/verdict_*.txt | paste -sd+ | bc)
  echo "[$MASK] floor $FLOOR: RES=$NRES MAX=$NM TO=$NTO"
  if [ "${NM:-0}" -gt 0 ]; then
    echo "[$MASK] floor $FLOOR: MAX gevonden -> witness in python"
    N15_LANG=dutch2026 N15_HMAX=15 .venv/bin/python -u experiments/_ladder_witness.py "$MASK" "$SD" 2100 && { echo "[$MASK] NEW LB gevonden -- ladder stopt"; exit 0; }
  fi
  # verdicts comprimeren om schijf te sparen (certificaat-artefact blijft, 10x kleiner)
  gzip -f "$SD"/verdict_*.txt "$SD"/shard_*.txt 2>/dev/null
done
echo "[$MASK] LADDER COMPLEET tot 376 (details per trede; TO-residu via CP-SAT afwikkelen)"
