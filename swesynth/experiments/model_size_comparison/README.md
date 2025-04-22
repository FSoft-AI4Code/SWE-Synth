# Model Size Comparison

This includes the experiments answering the following research question RQ4 mentioned in the paper:

- **RQ4**. Model Performance with Different Model Sizes: How does model performance vary across different model sizes when being fine-tuned on our synthetic training data in SWE-Synth?

## Setup

After created the synthetic dataset, you need to install llama-factory as described in [setup instructions](../README.md)

```bash
bash swesynth/lib/llama_factory/install-llama-factory.sh
```

## Create data for training

Run the following command to create the data for training:

```bash
python -m swesynth.experiments.model_size_comparison.create_data
```

## Train models

To train the models, you first need to add the created data to the llama-factory for training. Modify llama-factory `dataset_info.json` to [this](./dataset_info.json),
then run `conda activate swesynth-llama-factory` before running the following command to train the models with different sizes:

```bash
llamafactory-cli train swesynth/experiments/model_size_comparison/train7B.yaml
llamafactory-cli train swesynth/experiments/model_size_comparison/train14B.yaml
llamafactory-cli train swesynth/experiments/model_size_comparison/train32B.yaml
```
