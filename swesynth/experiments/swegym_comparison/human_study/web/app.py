import json
import subprocess
import os
from anthropic import Anthropic
from tqdm import tqdm

# def clone_and_checkout(repo_name, commit_hash):
#     # Convert repo name from format like 'facebookresearch_hydra' to 'facebookresearch/hydra'
#     repo_parts = repo_name.split('_')
#     repo_path = f"{repo_parts[0]}/{repo_parts[1]}"

#     # Create directory if it doesn't exist
#     if not os.path.exists('repos'):
#         os.makedirs('repos')

#     # Change to repos directory
#     os.chdir('repos')

#     # Clone the repo if it doesn't exist
#     if not os.path.exists(repo_parts[1]):
#         subprocess.run(['git', 'clone', f'https://github.com/{repo_path}.git', repo_parts[1] + '_' + commit_hash])

#     # Change into repo directory
#     os.chdir(repo_parts[1] + '_' + commit_hash)

#     # Checkout the specific commit
#     subprocess.run(['git', 'fetch'])
#     subprocess.run(['git', 'checkout', commit_hash])

#     # Change back to original directory
#     os.chdir('../..')

"""The application uses two JSONL 
Each line in these files represents a single bug with the following format:

```json
{"instance_id": "unique_id", "model_patch": "code_with_bug", "problem_statement": "description_of_the_bug"}
```
"""


def generate_issue_description(model_patch, problem_statement):
    """
    Generate a GitHub issue description from a bug's diff and error trace using Claude

    Args:
        model_patch (str): Git diff showing the bug fix
        problem_statement (str): Error trace/log of the bug

    Returns:
        str: Natural language description of the bug as a GitHub issue
    """
    anthropic = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are an experienced developer writing a GitHub issue to describe a bug.
    
The bug has the following git diff (- is buggy code, + is fix):
{model_patch}

The error trace/log is:
{problem_statement}

Write a clear, professional GitHub issue description that:
1. Summarizes the bug concisely in the title
2. Describes the problem and its impact
3. Includes relevant technical details from the diff and error
4. Is written in a helpful, constructive tone
5. No need to describe the fix, just the bug only

Format as:
Title: <issue title>
Description: <description>
"""

    message = anthropic.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=64000,
        system="You are an experienced software developer writing clear, professional GitHub issues.",
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# Process fake bugs
with open("frontend/public/data/rq8_all_fake_bug_sample200.jsonl", "r") as f:
    for line in tqdm(f):
        data = json.loads(line)
        # truncate to 10000 characters
        data["problem_statement"] = data["problem_statement"][:8000]
        issue_text = generate_issue_description(data["model_patch"], data["problem_statement"])
        # Add issue text to data or process as needed
        data["issue_description"] = issue_text
        # save to file
        with open("frontend/public/data/rq8_all_fake_bug_sample200_issues.jsonl", "a") as f:
            f.write(json.dumps(data) + "\n")

# Process real bugs
with open("frontend/public/data/rq8_all_real_bug_sample200.jsonl", "r") as f:
    for line in tqdm(f):
        data = json.loads(line)
        issue_text = generate_issue_description(data["model_patch"], data["problem_statement"])
        # Add issue text to data or process as needed
        data["issue_description"] = issue_text
        # save to file
        with open("frontend/public/data/rq8_all_real_bug_sample200_issues.jsonl", "a") as f:
            f.write(json.dumps(data) + "\n")
