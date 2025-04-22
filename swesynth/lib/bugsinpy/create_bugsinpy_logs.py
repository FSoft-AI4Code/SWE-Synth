from pathlib import Path
import pandas as pd
import os
import re
import git
from transformers import AutoTokenizer

# Load the tokenizer
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-32B-Instruct")


def shorten_log(problem_statement: str, max_tokens: int = 16000) -> str:
    """Shortens the problem statement if it exceeds max_tokens."""
    tokens = tokenizer.encode(problem_statement, add_special_tokens=False)
    if len(tokens) > max_tokens:
        truncated_log = tokenizer.decode(tokens[:max_tokens], skip_special_tokens=True)
        return truncated_log + "\n[log truncated]"
    return problem_statement


if __name__ == "__main__":
    path = Path("BugsInPy/projects/")

    # Clone the repository if not already present
    repo_url = "https://github.com/reproducing-research-projects/BugsInPy"
    if not path.parent.exists():
        git.Repo.clone_from(repo_url, path.parent)

    all_projects = [p for p in os.listdir(path) if not p.endswith(".csv")]

    data = []
    project_info = {}

    for project in all_projects:
        bugs = path / project / "bugs"
        _project_info = (path / project / "project.info").read_text()

        url = re.search(r'github_url="(.+?)"', _project_info).group(1).rstrip("/")
        project_info[project] = url

        for bug in bugs.iterdir():
            bug_id = bug.name
            bug_info = (bug / "bug.info").read_text()

            data.append(
                {
                    "project": project,
                    "bug_id": bug_id,
                    "patch": (bug / "bug_patch.txt").read_text(),
                    "test_patch": (bug / "bug_buggy.diff").read_text(),
                    "buggy_log": (bug / "bug_buggy.txt").read_text(),
                    "fixed_log": (bug / "bug_fixed.txt").read_text(),
                    "bug_info": bug_info,
                    "run_test": (bug / "run_test.sh").read_text(),
                }
            )

    data = pd.DataFrame(data)
    raw_df = data.assign(url=data["project"].map(project_info))

    df = raw_df.assign(
        repo=lambda x: x["url"].str.split("/").str[-2:].str.join("/"),
        instance_id=lambda x: x["repo"].str.replace("/", "__") + "-" + x["bug_id"],
        problem_statement=lambda x: x["buggy_log"].str.split("\n").str[3:].str.join("\n").str.strip(),
        base_commit=lambda x: x["bug_info"].str.extract(r'buggy_commit_id="(.+?)"').squeeze(),
        test_file=lambda x: x["bug_info"].str.extract(r'test_file="(.+?)"').squeeze(),
    )[["instance_id", "repo", "patch", "test_patch", "problem_statement", "run_test", "base_commit", "test_file"]]

    df.to_parquet("BugsInPy.parquet")
    df["problem_statement"] = df["problem_statement"].apply(shorten_log)
    df.to_parquet("BugsInPy_shortened.parquet")
    df.repo.unique().tolist()

    gold_prediction = (
        df.assign(model_name_or_path="gold")
        .rename(columns={"patch": "model_patch"})[["instance_id", "model_name_or_path", "model_patch"]]
        .to_json("bugsinpy_gold.jsonl", orient="records", lines=True)
    )

    print(df.sample(1).iloc[0]["problem_statement"])
    print(raw_df["project"].unique())
