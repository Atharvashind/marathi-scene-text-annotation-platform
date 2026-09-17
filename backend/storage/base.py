from abc import ABC, abstractmethod


class BaseStorageProvider(ABC):
    """
    Abstract interface for image storage.
    Implement this class to add new storage backends (S3, GCS, R2, Azure Blob).
    """

    @abstractmethod
    async def save(self, data: bytes, filename: str, project_id: str) -> str:
        """
        Save file data and return an opaque storage_key.
        The storage_key is persisted in the DB and passed back to get_url/delete.
        """
        ...

    @abstractmethod
    def get_url(self, storage_key: str) -> str:
        """
        Return a URL (or path) that can be used to retrieve the file.
        For local storage this is an API path; for S3 this would be a signed URL.
        """
        ...

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Delete the file associated with the given storage_key."""
        ...
