import boto3
import pytest
from moto import mock_aws

from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)
from naas_abi_core.services.object_storage.tests.object_storage__secondary_adapter__generic_test import (
    ObjectStorageSecondaryAdapterContract,
)


class _DummyS3Client:
    pass


def test_get_full_key_normalizes_slashes_for_prefix_and_key(monkeypatch):
    monkeypatch.setattr(
        "naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3.boto3.client",
        lambda *args, **kwargs: _DummyS3Client(),
    )

    adapter = ObjectStorageSecondaryAdapterS3(
        bucket_name="abi",
        access_key_id="id",
        secret_access_key="secret",
        base_prefix="datastore/",
    )

    full_key = adapter._ObjectStorageSecondaryAdapterS3__get_full_key(
        "/pernod_ricard/inputs/", "/workbook.xlsx"
    )

    assert full_key == "datastore/pernod_ricard/inputs/workbook.xlsx"


def test_get_full_key_keeps_prefix_trailing_slash_for_list_operations(monkeypatch):
    monkeypatch.setattr(
        "naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3.boto3.client",
        lambda *args, **kwargs: _DummyS3Client(),
    )

    adapter = ObjectStorageSecondaryAdapterS3(
        bucket_name="abi",
        access_key_id="id",
        secret_access_key="secret",
        base_prefix="datastore",
    )

    full_prefix = adapter._ObjectStorageSecondaryAdapterS3__get_full_key(
        "/pernod_ricard/inputs/"
    )

    assert full_prefix == "datastore/pernod_ricard/inputs/"


class TestObjectStorageSecondaryAdapterS3(ObjectStorageSecondaryAdapterContract):
    @pytest.fixture
    def adapter(self):
        with mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="abi")
            yield ObjectStorageSecondaryAdapterS3(
                bucket_name="abi",
                access_key_id="testing",
                secret_access_key="testing",
                base_prefix="datastore",
                region_name="us-east-1",
            )
