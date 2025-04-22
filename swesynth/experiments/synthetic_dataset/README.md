# Create synthetic dataset

We released the synthetic dataset used in the paper in the following links:

- SWE-Synth (9459 synthetic bugs with 3018 fixes): [https://huggingface.co/datasets/swesynth/SWE-Synth](https://huggingface.co/datasets/swesynth/SWE-Synth)

- SWE-Synth's Moatless trajectories for training SFT (3018 trajectories): [https://huggingface.co/datasets/swesynth/SWE-Synth_Moatless-SFT-Trajectories](https://huggingface.co/datasets/swesynth/SWE-Synth_Moatless-SFT-Trajectories)

Statistics of the synthetic dataset SWE-Synth can be found in the following notebook [statistics/data-statistic.ipynb](/swesynth/experiments/synthetic_dataset/statistics/data-statistic.ipynb).

## Create data

To create the synthetic dataset, run the following command:

```bash
bash swesynth/experiments/synthetic_dataset/create_data/create_variants.sh
bash swesynth/experiments/synthetic_dataset/create_data/collect_variants.sh
```

## Ground truth generation

To rollout trajectories and generate ground truth, first install Moatless

```bash
bash swesynth/lib/moatless/install-moatless-fork.sh
```

then modify the following script with the desired parameters and run it:

```bash
bash swesynth/lib/moatless/clone-repo-as-cache.sh
bash swesynth/experiments/synthetic_dataset/groundtruth_generation/rollout-trajectories.sh
bash swesynth/experiments/synthetic_dataset/groundtruth_generation/collect-trajectories.sh
```
