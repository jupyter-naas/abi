"""``python -m scenario_market``: M, run by ``abi dev up`` (``config.scenario.yaml``)."""

from launch import run_until_stopped

from scenario_market import ABIModule

if __name__ == "__main__":
    run_until_stopped(ABIModule)
