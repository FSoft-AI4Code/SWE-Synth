import pandas as pd
import json
from datasets import load_dataset

if __name__ == "__main__":
    traj = load_dataset("swesynth/SWE-Synth_Moatless-SFT-Trajectories", split="train").to_pandas()

    (
        traj.query('run_name == "32B-rollout-temp0"')
        .sample(1000)
        .explode("messages")
        .to_json(f"swesynth-1k-traj.jsonl.zst", orient="records", lines=True)
    )
