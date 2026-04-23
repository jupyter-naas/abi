---
sidebar_position: 2
---

# Managing Dependencies

This document provides a comprehensive guide on how to manage dependencies in this project, which uses Poetry for dependency management and Docker for containerization.

## Project Structure Overview

The project consists of two main Python packages, each with its own dependency management:

1. `src` - The main project (root level)
2. `lib/abi` - A local library that's included as a dependency in the main project

Both packages use Poetry for dependency management, and all operations should be performed through the Makefile targets to ensure consistency.

## Adding Dependencies

### Adding dependencies to the main project (`src`)

```bash
make add dep=<library-name>
```

For example:
```bash
make add dep=requests
```

To specify a specific version:
```bash
make add dep="requests==2.28.1"
```

To add a package with extras:
```bash
make add dep="uvicorn[standard]"
```

This will:
- Add the dependency to your root `pyproject.toml`
- Update the `uv.lock` file
- Install the package in your Docker environment

### Adding dependencies to the `lib/abi` project

```bash
make abi-add dep=<library-name>
```

For example:
```bash
make abi-add dep=numpy
```

This will:
- Add the dependency to the `lib/pyproject.toml` file
- Update the `lib/uv.lock` file
- Install the package in your Docker environment

## Updating Locked Dependencies

To update the lock files after manual changes to `pyproject.toml`:

```bash
make lock
```

## Installing All Dependencies

To install all dependencies after cloning the project or after updating lock files:

```bash
make install
```

This command:
- Installs all dependencies from both the main project and the `lib/abi` project
- Updates the `lib/abi` package in the main project's environment

## Accessing Shell with Dependencies Loaded

To access a shell inside the Docker container with all dependencies loaded:

```bash
make sh
```

This allows you to run commands that depend on the installed packages without having to install Poetry or the dependencies locally.

## Development Dependencies

Development dependencies in both `pyproject.toml` files are managed in the `[dependency-groups] dev =` section. These are automatically installed when you run `make install`.

## Docker Integration

All dependency management happens inside Docker containers, so you don't need to install Poetry or any Python packages locally on your machine. The project uses Docker Compose to ensure a consistent environment for all developers.

The Docker setup ensures that:
- All dependencies are isolated from your local system
- Everyone on the team has the exact same development environment
- Production builds have the same dependencies as your development environment

## Common Dependency Management Tasks

### Recreating the environment from scratch

```bash
make clean
make install
```

### Adding a dependency only for development

Edit the appropriate `pyproject.toml` file manually to add the dependency under `[dependency-groups] dev =`, then run:

```bash
make lock
make install
```

### Resolving dependency conflicts

If you encounter dependency conflicts when adding a new package:

1. Check the error message for details on the conflict
2. Modify the appropriate `pyproject.toml` file manually to adjust version constraints
3. Run `make lock` to attempt to resolve the conflict
4. Run `make install` if the lock was successful

### Running tests with the current dependencies

```bash
make test
```

## Best Practices

1. Always use the Makefile targets to manage dependencies
2. Keep the `uv.lock` files under version control
3. When adding dependencies, consider which package (`src` or `lib/abi`) should own the dependency
4. Regularly update dependencies to keep up with security patches
5. When collaborating, pull changes and run `make install` to ensure your environment matches the updated lock files