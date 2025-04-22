import unittest
import ast

import pytest

from .transform import empty_class, hint_class, replace_class_body


class TestEmptyClass(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        # Sample class content for testing
        self.sample_class_content = '''
# This is a comment
class SampleClass:
    """This is a sample class."""

    class_var = 42
    """this is a class variable"""

    def method_one(self):
        """
        This is a docstring for method_one.
        """
        print("This is method one")
        print("This is method one")
        print("This is method one")
        print("This is method one")
    
    def method_two(self):
        pass

    def method_with_decorator(self):
        """
        This is a docstring for method_with_decorator.
        """
        @classmethod
        def decorated_method(cls):
            print("Decorated method")
        return decorated_method
'''

        # The expected class content after emptying methods
        self.expected_class_content = '''
# This is a comment
class SampleClass:
    """This is a sample class."""

    class_var = 42
    """this is a class variable"""

    def method_one(self):
        """
        This is a docstring for method_one.
        """
        raise NotImplementedError
    
    def method_two(self):
        raise NotImplementedError

    def method_with_decorator(self):
        """
        This is a docstring for method_with_decorator.
        """
        raise NotImplementedError
'''

    def test_empty_class_methods(self):
        # Parse the sample class content
        tree = ast.parse(self.sample_class_content)

        # Find the class node in the AST
        class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef))

        # Apply the `empty_class` transformation
        modified_content = empty_class(self.sample_class_content, class_node)
        # print(modified_content)

        # Assert that the modified content matches the expected content
        self.assertEqual(modified_content.strip(), self.expected_class_content.strip())


class TestReplaceClassBody(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        # Sample class content for testing
        self.sample_class_content = '''
def sample_function():
    pass

class SampleClass:
    """
    This is the docstring for SampleClass.
    """
    class_var = 42

    def method_one(self):
        """
        This is a docstring for method_one.
        """
        print("This is method one")

    def method_two(self):
        pass
'''

        # The expected class content after replacing the body
        self.expected_class_content = '''
def sample_function():
    pass

class SampleClass:
    """
    This is the docstring for SampleClass.
    """
    NEW_CLASS_BODY_LINE_ONE
    NEW_CLASS_BODY_LINE_TWO
'''

    def test_replace_class_body(self):
        new_class_implementation = '''\
class SampleClass:
    """
    This is the docstring for SampleClass.
    """
    NEW_CLASS_BODY_LINE_ONE
    NEW_CLASS_BODY_LINE_TWO
'''
        # Parse the sample class content
        tree = ast.parse(self.sample_class_content)

        # Find the class node in the AST
        class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef))

        # Apply the `replace_class_body` transformation
        modified_content = replace_class_body(self.sample_class_content, class_node, new_class_implementation)
        # print(modified_content)

        # Assert that the modified content matches the expected content
        self.assertEqual(modified_content.strip(), self.expected_class_content.strip())

    def test_replace_class_body_2(self):
        new_class_implementation = '''

class SampleClass:
    """
    This is the docstring for SampleClass.
    """
    NEW_CLASS_BODY_LINE_ONE
    NEW_CLASS_BODY_LINE_TWO

'''
        # Parse the sample class content
        tree = ast.parse(self.sample_class_content)

        # Find the class node in the AST
        class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef))

        # Apply the `replace_class_body` transformation
        modified_content = replace_class_body(self.sample_class_content, class_node, new_class_implementation)
        # print(modified_content)

        # Assert that the modified content matches the expected content
        self.assertEqual(modified_content.strip(), self.expected_class_content.strip())


def test_hint_class():
    original_code = '''
class A:
    """This is a docstring."""
    a = b
    def function_one(param1, param2):
        """This is a docstring."""

    @decorator1
    @decorator2
    def example_function(param1, param2):
        """This is a docstring."""
        # This is a comment
        result = param1 + param2
        return result

    def function_two(
        param1,
        param2
    ):
        """This is a docstring."""
    '''

    expected_code = '''
class A:
    """This is a docstring."""
    a = b
    def function_one(param1, param2):
        """This is a docstring."""
        ... your code goes here ...

    @decorator1
    @decorator2
    def example_function(param1, param2):
        """This is a docstring."""
        ... your code goes here ...

    def function_two(
        param1,
        param2
    ):
        """This is a docstring."""
        ... your code goes here ...
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    function_node = parsed_code.body[0]

    transformed_code = hint_class(file_content=original_code, class_=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_hint_class_decorator():
    original_code = '''
import haha

if True:
    @dataclass1
    @dataclass2
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

import hehe
1 + 1
    '''

    expected_code = '''
@dataclass1
@dataclass2
class A:
    def function_one(param1, param2):
        """This is a docstring."""
        ... your code goes here ...

    @decorator1
    @decorator2
    def example_function(param1, param2):
        """This is a docstring."""
        ... your code goes here ...

    def function_two(param1, param2):
        """This is a docstring."""
        ... your code goes here ...
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    if_block = parsed_code.body[1]
    function_node = if_block.body[0]

    assert isinstance(function_node, ast.ClassDef)

    transformed_code = hint_class(file_content=original_code, class_=function_node)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


def test_hint_class_decorator2():
    original_code = '''
import haha

@dataclass
class A:
    def function_one(param1, param2):
        """This is a docstring."""

    def example_function(param1, param2):
        result = param1 + param2
        return result

    def function_two(param1, param2):
        """This is a docstring."""

import hehe
1 + 1
    '''

    expected_code = '''
@dataclass
class A:
    def function_one(param1, param2):
        """This is a docstring."""
        ... your code goes here ...

    def example_function(param1, param2):
        ... your code goes here ...

    def function_two(param1, param2):
        """This is a docstring."""
        ... your code goes here ...
'''

    # Parse the AST of the original code
    parsed_code = ast.parse(original_code)

    function_node = parsed_code.body[1]

    assert isinstance(function_node, ast.ClassDef)

    transformed_code = hint_class(file_content=original_code, class_=function_node)

    print(transformed_code)

    # Assert the transformed code matches the expected code
    assert transformed_code.strip() == expected_code.strip()


if __name__ == "__main__":
    # unittest.main()
    pytest.main()
