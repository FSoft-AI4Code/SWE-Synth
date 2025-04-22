import ast

__all__ = ["check_ast_correctness"]


def check_ast_correctness(code1: str, code2: str) -> bool:
    """Checks if two ASTs are structurally identical."""
    return ast.dump(ast.parse(code1)) == ast.dump(ast.parse(code2))
