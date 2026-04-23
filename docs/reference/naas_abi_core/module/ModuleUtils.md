# ModuleUtils

## What it is
Utility module providing a helper to locate the filesystem directory containing the source file where a given Python class is defined.

## Public API
- `find_class_module_root_path(class_: type) -> pathlib.Path`
  - Returns the directory path (`Path`) of the Python file that defines `class_`.

## Configuration/Dependencies
- Standard library only:
  - `inspect.getfile`
  - `pathlib.Path`

## Usage
```python
from naas_abi_core.module.ModuleUtils import find_class_module_root_path

class MyClass:
    pass

print(find_class_module_root_path(MyClass))  # e.g., PosixPath('/path/to/your/module')
```

## Caveats
- Requires a class with an inspectable source file; `inspect.getfile()` may fail for some built-in/extension types or dynamically created classes without a file-backed definition.
- Despite the name, it returns the class *file’s parent directory*, not a package/module “root” directory.
