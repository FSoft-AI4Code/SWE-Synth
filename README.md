# SWE-Synth: Synthesizing Verifiable Bug-Fix Data to Enable Large Language Models in Resolving Real-World Bugs

## About

Automated program repair (APR) aims to autonomously fix software bugs, yet its effectiveness is hampered by the lack of diverse, real-world bug datasets essential for model training. Although combining large-scale mining with human effort can yield such datasets, the associated costs limit scalability. To address this, we introduce a novel, scalable synthetic data pipeline that leverages large language models (LLMs) to generate synthetic bugs through targeted LLM-based code rewriting. Our pipeline is also capable of synthesizing valuable intermediate repair steps and enriches the training signal toward correct fixes. Using our method, we create SWE-Synth, a large and contextually rich dataset of bug-fix pairs that are natural, scalable, automated verifiable, and contain intermediate repair steps. Training LLMs on our synthetic dataset yields context-aware repair strategies, that achieve repair accuracy equivalent to those trained on manually curated datasets from GitHub like SWE-Gym while delivering superior scalability with effortless bug synthesis, as demonstrated on popular benchmarks (SWE-Bench and BugsInPy).

Source code and data are available in the following links:

Source code: [https://github.com/FSoft-AI4Code/SWE-Synth](https://github.com/FSoft-AI4Code/SWE-Synth)

Data: [https://huggingface.co/swesynth](https://huggingface.co/swesynth)

Survey link: [https://survey.swesynth.com](https://survey.swesynth.com)

## Setup

### Install

1. Clone the repository

2. Install the dependencies

```bash
conda create --name swesynth -y python=3.12
conda activate swesynth
pip install -e .
```

### Hardware Requirements

- Minimum 10 GB RAM, recommended >= 32 GB RAM
- \> 150GB disk space

### Software Requirements

- Linux OS (tested on Ubuntu 20.04)
- Docker (tested on version 27.5.1)

## Usage

### [Create synthetic dataset](./swesynth/experiments/synthetic_dataset/README.md)

For detailed instructions, please refer to the README in [swesynth/experiments/synthetic_dataset/README.md](./swesynth/experiments/synthetic_dataset/README.md).

We released the synthetic dataset used in the paper in the following links:

- SWE-Synth (9459 synthetic bugs with 3018 fixes): [https://huggingface.co/datasets/swesynth/SWE-Synth](https://huggingface.co/datasets/swesynth/SWE-Synth)

- SWE-Synth's Moatless trajectories for training SFT (3018 trajectories): [https://huggingface.co/datasets/swesynth/SWE-Synth_Moatless-SFT-Trajectories](https://huggingface.co/datasets/swesynth/SWE-Synth_Moatless-SFT-Trajectories)

Statistics of the synthetic dataset SWE-Synth can be found in the following notebook [swesynth/experiments/synthetic_dataset/statistics/data-statistic.ipynb](./swesynth/experiments/synthetic_dataset/statistics/data-statistic.ipynb).

### [Create benchmarking dataset for evaluation](./swesynth/experiments/benchmarks/README.md)

For detailed instructions, please refer to the README in [swesynth/experiments/benchmarks/README.md](./swesynth/experiments/benchmarks/README.md).

We released the benchmarking dataset used in the paper in the following links:

- SWE-Bench Lite logs dataset: [https://huggingface.co/datasets/swesynth/SWE-Bench_Lite-logs](https://huggingface.co/datasets/swesynth/SWE-Bench_Lite-logs)

- BugsInPy logs dataset: [https://huggingface.co/datasets/swesynth/BugsInPy-logs](https://huggingface.co/datasets/swesynth/BugsInPy-logs)

## Reproduce experiments

### [Manual data vs synthetic data](./swesynth/experiments/swegym_comparison/README.md)

For detailed instructions, please refer to the README in [swesynth/experiments/swegym_comparison/README.md](./swesynth/experiments/swegym_comparison/README.md).

This includes the experiments answering the following research questions RQ1, RQ2, RQ3 mentioned in the paper:

- **RQ1**. Model performance comparison on synthetic and manual data: How do the manual and synthetic training data in SWE-Synth influence the performance of models, when the training data is controlled to have either (a) the same total number of variants, or (b) the same total number of trajectories?

- **RQ2**. Synthetic Data Scaling: How does increasing the number of synthetic training instances affect model performance?

- **RQ3**. Human Study: How well can human subjects distinguish SWE-Synth's results from real-world, manually collected bugs?

Noted that readers are encouraged to take our survey (RQ3), available in the following link: [https://survey.swesynth.com](https://survey.swesynth.com)

### [Can SWE-Synth's synthetic data improve models across size?](./swesynth/experiments/model_size_comparison/README.md)

For detailed instructions, please refer to the README in [swesynth/experiments/model_size_comparison/README.md](./swesynth/experiments/model_size_comparison/README.md).

This includes the experiments answering the following research question RQ4 mentioned in the paper:

- **RQ4**. Model Performance with Different Model Sizes: How does model performance vary across different model sizes when being fine-tuned on our synthetic training data in SWE-Synth?

### [In-depth and ablation study of data pipeline](./swesynth/experiments/data_pipeline_ablation/README.md)

For detailed instructions, please refer to the README in [swesynth/experiments/data_pipeline_ablation/README.md](./swesynth/experiments/data_pipeline_ablation/README.md).

This includes the experiments answering the following research questions RQ5, RQ6, RQ7, RQ8 mentioned in the paper:

- **RQ5**. Impact of component granularity: How do different component granularities affect the trained models' performance?
- **RQ6**. Impact of component selection: How do different component selection strategies affect the trained models' performance?
- **RQ7**. Impact of model size: How does the size of the model used for component rewriting affect the trained models' performance?
- **RQ8**. Ground-truth extraction strategies: How well does the model perform when being trained on reverse patch diff compared to that when being trained on SWE-Synth with rollout?
