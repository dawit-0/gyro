"""Abstract base provider and shared event type."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ProviderEvent:
    """Unified event emitted by all providers.

    ``type`` values match the existing output schema consumed by the frontend:
      - "event"     — lifecycle markers (started, exited, …)
      - "assistant" — incremental text from the model
      - "result"    — final answer / output
      - "text"      — raw / unparsed text
      - "error"     — error message
    """
    type: str
    content: str


class BaseProvider(ABC):
    """Interface that every execution provider must implement."""

    pid: int | None = None  # Only set for subprocess-based providers

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        model: str,
        work_dir: str,
        permissions: dict,
    ) -> AsyncIterator[ProviderEvent]:
        """Yield streaming events. The orchestrator consumes these uniformly."""
        ...  # pragma: no cover

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel the running execution."""
        ...  # pragma: no cover
