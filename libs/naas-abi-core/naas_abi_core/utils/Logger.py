import os
import sys

from loguru import logger


def reconfigure(level: str = "DEBUG"):
    logger.remove()
    # No ``diagnose``: it prints the value of every variable on each frame's
    # line of a traceback, a service key or a token among them. No
    # ``backtrace`` either: it adds the callers' frames and their values.
    logger.add(sys.stderr, level=level, diagnose=False, backtrace=False)


reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))
