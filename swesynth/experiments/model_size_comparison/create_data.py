from datasets import load_dataset

if __name__ == "__main__":
    (
        load_dataset("swesynth/SWE-Synth_Moatless-SFT-Trajectories", split="train")
        .to_pandas()
        .sample(1027)
        .explode("messages")
        .to_json("model_size_comparison.jsonl.zst", orient="records", lines=True)
    )
    print("Done")
