"""Clock infrastructure for explicit time access."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Clock port for modules that need the current time."""

    def now(self) -> datetime:
        """Return the current datetime."""

    def now_iso(self) -> str:
        """Return the current datetime as an ISO string."""


class SystemClock:
    """Clock implementation backed by the system clock."""

    def now(self) -> datetime:
        """Return the current local datetime."""
        return datetime.now()

    def now_iso(self) -> str:
        """Return the current local datetime as an ISO string."""
        return self.now().isoformat()
