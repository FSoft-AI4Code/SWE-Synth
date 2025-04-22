#!/bin/bash
# bash eval-checkpoint.sh /path/to/checkpoint run_name
set -e

if [ -z "$CUDA_VISIBLE_DEVICES" ]; then
    export CUDA_VISIBLE_DEVICES=1
fi
if [ -z "$vllm_port" ]; then
    vllm_port=12822
fi

llm_checkpoint_path=$1
run_name=$2
current_dir=$(pwd)

full_llm_checkpoint_path=$(realpath $llm_checkpoint_path)
merged_checkpoint_path=$full_llm_checkpoint_path-merged

# cat <<EOF
cat <<EOF > export-config.yaml
model_name_or_path: Qwen/Qwen2.5-Coder-14B-Instruct
adapter_name_or_path: $full_llm_checkpoint_path
template: qwen
finetuning_type: lora
export_dir: $merged_checkpoint_path
export_size: 5
export_device: cuda
export_legacy_format: false
EOF

# eval "$(conda shell.bash hook)"
export HF_HOME=/cm/archive/user2/.cache/huggingface
source /cm/shared/user2/miniconda3/bin/activate base
conda activate /cm/shared/user2/.miniconda3/envs/swesynth
conda activate swesynth-llama-factory
set -x

if [ -d $merged_checkpoint_path ]; then
    echo "Checkpoint already exists at $merged_checkpoint_path"
else
    llamafactory-cli export export-config.yaml
    sed -i 's/"max_position_embeddings": 32768/"max_position_embeddings": 65536/' $merged_checkpoint_path/config.json
fi

# conda activate vllm
conda activate /cm/shared/user2/.miniconda3/envs/vllm
vllm serve \
    $merged_checkpoint_path \
    --host 0.0.0.0 --port $vllm_port --served-model-name \
    $run_name \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.6 \
    --max-model-len 65536 &

vllm_serve_pid=$!

# trap "kill -2 $vllm_serve_pid; rm -vrf $merged_checkpoint_path; trap - SIGINT" EXIT SIGINT
trap "kill -2 $vllm_serve_pid; trap - SIGINT" EXIT SIGINT

# wait until checkhealth returns 200
while true; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$vllm_port/health | grep -q 200; then
        echo "VLLM server is ready"
        break
    fi
    sleep 1
done

(
    trap - SIGINT

# export LLM_INFERENCE_API_ENDPOINT="http://localhost:$vllm_port"

LLM_INFERENCE_API_ENDPOINT=http://localhost:$vllm_port python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /cm/archive/user2/swesynth/data/swebench-lite-logs-verbose-gold-rag/prepared/eval_log_q1_1_formatted_dataset_64000 \
    --model_name_or_path $run_name \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag-eval-reverse \
    --retries 1 \
    --split test \
    --model_args temperature=0

)

kill -2 $vllm_serve_pid
wait $vllm_serve_pid

# rm -vrf $merged_checkpoint_path
