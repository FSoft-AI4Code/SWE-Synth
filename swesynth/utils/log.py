from loguru import logger
from tqdm import tqdm

logger.remove()
logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)


def log_exception():
    return logger.catch(BaseException, reraise=True)


logger.log_exception = log_exception

import logging

logging.getLogger("simple_parsing").setLevel(logging.WARNING)
