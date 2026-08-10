"""
Simple thread-safe token storage.

This module stores tokens locally for the current project.
Service-specific OAuth/refresh logic will live in the service modules.

The store itself deliberately does NOT know anything about Meta,
Google, Microsoft, or any other provider.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class TokenStore:
    """Thread-safe JSON-backed token store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def save(
        self,
        token: str,
        *,
        expires_at: float | None = None,
        **metadata: Any,
    ) -> None:
        """Save a token and optional metadata."""
        payload = {
            "access_token": token,
            "expires_at": expires_at,
            **metadata,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            temp_path = self.path.with_suffix(
                self.path.suffix + ".tmp"
            )

            temp_path.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )

            temp_path.replace(self.path)

    def load(self) -> dict[str, Any] | None:
        """Load the complete stored token record."""
        with self._lock:
            if not self.path.exists():
                return None

            try:
                return json.loads(
                    self.path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                return None

    def get_token(
        self,
        *,
        min_ttl_seconds: int = 300,
    ) -> str | None:
        """
        Return the cached access token if it exists and is not
        within min_ttl_seconds of expiry.

        If no expiry is stored, the token is considered usable.
        """
        record = self.load()

        if not record:
            return None

        token = record.get("access_token")

        if not token:
            return None

        expires_at = record.get("expires_at")

        if expires_at is not None:
            try:
                remaining = float(expires_at) - time.time()

                if remaining <= min_ttl_seconds:
                    return None

            except (TypeError, ValueError):
                return None

        return token

    def clear(self) -> None:
        """Delete the stored token."""
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass