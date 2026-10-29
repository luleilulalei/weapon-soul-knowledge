from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DeviceSession:
    device_id: str
    state: str = "connected"
    capabilities: list[str] = field(default_factory=list)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "state": self.state,
            "capabilities": self.capabilities,
            "connected_at": self.connected_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
        }


class DeviceRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, DeviceSession] = {}

    def connect(self, device_id: str, capabilities: list[str] | None = None) -> DeviceSession:
        session = DeviceSession(device_id=device_id, capabilities=capabilities or [])
        self._sessions[device_id] = session
        return session

    def touch(self, device_id: str, state: str | None = None) -> DeviceSession | None:
        session = self._sessions.get(device_id)
        if session is None:
            return None
        session.last_seen_at = datetime.now(timezone.utc)
        if state is not None:
            session.state = state
        return session

    def disconnect(self, device_id: str) -> None:
        self._sessions.pop(device_id, None)

    def list_devices(self) -> list[dict[str, Any]]:
        return [session.as_dict() for session in self._sessions.values()]


device_registry = DeviceRegistry()
