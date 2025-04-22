from dataclasses import dataclass, field
import pathlib
from typing import Literal, Union
import ast


@dataclass
class Target:
    ast_obj: Union[ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef] | None = None
    relative_path: str | None = None
    abs_path_to_file: pathlib.Path | None = None

    def __hash__(self) -> int:
        return hash((self.relative_path, self.ast_obj))

    def __eq__(self, value):
        if not isinstance(value, Target):
            return False

        if self.relative_path != value.relative_path:
            return False

        if self.ast_obj is None and value.ast_obj is None:
            return True

        return (
            self.ast_obj.name == value.ast_obj.name
            and self.ast_obj.lineno == value.ast_obj.lineno
            and self.ast_obj.col_offset == value.ast_obj.col_offset
            and self.ast_obj.end_lineno == value.ast_obj.end_lineno
            and self.ast_obj.end_col_offset == value.ast_obj.end_col_offset
        )

    def to_dict(self) -> dict:
        return {
            "target": self.ast_obj
            and {
                "name": self.ast_obj.name,
                "lineno": self.ast_obj.lineno,
                "col_offset": self.ast_obj.col_offset,
                "end_lineno": self.ast_obj.end_lineno,
                "end_col_offset": self.ast_obj.end_col_offset,
            },
            "abs_path_to_file": str(self.abs_path_to_file),
            "relative_path": str(self.relative_path),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Target":
        return cls(
            ast_obj=data["target"]
            and ast.FunctionDef(
                name=data["target"]["name"],
                lineno=data["target"]["lineno"],
                col_offset=data["target"]["col_offset"],
                end_lineno=data["target"]["end_lineno"],
                end_col_offset=data["target"]["end_col_offset"],
            ),
            abs_path_to_file=pathlib.Path(data["abs_path_to_file"]),
            relative_path=data["relative_path"],
        )

    @property
    def module_name(self) -> str | None:
        return self.relative_path and self.relative_path.replace("/", ".").replace(".py", "")

    @property
    def nodeid(self) -> str:
        """
        NOTE: this still intentionally omit the class name of the class methods
        """
        return f"{self.relative_path or ''}::{self.ast_obj.name}"


@dataclass
class MutationInfo:
    changed_targets: set[Target] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)
    strategy: (
        Literal[
            "EmptyFunctionStrategy",
            "PriorityAwareMutationStrategy",
            "EmptyClassStrategy",
        ]
        | None
    ) = None
    model_raw_output: str | None = None
    mutator_model_name: str | None = None

    def to_dict(self) -> dict:
        return {
            "changed_targets": [target.to_dict() for target in self.changed_targets],
            "metadata": {str(k): str(v) for k, v in self.metadata.items()},
            "strategy": self.strategy,
            "model_raw_output": self.model_raw_output,
            "mutator_model_name": self.mutator_model_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MutationInfo":
        return cls(
            changed_targets={Target.from_dict(target) for target in data["changed_targets"]},
            metadata=data["metadata"],
            strategy=data.get("strategy"),
            model_raw_output=data.get("model_raw_output"),
            mutator_model_name=data.get("mutator_model_name"),
        )

    def __repr__(self):
        return f"""MutationInfo(
    strategy={self.strategy},
    mutator_model_name={self.mutator_model_name},
    changed_targets={self.changed_targets},
    model_raw_output={self.model_raw_output},
    metadata={self.metadata},
)"""
