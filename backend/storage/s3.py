from backend.storage.base import BaseStorageProvider


class S3Provider(BaseStorageProvider):
    """
    AWS S3 storage provider stub.
    Implement using boto3/aioboto3 when S3 support is needed.
    """

    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self.region = region
        # boto3 client would be initialized here

    async def save(self, data: bytes, filename: str, project_id: str) -> str:
        raise NotImplementedError("S3Provider is not yet implemented")

    def get_url(self, storage_key: str) -> str:
        raise NotImplementedError("S3Provider is not yet implemented")

    async def delete(self, storage_key: str) -> None:
        raise NotImplementedError("S3Provider is not yet implemented")
