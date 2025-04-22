import sys
import pytest
import traceback


class PyTestCollector:
    """
    https://github.com/pytest-dev/pytest/discussions/2039
    """

    collected: set[str]

    def __init__(self):
        self.collected = set()

    def pytest_collection_modifyitems(self, items):
        for item in items:
            self.collected.add(item.nodeid)

    @staticmethod
    def run() -> set[str]:
        plugin = PyTestCollector()
        default_args = sys.argv[1:]
        # pytest.main(["--collect-only", '-qq', *default_args], plugins=[plugin])
        try:
            pytest.main(["--collect-only", "-qq", "--continue-on-collection-errors", "-s"], plugins=[plugin])
        except Exception as e:
            print(f"Failed to run pytest collection with error: {e}")
            print(traceback.format_exc())
        return plugin.collected
