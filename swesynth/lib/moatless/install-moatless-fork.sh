#!/bin/bash

cd swesynth/lib/moatless
git clone https://github.com/SWE-Gym/Moatless-Agent-Fork
cd Moatless-Agent-Fork
git checkout 816c6a29da1eccbdb984a6d3accbf320e876eb89
git apply -v ../SWE-Synth-patch-moatless.diff

conda create -n swesynth-moatless python=3.12 -y
conda activate swesynth-moatless
pip install -e .
pip install gitpython llama-index-embeddings-huggingface llama-index-embeddings-text-embeddings-inference pytest httpx==0.27.2
pip install -e .
