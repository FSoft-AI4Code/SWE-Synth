from dataclasses import dataclass
import re

from loguru import logger


def remove_ansi_colors(text: str) -> str:
    # Regular expression to match ANSI escape sequences
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


@dataclass
class LogExtractor:
    repo: str

    def parse_log(self, logs: str) -> str:
        """
        Extract the test log traces from the total raw logs in order to be used as **problem statement**

        If Error and Failure are found, return the logs until the first error/failure is found.
        """
        try:
            if self.repo == "django/django":
                _ = logs.split("./tests/runtests.py --verbosity 2")
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[-1]
                _ = logs.split("==============", maxsplit=1)
                if len(_) == 1:
                    logger.warning("No django test log found")
                    return logs
                assert len(_) == 2, logs
                logs = _[-1]
                _ = re.split(r"Ran \d+ test[s]? in [\d\.+]", logs)
                assert len(_) == 2, f"Got {len(_)}, {logs}"
                logs = _[0]
                # remove first line and last line
                logs = "\n".join(logs.split("\n")[1:-1]).strip()
                return logs
            elif self.repo == "sympy/sympy":
                _ = logs.split("= test process starts =")
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[-1]
                _ = re.split(r"\n\s[\=\s]*tests finished:[\s\d\w\,]+in[\s\.\d]+seconds[.\s\=]+DO \*NOT\* COMMIT!", logs)
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[0]
                # remove first line and last line
                logs = "\n".join(logs.split("\n")[1:-1])

                _ = logs.split("[FAIL]\n\n\n______")
                assert len(_) == 2, logs
                logs = _[-1]

                # _ = l.split('\n\n', maxsplit=1)
                # assert len(_) == 2
                # l = _[-1]

                return logs.strip()

            elif self.repo == "pytest-dev/pytest":
                _ = logs.split("+ pytest --continue-on-collection-errors --tb=long -vvv -rA")  # only for swesynth
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[-1]
                _ = logs.split("[100%]", maxsplit=1)
                assert len(_) == 2, f"Got {len(_)}"
                logs = _[-1]
                _ = logs.split("= short test summary info =")
                # get all from 0 -> -1
                logs = "= short test summary info =".join(_[:-1])
                # remove first line and last line
                logs = "\n".join(logs.split("\n")[1:-1])
                return logs.strip()

            else:
                # pytest
                _ = logs.split("= test session starts =")
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[-1]

                logs = remove_ansi_colors(logs)

                try:
                    try:
                        _ = logs.split("[100%]", maxsplit=1)
                        assert len(_) == 2, f"Got {len(_)}"
                        logs = _[-1]
                    except AssertionError:
                        try:
                            assert self.repo == "astropy/astropy"
                            # NOTE: pytest 3.3.1 won't have this [100%] marker, and therefore will throws error
                            # in `astropy/1.3/c76af9ed6bb89bfba45b9f5bc1e635188278e2fa/swebench_astropy__astropy-6938` for example
                            _ = re.split(r"astropy\/.+\.py::.+\n\n======================", logs)
                            assert len(_) == 2, f"Got {len(_)}: {logs}"
                            logs = _[-1]
                        except AssertionError:
                            regex = r"\[[\d\ ]{3}\%\]\n\n=="
                            _ = re.split(regex, logs)
                            assert len(_) == 2, f"Got {len(_)}"
                            logger.warning(f"Failed to split logs by [100%] marker, this is likely that the logs endswith [ 98%] for example")
                            logs = _[-1]
                except AssertionError:
                    regex = r"\n\=+\sFAILURES\s\=+"
                    _ = re.split(regex, logs)
                    assert len(_) == 2, f"Got {len(_)}"
                    logger.warning(f"Failed to split logs by [...%] marker, this is likely that the pytest doesn't have this marker")
                    logger.warning(f"Trying to split by === FAILURES ===")
                    logs = _[-1]

                _ = re.split(r"\n\=+ short test summary info\ \=+", logs)
                assert len(_) == 2, f"Expected 2 parts, got {len(_)}"
                logs = _[0]

                # remove first line and last line
                logs = "\n".join(logs.split("\n")[1:-1])

                return logs.strip()

        except Exception as e:
            logger.error(f"Failed to parse test log traces: {e}")
            logger.exception(e)
            logger.error(f"Raw error logs:\n====== Raw error logs ======\n{logs[-3000:]}\n========================")
            return logs
