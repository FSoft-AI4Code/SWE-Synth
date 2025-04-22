#!/bin/bash
export SWESYNTH_REPO_DIR=/tmp/swesynth/repo/
export TARGET_DIR=$SWESYNTH_REPO_DIR

# List of repositories
TEST_REPOS=(
    "astropy/astropy"
    "django/django"
    "matplotlib/matplotlib"
    "mwaskom/seaborn"
    "pallets/flask"
    "psf/requests"
    "pydata/xarray"
    "pylint-dev/pylint"
    "pytest-dev/pytest"
    "scikit-learn/scikit-learn"
    "sphinx-doc/sphinx"
    "sympy/sympy"
)
DEV_REPOS=(
    "pvlib/pvlib-python"
    "pydicom/pydicom"
    "sqlfluff/sqlfluff"
    "pylint-dev/astroid"
    "pyvista/pyvista"
    "marshmallow-code/marshmallow"
)

# Combine all repos into one list
ALL_REPOS=("${TEST_REPOS[@]}" "${DEV_REPOS[@]}")

# Function to clone repositories
clone_repo() {
    local repo=$1
    local repo_dir="${TARGET_DIR}/${repo//\//__}"
    echo "Cloning https://github.com/swe-bench/${repo//\//__}.git to $repo_dir"
    git clone "https://github.com/swe-bench/${repo//\//__}.git" "$repo_dir"
}

export -f clone_repo  # Export function so it's available to parallel

# Run git clone commands in parallel
echo "Cloning all repositories in parallel..."
parallel -u clone_repo ::: "${ALL_REPOS[@]}"

SWE_GYM_REPOS=(
    "python/mypy"
    "getmoto/moto"
    "conan-io/conan"
    "modin-project/modin"
    "Project-MONAI/MONAI"
    "iterative/dvc"
    "dask/dask"
    "bokeh/bokeh"
    "mne-tools/mne-python"
    "HypothesisWorks/hypothesis"
    "pydantic/pydantic"
    "pandas-dev/pandas"
    "facebookresearch/hydra"
)

clone_repo_swegym() {
    local repo=$1
    local repo_dir="${TARGET_DIR}/${repo//\//__}"
    echo "Cloning https://github.com/swe-train/${repo//\//__}.git to $repo_dir"
    git clone "https://github.com/swe-train/${repo//\//__}.git" "$repo_dir"
}

export -f clone_repo_swegym  # Export function so it's available to parallel

# Run git clone commands in parallel
echo "Cloning all repositories in parallel..."
parallel -u clone_repo_swegym ::: "${SWE_GYM_REPOS[@]}"

BugsInPy_repo=(
 'ansible/ansible'
 'psf/black'
 'cookiecutter/cookiecutter'
 'tiangolo/fastapi'
 'jakubroztocil/httpie'
 'keras-team/keras'
 'spotify/luigi'
 'matplotlib/matplotlib'
 'pandas-dev/pandas'
 'cool-RR/PySnooper'
 'huge-success/sanic'
 'scrapy/scrapy'
 'explosion/spaCy'
 'nvbn/thefuck'
 'tornadoweb/tornado'
 'tqdm/tqdm'
 'ytdl-org/youtube-dl'
)

clone_repo_BugsInPy() {
    local repo=$1
    local repo_dir="${TARGET_DIR}/${repo//\//__}"
    echo "Cloning https://github.com/$repo.git to $repo_dir"
    if [ -d "$repo_dir" ]; then
        echo "Repo $repo already exists, skipping..."
        return
    fi
    git clone https://github.com/$repo.git "$repo_dir"
}

export -f clone_repo_BugsInPy  # Export function so it's available to parallel

# Run git clone commands in parallel
echo "Cloning all repositories in parallel..."
parallel -u clone_repo_BugsInPy ::: "${BugsInPy_repo[@]}"
