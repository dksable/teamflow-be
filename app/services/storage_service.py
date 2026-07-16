from pathlib import Path

from app.core.config import settings


class StorageService:
    def upload_file(self, storage_key: str, content: bytes) -> str:
        raise NotImplementedError

    def open_file_path(self, storage_key: str) -> Path:
        raise NotImplementedError

    def delete_file(self, storage_key: str) -> None:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, storage_key: str, content: bytes) -> str:
        target = self._safe_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return storage_key

    def open_file_path(self, storage_key: str) -> Path:
        path = self._safe_path(storage_key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(storage_key)
        return path

    def delete_file(self, storage_key: str) -> None:
        path = self._safe_path(storage_key)
        if path.exists() and path.is_file():
            path.unlink()

    def _safe_path(self, storage_key: str) -> Path:
        path = (self.base_dir / storage_key).resolve()
        if self.base_dir not in path.parents and path != self.base_dir:
            raise ValueError("Invalid storage key")
        return path


def get_storage_service() -> StorageService:
    if settings.storage_provider != "local":
        raise NotImplementedError("Only local storage is configured")
    return LocalStorageService(settings.holiday_upload_dir)
