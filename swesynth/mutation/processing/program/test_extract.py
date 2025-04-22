import unittest
from .extract import get_class_from_line_number, get_function_from_line_number


class TestASTFunctions(unittest.TestCase):

    def setUp(self):
        self.file_content = """
class MyClass:
    def my_method(self):
        pass

    def another_method(self):
        pass

class AnotherClass:
    pass

def my_function():
    pass
"""

    def test_get_class_from_line_number(self):
        # Testing for line number 2, which should return MyClass
        result = get_class_from_line_number(self.file_content, 2)
        self.assertEqual(result.name, "MyClass")

        result = get_class_from_line_number(self.file_content, 4)
        self.assertEqual(result.name, "MyClass")

        # Testing for line number 10, which should return AnotherClass
        result = get_class_from_line_number(self.file_content, 10)
        self.assertEqual(result.name, "AnotherClass")

        # Testing for a line number not inside any class
        result = get_class_from_line_number(self.file_content, 12)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
