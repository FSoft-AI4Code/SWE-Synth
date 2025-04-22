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

eval "$(conda shell.bash hook)"
conda activate swesynth-llama-factory
set -x

if [ -d $merged_checkpoint_path ]; then
    echo "Checkpoint already exists at $merged_checkpoint_path"
else
    llamafactory-cli export export-config.yaml
    sed -i 's/"max_position_embeddings": 32768/"max_position_embeddings": 65536/' $merged_checkpoint_path/config.json
fi

conda activate vllm
vllm serve \
    $merged_checkpoint_path \
    --host 0.0.0.0 --port $vllm_port --served-model-name \
    $run_name \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 65536 &

vllm_serve_pid=$!

trap "kill -2 $vllm_serve_pid; rm -vrf $merged_checkpoint_path; trap - SIGINT" EXIT SIGINT

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

     function moatless_rollout_swebench {
        ulimit -n `ulimit -Hn`
        export API_BASE="http://localhost:$vllm_port"
        N=40
        DATASET="SWE-Bench_Lite-logs.txt"
        # run_name=$run_name
        export model="$run_name"
        export run_id="$run_name"_"$DATASET"
        export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
        export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:15272,http://localhost:15273"
        export dd=/home/user1/evaluation/swebench-moatless
        cd $dd
        LOG_DIR="$dd/tmp/${run_id}/logs"
        export TMPDIR="/dev/shm/user1/${run_id}/"
        conda activate swesynth-moatless
        mkdir -p "$TMPDIR"
        mkdir -p "$LOG_DIR"
        cat /home/user1/data/swebench/SWE-Bench_Lite-logs.txt | parallel --bar -j "$N" --results "$LOG_DIR" '
        echo "Processing INSTANCE_ID: {}"
        cd /home/user1/evaluation/swesynth-moatless-rollout
        python swesynth/lib/moatless/Moatless-Agent-Fork/scripts/single_sampling.py \
        --model "openai/${model}" \
        --temperature 0.0 \
        --dataset SWE-Bench_Lite-logs-shortened.parquet \
        --serve_api_base "${API_BASE}/v1" \
        --eval_name "${run_id}" \
        --eval_dir $dd/eval/ \
        --repo_base_dir "$dd/tmp/${run_id}/repos" \
        --index_store_dir "$dd/index_store_moatless_fork" \
        --split test \
        --instance "{}"
        echo "Finished INSTANCE_ID: {}"
        '
     }

moatless_rollout_swebench
moatless_rollout_swebench

echo "DONE MOATLESS ROLLOUT, BEGIN EVAL"
cd "$dd/eval/$run_id"

conda activate swesynth
python -m swesynth.lib.moatless.utils.merge_jsonl --exp_path .
python -m swesynth.lib.swebench.scripts.run_evaluation \
    --cache_level instance \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --predictions_path ./preds.jsonl \
    --max_workers 48 \
    --split test \
    --run_id $(basename $(pwd))
echo "DONE EVAL"
# python -m swesynth.lib.swebench.scripts.utils.read_eval_results '*.json'

python -m swesynth.scripts.correctness \
    --preds ./preds.jsonl \
    --dataset "princeton-nlp/SWE-bench_Lite" \
    --cache-dir /tmp/swesynth/cache/eval/

)

kill -2 $vllm_serve_pid
wait $vllm_serve_pid

rm -vrf $merged_checkpoint_path
