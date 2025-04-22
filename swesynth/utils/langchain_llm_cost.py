from langchain_community.callbacks import openai_info

# https://docs.together.ai/docs/serverless-models
# https://api.together.xyz/models
TOGETHER_API_MODEL_COST_PER_1K_TOKENS = {
    "meta-llama/Llama-3.2-3B-Instruct-Turbo": 0.06 / 1000,  # $0.06 per 1M tokens
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": 0.88 / 1000,  # $0.88 per 1M tokens
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": 0.18 / 1000,  # $0.18 per 1M tokens
    "Qwen/Qwen2.5-7B-Instruct-Turbo": 0.30 / 1000,  # $0.30 per 1M tokens
    "Qwen/Qwen2.5-Coder-32B-Instruct": 0.80 / 1000,  # $0.80 per 1M tokens
    "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ": 0.80 / 1000,  # $0.80 per 1M tokens
}

# NOTE: completion = output
SPLIT_PRICE_MODEL_COST_PER_1K_TOKENS = {
    "deepseek-chat": 0.14 / 1000,  # $0.14 per 1M tokens
    "deepseek-chat-completion": 0.28 / 1000,  # $0.28 per 1M tokens
}


def standardize_model_name(
    model_name: str,
    is_completion: bool = False,  # is_output_token
) -> str:
    model_name = model_name.lower()
    if ".ft-" in model_name:
        model_name = model_name.split(".ft-")[0] + "-azure-finetuned"
    if ":ft-" in model_name:
        model_name = model_name.split(":")[0] + "-finetuned-legacy"
    if "ft:" in model_name:
        model_name = model_name.split(":")[1] + "-finetuned"
    if is_completion and (
        model_name.startswith("gpt-4")
        or model_name.startswith("gpt-3.5")
        or model_name.startswith("gpt-35")
        or model_name.startswith("o1-")
        or ("finetuned" in model_name and "legacy" not in model_name)
        or (model_name in SPLIT_PRICE_MODEL_COST_PER_1K_TOKENS and f"{model_name}-completion" in SPLIT_PRICE_MODEL_COST_PER_1K_TOKENS)
    ):
        return model_name + "-completion"
    else:
        return model_name


openai_info.MODEL_COST_PER_1K_TOKENS.update({k.lower(): v for k, v in TOGETHER_API_MODEL_COST_PER_1K_TOKENS.items()})
openai_info.MODEL_COST_PER_1K_TOKENS.update({k.lower(): v for k, v in SPLIT_PRICE_MODEL_COST_PER_1K_TOKENS.items()})
openai_info.standardize_model_name = standardize_model_name
