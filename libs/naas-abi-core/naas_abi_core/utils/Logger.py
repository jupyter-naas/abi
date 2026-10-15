import os
import sys

from loguru import logger


def reconfigure(level: str = "DEBUG"):
    logger.remove()
    # diagnose prints the value of every variable in a logged traceback,
    # prompts and credentials included.
    logger.add(sys.stderr, level=level, diagnose=False)


reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))
