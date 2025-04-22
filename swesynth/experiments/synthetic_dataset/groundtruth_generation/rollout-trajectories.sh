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
cd /home/user1/run3/swegym-mutant-rollout/rollout
conda activate swesynth-moatless
export API_BASE="http://localhost:27439"
N=230
DATASET="SWE-Synth.txt"
run_name="32B-rollout-temp1-3"

export model=Qwen/Qwen2.5-Coder-32B-Instruct
export run_id="$run_name"_"$DATASET"
export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:15273"
export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
export dd=/home/user1/run3/swegym-mutant-rollout/rollout
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
  --dataset SWE-Synth-shortened.parquet \
  --serve_api_base "${API_BASE}/v1" \
  --eval_name "${run_id}" \
  --eval_dir $dd/eval/ \
  --repo_base_dir "$dd/tmp/${run_id}/repos" \
  --index_store_dir "$dd/index_store_moatless_fork" \
  --split test \
  --instance "{}"
  echo "Finished INSTANCE_ID: {}"
'
