"""
Safe CSV logging utilities.

Writes are performed through a temporary file and atomic replacement
so an interrupted write is less likely to corrupt the existing CSV.
"""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Iterable, Mapping


class CsvLogger:
    """Thread-safe CSV logger with atomic file replacement."""

    def __init__(
        self,
        path: str | Path,
        fieldnames: Iterable[str],
    ) -> None:
        self.path = Path(path)
        self.fieldnames = list(fieldnames)
        self._lock = threading.Lock()

    def append(self, row: Mapping[str, object]) -> None:
        """Append one row while preserving existing CSV data."""
        with self._lock:
            existing_rows = self._read_rows()

            existing_rows.append(
                {
                    field: row.get(field, "")
                    for field in self.fieldnames
                }
            )

            self._write_rows(existing_rows)

    def append_many(
        self,
        rows: Iterable[Mapping[str, object]],
    ) -> None:
        """Append multiple rows in one atomic write."""
        with self._lock:
            existing_rows = self._read_rows()

            for row in rows:
                existing_rows.append(
                    {
                        field: row.get(field, "")
                        for field in self.fieldnames
                    }
                )

            self._write_rows(existing_rows)

    def read(self) -> list[dict[str, str]]:
        """Return all currently stored rows."""
        with self._lock:
            return self._read_rows()

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []

        try:
            with self.path.open(
                "r",
                newline="",
                encoding="utf-8-sig",
            ) as handle:
                return list(csv.DictReader(handle))
        except (OSError, csv.Error):
            return []

    def _write_rows(
        self,
        rows: Iterable[Mapping[str, object]],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        try:
            with temp_path.open(
                "w",
                newline="",
                encoding="utf-8-sig",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=self.fieldnames,
                    extrasaction="ignore",
                )

                writer.writeheader()

                for row in rows:
                    writer.writerow(row)

            temp_path.replace(self.path)

        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)