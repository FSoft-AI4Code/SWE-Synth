#!/bin/bash

# pip install anthropic

python -m swesynth.lib.swebench.scripts.create_text_dataset \
    --dataset_name_or_path /cm/archive/user2/swesynth/data/swesynth18/swesynth18-10-2-2025-shortened.parquet \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag/ --prompt_style style-3 \
    --file_source oracle \
    --dump_parquet \
    --clone_from_local \
    --splits dev \
    --max_log_length 16000 \
    --tokenizer_name qwen2.5

python -m swesynth.experiments.data_pipeline_ablation.groundtruth_generation.prepare_dataset \
    --dataset_path /cm/archive/user2/swesynth/data/swesynth18/gold-rag/SWE-bench__style-3__fs-oracle/dev.parquet \
    --output_dir /cm/archive/user2/swesynth/data/swesynth18/gold-rag-prepared

ln -s ./gold-rag-prepared/formatted_dataset_llama_factory_train.jsonl.zst "/cm/archive/user2/swesynth/data/swesynth18/gold-rag-mutant-1k-reverse.jsonl.zst"

