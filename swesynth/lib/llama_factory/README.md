# SWE-Synth LLaMA Factory

This fork is based on `581392fdd1d7aca39558e817350a90e7392162a8` commit of [hiyouga/LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory.git).

All the changes we made are in the form of a patch file, which can be applied to the original repository. The patch file is located at [swesynth/lib/llama_factory/SWE-Synth-patch-llama-factory.diff](./SWE-Synth-patch-llama-factory.diff).

The changes can be summarized as follows:

1. Add support for reading `.jsonl.zst` file
2. Add LongLORA support for Qwen 2.5 Coder Instruct models

The folder `swesynth/lib/llama_factory/LLaMA-Factory` can be created by doing the following:

```bash
cd swesynth/lib/llama_factory
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
git checkout 581392fdd1d7aca39558e817350a90e7392162a8
git apply -v ../SWE-Synth-patch-llama-factory.diff
```
