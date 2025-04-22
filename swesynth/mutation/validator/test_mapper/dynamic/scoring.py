import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import torch
import zstandard as zstd
from loguru import logger
from torch_ppr import page_rank

if TYPE_CHECKING:
    from .parser import TestFunctionMap

edgeT = tuple[int, int]


@dataclass
class FunctionScores:
    function_to_scores: dict[str, float]

    def get_score(self, function: str) -> float:
        return self.function_to_scores[function]

    def save(self, path: Path) -> None:
        if not path.parent.exists():
            logger.warning(f"Creating directory {path.parent}")
            path.parent.mkdir(parents=True)

        if path.suffix == ".zst":
            path.write_bytes(zstd.compress(json.dumps(self.function_to_scores).encode()))
        else:
            path.write_text(json.dumps(self.function_to_scores))

    @classmethod
    def load(cls, path: Path) -> "FunctionScores":
        if path.suffix == ".zst":
            return cls(json.loads(zstd.decompress(path.read_bytes()).decode()))
        else:
            return cls(json.loads(path.read_text()))


@dataclass
class Scorer:
    test_function_map: "TestFunctionMap"

    def get_id_map(self) -> dict[str, int]:
        counter: int = 0
        mapping: dict[str, int] = {}
        for test_function in self.test_function_map.test_to_function_mapping.keys():
            if test_function not in mapping:
                mapping[test_function] = counter
                counter += 1
        for function in self.test_function_map.function_to_test_mapping.keys():
            if function not in mapping:
                mapping[function] = counter
                counter += 1
        return mapping

    def get_edges(self, id_map: dict[str, int]) -> list[edgeT]:
        edges: set[edgeT] = set()
        for test_function, functions in self.test_function_map.test_to_function_mapping.items():
            for function in functions:
                edges.add((id_map[test_function], id_map[function]))

        return list(edges)

    def parse_scores(self, scores: list[float], id_map: dict[str, int]) -> FunctionScores:
        result: dict[str, float] = {}
        for test_function, idx in id_map.items():
            result[test_function] = scores[idx]
        return FunctionScores(result)

    @staticmethod
    def get_scores(edges: list[edgeT]) -> list[float]:
        assert len(edges) > 0, "No edges found"
        return page_rank(edge_index=torch.as_tensor(data=edges).t(), device="cpu").tolist()

    def compute_node_degree(self) -> FunctionScores:
        node_degree: dict[str, int] = {}
        for function in self.test_function_map.function_to_test_mapping.keys():
            node_degree[function] = len(self.test_function_map.function_to_test_mapping[function])
        for test in self.test_function_map.test_to_function_mapping.keys():
            node_degree[test] = len(self.test_function_map.test_to_function_mapping[test])
        return FunctionScores(node_degree)

    def train(self) -> FunctionScores:
        id_map = self.get_id_map()
        edges: list[edgeT] = self.get_edges(id_map)
        # train model
        scores = self.get_scores(edges)
        function_to_scores = self.parse_scores(scores, id_map)
        return function_to_scores
