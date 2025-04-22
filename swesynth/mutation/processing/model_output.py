def extract_code(rawLLMGen: str, isOpenSource=False, lang="python") -> str:
    """
    This function extracts generated code from the llm response
    (e.g., removing tik marks, python word, and nat lang text)
    """

    # First, count the number of wrapper ticks
    numTicks = rawLLMGen.count("```")

    # No wrapper
    if numTicks == 0 and lang == "python" and not isOpenSource:
        return rawLLMGen

    if numTicks == 0 and lang == "json" and not isOpenSource:
        return rawLLMGen[rawLLMGen.find("[") : rawLLMGen.rfind("]") + 1]

    # if there is two or more, remove all code after the last one
    if numTicks >= 2:
        parts = rawLLMGen.split("```", 2)  # Split the string at most twice
        assert len(parts) > 2
        rawLLMGen = "```".join(parts[:2])  # Join the first two parts back together with sub

    if lang == "json":
        return rawLLMGen[rawLLMGen.find("[") : rawLLMGen.rfind("]") + 1]

    # Now, get rid of everything before the first one if it is ```python
    wrapper1 = "```" + lang

    wrapper1_idx = rawLLMGen.find(wrapper1)

    # If we find the full wrapper 1 exists
    if wrapper1_idx >= 0:
        rawLLMGen = rawLLMGen[wrapper1_idx + len(wrapper1) :]

    # at this point, just replace all remaining ``` and move on
    rawLLMGen = rawLLMGen.replace("```", "\n")

    # If we are using the open source model, additional pre-processing is needed due to less standard formatting of responses
    if isOpenSource:

        # First, split by new line and remove all lines that don't start in an assert
        all_lines = rawLLMGen.split("\n")

        import_lines = []
        code_lines = []

        for line in all_lines:
            if line.startswith("import") or line.startswith("from"):
                import_lines.append(line)
            if len(code_lines) == 0 and line.startswith("assert"):
                code_lines.append(line)
            elif len(code_lines) > 0 and (line.strip() == "" or line.startswith("#") or line.startswith("'''") or line.startswith("assert")):
                break
            elif len(code_lines) > 0:
                code_lines.append(line)

        if len(code_lines) == 0:
            rawLLMGen = "# NO VALID ASSERT PRODUCED, SO RETURNING FALSE\nassert FALSE"

        else:
            rawLLMGen = "\n".join(import_lines) + "\n" + "\n".join(code_lines)

    return rawLLMGen
