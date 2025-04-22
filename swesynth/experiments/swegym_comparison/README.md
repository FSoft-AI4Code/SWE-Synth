# Manual data vs synthetic data

This includes the experiments answering the following research questions RQ1, RQ2, RQ3 mentioned in the paper:

- **RQ1**. Model performance comparison on synthetic and manual data: How do the manual and synthetic training data in SWE-Synth influence the performance of models, when the training data is controlled to have either (a) the same total number of variants, or (b) the same total number of trajectories?

- **RQ2**. Synthetic Data Scaling: How does increasing the number of synthetic training instances affect model performance?

- **RQ3**. Human Study: How well can human subjects distinguish SWE-Synth's results from real-world, manually collected bugs?

## Setup

Run `create_swegym_logs.sh` to create the SWE-Gym-logs dataset for the experiments.

```bash
bash swesynth/experiments/swegym_comparison/setup/create_swegym_logs.sh
```

We released the resulting SWE-Gym logs dataset in the following link: [https://huggingface.co/datasets/swesynth/SWE-Gym-logs](https://huggingface.co/datasets/swesynth/SWE-Gym-logs)

After created the dataset, you need to install llama-factory and moatless as described in [setup instructions](../README.md)

```bash
bash swesynth/lib/llama_factory/install-llama-factory.sh
bash swesynth/lib/moatless/install-moatless-fork.sh
```

## **RQ1**

### Same total number of variants

From created SWE-Gym log data, run the following command to rollout trajectories on SWE-Gym Lite logs and then cap the instances:

```bash
bash swesynth/experiments/swegym_comparison/same_instances/rollout_swegym_lite.sh
python -m swesynth.experiments.swegym_comparison.same_instances.cap_instances
```

then run the following command to collect the trajectories from SWE-Synth with the same total number of variants:

```bash
python -m swesynth.experiments.swegym_comparison.same_instances.sample_variants
```

Then modify llama-factory `dataset_info.json` to [this](./same_instances/dataset_info.json), then run the following command to train the models with different capping per instance settings using config files in [./same_instances](./same_instances) folder.

```bash
conda activate swesynth-llama-factory
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-lite-cap1.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-lite-cap2.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-lite-cap3.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-mutant-cap1.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-mutant-cap2.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_instances/swegym-mutant-cap3.yaml
```

### Same total number of trajectories

From created SWE-Gym log data, run the following command to rollout trajectories on SWE-Gym Lite logs and then cap the trajectories:

```bash
bash swesynth/experiments/swegym_comparison/same_trajectories/rollout_swegym_lite.sh
python -m swesynth.experiments.swegym_comparison.same_trajectories.cap_traj
```

then run the following command to collect the trajectories from SWE-Synth with the same total number of trajectories:

```bash
python -m swesynth.experiments.swegym_comparison.same_trajectories.sample_traj
```

Then modify llama-factory `dataset_info.json` to [this](./same_trajectories/dataset_info.json), then run the following command to train the models with different settings using config files in [./same_trajectories](./same_trajectories) folder.

```bash
llamafactory-cli train swesynth/experiments/swegym_comparison/same_trajectories/mutant-1k.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/same_trajectories/swegym-lite-cap30.yaml
```

## **RQ2**

From created SWE-Gym log data, run the following command to rollout and collect trajectories on SWE-Gym Full logs:

```bash
bash swesynth/experiments/swegym_comparison/data_scaling/rollout_swegym_full.sh
```

Follows the similar setup as above to train remaining experiments using config files in [./data_scaling](./data_scaling) folder.

```bash
llamafactory-cli train swesynth/experiments/swegym_comparison/data_scaling/swegym-full-cap1.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/data_scaling/swegym-full-cap2.yaml
llamafactory-cli train swesynth/experiments/swegym_comparison/data_scaling/swegym-lite-cap14.yaml
```

## **RQ3**

Run the following command to sample the synthetic and manual data for the human study:

```bash
python -m swesynth.experiments.swegym_comparison.human_study.random_real_bug
python -m swesynth.experiments.swegym_comparison.human_study.random_synthetic_bug
```

Noted that readers are encouraged to take our survey (RQ3), available in the following link: [https://survey.swesynth.com](https://survey.swesynth.com)

The source code for the human study can be found in [human_study/web](./human_study/web) folder.
