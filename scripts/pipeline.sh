#!/bin/bash
# Every step for one book, in order, from its text to its knitting pattern.
#   scripts/pipeline.sh <slug> [model] [run]
# The book needs books/<slug>.json and its text under data/raw/. Each model step resumes if stopped;
# to continue a stopped run, pass its folder as the third argument instead of starting a new read.
# By default the first read asks only who is in each passage, which is all the scarf needs.
# FULL=1 scripts/pipeline.sh <slug> also reads interactions, places, objects and events and decides
# where each passage is set (what the map and the weave draw from); that takes about twice as long.
set -e
SLUG=$1
MODEL=${2:-ollama:qwen3:30b-a3b-instruct-2507-q4_K_M}
RUN=$3
cd "$(dirname "$0")/.."
export PYTHONPATH=src

uv run rebind segment --book "$SLUG"
if [ -z "$RUN" ]; then
  if [ -n "$FULL" ]; then
    uv run rebind read --book "$SLUG" --model "$MODEL"                    # who, what, where, with cited sentences
  else
    uv run rebind read --book "$SLUG" --model "$MODEL" --only characters  # who, with cited sentences
  fi
  RUN=$(ls -d out/"$SLUG"/runs/*/ | tail -1)
fi
echo "run: $RUN"
uv run rebind resolve "$RUN"                               # names -> people
if [ -n "$FULL" ]; then
  uv run rebind locate "$RUN"                              # where each passage is set
fi
uv run rebind label "$RUN" --reading a                     # every sentence: warm/cold/neither, tense/calm
uv run rebind label "$RUN" --reading b                     # the same, asked in other words
uv run rebind tokenize "$RUN"                              # book.json
uv run rebind knit --book "$SLUG"                          # pattern.json
uv run rebind check "$RUN"                                 # checks.json
echo "scarf ready: http://localhost:8737/knit/?book=$SLUG"
uv run rebind label "$RUN" --reading a --swapped           # again with every name swapped, for the memory check
uv run rebind check "$RUN"
echo "done: http://localhost:8737/knit/?book=$SLUG"
