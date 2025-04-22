#!/bin/bash

docker run --gpus device=6 -p 0.0.0.0:15273:80 \
    -v $PWD/data:/data --pull always \
    ghcr.io/huggingface/text-embeddings-inference:1.6 \
    --model-id jinaai/jina-embeddings-v2-base-code \
    --max-client-batch-size 1024 &

CUDA_VISIBLE_DEVICES="" python -m swesynth.scripts.misc.yarn \
    --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
    --output_dir ./output/models/Qwen2.5-Coder-32B-Instruct-AWQ_128K

CUDA_VISIBLE_DEVICES=0,1 vllm serve \
    ./output/models/Qwen2.5-Coder-32B-Instruct-AWQ_128K \
    --host 0.0.0.0 --port 27439 --served-model-name \
    Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
    Qwen/Qwen2.5-Coder-32B-Instruct \
    models/Qwen2.5-Coder-32B-Instruct-AWQ_128K \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --tensor-parallel-size 2 \
    --max-model-len 65536 &

export current_dir=$(pwd)

cd /home/user1/run3/swegym-full-rollout/rollout
conda activate swesynth-moatless
export API_BASE="http://localhost:27439"
N=230
DATASET="SWE-Gym-logs.txt"
run_name="swegym-log-full-reproduce-temp0"

export model=Qwen/Qwen2.5-Coder-32B-Instruct
export run_id="$run_name"_"$DATASET"
export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:15273"
export dd=/home/user1/run3/swegym-full-rollout/rollout
export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
LOG_DIR="$dd/tmp/${run_id}/logs"
export TMPDIR="/dev/shm/user1/${run_id}/"
mkdir -p "$TMPDIR"
mkdir -p "$LOG_DIR"
cat "${DATASET}" | parallel --bar -j "$N" --results "$LOG_DIR" '
echo "Processing INSTANCE_ID: {}"
cd ${current_dir}
python swesynth/lib/moatless/Moatless-Agent-Fork/scripts/single_sampling.py \
--model "openai/${model}" \
--temperature 0.0 \
--dataset SWE-Gym-logs-shortened.parquet \
--serve_api_base "${API_BASE}/v1" \
--eval_name "${run_id}" \
--eval_dir $dd/eval/ \
--repo_base_dir "$dd/tmp/${run_id}/repos" \
--index_store_dir "$dd/index_store_moatless_fork" \
--split test \
--instance "{}"
echo "Finished INSTANCE_ID: {}"
'

for i in 1; do
    cd /home/user1/run3/swegym-full-rollout/rollout
    conda activate swesynth-moatless
    export API_BASE="http://localhost:27439"
    N=230
    DATASET="SWE-Gym-logs.txt"
    run_name="swegym-log-full-reproduce-temp1-$i"

    export model=Qwen/Qwen2.5-Coder-32B-Instruct
    export run_id="$run_name"_"$DATASET"
    export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:15273"
    export dd=/home/user1/run3/swegym-full-rollout/rollout
    export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
    LOG_DIR="$dd/tmp/${run_id}/logs"
    export TMPDIR="/dev/shm/user1/${run_id}/"
    mkdir -p "$TMPDIR"
    mkdir -p "$LOG_DIR"
    cat "${DATASET}" | parallel --bar -j "$N" --results "$LOG_DIR" '
    echo "Processing INSTANCE_ID: {}"
    cd ${current_dir}
    python swesynth/lib/moatless/Moatless-Agent-Fork/scripts/single_sampling.py \
    --model "openai/${model}" \
    --temperature 1.0 \
    --dataset SWE-Gym-logs-shortened.parquet \
    --serve_api_base "${API_BASE}/v1" \
    --eval_name "${run_id}" \
    --eval_dir $dd/eval/ \
    --repo_base_dir "$dd/tmp/${run_id}/repos" \
    --index_store_dir "$dd/index_store_moatless_fork" \
    --split test \
    --instance "{}"
    echo "Finished INSTANCE_ID: {}"
    '
done

cd /home/user1/run3/swegym-full-rollout/rollout
conda activate swesynth

cd /home/user1/run3/swegym-full-rollout/rollout
if [ ! -d "swegym-log-full-reproduce-temp0_swegym-log-full.txt" ]; then
    echo "swegym-log-full-reproduce-temp0_swegym-log-full.txt does not exist"
    continue
fi
cd /home/user1/run3/swegym-full-rollout/rollout/swegym-log-full-reproduce-temp0_swegym-log-full.txt
python -m swesynth.lib.moatless.utils.merge_jsonl --exp_path .
shuf preds.jsonl -o preds.jsonl
python -m swesynth.lib.swebench.scripts.run_evaluation \
    --cache_level instance \
    --dataset_name SWE-Gym-logs-shortened.parquet \
    --predictions_path ./preds.jsonl \
    --max_workers 48 \
    --split train \
    --run_id swegym-log-full-reproduce-temp0

for i in 1; do
    cd /home/user1/run3/swegym-full-rollout/rollout
    if [ ! -d "swegym-log-full-reproduce-temp1-${i}_swegym-log-full.txt" ]; then
        echo "swegym-log-full-reproduce-temp1-${i}_swegym-log-full.txt does not exist"
        continue
    fi
    cd /home/user1/run3/swegym-full-rollout/rollout/swegym-log-full-reproduce-temp1-"$i"_swegym-log-full.txt
    python -m swesynth.lib.moatless.utils.merge_jsonl --exp_path .
    shuf preds.jsonl -o preds.jsonl
    mkdir logs && cd logs && cp ../../swegym-log-full-reproduce-temp0_swegym-log-full.txt/logs/repo_version_mapping.json.gz . && cd ..
    python -m swesynth.lib.swebench.scripts.run_evaluation \
        --cache_level instance \
        --dataset_name SWE-Gym-logs-shortened.parquet \
        --predictions_path ./preds.jsonl \
        --max_workers 48 \
        --split train \
        --run_id swegym-log-full-reproduce-temp1-"$i"
done

cd /home/user1/run3/swegym-full-rollout/rollout/eval
for dirr in *; do
    file=$(basename $(ls /home/user1/run3/swegym-full-rollout/rollout/eval/$dirr/*.json | grep -v args))
    if ! [ -f "/home/user1/run3/swegym-full-rollout/rollout/eval/$dirr/$file" ]; then
        echo "/home/user1/run3/swegym-full-rollout/rollout/eval/$dirr/$file does not exist"
        continue
    fi
    python -m swesynth.lib.moatless.utils.moatless_export_llama_factory \
        --input-file /home/user1/run3/swegym-full-rollout/rollout/eval/$dirr/$file \
        --dataset $dirr
done

zstdcat */*.jsonl.zst | zstd -z -q -o SWE-Gym-full-logs-shortened-rollout2.jsonl.zst
