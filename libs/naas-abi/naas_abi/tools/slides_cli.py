"""Replace text in a Nexus deck.html file.

The deck stays HTML. This command calls the same replace helper as
``replace_in_slides_deck`` and does not start a second slide runtime.

Usage::

    python -m naas_abi.tools.slides_cli replace deck.html \\
        --old OLD --new NEW --element-path 0:h1:0 -o out.html
"""

from __future__ import annotations

import argparse
from pathlib import Path

from naas_abi.tools.slides_tools import _apply_replacements_in_section


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m naas_abi.tools.slides_cli",
        description="Edit a Nexus deck.html file",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    replace = sub.add_parser(
        "replace",
        help="Replace text, optionally inside one preview node",
    )
    replace.add_argument("html", type=Path, help="Path to deck.html")
    replace.add_argument("--old", required=True, help="Text to find")
    replace.add_argument("--new", required=True, help="Replacement text")
    replace.add_argument(
        "--element-path",
        default="",
        help="Preview node slideIndex:tag:nth (data-nexus-edit)",
    )
    replace.add_argument(
        "--section-index",
        type=int,
        default=None,
        help="Limit the replace to this slide index",
    )
    replace.add_argument(
        "--occurrence",
        type=int,
        default=0,
        help="0 replaces every match in scope; 1 is the first",
    )
    replace.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    text = args.html.read_text(encoding="utf-8")
    applied = _apply_replacements_in_section(
        text,
        args.old,
        args.new,
        args.occurrence,
        section_index=args.section_index,
        element_path=args.element_path or None,
    )
    if isinstance(applied, dict):
        raise SystemExit(str(applied.get("error") or "replace failed"))
    updated, found, replaced, section_idx = applied
    args.output.write_text(updated, encoding="utf-8")
    scope = f"slide {section_idx}" if section_idx >= 0 else "deck"
    print(f"replaced {replaced} of {found} in {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
