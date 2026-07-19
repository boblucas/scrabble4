#!/bin/bash
cd /home/bob/programming/scrabble4
SD=$1
SEED=$SD MGTRIPLES=3 MGBEAM=8 MGBRANCH=5 .venv/bin/python -u experiments/maxgame_play6.py \
  > experiments/results/maxgame_pipeb_$SD.log 2>&1
J=experiments/results/maxgame_play6_$SD.json
[ -f "$J" ] && timeout 420 .venv/bin/python experiments/maxgame_extend.py "$J" dutch2026 \
  >> experiments/results/maxgame_pipeb_$SD.log 2>&1
