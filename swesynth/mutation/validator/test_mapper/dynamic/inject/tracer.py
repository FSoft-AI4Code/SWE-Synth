from collections import defaultdict
import time
import json
import multiprocessing
import subprocess
import os
from pathlib import Path
import threading
from functools import partial

from coverage import Coverage
from typing import Optional, Union, TYPE_CHECKING

from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

if TYPE_CHECKING:
    from .collector import PyTestCollector
    from .utils import get_function_from_line_number, remove_empty, convert_to_normalized_name

pytest_nodeidT = str
function_nameT = str

global_relative_path_to_file_content = None


def process_file(coverage_file: str) -> set[str]:
    """main trace logic"""
    if not Path(coverage_file).exists():
        return set()
    cov = Coverage(data_file=coverage_file)
    cov.load()
    data = cov.get_data()

    # loop all files
    all_related_funcs = set()

    for relative_path, file_content in global_relative_path_to_file_content.items():
        relative_path = Path(relative_path)
        lineno_to_test_cases = data.contexts_by_lineno(relative_path.absolute().as_posix())
        lineno_to_test_cases = remove_empty(lineno_to_test_cases)
        all_lineno: set[int] = set(lineno_to_test_cases.keys())

        map_lineno_to_function = {lineno: get_function_from_line_number(file_content, lineno) for lineno in all_lineno}
        map_lineno_to_full_function_path = {lineno: f"{relative_path}::{node and node.name}" for lineno, node in map_lineno_to_function.items()}

        all_funcs = set(map_lineno_to_full_function_path.values())
        all_related_funcs.update(all_funcs)
    os.remove(coverage_file)
    return all_related_funcs


def process_task(file_queue: multiprocessing.Queue, total_length: int) -> None:
    """Worker listen from task pool"""
    print(f"Process worker {os.getpid()} started")
    counter = 0
    try:
        while True:
            print(f"Remaining queue size: {file_queue.qsize()} / {total_length}")
            payload: Optional[tuple[str, str]] = file_queue.get(block=True)

            if payload is None:
                print(f"Process worker {os.getpid()} finished after processing {counter} files")
                break

            counter += 1
            coverage_file, test_case = payload
            _begin_time = time.time()
            print(f"Process worker {os.getpid()} started '{test_case}'")
            all_related_funcs: set[str] = process_file(coverage_file)
            print(f"Process worker {os.getpid()} finished '{test_case}' in {time.time() - _begin_time:.2f}s")
            print(f"Found {len(all_related_funcs)} functions")
            if len(all_related_funcs) == 0:
                print(f"Skipping '{test_case}' as no functions found")
                continue
            os.makedirs("output", exist_ok=True)
            with open(f"output/{coverage_file}", "w") as f:
                json.dump({test_case: list(all_related_funcs)}, f)
    except Exception as e:
        print(f"Process worker {os.getpid()} failed with {e}")
        raise e


def parse_output(output_dir: str) -> dict[str, set[str]]:
    """Collect (reduce)"""
    all_related_funcs: dict[str, set[str]] = defaultdict(set)
    for file in tqdm(os.listdir(output_dir), desc="Parsing output"):
        with open(f"{output_dir}/{file}") as f:
            data = json.load(f)
            assert len(list(data.keys())) == 1
            test_case = list(data.keys())[0]
            all_related_funcs[test_case] |= set(data[test_case])
    return dict(all_related_funcs)


def begin_get_test_case_to_funcs(test_case: str, file_queue: multiprocessing.Queue) -> None:
    """Map"""
    coverage_file = f".coverage_tmp_{os.getpid()}_{threading.get_ident()}_{convert_to_normalized_name(test_case)}.db"

    env = os.environ.copy()
    env["COVERAGE_FILE"] = coverage_file

    # Build the pytest command with the required arguments
    pytest_command = [
        "timeout",
        "120m",
        "pytest",
        "--cov-context=test",
        "--cov",
        "-qq",
        "--cov-report=",
        "--continue-on-collection-errors",
        "-s",
        "--remote-data=none",
        test_case,
    ]

    # Run pytest as a subprocess with the modified environment
    result = subprocess.run(pytest_command, env=env)

    # # Check if the pytest command was successful
    # if result.returncode != 0:
    #     print(f"Pytest failed with return code {result.returncode}")
    #     # return set()  # or handle the error as appropriate
    #     return
    # https://docs.pytest.org/en/stable/reference/exit-codes.html

    file_queue.put((coverage_file, test_case))


class Tracer:
    project_root: Path
    test_cases_to_function: dict[pytest_nodeidT, set[str]]

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        if project_root is None:
            project_root = Path(os.getcwd())
        self.project_root = Path(project_root)

    def scan_all_files(self):
        global global_relative_path_to_file_content
        relative_path_to_file_content: dict[str, str] = {}
        for abs_file_path in tqdm(list(self.project_root.rglob("*.py")), desc="Scanning files"):
            relative_path = abs_file_path.relative_to(self.project_root)

            try:
                file_content = relative_path.read_text("utf-8")
            except Exception as e:
                print(f"Failed to read {relative_path} with utf-8 encoding {e}. Trying latin-1")
                try:
                    file_content = relative_path.read_text("latin-1")
                except Exception as e:
                    print(f"Failed to read {relative_path} with latin-1 encoding {e}. Try none")
                    try:
                        file_content = relative_path.read_text()
                    except Exception as e:
                        print(f"Failed to read {relative_path} with no encoding {e}. Skipping")
                        continue

            relative_path_to_file_content[str(relative_path)] = file_content

        # update the global variable
        global_relative_path_to_file_content = relative_path_to_file_content

        print(f"Scanned {len(relative_path_to_file_content)} python files")

        return relative_path_to_file_content

    def run(
        self,
        num_test_runners: Optional[int] = None,
        num_collectors: Optional[int] = None,
    ) -> "Tracer":
        print("Total number of CPUs:", multiprocessing.cpu_count())
        max_num_cpus = max((multiprocessing.cpu_count() // 2) - 5, 2)

        if num_test_runners is None:
            num_test_runners = max_num_cpus // 2
            print("Number of test runners:", num_test_runners)
        if num_collectors is None:
            num_collectors = max_num_cpus - num_test_runners
            print("Number of collectors:", num_collectors)

        all_test_cases: list[pytest_nodeidT] = list(PyTestCollector.run())

        print(f"Collected {len(all_test_cases)} test cases")

        self.scan_all_files()

        test_case_to_funcs: dict[pytest_nodeidT, set[str]] = {}

        queue: multiprocessing.Queue[Optional[tuple[str, str]]] = multiprocessing.Queue()
        get_test_case_to_funcs = partial(begin_get_test_case_to_funcs, file_queue=queue)

        # num_processes = num_collectors
        # with multiprocessing.Pool(num_processes, process_task, (queue,)) as pool:
        workers = []
        for _ in range(num_collectors):
            worker = multiprocessing.Process(target=process_task, args=(queue, len(all_test_cases)))
            worker.start()
            workers.append(worker)

        __begin = time.time()
        thread_map(get_test_case_to_funcs, all_test_cases, max_workers=num_test_runners, ascii=True, desc="Tracing test cases")
        print(f"All {len(all_test_cases)} test cases finished in {time.time() - __begin:.2f}s")

        print(f"Done running all test cases, now move {num_test_runners} processes to become collectors")

        for _ in range(num_test_runners):
            worker = multiprocessing.Process(target=process_task, args=(queue, len(all_test_cases)))
            worker.start()
            workers.append(worker)

        num_total = num_collectors + num_test_runners
        for _ in range(num_total):
            queue.put(None)

        print("Waiting for all processes to finish")

        join_counter = 0
        for worker in workers:
            worker.join()
            join_counter += 1
            print(f"{join_counter}/{num_total} workers joined")

        print("All processes finished")

        test_case_to_funcs = parse_output("output")

        print("All outputs collected")

        self.test_cases_to_function = test_case_to_funcs

        return self

    def dump(self) -> dict[str, list[str]]:
        assert self.test_cases_to_function is not None, "Run the tracer first"
        return {k: list(v) for k, v in self.test_cases_to_function.items()}
