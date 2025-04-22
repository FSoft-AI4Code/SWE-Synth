#!/bin/bash

python -m swesynth.lib.bugsinpy.create_bugsinpy_logs

python -m swesynth.lib.moatless.utils.dump_instance_ids \
    --input-file BugsInPy.parquet \
    --output-file bugsinpy.txt
