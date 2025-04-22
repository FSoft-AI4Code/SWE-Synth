import ast
from swebench.harness.utils import extract_minimal_patch
from swebench.harness.constants import NON_TEST_EXTS
from ast import AsyncFunctionDef, ClassDef, Constant, Expr, FunctionDef, Module, Str
import re
from typing import Iterable

from loguru import logger
import unidiff


def _get_docstring_node(node):
    """
    Return the docstring for the given node or None if no docstring can
    be found.  If the node provided does not have docstrings a TypeError
    will be raised.

    If *clean* is `True`, all tabs are expanded to spaces and any whitespace
    that can be uniformly removed from the second line onwards is removed.
    """
    if not isinstance(node, (AsyncFunctionDef, FunctionDef, ClassDef, Module)):
        raise TypeError("%r can't have docstrings" % node.__class__.__name__)
    if not (node.body and isinstance(node.body[0], Expr)):
        return None
    _node = node.body[0].value
    if isinstance(_node, Str):
        return node.body[0]
    elif isinstance(_node, Constant) and isinstance(_node.value, str):
        return node.body[0]
    else:
        return None


def get_start_location_of_function_body(function: FunctionDef) -> int:
    """
    Get the start location of the function body.
    """
    docstring_node = _get_docstring_node(function)
    if docstring_node is not None:
        return docstring_node.end_lineno + 1
    else:
        return function.body[0].lineno


def get_function_signature(
    file_content: str,
    function: ast.FunctionDef,
) -> str:
    start_lineno = function.lineno

    if len(function.decorator_list) > 0:
        # handle decorators
        start_lineno = function.decorator_list[0].lineno

    start_lineno -= 1

    end_lineno = function.end_lineno
    lines = file_content.splitlines()[start_lineno:end_lineno]
    return "\n".join(lines)


def extract_function_body(file_content: str, node: ast.FunctionDef) -> str:
    start_of_original_function_body_after_docstring: int = get_start_location_of_function_body(node)
    end_of_original_function_body: int = node.end_lineno
    output = "\n".join(file_content.splitlines()[start_of_original_function_body_after_docstring - 1 : end_of_original_function_body])
    return output


def get_all_functions(file_content: str) -> Iterable[FunctionDef]:
    try:
        tree = ast.parse(file_content)
    except Exception:
        logger.error(f"Failed to parse the file content:\n====\n{file_content}\n====\n")
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            yield node


def get_all_classes(file_content: str) -> Iterable[ClassDef]:
    try:
        tree = ast.parse(file_content)
    except Exception:
        logger.error(f"Failed to parse the file content:\n====\n{file_content}\n====\n")
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def get_function_from_line_number(file_content: str, line_no: int) -> ast.FunctionDef | None:
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


def get_class_from_line_number(file_content: str, line_no: int) -> ast.ClassDef | None:
    """
    Given the content of a Python file and a line number, this function returns the
    `ast.ClassDef` node that corresponds to the class containing that line.

    :param file_content: The source code of the Python file.
    :param line_no: The line number to search for the corresponding class.
    :return: The ast.ClassDef node if found, else None.
    """
    tree = ast.parse(file_content)

    # Variable to store the class node found
    class_found = None

    # Traverse through the AST nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Get the class's starting line (node.lineno)
            class_start_line = node.lineno

            # Use the class's body to determine its range
            if node.body:
                class_end_line = max(child.lineno for child in ast.walk(node) if hasattr(child, "lineno"))
            else:
                class_end_line = class_start_line  # If no body, class occupies one line

            # Check if the given line falls within this class's range
            if class_start_line <= line_no <= class_end_line:
                class_found = node
                break

    return class_found


def get_line_number_from_patch(patch: str) -> int:
    """
    Given a patch, this function returns the line number that corresponds to the
    mutation.

    :param patch: The patch that corresponds to the mutation.
    :return: The line number if found, else None.
    """
    match = re.search(r"@@\s-\d+,\d+\s\+(\d+),\d+", patch)
    if not match:
        raise ValueError("Could not extract line number from patch")

    # The line number is captured in the first group (the new line number in the patch)
    return int(match.group(1))


def get_changed_files_from_diff(diff: str) -> set[str]:
    source_files = {patch_file.path for patch_file in unidiff.PatchSet(diff)}
    return source_files


def get_changed_code_files_from_minimized_diff(diff: str) -> set[str]:
    diff_pat = r"--- a/(.*)"
    directives = re.findall(diff_pat, diff)
    directives = [d for d in directives if not any(d.endswith(ext) for ext in NON_TEST_EXTS)]
    return set(directives)


def get_mutated_object_from_simple_diff(file_content: str, diff: str) -> ast.FunctionDef | ast.ClassDef | None:
    """
    Given the content of a Python file and a diff, this function returns the
    `ast.FunctionDef` or `ast.ClassDef` node that corresponds to the function or class
    that has been mutated.

    :param file_content: The source code of the Python file.
    :param diff: The diff that corresponds to the mutation.
    :return: The ast.FunctionDef or ast.ClassDef node if found, else None.
    """
    # Extract the minimal patch from the diff
    minimal_patch: str = extract_minimal_patch(diff)

    line_no: int = get_line_number_from_patch(minimal_patch)

    # Get the function or class node from the line number
    res: ast.FunctionDef | None = get_function_from_line_number(file_content, line_no)

    if res is None:
        res = get_class_from_line_number(file_content, line_no)

    if res is None:
        logger.error(f"Failed to extract the mutated object from the diff:\n====\n{diff}\n====\n")

    return res
