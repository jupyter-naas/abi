from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)

R2_REGION = "auto"


class ObjectStorageSecondaryAdapterR2(ObjectStorageSecondaryAdapterS3):
    """Cloudflare R2 implementation of the Object Storage adapter.

    R2 exposes an S3-compatible API, so this adapter reuses the S3 adapter
    wholesale and only derives the account-scoped endpoint and the "auto"
    region R2 requires for request signing.
    """

    def __init__(
        self,
        account_id: str,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        base_prefix: str = "",
    ):
        """Initialize R2 adapter with account id, bucket name and credentials.

        Args:
            account_id (str): Cloudflare account ID (used to derive the R2 endpoint)
            bucket_name (str): Name of the R2 bucket to use
            access_key_id (str): R2 access key ID
            secret_access_key (str): R2 secret access key
            base_prefix (str, optional): Base prefix to prepend to all operations. Defaults to ""
        """
        super().__init__(
            bucket_name=bucket_name,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            base_prefix=base_prefix,
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            region_name=R2_REGION,
        )
