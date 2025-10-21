"""
Main entry point for running onto2py as a module.

Usage: python -m onto2py <ttl_file> <output_file>
"""

import sys
from .onto2py import onto2py

def main():
    if len(sys.argv) < 3:
        print("Usage: python -m onto2py <ttl_file> <output_file>")
        sys.exit(1)
    
    # take a ttl file as input
    ttl_file = sys.argv[1]
    output_file = sys.argv[2]
    
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