# ABI Project Makefile Documentation

## Table of Contents
- [ABI Project Makefile Documentation](#abi-project-makefile-documentation)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Environment Setup](#environment-setup)
    - [.venv](#venv)
    - [dev-build](#dev-build)
    - [install](#install)
    - [add](#add)
    - [abi-add](#abi-add)
    - [lock](#lock)
  - [Development](#development)
    - [sh](#sh)
    - [api](#api)
    - [api-prod](#api-prod)
    - [sparql-terminal](#sparql-terminal)
  - [Testing](#testing)
    - [test](#test)
  - [Data Management](#data-management)
    - [dvc-login](#dvc-login)
    - [storage-pull](#storage-pull)
    - [storage-push](#storage-push)
    - [triplestore-prod-remove](#triplestore-prod-remove)
    - [triplestore-prod-override](#triplestore-prod-override)
    - [triplestore-prod-pull](#triplestore-prod-pull)
  - [Building](#building)
    - [build](#build)
    - [build.linux.x86\_64](#buildlinuxx86_64)
  - [Agents](#agents)
    - [chat-naas-agent](#chat-naas-agent)
    - [chat-abi-agent](#chat-abi-agent)
    - [chat-ontology-agent](#chat-ontology-agent)
    - [chat-support-agent](#chat-support-agent)
  - [Docker Compose](#docker-compose)
    - [oxigraph-up](#oxigraph-up)
    - [oxigraph-down](#oxigraph-down)
    - [oxigraph-status](#oxigraph-status)
    - [dev-up](#dev-up)
    - [dev-down](#dev-down)
    - [container-up](#container-up)
    - [container-down](#container-down)
  - [Cleanup](#cleanup)
    - [clean](#clean)
  - [Help](#help)
    - [help](#help-1)
  - [Default Target](#default-target)

## Introduction

A Makefile is a special file that contains a set of instructions (called targets) used to automate common tasks in software development. Each target defines a series of commands that will be executed when you run `make <target-name>` in your terminal.

This documentation explains the Makefile used in the ABI project, which primarily uses Docker and Poetry for containerization and dependency management. The Makefile simplifies complex Docker and Poetry commands into easy-to-remember shortcuts.

## Environment Setup

### .venv

```bash
make .venv
```

This target sets up a virtual environment inside a Docker container using Poetry. It's a foundational target that many other targets depend on.

**What it does:** Creates a Python virtual environment with all project dependencies installed.

**When to use it:** You usually don't need to run this directly as other commands will trigger it when needed.

### dev-build

```bash
make dev-build
```

**What it does:** Builds all the Docker containers defined in the docker/compose/docker-compose.yml file.

**When to use it:** When you first start working with the project or when the Docker configuration changes.

### install

```bash
make install
```

**What it does:** Installs all dependencies using Poetry and specifically updates the `abi` package.

**When to use it:** When you first clone the repository or when dependencies have changed.

### add

```bash
make add dep=<package-name>
```

**What it does:** Adds a new dependency to the project using Poetry.

**When to use it:** When you need to add a new Python package to the project.

**Parameters:**
- `dep`: The name of the package to add (e.g., `make add dep=pandas`)

### abi-add

```bash
make abi-add dep=<package-name>
```

**What it does:** Adds a new dependency specifically to the `lib` directory of the project.

**When to use it:** When you need to add a new dependency to the library part of the project.

**Parameters:**
- `dep`: The name of the package to add

### lock

```bash
make lock
```

**What it does:** Updates the Poetry lock file without installing packages.

**When to use it:** When you want to update the dependency lock file after manual changes to pyproject.toml.

## Development

### sh

```bash
make sh
```

**What it does:** Opens an interactive bash shell in the ABI Docker container.

**When to use it:** When you need to run custom commands inside the container or debug issues.

### api

```bash
make api
```

**What it does:** Starts the API server on port 9879.

**When to use it:** When you want to run the API locally for development.

### api-prod

```bash
make api-prod
```

**What it does:** Builds and runs the production API server in a Docker container.

**When to use it:** When you want to test the API in a production-like environment.

### sparql-terminal

```bash
make sparql-terminal
```

**What it does:** Opens an interactive SPARQL terminal for querying the triplestore.

**When to use it:** When you need to run SPARQL queries for debugging or data exploration.

## Testing

### test

```bash
make test
```

**What it does:** Runs all the Python tests using pytest.

**When to use it:** When you want to verify that your code changes don't break existing functionality.

## Data Management

### dvc-login

```bash
make dvc-login
```

**What it does:** Sets up Data Version Control (DVC) authentication.

**When to use it:** When you need to authenticate with the DVC remote storage.

### storage-pull

```bash
make storage-pull
```

**What it does:** Pulls data from the remote storage.

**When to use it:** When you need to update your local data from the remote storage.

### storage-push

```bash
make storage-push
```

**What it does:** Pushes local data changes to the remote storage.

**When to use it:** After making changes to data that need to be shared with the team.

### triplestore-prod-remove

```bash
make triplestore-prod-remove
```

**What it does:** Removes the production triplestore data.

**When to use it:** When you need to clean up production triplestore data.

### triplestore-prod-override

```bash
make triplestore-prod-override
```

**What it does:** Overrides the production triplestore with local data.

**When to use it:** When you need to update the production triplestore with your local changes.

### triplestore-prod-pull

```bash
make triplestore-prod-pull
```

**What it does:** Pulls triplestore data from production.

**When to use it:** When you need to sync your local environment with the production triplestore.

## Building

### build

```bash
make build
```

**What it does:** Builds the Docker image for the project. This is an alias for `build.linux.x86_64`.

**When to use it:** When you need to create a production-ready Docker image.

### build.linux.x86_64

```bash
make build.linux.x86_64
```

**What it does:** Builds a Docker image specifically for Linux x86_64 architecture.

**When to use it:** When you need a Docker image that will run on x86_64/amd64 platforms.

## Agents

### chat-naas-agent

```bash
make chat-naas-agent
```

**What it does:** Starts the Naas agent in terminal mode.

**When to use it:** When you want to interact with the Naas agent through the terminal.

### chat-abi-agent

```bash
make chat-abi-agent
```

**What it does:** Starts the Abi agent in terminal mode.

**When to use it:** When you want to interact with the Abi agent through the terminal. This is the default target.

### chat-ontology-agent

```bash
make chat-ontology-agent
```

**What it does:** Starts the Ontology agent in terminal mode.

**When to use it:** When you want to interact with the Ontology agent through the terminal.

### chat-support-agent

```bash
make chat-support-agent
```

**What it does:** Starts the Support agent in terminal mode.

**When to use it:** When you want to interact with the Support agent through the terminal.

## Docker Compose

### oxigraph-up

```bash
make oxigraph-up
```

**What it does:** Starts the Oxigraph triple store container.

**When to use it:** When you need to start just the Oxigraph service without starting other containers.

### oxigraph-down

```bash
make oxigraph-down
```

**What it does:** Stops the Oxigraph triple store container.

**When to use it:** When you want to stop the Oxigraph service but keep other containers running.

### oxigraph-status

```bash
make oxigraph-status
```

**What it does:** Shows the current status of the Oxigraph container.

**When to use it:** When you want to check if Oxigraph is running and see its current state.

### dev-up

```bash
make dev-up
```

**What it does:** Starts development services including Oxigraph and YasGUI (SPARQL web UI).

**When to use it:** When you want to start the supporting services for development. Note: This does not start the ABI application itself, which is typically run with `uv` directly.

### dev-down

```bash
make dev-down
```

**What it does:** Stops all development services.

**When to use it:** When you want to shut down the development services.

### container-up

```bash
make container-up
```

**What it does:** Starts the ABI application in container mode.

**When to use it:** When you specifically need to run ABI in a Docker container instead of using `uv` directly. This is rarely needed in normal development.

### container-down

```bash
make container-down
```

**What it does:** Stops the ABI container.

**When to use it:** When you want to stop the ABI container that was started with `container-up`.

## Cleanup

### clean

```bash
make clean
```

**What it does:** Cleans up build artifacts, caches, and Docker containers.

**When to use it:** When you want to do a clean rebuild or free up disk space by removing temporary files.

## Help

### help

```bash
make help
```

**What it does:** Displays a comprehensive help menu showing all available make targets organized by category.

**When to use it:** When you're unfamiliar with the available commands or need a quick reference for what each command does.

## Default Target

The default target is `help`, which means if you run just `make` without specifying a target, it will display the help menu with all available commands.
