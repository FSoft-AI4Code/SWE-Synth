import ast
import pytest

from .transform import empty_function_body, replace_function_body, hint_function
from .extract import get_function_signature
from .process import unindent


def test_empty_function_body():
    # Input Python code
    original_code = '''
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result
    '''

    # Expected transformed code
    expected_code = '''
def example_function(param1, param2):
    """This is a docstring."""
    raise NotImplementedError
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_node = next(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))

    # Apply the empty_function_body transformation
    transformed_code = empty_function_body(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_replace_function_body():
    # Input Python code
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # Expected transformed code
    expected_code = '''
def function_one(param1, param2):
    """This is a docstring."""

def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 * param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # New function implementation
    new_implementation = '''
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 * param2
    return result
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    # Apply the replace_function_body transformation
    transformed_code = replace_function_body(file_content=original_code, function=function_node, new_function_implementation=new_implementation)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_replace_function_body_with_decorator():
    # Input Python code
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # Expected transformed code
    expected_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 * param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # New function implementation
    new_implementation = '''
@some_decorator
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 * param2
    return result
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    # Apply the replace_function_body transformation
    transformed_code = replace_function_body(file_content=original_code, function=function_node, new_function_implementation=new_implementation)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_replace_function_body_with_changed_docstring():
    # Input Python code
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """
    This is a docstring.
    
    """
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # Expected transformed code
    expected_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """
    This is a docstring.
    
    """
    # This is a comment
    result = param1 * param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # New function implementation
    new_implementation = '''
@some_decorator
def example_function(param1, param2):
    """ This is a docstring.  """
    # This is a comment
    result = param1 * param2
    return result
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    # Apply the replace_function_body transformation
    transformed_code = replace_function_body(
        file_content=original_code, function=function_node, new_function_implementation=new_implementation, preserve_original_docstring=True
    )

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_replace_function_body_with_changed_docstring_indent():
    # Input Python code
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """
    This is a docstring.
    
    """
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # Expected transformed code
    expected_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@some_decorator
def example_function(param1, param2):
    """
    This is a docstring.
    
    """
    # This is a comment
    result = param1 * param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    # New function implementation
    new_implementation = '''
        @some_decorator
        def example_function(param1, param2):
            """ This is a docstring.  """
            # This is a comment
            result = param1 * param2
            return result
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    # Apply the replace_function_body transformation
    transformed_code = replace_function_body(
        file_content=original_code, function=function_node, new_function_implementation=new_implementation, preserve_original_docstring=True
    )

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_replace_method_body():
    # Input Python code
    original_code = '''
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    def example_function(param1, param2):
        """This is a docstring."""
        # This is a comment
        result = param1 + param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""
    '''

    # Expected transformed code
    expected_code = '''
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    def example_function(param1, param2):
        """This is a docstring."""
        # This is a comment
        result = param1 * param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""
    '''

    # New function implementation
    new_implementation = '''
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 * param2
    return result
    '''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    class_node = next(node for node in parsed_code.body if isinstance(node, ast.ClassDef))
    function_nodes = list(node for node in class_node.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    # Apply the replace_function_body transformation
    transformed_code = replace_function_body(file_content=original_code, function=function_node, new_function_implementation=new_implementation)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_extract_function():
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    expected_code = '''
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    transformed_code = get_function_signature(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_extract_method():
    original_code = '''
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    def example_function(param1, param2):
        """This is a docstring."""
        # This is a comment
        result = param1 + param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""
    '''

    expected_code = '''
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    class_node = next(node for node in parsed_code.body if isinstance(node, ast.ClassDef))
    function_nodes = list(node for node in class_node.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    transformed_code = get_function_signature(file_content=original_code, function=function_node)

    transformed_code = unindent(transformed_code)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_extract_function_with_decorator():
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@decorator1
@decorator2
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    expected_code = '''
@decorator1
@decorator2
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))
    function_node = function_nodes[1]

    transformed_code = get_function_signature(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_hint_function():
    original_code = '''
def function_one(param1, param2):
    """This is a docstring."""

@decorator1
@decorator2
def example_function(param1, param2):
    """This is a docstring."""
    # This is a comment
    result = param1 + param2
    return result

def function_two(param1, param2):
    """This is a docstring."""
    '''

    expected_code = '''
@decorator1
@decorator2
def example_function(param1, param2):
    """This is a docstring."""
    ... your code goes here ...
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the AST
    function_nodes = list(node for node in parsed_code.body if isinstance(node, ast.FunctionDef))

    function_node = function_nodes[1]

    transformed_code = hint_function(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_hint_function_indent():
    original_code = '''
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    @decorator1
    @decorator2
    def example_function(param1, param2):
        """This is a docstring."""
        # This is a comment
        result = param1 + param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""
'''

    expected_code = '''
@decorator1
@decorator2
def example_function(param1, param2):
    """This is a docstring."""
    ... your code goes here ...
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the
    class_node = next(node for node in parsed_code.body if isinstance(node, ast.ClassDef))
    function_nodes = list(node for node in class_node.body if isinstance(node, ast.FunctionDef))

    function_node = function_nodes[1]

    transformed_code = hint_function(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_hint_function_indent2():
    original_code = '''
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    @decorator1
    @decorator2
    def example_function(param1, param2):
        a = b
        # This is a comment
        result = param1 + param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""
'''

    expected_code = """
@decorator1
@decorator2
def example_function(param1, param2):
    ... your code goes here ...
"""

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    # Find the function node in the
    class_node = next(node for node in parsed_code.body if isinstance(node, ast.ClassDef))
    function_nodes = list(node for node in class_node.body if isinstance(node, ast.FunctionDef))

    function_node = function_nodes[1]

    transformed_code = hint_function(file_content=original_code, function=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


if __name__ == "__main__":
    pytest.main()
