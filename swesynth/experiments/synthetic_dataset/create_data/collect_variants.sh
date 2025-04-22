#!/bin/bash

find "./output/" -type f -name "*.jsonl" | \
    tqdm --desc "Processing files" --unit "file" | \
    while read -r file; do echo "Scanning: $file ($(wc -l < "$file") lines)" >&2; cat "$file"; done | \
    zstd -z -q -o SWE-Synth.jsonl.zst

python -m swesynth.scripts.convert_to_swebench_dataset \
    --parquet \
    --file_paths SWE-Synth.jsonl.zst \
    --output_file SWE-Synth.parquet

python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --input-file SWE-Synth.parquet \
    --output-file SWE-Synth-shortened.parquet

python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file SWE-Synth-shortened.parquet \
    --output-file SWE-Synth.txt

shuf SWE-Synth.txt -o SWE-Synth.txt
