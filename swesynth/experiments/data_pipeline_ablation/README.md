# Data Pipeline Ablation study

This includes the experiments answering the following research questions RQ5, RQ6, RQ7, RQ8 mentioned in the paper:

- **RQ5**. Impact of component granularity: How do different component granularities affect the trained models' performance?
- **RQ6**. Impact of component selection: How do different component selection strategies affect the trained models' performance?
- **RQ7**. Impact of model size: How does the size of the model used for component rewriting affect the trained models' performance?
- **RQ8**. Ground-truth extraction strategies: How well does the model perform when being trained on reverse patch diff compared to that when being trained on SWE-Synth with rollout?

## Setup for RQ5, RQ6, RQ7, RQ8

After created the synthetic dataset, you need to install llama-factory and moatless as described in [setup instructions](../README.md)

```bash
bash swesynth/lib/llama_factory/install-llama-factory.sh
bash swesynth/lib/moatless/install-moatless-fork.sh
```

## RQ5 + RQ6

Create the synthetic dataset using the following notebook [component-ablation.ipynb](./component-ablation.ipynb)

The generated dataset can be later used for training models with different component granularity and selection strategies using the following command:

```bash
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/component_granularity/ablation_EmptyClassStrategy.yaml
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/component_granularity/ablation_EmptyFunctionStrategy.yaml
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/component_selection/ablation_PriorityAwareMutationStrategy.yaml
```

## RQ7

Create the synthetic dataset using the following command:

```bash
bash swesynth/experiments/data_pipeline_ablation/mutator_model_size/collect.sh
```

The generated dataset can be later used for training models with different sizes using the following command:

```bash
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/mutator_model_size/ablation_05.yaml
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/mutator_model_size/ablation_3B.yaml
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/mutator_model_size/ablation_14B.yaml
```

## **RQ8**

First we need to prepare Gold RAG dataset

```bash
bash swesynth/experiments/data_pipeline_ablation/groundtruth_generation/create-data.sh
```

Then sampling 3 times

```bash
bash swesynth/experiments/data_pipeline_ablation/groundtruth_generation/rejection-sampling-rollout.sh
```

The generated dataset can be later used for training RAG reverse patch diff model and RAG rejection sampling model using the following command:

```bash
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/groundtruth_generation/gold-rollout.yaml
llamafactory-cli train swesynth/experiments/data_pipeline_ablation/groundtruth_generation/reverse.yaml
```
