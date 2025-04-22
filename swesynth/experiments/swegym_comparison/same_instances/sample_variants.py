import pandas as pd
import json
from datasets import load_dataset

if __name__ == "__main__":
    # Load the dataset and select targeted instance IDs
    data = load_dataset("swesynth/SWE-Synth", split="train", columns=["instance_id"])
    targeted_instance_ids: set[str] = set(data.to_pandas().sample(230)["instance_id"].unique())
    assert len(targeted_instance_ids) == 230

    # Load trajectory data
    traj = load_dataset("swesynth/SWE-Synth_Moatless-SFT-Trajectories", split="train").to_pandas()
    assert traj["run_name"].nunique() == 3

    # (
    #     traj
    #     .query('instance_id in @targeted_instance_ids')
    #     .explode('messages')
    #     .to_json('same_instances_comparison_variants3.jsonl.zst', orient='records', lines=True)
    # )

    for cap in [1, 2, 3]:
        (
            traj.query("instance_id in @targeted_instance_ids")
            .groupby("instance_id")
            .head(cap)
            .explode("messages")
            .to_json(f"swesynth-same_instances_comparison_cap{cap}.jsonl.zst", orient="records", lines=True)
        )
