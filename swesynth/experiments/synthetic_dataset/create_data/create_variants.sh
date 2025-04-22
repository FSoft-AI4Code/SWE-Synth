#!/bin/bash

all_repos=(
    "getmoto/moto"
    "conan-io/conan"
    "iterative/dvc"
    "dask/dask"
    "bokeh/bokeh"
    "pydantic/pydantic"
    "facebookresearch/hydra"
)
for repo in "${all_repos[@]}"; do
    echo "python -m swesynth.scripts.create_dataset --repo \"$repo\" --output_dir output"
    python -m swesynth.scripts.create_dataset --repo "$repo" --output_dir output
done
