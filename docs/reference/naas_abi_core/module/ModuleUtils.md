# ModuleUtils

## What it is
A small utility module that locates the filesystem directory containing the Python source file where a given class is defined.

## Public API
- `find_class_module_root_path(class_: type) -> pathlib.Path`
  - Returns the directory path (`Path`) of the file that defines `class_`.

## Configuration/Dependencies
- Standard library only:
  - `inspect.getfile` (to resolve the defining file for a class)
  - `pathlib.Path` (for path handling)

## Usage
```python
from naas_abi_core.module.ModuleUtils import find_class_module_root_path

class MyClass:
    pass

print(find_class_module_root_path(MyClass))
# -> Path to the directory containing the file where MyClass is defined
```

## Caveats
- `inspect.getfile(class_)` can fail for classes without an associated Python source file (e.g., some built-ins, dynamically created classes).
