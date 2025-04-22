import json
import os
import traceback
from argparse import ArgumentParser
from pathlib import Path

from langchain_openai import ChatOpenAI
import numpy as np
from datasets import load_dataset, load_from_disk
from swebench.inference import run_api
from tqdm import tqdm
import logging

logger = run_api.logger
logger.setLevel(logging.DEBUG)

run_api.MODEL_LIMITS.update(
    {
        k.lower(): v
        for k, v in {
            "gpt-4o-mini-2024-07-18": 128_000,
        }.items()
    }
)
run_api.MODEL_COST_PER_INPUT.update({k.lower(): v for k, v in {"gpt-4o-mini-2024-07-18": 0.00000001}.items()})  # fake
run_api.MODEL_COST_PER_OUTPUT.update({k.lower(): v for k, v in {"gpt-4o-mini-2024-07-18": 0.00000001}.items()})  # fake

from langchain_together import ChatTogether
from langchain_core.output_parsers import StrOutputParser
from langchain_community.callbacks.manager import get_openai_callback


def langchain_inference(
    test_dataset,
    model_name_or_path,
    output_file,
    existing_ids,
    max_cost,
    model_args,
):
    """
    Runs inference on a dataset using LangChain Together API.

    Args:
    test_dataset (datasets.Dataset): The dataset to run inference on.
    model_name_or_path (str): The name or path of the LangChain model to use.
    output_file (str): The path to the output file.
    existing_ids (set): A set of ids that have already been processed.
    max_cost (float): The maximum cost to spend on inference.
    """
    temperature = model_args.pop("temperature", 0.2)
    top_p = model_args.pop("top_p", 0.95 if temperature > 0 else 1)
    print(f"Using temperature={temperature}, top_p={top_p}")

    if os.environ.get("LLM_INFERENCE_API_ENDPOINT"):
        llm = (
            ChatOpenAI(
                model_name=model_name_or_path,
                base_url=f"http://{os.environ.get('LLM_INFERENCE_API_ENDPOINT', 'localhost:27439')}/v1/",
                api_key="null",
                temperature=temperature,
                top_p=top_p,
                max_retries=100,
            )
            | StrOutputParser()
        )
    else:
        llm = ChatTogether(model=model_name_or_path, temperature=temperature, top_p=top_p) | StrOutputParser()

    total_cost = 0
    print(f"Filtered to {len(test_dataset)} instances")
    with open(output_file, "a+") as f, get_openai_callback() as cost:
        for datum in tqdm(test_dataset, desc=f"Inference for {model_name_or_path}"):
            instance_id = datum["instance_id"]
            if instance_id in existing_ids:
                continue

            output_dict = {"instance_id": instance_id, "model_name_or_path": model_name_or_path}

            if "messages_eval" in datum:
                output_dict["messages"] = datum["messages_eval"]

                assert len(output_dict["messages"]) == 2
                assert output_dict["messages"][0]["role"] == "system"
                system_messages = output_dict["messages"][0]["content"]
                assert output_dict["messages"][1]["role"] == "user"
                user_message = output_dict["messages"][1]["content"]
            elif "text" in datum:
                inputs = datum["text"]
                system_messages = inputs.split("\n", 1)[0]
                user_message = inputs.split("\n", 1)[1]
                output_dict["messages"] = [{"role": "system", "content": system_messages}, {"role": "user", "content": user_message}]
                output_dict["text"] = inputs
            else:
                raise ValueError(f"Invalid datum: {datum}")

            try:
                response = llm.invoke([("system", system_messages), ("user", user_message)])
                completion = response
                # Estimate cost (if available via API, implement here)
                total_cost = cost.total_cost
                print(f"Total Cost: {total_cost}")

                output_dict["full_output"] = completion
                print(f"Output: -----\n{completion}\n-----")
                output_dict["model_patch"] = run_api.extract_diff(completion)

                print(json.dumps(output_dict), file=f, flush=True)

                if max_cost is not None and total_cost >= max_cost:
                    print(f"Reached max cost {max_cost}, exiting")
                    break
            except Exception as e:
                logger.error(e)
                logger.error(f"Error processing instance {instance_id}")
                traceback.print_exc()
                continue


def main(
    dataset_name_or_path,
    split,
    model_name_or_path,
    shard_id,
    num_shards,
    output_dir,
    model_args,
    max_cost,
):
    if shard_id is None and num_shards is not None:
        logger.warning(f"Received num_shards={num_shards} but shard_id is None, ignoring")
    if shard_id is not None and num_shards is None:
        logger.warning(f"Received shard_id={shard_id} but num_shards is None, ignoring")
    model_args = run_api.parse_model_args(model_args)
    model_nickname = model_name_or_path
    if "checkpoint" in Path(model_name_or_path).name:
        model_nickname = Path(model_name_or_path).parent.name
    else:
        model_nickname = Path(model_name_or_path).name
    output_file = f"{model_nickname}__{dataset_name_or_path.split('/')[-1]}__{split}"
    if shard_id is not None and num_shards is not None:
        output_file += f"__shard-{shard_id}__num_shards-{num_shards}"
    output_file = Path(output_dir, output_file + ".jsonl")
    logger.info(f"Will write to {output_file}")
    existing_ids = set()
    if os.path.exists(output_file):
        with open(output_file) as f:
            for line in f:
                data = json.loads(line)
                instance_id = data["instance_id"]
                existing_ids.add(instance_id)
    logger.info(f"Read {len(existing_ids)} already completed ids from {output_file}")
    if Path(dataset_name_or_path).exists():
        dataset = load_from_disk(dataset_name_or_path)
    else:
        dataset = load_dataset(dataset_name_or_path)
    if not split in dataset:
        raise ValueError(f"Invalid split {split} for dataset {dataset_name_or_path}")
    dataset = dataset[split]
    lens = np.array(list(map(len, dataset["text"])))
    dataset = dataset.select(np.argsort(lens))
    if len(existing_ids) > 0:
        dataset = dataset.filter(
            lambda x: x["instance_id"] not in existing_ids,
            desc="Filtering out existing ids",
            load_from_cache_file=False,
        )
    if shard_id is not None and num_shards is not None:
        dataset = dataset.shard(num_shards, shard_id, contiguous=True)
    inference_args = {
        "test_dataset": dataset,
        "model_name_or_path": model_name_or_path,
        "output_file": output_file,
        "model_args": model_args,
        "existing_ids": existing_ids,
        "max_cost": max_cost,
    }
    if model_name_or_path.startswith("claude"):
        run_api.anthropic_inference(**inference_args)
    elif model_name_or_path.startswith("gpt"):
        run_api.openai_inference(**inference_args)
    else:
        langchain_inference(**inference_args)
    logger.info(f"Done!")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset_name_or_path",
        type=str,
        required=True,
        help="HuggingFace dataset name or local path",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split to use",
    )
    parser.add_argument(
        "--model_name_or_path",
        type=str,
        help="Name of API model. Update MODEL* constants in this file to add new models.",
        # choices=sorted(list(run_api.MODEL_LIMITS.keys())),
    )
    parser.add_argument(
        "--shard_id",
        type=int,
        default=None,
        help="Shard id to process. If None, process all shards.",
    )
    parser.add_argument(
        "--num_shards",
        type=int,
        default=None,
        help="Number of shards. If None, process all shards.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        required=True,
        help="Path to the output file.",
    )
    parser.add_argument(
        "--model_args",
        type=str,
        default=None,
        help="List of model arguments separated by commas. (e.g. 'top_p=0.95,temperature=0.70')",
    )
    parser.add_argument(
        "--max_cost",
        type=float,
        default=None,
        help="Maximum cost to spend on inference.",
    )
    args = parser.parse_args()
    main(**vars(args))
