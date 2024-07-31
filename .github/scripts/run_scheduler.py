#!/usr/bin/env python

# This script is used to run a scheduler defined in config.yml

import os
import sys

import papermill
import yaml
import re

class SchedulerNotFoundError(Exception):
    pass


class UnknownStepTypeError(Exception):
    pass

# Backing up environment variables.
environment_vars_backup: dict[str, str] = os.environ.copy()


def sanitize_string_to_filename(filename):
    # Remove invalid characters
    filename = re.sub(r'[\\/*?:"<>|]', '', filename)
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove leading/trailing whitespace
    filename = filename.strip()

    # Ensure filename doesn't exceed the max length
    max_filename_length = 255
    if len(filename) > max_filename_length:
        filename = filename[:max_filename_length]
    
    return filename.lower()

def get_scheduler(scheduler_name: str):
    with open("config.yml", "r") as file:
        config = yaml.safe_load(file)

    for scheduler in config["schedulers"]:
        if scheduler["name"] == scheduler_name:
            return scheduler

    raise SchedulerNotFoundError(
        f"Scheduler '{scheduler_name}' not found in config.yml"
    )


def reset_environment_vars():
    os.environ.clear()
    os.environ.update(environment_vars_backup)


def run_notebook_step(scheduler_name: str, step: dict):
    reset_environment_vars()

    if "environment_variables" in step:
        for key, value in step["environment_variables"].items():
            os.environ[key] = value

    entrypoint_path = '/'.join(step["entrypoint"].split('/')[:-1])
    notebook_name = step["entrypoint"].split('/')[-1]

    output_path = os.path.join(f"outputs/scheduler_executions/{sanitize_string_to_filename(scheduler_name)}/{sanitize_string_to_filename(step['name'])}", entrypoint_path)
    os.makedirs(output_path, exist_ok=True)

    papermill.execute_notebook(
        input_path=step["entrypoint"],
        output_path=os.path.join(output_path, notebook_name),
        parameters=step.get("inputs", {}),
    )

def run_scheduler(scheduler_name: str):
    scheduler = get_scheduler(scheduler_name)

    for step in scheduler["steps"]:
        if step.get("enabled", False) is False:
            continue

        if step.get("type") == "notebook":
            run_notebook_step(scheduler_name, step)
        else:
            raise UnknownStepTypeError(f"Unknown step type: {step.get('type')}")


if __name__ == "__main__":
    scheduler_name = sys.argv[1]
    run_scheduler(scheduler_name)
