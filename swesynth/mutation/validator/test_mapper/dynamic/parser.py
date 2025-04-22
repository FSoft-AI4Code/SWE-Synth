import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from loguru import logger
import numpy as np
import zstandard as zstd

from .inject.constants import DELIMITER

if TYPE_CHECKING:
    from swesynth.mutation.validator.entities.status import TestStatus


@dataclass
class TestFunctionMap:
    function_to_test_mapping: dict[str, list[str]] | None = None
    test_to_function_mapping: dict[str, list[str]] | None = None

    def __post_init__(self):
        assert (
            self.function_to_test_mapping is not None or self.test_to_function_mapping is not None
        ), "At least one of the mappings should be provided"

        if self.test_to_function_mapping is None:
            _test_to_function_mapping = defaultdict(list[str])
            for function, tests in self.function_to_test_mapping.items():
                for test in tests:
                    _test_to_function_mapping[test].append(function)
            self.test_to_function_mapping = dict(_test_to_function_mapping)
        elif self.function_to_test_mapping is None:
            _function_to_test_mapping = defaultdict(list[str])
            for test, functions in self.test_to_function_mapping.items():
                for function in functions:
                    _function_to_test_mapping[function].append(test)
            self.function_to_test_mapping = dict(_function_to_test_mapping)
        else:
            raise ValueError("Both mappings are provided")

    def json(self) -> str:
        return json.dumps(
            {"function_to_test_mapping": self.function_to_test_mapping, "test_to_function_mapping": self.test_to_function_mapping}, indent=4
        )

    @classmethod
    def from_json_file(cls, path: Path) -> "TestFunctionMap":
        if path.suffix == ".zst":
            with path.open("rb") as f:
                compressed_data = f.read()
            json_data = zstd.decompress(compressed_data).decode()
        elif path.suffix == ".json":
            json_data = path.read_text()
        else:
            raise ValueError(f"Invalid file extension: {path.suffix}")

        data = json.loads(json_data)
        return cls(function_to_test_mapping=data["function_to_test_mapping"])

    def save(self, path: Path) -> None:
        json_data = json.dumps({"function_to_test_mapping": self.function_to_test_mapping})
        compressed_data = zstd.compress(json_data.encode())

        with path.open("wb") as f:
            f.write(compressed_data)

    def get_related_test_cases(self, function_nodeids: set[str]) -> set[str]:
        output = []
        for nodeid in function_nodeids:
            related_tests = self.function_to_test_mapping.get(nodeid, set())
            t = str(related_tests)
            logger.info(f"Related tests for '{nodeid}': {t[:40] + '...' if len(t) > 40 else t}")
            output.extend(related_tests)
        return set(output)

    def __repr__(self):
        return f"TestFunctionMap(num_functions={len(self.function_to_test_mapping)}, num_tests={len(self.test_to_function_mapping)})"


@dataclass
class CallGraphOutputParser:
    def parse(self, raw_test_output: str) -> TestFunctionMap:
        # graph_output: dict = self.parse_raw_output(raw_test_output)
        graph_output = json.loads(raw_test_output)
        return TestFunctionMap(test_to_function_mapping=graph_output)

    @staticmethod
    def parse_raw_output(raw_test_output: str) -> dict:
        data = raw_test_output.split(DELIMITER)
        assert (
            len(data) == 2
        ), f"Invalid data: {len(data)} | {raw_test_output if len(raw_test_output) < 1000 else raw_test_output[:1000] + '...' + raw_test_output[-1000:]}"
        return json.loads(data[-1])


if __name__ == "__main__":
    from swesynth.mutation.validator.entities.status import TestStatus

    graph_data = {}

    # List of test cases
    test_cases = {
        "test_hello.py::test_hello_world",
        "test_hello.py::test_hello_world2",
        "tests/test_sub.py::test_hello_world_in",
    }

    graph_raw = f"someloghere\n{DELIMITER}\n{json.dumps(graph_data)}"
    test_status = TestStatus(test_cases, set())

    call_graph_output_parser = CallGraphOutputParser()

    test_function_map: TestFunctionMap = call_graph_output_parser.parse(graph_raw, test_status)
    print(test_function_map.json())
