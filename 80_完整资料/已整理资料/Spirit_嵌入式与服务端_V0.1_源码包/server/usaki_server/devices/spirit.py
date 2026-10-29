"""Bounded Spirit v1 protocol. NFC UID observation is NOT authentication."""
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SpiritTelemetry(StrictModel):
    protocol: Literal["spirit.v1"] = "spirit.v1"
    uptime_ms: int = Field(ge=0, le=2**63-1)
    privacy_muted: bool
    peripherals_ready: bool = False
    touch_valid: bool = False
    expander_valid: bool = False
    sampled_us: int = Field(default=0, ge=0, le=2**63-1)
    imu_sampled_us: int = Field(default=0, ge=0, le=2**63-1)
    battery_calibrated: bool = False
    docked: bool = False
    usb_present: bool = False
    accessory_changed: bool = False
    bus_errors: int = Field(default=0, ge=0, le=2**32-1)
    imu_valid: bool = False
    accel_raw: list[Annotated[int, Field(ge=-32768, le=32767)]] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    gyro_raw: list[Annotated[int, Field(ge=-32768, le=32767)]] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    touch_mask: int = Field(default=0, ge=0, le=65535)
    battery_valid: bool = False
    battery_pin_mv: int = Field(default=-1, ge=-1, le=5000)
    battery_mv: int = Field(default=-1, ge=-1, le=20000)
    charging: bool = False
    power_good: bool = False
    accessory_present: bool = False
    haptic_ready: bool = False
    blade_ready: Literal[False] = False  # No verified blade protocol in v0.1.
    nfc_uid: str | None = Field(default=None, pattern=r"^(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{14}|[0-9A-Fa-f]{20})$")


class SpiritEffect(StrictModel):
    command_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    effect: Literal["stop", "haptic", "blade"]
    library_effect: int = Field(default=1, ge=1, le=123)
    duration_ms: int = Field(default=100, ge=1, le=1000)
    ttl_ms: int = Field(default=1000, ge=100, le=3000)


class SpiritAck(StrictModel):
    command_id: str = Field(min_length=1, max_length=64)
    status: Literal["applied", "rejected", "expired"]
    reason: str = Field(default="", max_length=160)


class SpiritMessage(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["spirit.telemetry", "spirit.ack"]
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    seq: int = Field(ge=0, le=2**31-1)
    data: dict
