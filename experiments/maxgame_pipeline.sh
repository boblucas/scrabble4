#!/bin/bash
# spel bouwen -> verlengen -> BEST bijwerken.  Usage: maxgame_pipeline.sh <seed> [MGTRIPLES] [extra-env]
cd /home/bob/programming/scrabble4
SD=$1; MT=${2:-5}
SEED=$SD MGTRIPLES=$MT .venv/bin/python -u experiments/maxgame_play5.py \
  > experiments/results/maxgame_pipe_$SD.log 2>&1
J=experiments/results/maxgame_play5_$SD.json
[ -f "$J" ] && timeout 420 .venv/bin/python experiments/maxgame_extend.py "$J" dutch2026 \
  >> experiments/results/maxgame_pipe_$SD.log 2>&1
grep -hE "BESTE VAN|VERLENGD|NIEUW RECORD" experiments/results/maxgame_pipe_$SD.log | tail -3
