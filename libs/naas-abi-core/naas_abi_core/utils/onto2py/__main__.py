"""
Main entry point for running onto2py as a module.

Usage: python -m onto2py <ttl_file> [<output_file>]

If <output_file> is omitted, the .py file is written next to the .ttl file
(same directory and base name, with a .py extension).
"""

import sys
from pathlib import Path
from .onto2py import onto2py

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m onto2py <ttl_file> [<output_file>]")
        sys.exit(1)

    ttl_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_file = str(Path(ttl_file).with_suffix(".py"))

    try:
        python_code = onto2py(ttl_file)
        with open(output_file, "w") as f:
            f.write(python_code)
        print(f"✅ Python code written to {output_file}")
    except Exception as e:
        print(f"❌ Error converting TTL file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
