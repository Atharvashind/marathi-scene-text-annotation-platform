import re
from pathlib import Path

from backend.storage.base import BaseStorageProvider


class LocalDiskProvider(BaseStorageProvider):
    """
    Stores images on the local filesystem under {base_dir}/{project_id}/{filename}.
    storage_key format: "{project_id}/{filename}"
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    async def save(self, data: bytes, filename: str, project_id: str) -> str:
        # Sanitise filename — keep only safe characters
        safe_filename = re.sub(r'[^a-zA-Z0-9._\-]', '_', filename)
        dest_dir = self.base_dir / project_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / safe_filename
        # Avoid overwriting existing files by appending a counter
        counter = 1
        while dest_path.exists():
            stem = Path(safe_filename).stem
            suffix = Path(safe_filename).suffix
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        dest_path.write_bytes(data)
        storage_key = f"{project_id}/{dest_path.name}"
        return storage_key

    def get_url(self, storage_key: str) -> str:
        """Returns the API path to serve the file via the images file endpoint."""
        return f"/api/images/file/{storage_key}"

    async def delete(self, storage_key: str) -> None:
        target = self.base_dir / storage_key
        target.unlink(missing_ok=True)
