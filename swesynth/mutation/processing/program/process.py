def remove_lines_from_file(file_content: str, start_line: int, end_line: int) -> str:
    """
    Remove the lines from the file content.
    """
    lines = file_content.splitlines()
    del lines[start_line - 1 : end_line]
    return "\n".join(lines)


def add_content_at_line_with_correct_indentation(
    file_content: str,
    line_number: int,
    indentation: int,
    content: str = "# TODO",
) -> str:
    """
    Add the content at the line number with the correct indentation.
    """
    lines = file_content.splitlines()
    lines.insert(line_number, " " * indentation + content)
    return "\n".join(lines)


def add_multiline_content_at_line_with_correct_indentation(
    file_content: str,
    line_number: int,
    indentation: int,
    content: str,
) -> str:
    """
    Add the multi-line content at the line number with the correct indentation.
    """
    lines: list[str] = file_content.splitlines()
    contents: list[str] = content.splitlines()
    # lines.insert(line_number, " " * indentation + content)
    for i, line in enumerate(contents):
        lines.insert(line_number + i, " " * indentation + line)
    return "\n".join(lines)


def unindent(content: str) -> str:
    """
    Unindent the content by the minimum indentation level.
    """
    if not content.strip():
        return content
    lines = content.splitlines()
    min_indentation = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    return "\n".join(line[min_indentation:] for line in lines)
