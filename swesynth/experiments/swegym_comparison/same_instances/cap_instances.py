import pandas as pd
import json
from datasets import load_dataset

if __name__ == "__main__":
    # load rollout swegym lite trajectories
    train_traj = pd.read_json("SWE-Gym-Lite-logs-shortened-rollout3.jsonl.zst", orient="records", lines=True, compression="zstd")

    traj = (
        train_traj.rename(columns={"exp_name": "run_name"})
        .groupby(["instance_id", "run_name", "model_patch"])
        .agg({"messages": list})
        .reset_index()[["instance_id", "messages", "model_patch", "run_name"]]
    )

    assert traj["run_name"].nunique() == 3

    for cap in [1, 2, 3]:
        (
            traj.groupby("instance_id")
            .head(cap)
            .explode("messages")
            .to_json(f"swegym-lite-same_instances_comparison_cap{cap}.jsonl.zst", orient="records", lines=True)
        )
