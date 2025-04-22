import ast
from .extract import get_start_location_of_function_body, get_function_signature, extract_function_body
from .process import (
    remove_lines_from_file,
    add_content_at_line_with_correct_indentation,
    add_multiline_content_at_line_with_correct_indentation,
    unindent,
)


def empty_function_body(
    file_content: str,
    function: ast.FunctionDef,
    content: str = "raise NotImplementedError",
) -> str:
    """
    Empty the function body, keeping the function signature, all comments, and docstrings.

    Args:
        file_content (str): The content of the file.
        function (ast.FunctionDef): The function to be transformed.

    Returns:
        str: The transformed content of the file, with the function body emptied.
    """
    start_body: int = get_start_location_of_function_body(function)
    end_body: int = function.end_lineno

    added_content: str = add_content_at_line_with_correct_indentation(
        file_content=file_content,
        line_number=end_body,
        indentation=function.body[0].col_offset,
        content=content,
    )

    processed_content: str = remove_lines_from_file(added_content, start_line=start_body, end_line=end_body)

    return processed_content


def hint_function(
    file_content: str,
    function: ast.FunctionDef,
) -> str:
    extracted_function_signature: str = get_function_signature(file_content, function)

    extracted_function_signature = unindent(extracted_function_signature)

    function = ast.parse(extracted_function_signature).body[0]
    return empty_function_body(extracted_function_signature, function, content=f"... your code goes here ...")


def replace_function_body(
    file_content: str,
    function: ast.FunctionDef,
    new_function_implementation: str,
    preserve_original_docstring: bool = True,
) -> str:
    """
    Replace the function body with new implementation, keeping the function signature, all comments, and docstrings.

    Args:
        file_content (str): The content of the file.
        function (ast.FunctionDef): The function to be transformed.
        new_function_implementation (str): The new function implementation to be inserted.
    Returns:
        str: The transformed content of the file, with the new function implementation inserted.
    """
    if preserve_original_docstring:
        return replace_function_body_preserve_function_docstring(file_content, function, new_function_implementation)

    start_body: int = function.lineno
    end_body: int = function.end_lineno

    if len(function.decorator_list) > 0:
        # handle decorators
        start_body = function.decorator_list[0].lineno

    new_function_implementation = new_function_implementation.strip()

    added_content: str = add_multiline_content_at_line_with_correct_indentation(
        file_content=file_content, line_number=end_body, indentation=function.col_offset, content=new_function_implementation
    )

    processed_content: str = remove_lines_from_file(added_content, start_line=start_body, end_line=end_body)

    return processed_content


def replace_function_body_preserve_function_docstring(
    file_content: str,
    function: ast.FunctionDef,
    new_function_implementation: str,
) -> str:
    """
    Replace the function body with new implementation, keeping the function signature, all comments, and docstrings.

    Args:
        file_content (str): The content of the file.
        function (ast.FunctionDef): The function to be transformed.
        new_function_implementation (str): The new function implementation to be inserted.
    Returns:
        str: The transformed content of the file, with the new function implementation inserted.
    """
    start_of_original_function_body_after_docstring: int = get_start_location_of_function_body(function)
    # original_function_body: str = extract_function_body(file_content, function)

    # Extract the new function implementation
    new_function_implementation = unindent(new_function_implementation).strip()
    _ = ast.parse(new_function_implementation).body
    assert len(_) == 1, f"The new function implementation should contain only one function definition, got {len(_)}: \n{new_function_implementation}"
    new_function: ast.FunctionDef = _[0]

    new_implementation_function_body: str = extract_function_body(new_function_implementation, new_function)
    new_implementation_function_body = unindent(new_implementation_function_body)
    added_content: str = add_multiline_content_at_line_with_correct_indentation(
        file_content=file_content,
        line_number=function.end_lineno,
        indentation=function.body[0].col_offset,
        content=new_implementation_function_body,
    )
    # Remove the original function body content and replace it with the new content
    processed_content: str = remove_lines_from_file(
        added_content,
        start_line=start_of_original_function_body_after_docstring,
        end_line=function.end_lineno,
    )

    return processed_content


def empty_class(
    file_content: str,
    class_: ast.ClassDef,
) -> str:
    """
    Loop through all the methods in the class and empty their bodies, keeping the method signatures and docstrings.
    Leave all other class attributes untouched.

    Args:
        file_content (str): The content of the file.
        class_ (ast.ClassDef): The class to be transformed.

    Returns:
        str: The transformed content of the file, with the class body emptied.
    """
    # Extract all function nodes within the class
    function_nodes = [node for node in class_.body if isinstance(node, ast.FunctionDef)]

    # Sort the functions in reverse order of their starting line numbers
    function_nodes_sorted = sorted(function_nodes, key=lambda x: x.lineno, reverse=True)

    # Process each function
    for node in function_nodes_sorted:
        file_content = empty_function_body(file_content, node)

    return file_content


def replace_class_body(
    file_content: str,
    class_: ast.ClassDef,
    new_class_implementation: str,
) -> str:
    """
    Replace the class body with a new implementation, keeping the class signature and docstring.

    Args:
        file_content (str): The content of the file.
        class_ (ast.ClassDef): The class to be transformed.
        new_class_implementation (str): The new class implementation to be inserted.

    Returns:
        str: The transformed content of the file, with the new class body inserted.
    """
    # Start and end of the class body
    start_body: int = class_.lineno
    end_body: int = class_.end_lineno

    if class_.decorator_list:
        # Adjust the start line to handle decorators, if any
        start_body = class_.decorator_list[0].lineno

    new_class_implementation = new_class_implementation.strip()

    # Add the new implementation at the class's location
    added_content: str = add_multiline_content_at_line_with_correct_indentation(
        file_content=file_content, line_number=end_body, indentation=class_.col_offset, content=new_class_implementation
    )

    # Remove the original class body content and replace it with the new content
    processed_content: str = remove_lines_from_file(added_content, start_line=start_body, end_line=end_body)

    return processed_content


def hint_class(
    file_content: str,
    class_: ast.ClassDef,
) -> str:
    """
    Loop through all the methods in the class and empty their bodies, keeping the method signatures and docstrings.
    Leave all other class attributes untouched.

    Args:
        file_content (str): The content of the file.
        class_ (ast.ClassDef): The class to be transformed.

    Returns:
        str: The transformed content of the file, with the class body emptied.
    """
    extracted_class_signature: str = get_function_signature(file_content, class_)

    extracted_class_signature = unindent(extracted_class_signature)

    class_ = ast.parse(extracted_class_signature).body[0]

    # Extract all function nodes within the class
    function_nodes = [node for node in class_.body if isinstance(node, ast.FunctionDef)]

    # Sort the functions in reverse order of their starting line numbers
    function_nodes_sorted = sorted(function_nodes, key=lambda x: x.lineno, reverse=True)

    # Process each function
    for node in function_nodes_sorted:
        extracted_class_signature = empty_function_body(extracted_class_signature, node, content=f"... your code goes here ...")

    return extracted_class_signature
