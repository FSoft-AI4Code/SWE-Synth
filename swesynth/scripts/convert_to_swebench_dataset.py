"""
python -m swesynth.scripts.convert_to_swebench_dataset \
    --file_paths $(ls *.jsonl) \
    --output_file ./output/synthetic_dataset
"""

import argparse
import json
from pathlib import Path

from datasets import Dataset, DatasetDict
from loguru import logger
import pandas as pd
from swebench.harness.constants import SWEbenchInstance
from tqdm import tqdm

from swesynth import RepositorySnapshot
from swesynth.utils import read_jsonl


def split_into_dev_test_set(data: list[SWEbenchInstance]) -> dict[str, list[SWEbenchInstance]]:
    TEST_REPOS: set[str] = {
        "astropy/astropy",
        "django/django",
        "matplotlib/matplotlib",
        "mwaskom/seaborn",
        "pallets/flask",
        "psf/requests",
        "pydata/xarray",
        "pylint-dev/pylint",
        "pytest-dev/pytest",
        "scikit-learn/scikit-learn",
        "sphinx-doc/sphinx",
        "sympy/sympy",
    }

    DEV_REPOS: set[str] = {
        "pvlib/pvlib-python",
        "pydicom/pydicom",
        "sqlfluff/sqlfluff",
        "pylint-dev/astroid",
        "pyvista/pyvista",
        "marshmallow-code/marshmallow",
    }

    dev: list[SWEbenchInstance] = []
    test: list[SWEbenchInstance] = []

    for instance in data:
        if instance["repo"] in TEST_REPOS:
            test.append(instance)
        elif instance["repo"] in DEV_REPOS:
            dev.append(instance)
        else:
            raise ValueError(f"Unknown repo: {instance['repo']}")

    return {"dev": dev, "test": test}


@logger.catch
def main(file_paths: list[str], output_file: str, parquet: bool):
    output_file = Path(output_file)
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    logger.add(f"{output_file}_build_dataset.log", level="INFO")

    output: list[SWEbenchInstance] = []

    logger.info(f"Found {len(file_paths)} files to process")

    # Process each file
    with tqdm(file_paths, desc="Processing files") as pbar:
        for file_path in pbar:
            logger.info(f"Processing file: {file_path}")
            for data in read_jsonl(file_path):
                mutant: RepositorySnapshot = RepositorySnapshot.from_dict(data)
                instance: SWEbenchInstance = mutant.to_swebench_instance()
                instance["swesynth_mutation_info"] = mutant.mutation_info.to_dict()
                output.append(instance)
                pbar.set_postfix({"instances": len(output)})

    logger.info(f"Processed {len(output)} instances")
    # data = split_into_dev_test_set(output)
    # logger.info(f"Split into dev: {len(data['dev'])} and test: {len(data['test'])}")

    # dev_df = pd.DataFrame(data["dev"])
    # test_df = pd.DataFrame(data["test"])

    data_df = pd.DataFrame(output)

    logger.info(f"data_df: {data_df.shape}")

    if parquet:
        data_df.to_parquet(output_file.with_suffix(".parquet"), index=False)
        logger.info(f"Dataset saved in Parquet format to: {output_file}")
        logger.info(
            f"""Usage:
```python
from datasets import load_dataset
dataset = load_dataset("parquet", data_files={{
    'dev': "{output_file.with_suffix(".parquet")}",
}})
```
"""
        )
        return


#     dataset = {}
#     if len(data["dev"]) > 0:
#         dataset["dev"] = Dataset.from_pandas(dev_df)
#     if len(data["test"]) > 0:
#         dataset["test"] = Dataset.from_pandas(test_df)

#     dataset = DatasetDict(dataset)

#     logger.info("Saving dataset to disk")
#     logger.info(f"Dataset: {dataset}")

#     dataset.save_to_disk(output_file)

#     logger.info(f"Dataset saved to: {output_file}")
#     logger.info(f"""Usage:
# ```python
# from datasets import load_from_disk
# dataset = load_from_disk("{output_file}")
# ```
# """)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert data to SWEbench-compatible dataset format.")
    parser.add_argument("--file_paths", nargs="+", required=True, help="Paths to the input JSONL files.")
    parser.add_argument("--output_file", required=True, help="Directory where the output dataset will be saved.")
    parser.add_argument("--parquet", action="store_true", help="Save dataset in Parquet format.")
    args = parser.parse_args()
    main(args.file_paths, args.output_file, args.parquet)
