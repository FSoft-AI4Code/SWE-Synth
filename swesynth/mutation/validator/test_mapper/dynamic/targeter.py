from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import TYPE_CHECKING

from loguru import logger

from docker.models.containers import Container
from swesynth.mutation.validator.entities.mutation_info import MutationInfo, Target
from swesynth.mutation.validator.entities.status import TestStatus, TestStatusDiff
from swesynth.mutation.validator.test_mapper.dynamic.scoring import Scorer, FunctionScores
from swesynth.mutation.validator.docker.communication import read_file_from_container

from .parser import CallGraphOutputParser, TestFunctionMap
from .backward_compatible import remove_type_hints
from .inject.constants import DUMP_PATH

if TYPE_CHECKING:
    from swesynth.mutation.validator.tester import Tester
    from swesynth.mutation.version_control.repository import RepositorySnapshot


@dataclass
class DynamicCallGraphTestTargeter:
    tester: "Tester"
    callgraph_parser: CallGraphOutputParser = field(default_factory=CallGraphOutputParser)
    test_function_map: TestFunctionMap | None = None

    original_source_code: "RepositorySnapshot" = field(init=False)

    @property
    def test_function_map_file_path(self) -> Path:
        return self.tester.docker_manager.log_dir / "test2function_mapping.json.zst"

    # @property
    # def score_mapping_file_path(self) -> Path:
    #     return self.tester.docker_manager.log_dir / "function_to_score.json.zst"

    # def get_function_scores(self) -> FunctionScores:
    #     return FunctionScores.load(self.score_mapping_file_path)

    def __post_init__(self):
        self.original_source_code = self.tester.source_code
        if self.test_function_map_file_path.exists():
            logger.info(f"Loading saved test function map from {self.test_function_map_file_path}")
            self.test_function_map = TestFunctionMap.from_json_file(self.test_function_map_file_path)

    def get_first_test_command(self) -> str:
        # install = "pip install python-call-graph==2.1.2"  # Support for Python 3.8 - 3.12.
        inject_dir = Path(__file__).parent / "inject"
        inject_files = [
            "constants.py",
            "collector.py",
            "utils.py",
            "tracer.py",
            "main.py",
        ]
        file_content = "\n".join([(inject_dir / f).read_text() for f in inject_files])
        file_content = remove_type_hints(file_content)
        file_content = f"TYPE_CHECKING = False\n{file_content}"

        # check if dynamic context in .coveragerc, pyproject.toml, setup.cfg, tox.ini, find recursive
        # dynamic_context = test_function
        # dynamic_context = "test_function"
        make_sure_no_dynamic_context = r"""
find . -type f -exec sh -c '
  sed -i "s/^dynamic_context = test_function/#dynamic_context = test_function/g" "$1" &&
  grep -q "^#dynamic_context = test_function" "$1" && echo "success replacing $1"
' sh {} \;

find . -type f -exec sh -c '
  sed -i "s/^dynamic_context = \"test_function\"/#dynamic_context = \"test_function\"/g" "$1" &&
  grep -q "^#dynamic_context = \"test_function\"" "$1" && echo "success replacing $1"
' sh {} \;
"""
        """
[tool.coverage.run]
branch = true
source = ["mypy"]
parallel = true
"""
        make_sure_no_branch_coverage = r"""
find . -type f -exec sh -c '
    sed -i "s/^branch = true/#branch = true/g" "$1" &&
    grep -q "^#branch = true" "$1" && echo "success replacing $1"
' sh {} \;

find . -type f -exec sh -c '
    sed -i "s/^branch = \"true\"/#branch = \"true\"/g" "$1" &&
    grep -q "^#branch = \"true\"" "$1" && echo "success replacing $1"
' sh {} \;
"""
        make_sure_no_parallel = r"""
find . -type f -exec sh -c '
    sed -i "s/^parallel = true/#parallel = true/g" "$1" &&
    grep -q "^#parallel = true" "$1" && echo "success replacing $1"
' sh {} \;

find . -type f -exec sh -c '
    sed -i "s/^parallel = \"true\"/#parallel = \"true\"/g" "$1" &&
    grep -q "^#parallel = \"true\"" "$1" && echo "success replacing $1"
' sh {} \;
"""
        commands = f"""
cat <<-"EOF" > callgraph_tracker.py
{file_content}
EOF
{make_sure_no_dynamic_context}
{make_sure_no_branch_coverage}
{make_sure_no_parallel}
pip install pytest-cov tqdm pytest-remotedata
rm -f .coverage
# pytest --cov-context=test --cov=. -rA --continue-on-collection-errors
python callgraph_tracker.py
"""
        cmd: str = self.tester.docker_manager.get_test_command(self.original_source_code)
        # NOTE: currently we are only supporting `pytest`, might support others in the future
        assert "pytest" in cmd
        # final_cmd = cmd.replace("pytest", f"\n{commands}")
        # comment out `pytest` command
        cmd = re.sub(r"^pytest", "# pytest", cmd, flags=re.MULTILINE)
        final_cmd = f"{cmd}\n{commands}"
        # logger.info(f"""Before:\n{cmd}\n\nAfter:\n{final_cmd}""")
        return final_cmd

    def parse_test_output(self, raw_test_output: str, container: Container) -> TestStatus:
        # we no longer use raw_test_output, instead we use the container's dump file
        output = read_file_from_container(container, Path("/testbed/") / DUMP_PATH)
        self.test_function_map: TestFunctionMap = self.callgraph_parser.parse(output)
        self.test_function_map.save(self.test_function_map_file_path)

    def get_related_test_cases(
        self,
        # mutation_info: MutationInfo,
        changed_targets: set[Target],
    ) -> set[str]:
        """
        This is over-estimated related test cases, because it includes all setup-teardown functions
        """
        assert self.test_function_map is not None

        # mutated_functions: set[Target] = mutation_info.changed_targets
        mutated_functions: set[Target] = changed_targets

        need_to_test: set[str] = self.test_function_map.get_related_test_cases({target.nodeid for target in mutated_functions})

        return need_to_test

    def train(self):
        assert self.test_function_map is not None

        scorer = Scorer(self.test_function_map)
        # score_mapping = scorer.train()
        # score_mapping.save(self.score_mapping_file_path)

        scorer.compute_node_degree().save(self.tester.docker_manager.log_dir / "node_degree.json.zst")


if __name__ == "__main__":
    # preview build
    inject_dir = Path(__file__).parent / "inject"
    inject_files = [
        "constants.py",
        "collector.py",
        "utils.py",
        "tracer.py",
        "main.py",
    ]
    file_content = "\n".join([(inject_dir / f).read_text() for f in inject_files])
    file_content = remove_type_hints(file_content)
    file_content = f"TYPE_CHECKING = False\n{file_content}"

    (inject_dir / "callgraph_tracker.py").write_text(file_content)
