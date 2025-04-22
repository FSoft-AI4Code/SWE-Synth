import pytest
from .process import unindent  # Replace 'your_module' with the module name where unindent is defined.

# FIXME: handle this case when unindent fail
'''
    def create_message_definition_from_tuple(self, msgid, msg_tuple):
        if implements(self, (IRawChecker, ITokenChecker)):
            default_scope = WarningScope.LINE
        else:
            default_scope = WarningScope.NODE
        options = {}
        if len(msg_tuple) > 3:
            (msg, symbol, descr, options) = msg_tuple
        elif len(msg_tuple) > 2:
            (msg, symbol, descr) = msg_tuple
        else:
            error_msg = """Messages should have a msgid and a symbol. Something like this :

"W1234": (
    "message",
    "message-symbol",
    "Message description with detail.",
    ...
),
"""
            raise InvalidMessageError(error_msg)
        options.setdefault("scope", default_scope)
        return MessageDefinition(self, msgid, msg, descr, symbol, **options)
'''


def test_basic_unindent():
    content = """
        line 1
        line 2
        line 3
    """
    expected = """
line 1
line 2
line 3
"""
    assert unindent(content).strip() == expected.strip()


def test_no_indentation():
    content = "line 1\nline 2\nline 3"
    assert unindent(content).strip() == content


def test_empty_string():
    content = ""
    assert unindent(content).strip() == ""


def test_single_line():
    content = "    line 1"
    expected = "line 1"
    assert unindent(content).strip() == expected


def test_mixed_indentation():
    content = """
        line 1
           line 2
        line 3
    """
    expected = """
line 1
   line 2
line 3
"""
    assert unindent(content).strip() == expected.strip()


def test_blank_lines():
    content = """
        line 1

        line 3
    """
    expected = """
line 1

line 3
"""
    assert unindent(content).strip() == expected.strip()


def test_trailing_whitespace():
    content = """
        line 1   
        line 2    
        line 3  
    """
    expected = """
line 1   
line 2    
line 3  
"""
    assert unindent(content).strip() == expected.strip()


def test_tabs_and_spaces():
    content = """
\t\tline 1
\t\t  line 2
\t\tline 3
    """
    expected = """
line 1
  line 2
line 3
"""
    assert unindent(content).strip() == expected.strip()


def test_all_blank_lines():
    content = """



    """
    assert unindent(content).strip() == ""


def test_indentation_with_empty_lines():
    content = """
        line 1

           line 2

        line 3
    """
    expected = """
line 1

   line 2

line 3
"""
    assert unindent(content).strip() == expected.strip()


if __name__ == "__main__":
    pytest.main()
