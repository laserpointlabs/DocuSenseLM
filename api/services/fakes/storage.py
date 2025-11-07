from __future__ import annotations

from collections import defaultdict
from typing import Dict


class InMemoryStorageService:
    """
    Simple in-memory storage drop-in replacement for StorageService.
    Stores objects in a nested dict: {bucket: {object_name: bytes}}.
    """

    def __init__(self):
        self._buckets: Dict[str, Dict[str, bytes]] = defaultdict(dict)

    def upload_file(self, bucket: str, object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
        self._buckets[bucket][object_name] = bytes(file_data)
        return f"{bucket}/{object_name}"

    def download_file(self, bucket: str, object_name: str) -> bytes:
        try:
            return self._buckets[bucket][object_name]
        except KeyError as exc:
            raise FileNotFoundError(f"{bucket}/{object_name} not found") from exc

    def delete_file(self, bucket: str, object_name: str) -> None:
        self._buckets[bucket].pop(object_name, None)

    def file_exists(self, bucket: str, object_name: str) -> bool:
        return object_name in self._buckets.get(bucket, {})

