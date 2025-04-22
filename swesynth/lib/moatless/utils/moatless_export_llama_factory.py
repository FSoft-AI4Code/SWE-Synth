import argparse
from pathlib import Path
from swesynth.utils import read_jsonl
import pandas as pd
import zstandard as zstd
import json
from tqdm import tqdm

tqdm.pandas()


def export_traj(row, run_path):
    trajs = list((run_path.parent / "prompt_logs" / row["instance_id"]).rglob("*.json"))
    out_traj = []
    for s in trajs:
        so_far_traj = json.loads(s.read_text())
        if so_far_traj["completion"] is None:
            continue
        messages = so_far_traj["messages"]
        messages.extend(so_far_traj["completion"])
        assert len(so_far_traj["completion"]) == 1
        out_traj.append(
            {
                "messages": messages,
                "instance_id": row["instance_id"],
                "exp_name": row["model_name_or_path"],
            }
        )
    return out_traj


def main():
    parser = argparse.ArgumentParser(description="Export trajectory data from JSONL predictions.")
    parser.add_argument("--input-file", required=True, help="Path to the input JSON file.")
    parser.add_argument("--dataset", required=True, help="Dataset name for output file.")
    args = parser.parse_args()

    run_path = Path(args.input_file)
    all_predictions = run_path.parent / "preds.jsonl"

    resolved_ids = json.loads(run_path.read_text())["resolved_ids"]
    resolved_predictions = [p for p in read_jsonl(all_predictions) if p["instance_id"] in resolved_ids]

    df = pd.DataFrame(resolved_predictions)
    df["traj"] = df.progress_apply(lambda row: export_traj(row, run_path), axis=1)

    print(f"Exported {len(df)} success packed trajectories")
    output = df["traj"].explode().tolist()
    print(f"Exported {len(output)} success trajectories")

    output_file = run_path.parent / f"{args.dataset}.jsonl.zst"
    with zstd.open(output_file, "wt") as f:
        for line in output:
            f.write(json.dumps(line) + "\n")

    print(f"Saved output to {output_file}")


if __name__ == "__main__":
    main()
