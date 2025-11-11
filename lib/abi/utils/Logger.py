import os
import sys

from loguru import logger


def reconfigure(level: str = "DEBUG"):
    logger.remove()
    logger.add(sys.stderr, level=level)


reconfigure(os.environ.get("LOG_LEVEL", "DEBUG"))
