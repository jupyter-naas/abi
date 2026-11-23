"""Every kernel stream host bounds what a caller may spool, and to which operations."""

from __future__ import annotations

import asyncio
import math
from unittest import mock

import pytest
from naas_abi_core.engine.call_context import CallContext, service_account
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSModelStreamingConfiguration,
    NATSStreamingConfiguration,
)
from naas_abi_core.engine.nats_overflow import OverflowHost
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.engine.nats_transfer import TransferHost
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

VERIFIER = TEST_TOKENS.verifier
MODULE = CallContext(principal=service_account("module/p/m"))


def _hosts() -> dict[str, tuple[TransferHost, set[str]]]:
    """Each stream host as the engine builds it, and the operations that upload."""
    return {
        "event": (EventPrimaryAdapterNATS(mock.Mock(), VERIFIER)._transfer, set()),
        "triple_store": (
            TripleStorePrimaryAdapterNATS(mock.Mock(), VERIFIER)._transfer,
            set(),
        ),
        "vector_store": (
            VectorStorePrimaryAdapterNATS(mock.Mock(), VERIFIER)._transfer,
            set(),
        ),
        "activity_log": (
            ActivityLogPrimaryAdapterNATS(mock.Mock(), VERIFIER)._transfer,
            set(),
        ),
        "dataset": (DatasetPrimaryAdapterNATS(mock.Mock(), VERIFIER)._transfer, {"write"}),
        "object_storage": (
            ObjectStoragePrimaryAdapterNATS(
                mock.Mock(),
                VERIFIER,
                transfer_options=NATSStreamingConfiguration().model_dump(),
            )._transfer,
            {"put"},
        ),
        "model_registry": (
            ModelRegistryNATS(
                mock.Mock(),
                VERIFIER,
                transfer_options=NATSModelStreamingConfiguration().model_dump(),
            ).transfer,
            {"chat", "stream", "embed"},
        ),
        "overflow": (OverflowHost(VERIFIER), {"request"}),
    }


@pytest.mark.parametrize("name", sorted(_hosts()))
def test_every_transfer_host_keeps_a_finite_upload_budget(name):
    host, uploads = _hosts()[name]

    assert host.uploads == uploads
    for budget in (
        host.max_upload_bytes,
        host.max_buffered_upload_bytes,
        host.max_caller_buffered_bytes,
    ):
        assert isinstance(budget, int) and math.isfinite(budget) and budget > 0
    assert host.max_caller_sessions < host.max_sessions or host.max_sessions == 1


@pytest.mark.parametrize(
    ("name", "operation"),
    [
        ("event", "query"),
        ("triple_store", "query"),
        ("triple_store", "export"),
        ("vector_store", "list_vectors"),
        ("activity_log", "query"),
        ("object_storage", "get"),
        ("dataset", "query"),
    ],
)
def test_transfer_write_on_a_read_only_stream_is_refused_by_every_host(name, operation):
    from naas_abi_core.engine.nats_transfer import TransferError

    host, _ = _hosts()[name]

    async def scenario():
        opened = await host._execute(
            "open", pb.OpenRequest(operation=operation), "module/p/m", None, MODULE
        )
        with pytest.raises(TransferError, match="no upload"):
            await host._execute(
                "write",
                pb.WriteRequest(id=opened.id, data=b"x" * 1024),
                "module/p/m",
                None,
                MODULE,
            )
        assert host.buffered_upload_bytes == 0
        await host.stop()

    asyncio.run(scenario())


def test_object_and_dataset_uploads_are_authorized_at_open():
    denied = PermissionDeniedError("x:Write", "x")
    storage = mock.Mock()
    storage.authorize_put_stream.side_effect = denied
    datasets = mock.Mock()
    datasets.authorize_write_stream.side_effect = denied
    objects_host = ObjectStoragePrimaryAdapterNATS(storage, VERIFIER)._transfer
    datasets_host = DatasetPrimaryAdapterNATS(datasets, VERIFIER)._transfer
    put = object_storage_pb2.GetObjectRequest(prefix="mod", key="big.bin")
    write = dataset_pb2.WriteRequest(name="rows", namespace="mod")

    async def scenario():
        for host, operation, metadata in (
            (objects_host, "put", put.SerializeToString()),
            (datasets_host, "write", write.SerializeToString()),
        ):
            with pytest.raises(PermissionDeniedError):
                await host._execute(
                    "open",
                    pb.OpenRequest(operation=operation, metadata=metadata),
                    "module/p/m",
                    None,
                    MODULE,
                )
            assert host.sessions == {}
            await host.stop()

    asyncio.run(scenario())
    storage.authorize_put_stream.assert_called_once_with("mod", "big.bin")
    datasets.authorize_write_stream.assert_called_once_with("rows", namespace="mod")
    # Nothing reached the backends.
    storage.put_object_stream.assert_not_called()
    datasets.write_stream.assert_not_called()
