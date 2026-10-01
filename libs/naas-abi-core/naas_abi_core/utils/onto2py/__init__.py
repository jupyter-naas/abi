"""
TTL to Python converter

Convert TTL (Turtle) files to Python Pydantic classes.
"""

from .onto2py import (
    check_continuants_connected_to_process,
    continuants_without_process,
    onto2py,
)

__version__ = "0.1.0"
__all__ = [
    "check_continuants_connected_to_process",
    "continuants_without_process",
    "onto2py",
] 