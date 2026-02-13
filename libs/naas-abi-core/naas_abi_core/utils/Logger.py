import os
import sys

from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def reconfigure(level: str = "DEBUG"):
    logger.remove()
    logger.add(sys.stderr, level=level)


reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))
