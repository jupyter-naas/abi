"""One-off audit: dataset post totals (CLI helper)."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.api import graph_totals


def print_dataset_totals(dataset) -> None:
    totals = graph_totals(dataset)
    print("dataset_graph_totals", totals)


if __name__ == "__main__":
    raise SystemExit("Run via Engine bootstrap or import print_dataset_totals")
