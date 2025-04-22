# Experiments

- [Create synthetic dataset](./synthetic_dataset/README.md)
- [Create benchmarking dataset for evaluation](./benchmarks/README.md)
- [Manual data vs synthetic data](./swegym_comparison/README.md)
- [Model size comparison](./model_size_comparison/README.md)
- [Data pipeline ablation](./data_pipeline_ablation/README.md)

## Setup for rollout trajectories using Moatless

For experiments require rollout trajectories using Moatless, you need to install Moatless as follows:

```bash
bash swesynth/lib/moatless/install-moatless-fork.sh
```

then run `conda activate swesynth-moatless` before generating rollout trajectories.

## Setup for training models

For experiments require training models, you need to install LLaMA Factory as follows:

```bash
bash swesynth/lib/llama_factory/install-llama-factory.sh
```

then run `conda activate swesynth-llama-factory` before training models using `llamafactory-cli`.
