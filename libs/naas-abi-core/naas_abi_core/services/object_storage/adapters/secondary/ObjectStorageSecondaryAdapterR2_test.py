from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterR2 import (
    ObjectStorageSecondaryAdapterR2,
)


def test_init_derives_endpoint_url_and_forces_auto_region(monkeypatch):
    captured_kwargs = {}

    def fake_client(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(
        "naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3.boto3.client",
        fake_client,
    )

    adapter = ObjectStorageSecondaryAdapterR2(
        account_id="my-account",
        bucket_name="my-bucket",
        access_key_id="id",
        secret_access_key="secret",
        base_prefix="datastore",
    )

    assert adapter.bucket_name == "my-bucket"
    assert adapter.base_prefix == "datastore"
    assert (
        captured_kwargs["endpoint_url"]
        == "https://my-account.r2.cloudflarestorage.com"
    )
    assert captured_kwargs["region_name"] == "auto"
