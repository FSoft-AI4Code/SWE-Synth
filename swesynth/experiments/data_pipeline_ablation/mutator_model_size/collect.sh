#!/bin/bash

export current_dir=$(pwd)

for m in 3B 0.5B 14B ; do

    find "./output/" -type f -name "*.jsonl" | \
        tqdm --desc "Processing files" --unit "file" | \
        while read -r file; do echo "Scanning: $file ($(wc -l < "$file") lines)" >&2; cat "$file"; done | \
        zstd -z -q -o "$m"-mutation.jsonl.zst

    # 1
    python -m swesynth.scripts.convert_to_swebench_dataset \
        --parquet \
        --file_paths "$m"-mutation.jsonl.zst \
        --output_file "$m"-mutation.parquet

    python -m swesynth.lib.moatless.utils.prepare_for_moatless \
        --input-file "$m"-mutation.parquet \
        --output-file "$m"-mutation-shortened.parquet

    python -m swesynth.lib.moatless.utils.dump_instance_ids \
        --input-file "$m"-mutation-shortened.parquet \
        --output-file "$m"-mutation.txt
    shuf "$m"-mutation.txt -o "$m"-mutation.txt


    export m=$m
    ulimit -n `ulimit -Hn`
    export API_BASE="http://localhost:27439"
    N=80
    DATASET="$m"-mutation.txt
    run_name="$m"-rollout-temp0
    export model=Qwen/Qwen2.5-Coder-32B-Instruct
    export run_id="$run_name"_"$DATASET"
    export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
    export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:7751,http://localhost:7752"
    export dd=/home/clouduser/mutation/ablation/"$m"/rollout
    mkdir -p "$dd"
    cd $dd
    LOG_DIR="$dd/tmp/${run_id}/logs"
    export TMPDIR="/dev/shm/user1/${run_id}/"
    conda activate swesynth-moatless
    mkdir -p "$TMPDIR"
    mkdir -p "$LOG_DIR"
    cat /home/clouduser/mutation/ablation/"$m"/$DATASET | parallel --bar -j "$N" --results "$LOG_DIR" '
        echo "Processing INSTANCE_ID: {}"
        cd ${current_dir}
        python swesynth/lib/moatless/Moatless-Agent-Fork/scripts/single_sampling.py \
        --model "openai/${model}" \
        --temperature 0.0 \
        --dataset /home/clouduser/mutation/ablation/${m}/${m}-mutation-shortened.parquet \
        --serve_api_base "${API_BASE}/v1" \
        --eval_name "${run_id}" \
        --eval_dir $dd/eval/ \
        --repo_base_dir "$dd/tmp/${run_id}/repos" \
        --index_store_dir "$dd/index_store_moatless_fork" \
        --split test \
        --instance "{}"
        echo "Finished INSTANCE_ID: {}"
    '

    ulimit -n `ulimit -Hn`
    export API_BASE="http://localhost:27439"
    N=80
    DATASET="$m"-mutation.txt
    run_name="$m"-rollout-temp1
    export model=Qwen/Qwen2.5-Coder-32B-Instruct
    export run_id="$run_name"_"$DATASET"
    export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
    export SWESYNTH_MOATLESS_EMBEDDING_ENDPOINT="http://localhost:7751,http://localhost:7752"
    export dd=/home/clouduser/mutation/ablation/"$m"/rollout
    mkdir -p "$dd"
    cd $dd
    LOG_DIR="$dd/tmp/${run_id}/logs"
    export TMPDIR="/dev/shm/user1/${run_id}/"
    conda activate swesynth-moatless
    mkdir -p "$TMPDIR"
    mkdir -p "$LOG_DIR"
    cat /home/clouduser/mutation/ablation/"$m"/$DATASET | parallel --bar -j "$N" --results "$LOG_DIR" '
        echo "Processing INSTANCE_ID: {}"
        cd ${current_dir}
        python swesynth/lib/moatless/Moatless-Agent-Fork/scripts/single_sampling.py \
        --model "openai/${model}" \
        --temperature 1.0 \
        --dataset /home/clouduser/mutation/ablation/${m}/${m}-mutation-shortened.parquet \
        --serve_api_base "${API_BASE}/v1" \
        --eval_name "${run_id}" \
        --eval_dir $dd/eval/ \
        --repo_base_dir "$dd/tmp/${run_id}/repos" \
        --index_store_dir "$dd/index_store_moatless_fork" \
        --split test \
        --instance "{}"
        echo "Finished INSTANCE_ID: {}"
    '

    conda activate swesynth
    python -m swesynth.lib.moatless.utils.merge_jsonl --exp_path .
    python -m swesynth.lib.swebench.scripts.run_evaluation \
        --cache_level instance \
        --dataset_name /home/clouduser/mutation/ablation/${m}/${m}-mutation-shortened.parquet \
        --predictions_path ./preds.jsonl \
        --max_workers 48 \
        --split test \
        --run_id $(basename $(pwd))

    python -m swesynth.lib.moatless.utils.moatless_export_llama_factory \
        --input-file $(ls *.json | grep -v args) \
        --dataset $(basename $(pwd))

    zstdcat */*.jsonl.zst | zstd -z -q -o ${m}-ablation-01.jsonl.zst
done 


