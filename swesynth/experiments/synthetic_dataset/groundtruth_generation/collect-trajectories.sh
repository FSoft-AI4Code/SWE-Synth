#!/bin/bash

cd /home/user1/run3/swegym-mutant-rollout/rollout/eval/32B-rollout-temp1-3_SWE-Synth.txt
conda activate swesynth
python -m swesynth.lib.moatless.utils.merge_jsonl --exp_path .
shuf preds.jsonl -o preds.jsonl
SWESYNTH_USE_REMAP_IMAGE="true" python -m swesynth.lib.swebench.scripts.run_evaluation \
    --cache_level instance \
    --dataset_name SWE-Synth-shortened.parquet \
    --predictions_path ./preds.jsonl \
    --max_workers 48 \
    --split train \
    --run_id temp1-3

cd /home/user1/run3/swegym-mutant-rollout/rollout/eval
for dirr in *; do
    python -m swesynth.lib.moatless.utils.moatless_export_llama_factory \
        --input-file /home/user1/run3/swegym-mutant-rollout/rollout/eval/$dirr/$(basename $(ls /home/user1/run3/swegym-mutant-rollout/rollout/eval/$dirr/*.json | grep -v args)) \
        --dataset $dirr
done

zstdcat */*.jsonl.zst | zstd -z -q -o SWE-Synth-shortened-rollout.jsonl.zst