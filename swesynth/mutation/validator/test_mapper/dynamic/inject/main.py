if __name__ == "__main__":
    # https://stackoverflow.com/a/64369870/11806050
    import faulthandler
    import signal

    faulthandler.enable()
    faulthandler.register(signal.SIGUSR1.value)

    import json
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from .constants import DELIMITER, DUMP_PATH
        from .tracer import Tracer

    tracer = Tracer().run()

    output: dict[str, list[str]] = tracer.dump()

    with open(DUMP_PATH, "w") as f:
        f.write(json.dumps(output))

    print(DELIMITER)
    print(json.dumps(output))
