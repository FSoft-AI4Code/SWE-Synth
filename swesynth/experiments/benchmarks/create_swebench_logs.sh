#!/bin/bash

USE_SWEBENCH_DJANGO_TEST_DIRECTIVES=true USE_SWEBENCH_SYMPY_TEST_DIRECTIVES=true \
    python -m swesynth.scripts.create_logs.create_swebench_log_trace \
    --dataset "princeton-nlp/SWE-bench_Lite" \
    --output_dir SWE-Bench_Lite-logs

python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --dataset SWE-Bench_Lite-logs \
    --output-file SWE-Bench_Lite-logs-shortened.parquet \
    --split test

python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file SWE-Bench_Lite-logs-shortened.parquet \
    --output-file SWE-Bench_Lite-logs.txt

shuf SWE-Bench_Lite-logs.txt -o SWE-Bench_Lite-logs.txt
