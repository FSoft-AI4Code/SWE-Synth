# Create benchmarking dataset for evaluation

We released the benchmarking dataset used in the paper in the following links:

- SWE-Bench Lite logs dataset: [https://huggingface.co/datasets/swesynth/SWE-Bench_Lite-logs](https://huggingface.co/datasets/swesynth/SWE-Bench_Lite-logs)

- BugsInPy logs dataset: [https://huggingface.co/datasets/swesynth/BugsInPy-logs](https://huggingface.co/datasets/swesynth/BugsInPy-logs)

## Create SWE-Bench Lite logs dataset

To create the SWE-Bench Lite logs dataset and to prepare the processed data for later use, run the following command:

```bash
bash swesynth/experiments/benchmarks/create_swebench_logs.sh
```

## Create BugsInPy logs dataset

To create the BugsInPy logs dataset and to prepare the processed data for later use, run the following command:

```bash
bash swesynth/experiments/benchmarks/create_bugsinpy_logs.sh
```

## To evaluate model checkpoint on the benchmarking dataset, run the following commands:

```bash
bash swesynth/experiments/benchmarks/evaluation/eval-checkpoint-swebench-lite.sh <checkpoint_path> <exp_name>
bash swesynth/experiments/benchmarks/evaluation/eval-checkpoint-bugsinpy.sh <checkpoint_path> <exp_name>
```
