import ast
import hashlib
import re

from typing import Optional


def get_function_from_line_number(file_content: str, line_no: int) -> Optional[ast.FunctionDef]:
    """
    Given the content of a Python file and a line number, this function returns the
    `ast.FunctionDef` node that corresponds to the function containing that line.

    :param file_content: The source code of the Python file.
    :param line_no: The line number to search for the corresponding function.
    :return: The ast.FunctionDef node if found, else None.
    """
    tree = ast.parse(file_content)

    # Variable to store the function node found
    function_found = None

    # Traverse through the AST nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Get the function's starting line (node.lineno)
            func_start_line = node.lineno

            # Use the function's body to determine its range
            if node.body:
                func_end_line = max(child.lineno for child in ast.walk(node) if hasattr(child, "lineno"))
            else:
                func_end_line = func_start_line  # If no body, function occupies one line

            # Check if the given line falls within this function's range
            if func_start_line <= line_no <= func_end_line:
                function_found = node
                break

    return function_found


def remove_empty(test_cases: dict[str, list[str]]) -> dict[str, set[str]]:
    output = {}
    for k, v in test_cases.items():
        _v = {x.strip() for x in v}
        _v = {x for x in _v if x}
        if len(_v) > 0:
            output[k] = _v
    return output


def convert_to_normalized_name(testcase: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", testcase)
    hash_of_name = hashlib.md5(name.encode()).hexdigest()[:10]
    name = f"{name[:50]}_{hash_of_name}"
    return name
