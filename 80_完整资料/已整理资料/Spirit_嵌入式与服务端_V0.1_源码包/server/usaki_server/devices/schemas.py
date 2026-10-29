from typing import Any

from pydantic import BaseModel, Field


class DeviceReport(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    state: str = Field(default="online", min_length=1, max_length=32)
    firmware_version: str | None = Field(default=None, max_length=64)
    capabilities: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class DeviceReportAck(BaseModel):
    device_id: str
    state: str
    stored: bool = True
