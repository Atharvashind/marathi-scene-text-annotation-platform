from abc import ABC, abstractmethod
from typing import Optional


class BaseAnalyticsProvider(ABC):
    """
    Pluggable external analytics provider interface.
    Implement this to add Mixpanel, PostHog, OpenTelemetry etc.
    without modifying any router or business logic.
    """

    @abstractmethod
    async def track(
        self,
        event_type: str,
        user_id: Optional[str],
        properties: dict,
    ) -> None:
        """Fire-and-forget event to the external provider."""
        ...


class InternalOnlyProvider(BaseAnalyticsProvider):
    """Default: events are stored in PostgreSQL only, no external dispatch."""

    async def track(self, event_type: str, user_id: Optional[str], properties: dict) -> None:
        pass  # No-op — internal DB storage is handled by TelemetryService
