# ModuleUtils

## What it is
Small utility module for:
- Determining the dotted *package* associated with the folder that “holds” a class.
- Locating the filesystem directory containing the source file where a given class is defined.

## Public API
- `module_package(class_: type) -> str`
  - Returns a dotted package name for the folder that should contain related components (e.g., `agents/`, `workflows/`, `models/`).
  - Uses `sys.modules[class_.__module__]` and the module’s `__package__` when available; otherwise derives the package from `__module__` and whether the module file is an `__init__.py`.

- `find_class_module_root_path(class_: type) -> pathlib.Path`
  - Returns a `Path` pointing to the **parent directory of the file** where `class_` is defined.

## Configuration/Dependencies
- Standard library:
  - `inspect.getfile`
  - `sys.modules`
  - `pathlib.Path`

## Usage
```python
from naas_abi_core.module.ModuleUtils import module_package, find_class_module_root_path

class MyClass:
    pass

print(module_package(MyClass))               # e.g., "__main__" (in scripts) or "my_pkg"
print(find_class_module_root_path(MyClass))  # directory containing the defining file
```

## Caveats
- `inspect.getfile()` may fail for built-in/extension types or dynamically created classes without a file-backed definition.
- Despite the name, `find_class_module_root_path()` returns the **class file’s parent directory**, not a project/package “root”.
- `module_package()` depends on `sys.modules` and module attributes; unusual import setups may affect results.
