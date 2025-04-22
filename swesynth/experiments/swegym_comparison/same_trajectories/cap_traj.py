import pandas as pd
import json
from datasets import load_dataset

if __name__ == "__main__":
    # load rollout swegym lite trajectories
    train_traj = pd.read_json("SWE-Gym-Lite-logs-shortened-rollout30.jsonl.zst", orient="records", lines=True, compression="zstd")

    traj = (
        train_traj.rename(columns={"exp_name": "run_name"})
        .groupby(["instance_id", "run_name", "model_patch"])
        .agg({"messages": list})
        .reset_index()[["instance_id", "messages", "model_patch", "run_name"]]
    )

    assert traj["run_name"].nunique() == 30

    (traj.sample(1000).explode("messages").to_json(f"swegym-lite-1k-traj.jsonl.zst", orient="records", lines=True))
