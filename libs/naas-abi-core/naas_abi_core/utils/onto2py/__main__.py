"""
Main entry point for running onto2py as a module.

Usage: python -m onto2py <ttl_file> [<output_file>]
       python -m onto2py --check-process-connectivity <ttl_file>...
       python -m onto2py --module <module_dir>... [--force]

If <output_file> is omitted, the .py file is written next to the .ttl file
(same directory and base name, with a .py extension).

``--check-process-connectivity`` writes nothing: it lists every continuant a file
declares that no process is tied to, and exits 1 if there is one.

``--module`` runs onto2py on a module's process slices, consolidates them into
``ontologies/modules/<Module>Ontology.ttl``, then runs onto2py on its module
ontologies. Unchanged files are skipped by hash; ``--force`` regenerates all.
"""

import sys
from pathlib import Path

from .module_codegen import onto2py_module
from .onto2py import check_continuants_connected_to_process, onto2py


def check_process_connectivity(ttl_files: list[str]) -> int:
    failed = 0
    for ttl_file in ttl_files:
        issues = check_continuants_connected_to_process(ttl_file, raise_error=False)
        if not issues:
            print(f"✅ {ttl_file}: every continuant is connected to a process")
            continue
        failed += len(issues)
        print(f"❌ {ttl_file}: {len(issues)} continuant(s) not connected to a process")
        for issue in issues:
            print(f"   {issue['subject']}: {issue['message']}")
    return 1 if failed else 0


def generate_modules(args: list[str]) -> int:
    force = "--force" in args
    module_dirs = [a for a in args if a != "--force"]
    failed = 0
    for module_dir in module_dirs:
        report = onto2py_module(module_dir, force=force)
        print(
            f"📦 {module_dir}: {len(report.generated)} generated, "
            f"{len(report.skipped)} unchanged"
        )
        if report.consolidated:
            print(f"   consolidated processes into {report.consolidated}")
        for path, error in report.errors.items():
            failed += 1
            print(f"❌ {path}: {error}")
    return 1 if failed else 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m onto2py <ttl_file> [<output_file>]")
        sys.exit(1)

    if sys.argv[1] == "--check-process-connectivity":
        if len(sys.argv) < 3:
            print("Usage: python -m onto2py --check-process-connectivity <ttl_file>...")
            sys.exit(1)
        sys.exit(check_process_connectivity(sys.argv[2:]))

    if sys.argv[1] == "--module":
        if len(sys.argv) < 3:
            print("Usage: python -m onto2py --module <module_dir>... [--force]")
            sys.exit(1)
        sys.exit(generate_modules(sys.argv[2:]))

    ttl_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        python_code = onto2py(ttl_file)
        # onto2py already wrote <ttl>.py with its source-hash marker; writing it
        # again here would strip the marker and defeat the cache.
        if output_file is not None:
            with open(output_file, "w") as f:
                f.write(python_code)
        print(
            f"✅ Python code written to {output_file or Path(ttl_file).with_suffix('.py')}"
        )
    except Exception as e:  # noqa: BLE001
        print(f"❌ Error converting TTL file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
