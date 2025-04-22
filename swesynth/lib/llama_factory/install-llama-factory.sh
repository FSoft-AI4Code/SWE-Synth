#!/bin/bash

cd swesynth/lib/llama_factory
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
git checkout 6f1e4507393b7903cdf68e29d46708290aeb8e9a
git apply -v ../SWE-Synth-patch-llama-factory.diff

conda create --name swesynth-llama-factory -y python=3.11
conda activate swesynth-llama-factory
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -e '.[torch,metrics,deepspeed,liger-kernel,bitsandbytes,vllm,qwen,badam,adam-mini]'
pip install packaging ninja einops xformers trl peft accelerate bitsandbytes wandb
pip install flash-attn
pip install zstandard
