"""Structured errors for Clockify API interactions."""
from __future__ import annotations

from typing import Optional


class ClockifyAPIError(Exception):
    """Raised when the Clockify API returns a non-recoverable error response.

    Attributes:
        status_code: HTTP status code (None if request never completed).
        url: URL that triggered the failure.
        body: Response body snippet (truncated) — never includes auth headers.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.body = (body[:500] + "…") if body and len(body) > 500 else body
