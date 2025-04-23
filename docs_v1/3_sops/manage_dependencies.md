# Manage Dependencies

## Add a new Python dependency to `src` project

```bash
make add dep=<library-name>
```

This will automatically:
- Add the dependency to your `pyproject.toml`
- Update the `poetry.lock` file
- Install the package in your virtual environment

## Add a new Python dependency to `lib/abi` project

```bash
make abi-add dep=<library-name>
```