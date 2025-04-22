#!/bin/bash

python -m swesynth.scripts.create_logs.create_swegym_log_trace_multiprocessing \
    --dataset SWE-Gym/SWE-Gym-Lite \
    --output_dir SWE-Gym-Lite-logs \
    --num_workers 24

python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --dataset SWE-Gym-Lite-logs \
    --output-file SWE-Gym-Lite-logs-shortened.parquet \
    --split test

python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file SWE-Gym-Lite-logs-shortened.parquet \
    --output-file SWE-Gym-Lite-logs.txt

shuf SWE-Gym-Lite-logs.txt -o SWE-Gym-Lite-logs.txt

python -m swesynth.scripts.create_logs.create_swegym_log_trace_multiprocessing \
    --dataset SWE-Gym/SWE-Gym \
    --output_dir SWE-Gym-logs \
    --num_workers 24

python -m swesynth.lib.moatless.utils.prepare_for_moatless \
    --dataset SWE-Gym-logs \
    --output-file SWE-Gym-logs-shortened.parquet \
    --split test

python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file SWE-Gym-logs-shortened.parquet \
    --output-file SWE-Gym-logs.txt

shuf SWE-Gym-logs.txt -o SWE-Gym-logs.txt
