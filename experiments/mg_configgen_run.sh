#!/usr/bin/env bash
# Draaiboek voor de configuratie-generator (experiments/mg_configgen.py).
# Elke fase is gesharded en hervatbaar; opnieuw starten slaat afgeronde lanen/skeletten over.
set -u
cd /home/bob/programming/scrabble4
RES=experiments/results/configgen
mkdir -p $RES
N=${N:-10}

phase=${1:-help}
case "$phase" in

A)  # SKELETTEN met volle tegelinzet (56), een laan, hoogstens een niet-'full' drager
    for s in $(seq 0 $((N-1))); do
      MODE=enum SHARD=$s NSHARD=$N TMIN=56 TMAX=56 TOPK=12000 FLOOR=4800 \
      OUT=$RES/skelA_$s.jsonl nohup .venv/bin/python experiments/mg_configgen.py \
        >> $RES/enumA.log 2>&1 &
    done ;;

B)  # SKELETTEN met 1-2 tegels speling (54/55) -> daarna fase Bx (uitbreidingen)
    for s in $(seq 0 $((N-1))); do
      MODE=enum SHARD=$s NSHARD=$N TMIN=54 TMAX=55 TOPK=8000 FLOOR=4800 PEELS=0 \
      OUT=$RES/skelB_$s.jsonl nohup .venv/bin/python experiments/mg_configgen.py \
        >> $RES/enumB.log 2>&1 &
    done ;;

Bx) # UITBREIDINGEN (extra kolom / laanhangers) op de beste B-skeletten
    for s in $(seq 0 $((N-1))); do
      MODE=expand IN=$RES TOPN=${TOPN:-4000} PER=${PER:-4} SHARD=$s NSHARD=$N FLOOR=4800 \
      OUT=$RES/expB_$s.jsonl nohup .venv/bin/python experiments/mg_configgen.py \
        >> $RES/expandB.log 2>&1 &
    done ;;

C)  # TWEE LANEN met korte (stub) dragers -- structureel nieuw terrein: horizontale in
    # plaats van verticale structuur bij GELIJK tegelaantal (dus een RUIL, geen toevoeging)
    for s in $(seq 0 $((N-1))); do
      MODE=enum SHARD=$s NSHARD=$N NLANE=2 TMIN=54 TMAX=56 TOPK=8000 FLOOR=4800 \
      LX0=${LX0:-2,4} LX1=${LX1:-12,14} \
      OUT=$RES/skelC_$s.jsonl nohup .venv/bin/python experiments/mg_configgen.py \
        >> $RES/enumC.log 2>&1 &
    done ;;

R)  # VERFIJNING: vol schema-onderzoek + lijnconsistentie op een gespreide top
    for s in $(seq 0 $((N-1))); do
      MODE=refine IN=$RES TOPN=${TOPN:-2000} PER=${PER:-3} SHARD=$s NSHARD=$N \
      ITERS=800 SEEDS=2 OUT=$RES/ref_$s.jsonl \
      nohup .venv/bin/python experiments/mg_configgen.py >> $RES/refine.log 2>&1 &
    done ;;

D)  # BESLISSEN: CP-SAT in beslissingsvorm, target = record+1
    for s in $(seq 0 $((N-1))); do
      MODE=decide IN=$RES TOPN=${TOPN:-300} TLIM=${TLIM:-300} NW=${NW:-1} \
      TARGET=${TARGET:-4794} SHARD=$s NSHARD=$N OUT=$RES/dec_$s.jsonl \
      nohup .venv/bin/python experiments/mg_configgen.py >> $RES/decide.log 2>&1 &
    done ;;

S)  MODE=stats IN=$RES PAT=${PAT:-skel} .venv/bin/python experiments/mg_configgen.py ;;

*)  echo "gebruik: $0 {A|B|Bx|C|R|D|S}"; exit 1 ;;
esac
echo "fase $phase gestart met $N shards"
