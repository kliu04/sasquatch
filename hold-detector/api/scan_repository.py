from __future__ import annotations

from abc import ABC, abstractmethod

from api.scan_service import ScanState


class ScanRepository(ABC):
    """Abstract data access layer for scans. Swap implementation for DB backing."""

    @abstractmethod
    def create(self, scan: ScanState) -> None: ...

    @abstractmethod
    def get(self, scan_id: str) -> ScanState | None: ...

    @abstractmethod
    def update(self, scan: ScanState) -> None: ...

    @abstractmethod
    def list_ids(self) -> list[str]: ...


class InMemoryScanRepository(ScanRepository):
    """In-memory implementation — replace with SQLAlchemy/etc. when a DB is added."""

    def __init__(self) -> None:
        self._store: dict[str, ScanState] = {}

    def create(self, scan: ScanState) -> None:
        self._store[scan.scan_id] = scan

    def get(self, scan_id: str) -> ScanState | None:
        return self._store.get(scan_id)

    def update(self, scan: ScanState) -> None:
        self._store[scan.scan_id] = scan

    def list_ids(self) -> list[str]:
        return list(self._store.keys())
