"""The one entry a module has to the dataset service's engine-only SQL.

Catalog maintenance (``DESCRIBE``, ``ALTER``, ``CALL ducklake_*``,
``duckdb_tables()``) is SQL only the engine may run (``dataset:QueryUnchecked``).
A module that owns tables in the catalog, such as the X module, runs it through
``catalog_maintenance``: each call on the returned dataset runs as the engine,
and nothing around it does. Wrap the dataset once, call it only with the
module's own fixed statements, and never pass it a caller's SQL.
"""

from __future__ import annotations

from typing import cast

from naas_abi_core.services.dataset.DatasetPort import IDatasetPort
from naas_abi_core.services.iam.enforcement import own_storage


def catalog_maintenance(dataset: IDatasetPort) -> IDatasetPort:
    """``dataset`` with each call run as the engine. Only a dataset: it is not
    a way to run another service's calls as the engine."""
    return cast(IDatasetPort, own_storage(dataset))
