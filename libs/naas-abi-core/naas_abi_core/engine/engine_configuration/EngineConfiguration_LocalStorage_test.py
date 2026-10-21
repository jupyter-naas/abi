"""Where each service's data lives, for deploys without downtime.

docs/adr/20261006_single-serving-engine.md: an engine handing over to another
must not keep data on its own host.
"""

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ServicesConfiguration,
)

ALL = (
    "activity_log",
    "cache",
    "coding_environment",
    "dataset",
    "document",
    "email",
    "event",
    "kv",
    "object_storage",
    "secret",
    "source_control",
    "triple_store",
    "vector_store",
)

S3 = {
    "bucket_name": "abi",
    "base_prefix": "abi",
    "access_key_id": "key",
    "secret_access_key": "secret",
}
NATS = {"nats_url": "nats://nats:4222", "jwt_secret": "x" * 32}

SHARED = {
    "document": {
        "document_adapter": {
            "adapter": "postgresql",
            "config": {"dsn": "postgresql://abi:abi@db:5432/abi"},
        }
    },
    "object_storage": {"object_storage_adapter": {"adapter": "s3", "config": S3}},
    "dataset": {
        "dataset_adapter": {
            "adapter": "ducklake",
            "config": {
                "catalog": "postgres:postgresql://abi:abi@db:5432/ducklake",
                "data_path": "s3://abi/datasets/",
                "s3_endpoint": "http://minio:9000",
            },
        }
    },
    "triple_store": {
        "triple_store_adapter": {
            "adapter": "oxigraph",
            "config": {"oxigraph_url": "http://oxigraph:7878"},
        }
    },
    "vector_store": {
        "vector_store_adapter": {"adapter": "qdrant", "config": {"host": "qdrant"}}
    },
    "kv": {
        "kv_adapter": {
            "adapter": "redis",
            "config": {"redis_url": "redis://redis:6379/0"},
        }
    },
    "cache": {
        "adapters": [
            {
                "adapter": "redis",
                "tier": "hot",
                "config": {"redis_url": "redis://redis:6379/0"},
            },
            {"adapter": "object_storage", "tier": "cold", "config": {}},
        ]
    },
    "coding_environment": {
        "coding_environment_adapter": {
            "adapter": "coder",
            "config": {
                "access_url": "https://coder.example.com",
                "wildcard_access_url": "*.coder.example.com",
                "admin_token": "token",
            },
        }
    },
    "source_control": {
        "source_control_adapter": {
            "adapter": "forgejo",
            "config": {
                "base_url": "https://forge.example.com",
                "admin_token": "token",
            },
        }
    },
    "event": {
        "event_adapter": {
            "adapter": "postgresql",
            "config": {"dsn": "postgresql://abi:abi@db:5432/abi"},
        }
    },
    "activity_log": {"activity_log_adapter": {"adapter": "document"}},
}


def local(services: dict | None = None, owned=ALL) -> dict[str, str]:
    return ServicesConfiguration.model_validate(services or {}).local_backends(owned)


def test_the_default_services_keep_their_data_on_this_host():
    found = local()

    assert set(found) == {
        "activity_log",
        "cache",
        "coding_environment",
        "dataset",
        "document",
        "event",
        "kv",
        "object_storage",
        "source_control",
        "triple_store",
        "vector_store",
    }
    assert "storage/documents.sqlite" in found["document"]
    assert "storage/datastore" in found["object_storage"]
    assert "embedded Oxigraph" in found["triple_store"]


def test_shared_backends_report_nothing():
    assert local(SHARED) == {}


def test_only_the_services_this_engine_owns_are_reported():
    assert set(local(owned=("document", "kv"))) == {"document", "kv"}


@pytest.mark.parametrize(
    ("service", "block", "reason"),
    [
        (
            "document",
            {"document_adapter": {"adapter": "sqlite", "config": {"path": "a.db"}}},
            "a.db",
        ),
        (
            "object_storage",
            {
                "object_storage_adapter": {
                    "adapter": "fs",
                    "config": {"base_path": "/data"},
                }
            },
            "/data",
        ),
        (
            "dataset",
            {
                "dataset_adapter": {
                    "adapter": "ducklake",
                    "config": {
                        "catalog": "postgres:postgresql://db/ducklake",
                        "data_path": "storage/datasets/",
                    },
                }
            },
            "storage/datasets/",
        ),
        (
            "dataset",
            {
                "dataset_adapter": {
                    "adapter": "ducklake",
                    "config": {
                        "catalog": "sqlite:storage/datasets.sqlite",
                        "data_path": "s3://abi/datasets/",
                        "s3_endpoint": "http://minio:9000",
                    },
                }
            },
            "sqlite:storage/datasets.sqlite",
        ),
        (
            "vector_store",
            {"vector_store_adapter": {"adapter": "qdrant_in_memory", "config": {}}},
            "embedded Qdrant",
        ),
        (
            "vector_store",
            {
                "vector_store_adapter": {
                    "adapter": "sqlite_vec",
                    "config": {"persistence_path": "v.db"},
                }
            },
            "v.db",
        ),
        (
            "kv",
            {"kv_adapter": {"adapter": "python", "config": {}}},
            "this process",
        ),
        (
            "email",
            {"email_adapter": {"adapter": "filesystem", "config": {}}},
            "storage/email",
        ),
        (
            "event",
            {"event_adapter": {"adapter": "sqlite", "config": {}}},
            "storage/events/events.sqlite",
        ),
        (
            "source_control",
            {
                "source_control_adapter": {
                    "adapter": "local_git",
                    "config": {"repos_root": "/git"},
                }
            },
            "/git",
        ),
    ],
)
def test_local_backends_say_where_their_data_is(service, block, reason):
    found = local({**SHARED, service: block}, owned=(service,))

    assert reason in found[service]


def test_remote_services_are_not_this_engine_s_data():
    services = {
        **SHARED,
        "document": {"document_adapter": {"adapter": "nats_rpc", "config": NATS}},
        "kv": {"kv_adapter": {"adapter": "nats_rpc", "config": NATS}},
    }

    assert local(services) == {}


def test_a_custom_adapter_must_declare_shared_storage():
    custom = {"adapter": "custom", "python_module": "x", "module_callable": "y"}

    found = local({**SHARED, "kv": {"kv_adapter": custom}}, owned=("kv",))
    assert "shared_storage" in found["kv"]

    shared = {**custom, "shared_storage": True}
    assert local({**SHARED, "kv": {"kv_adapter": shared}}, owned=("kv",)) == {}


def test_cache_tiers_follow_the_stores_they_use():
    on_local_storage = {
        **SHARED,
        "object_storage": {
            "object_storage_adapter": {"adapter": "fs", "config": {"base_path": "/d"}}
        },
    }

    found = local(on_local_storage, owned=("cache",))
    assert "object_storage" in found["cache"]

    on_local_kv = {
        **SHARED,
        "kv": {"kv_adapter": {"adapter": "python", "config": {}}},
        "cache": {"adapters": [{"adapter": "keyvalue", "config": {}}]},
    }
    assert "keyvalue" in local(on_local_kv, owned=("cache",))["cache"]


def test_a_triple_store_on_object_storage_follows_that_storage():
    def on(object_storage_adapter):
        return {
            **SHARED,
            "triple_store": {
                "triple_store_adapter": {
                    "adapter": "object_storage",
                    "config": {
                        "object_storage_service": {
                            "object_storage_adapter": object_storage_adapter
                        }
                    },
                }
            },
        }

    assert local(on({"adapter": "s3", "config": S3}), owned=("triple_store",)) == {}
    found = local(
        on({"adapter": "fs", "config": {"base_path": "/t"}}), owned=("triple_store",)
    )
    assert "/t" in found["triple_store"]


def test_an_activity_log_in_documents_is_as_shared_as_the_document_service():
    in_documents = {"activity_log_adapter": {"adapter": "document"}}

    assert (
        local({**SHARED, "activity_log": in_documents}, owned=("activity_log",)) == {}
    )
    on_sqlite = {
        **SHARED,
        "activity_log": in_documents,
        "document": {"document_adapter": {"adapter": "sqlite", "config": {}}},
    }
    found = local(on_sqlite, owned=("activity_log",))
    assert "storage/documents.sqlite" in found["activity_log"]
