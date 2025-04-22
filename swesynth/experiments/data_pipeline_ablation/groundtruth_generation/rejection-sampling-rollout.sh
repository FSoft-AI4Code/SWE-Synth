#!/bin/bash

CUDA_VISIBLE_DEVICES=0,3 vllm serve \
    /cm/shared/user2/Workspace/swesynth/mutation/models/Qwen2.5-Coder-32B-Instruct-AWQ_128K \
    --host 0.0.0.0 --port 27439 --served-model-name \
    Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \
    Qwen/Qwen2.5-Coder-32B-Instruct \
    models/Qwen2.5-Coder-32B-Instruct-AWQ_128K \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --tensor-parallel-size 2 \
    --max-model-len 65536

while true; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:27439/health | grep -q 200; then
        echo "VLLM server is ready"
        break
    fi
    sleep 1
done

# rollout on train set
LLM_INFERENCE_API_ENDPOINT=localhost:27439 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /cm/archive/user2/swesynth/data/swesynth18/gold-rag-prepared/formatted_dataset \
    --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag-rollout \
    --split train \
    --retries 1 \
    --model_args temperature=0

mkdir -p /home/user1/data/swegym-mutants/reverse-diff/output/attempt2/
LLM_INFERENCE_API_ENDPOINT=localhost:12839 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /home/user1/data/swegym-mutants/reverse-diff/formatted_dataset \
    --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct \
    --output_dir /home/user1/data/swegym-mutants/reverse-diff/output/attempt2/ \
    --split train \
    --retries 5 \
    --model_args temperature=1

mkdir -p /home/user1/data/swegym-mutants/reverse-diff/output/attempt3/
LLM_INFERENCE_API_ENDPOINT=localhost:12839 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /home/user1/data/swegym-mutants/reverse-diff/formatted_dataset \
    --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct \
    --output_dir /home/user1/data/swegym-mutants/reverse-diff/output/attempt3/ \
    --split train \
    --retries 5 \
    --model_args temperature=1

mkdir -p /home/user1/data/swegym-mutants/reverse-diff/output/attempt4/
LLM_INFERENCE_API_ENDPOINT=localhost:12839 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /home/user1/data/swegym-mutants/reverse-diff/formatted_dataset \
    --model_name_or_path Qwen/Qwen2.5-Coder-32B-Instruct \
    --output_dir /home/user1/data/swegym-mutants/reverse-diff/output/attempt4/ \
    --split train \
    --retries 5 \
    --model_args temperature=1

# ------

CUDA_VISIBLE_DEVICES=0,3 vllm serve \
    /cm/shared/user2/Workspace/swesynth/training/swesynth-llama-factory/saves/qwen-sft-14B_gold-rag-mutant-1k-reverse/checkpoint-480-merged \
    --host 0.0.0.0 --port 27439 --served-model-name \
    gold-rag-mutant-1k-reverse-480 \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --tensor-parallel-size 2 \
    --max-model-len 65536
    # --gpu-memory-utilization 0.85

# eval trained reverse on dev
LLM_INFERENCE_API_ENDPOINT=localhost:27439 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /cm/archive/user2/swesynth/data/swesynth18/gold-rag-prepared/formatted_dataset \
    --model_name_or_path gold-rag-mutant-1k-reverse-480 \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag-eval-reverse \
    --retries 1 \
    --split test \
    --model_args temperature=0


# --- test ---

python -m swesynth.lib.swebench.scripts.create_text_dataset \
    --dataset_name_or_path anonymous/SWE-bench_Lite_logs \
    --output_dir /cm/archive/user2/swesynth/data/swebench-lite-logs-verbose-gold-rag/ --prompt_style style-3 \
    --file_source oracle \
    --dump_parquet \
    --clone_from_local \
    --splits test \
    --max_log_length 16000 \
    --tokenizer_name qwen2.5

python -m swesynth.experiments.data_pipeline_ablation.groundtruth_generation.prepare_dataset_for_rag \
    --dataset_path /cm/archive/user2/swesynth/data/swebench-lite-logs-verbose-gold-rag/SWE-bench__style-3__fs-oracle \
    --output_dir /cm/archive/user2/swesynth/data/swebench-lite-logs-verbose-gold-rag/prepared

# eval trained reverse on test

unset https_proxy http_proxy
LLM_INFERENCE_API_ENDPOINT=localhost:27439 python -m swesynth.lib.swebench.scripts.run_api_parallel \
    --dataset_name_or_path /cm/archive/user2/swesynth/data/swebench-lite-logs-verbose-gold-rag/prepared/eval_log_q1_1_formatted_dataset_64000 \
    --model_name_or_path gold-rag-mutant-1k-reverse-480 \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag-eval-reverse \
    --retries 1 \
    --split test \
    --model_args temperature=0


for pred in $(ls *.jsonl); do
    shuf $pred -o $pred
    SWESYNTH_USE_REMAP_IMAGE="true" python -m swesynth.lib.swebench.scripts.run_evaluation \
        --cache_level instance \
        --dataset_name /mnt/data/user1/run3/swegym-mutant-rollout/swesynth18-10-2-2025-shortened.parquet \
        --predictions_path $pred \
        --max_workers 60 \
        --split train \
        --run_id $pred
done
