from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter

from usaki_server.devices.registry import device_registry

from usaki_server.api.model import (
    ApiResponse,
    DeviceConfigGetRequest,
    DeviceConfigUpdateRequest,
    DeviceConnectRequest,
    DeviceConnectResponse,
    DeviceDetailRequest,
    DeviceRegisterRequest,
    now_ms
)

from usaki_server.storage.sqlite import list_devices as list_persisted_devices
from usaki_server.storage.sqlite import save_device_report

router = APIRouter()

_devices: dict[str, dict[str, Any]] = {}
_configs: dict[str, dict[str, Any]] = {}
_config_versions: dict[str, int] = {}

DEFAULT_CONFIG: dict[str, Any] = {
    "volume": 70,
    "brightness": 80,
    "language": "zh-CN",
    "nickname": "Spirit",
    "sleep_policy": {
        "enabled": True,
        "start": "22:00",
        "end": "07:00",
    },
    "animation_speed": 1.0,
}



@router.post("/connect", response_model=ApiResponse)
async def connect_device(request: DeviceConnectRequest) -> ApiResponse:
    device_registry.connect(request.device_id, request.capabilities.as_list())
    _devices.setdefault(request.device_id, {})
    _devices[request.device_id].update(
        {
            "device_id": request.device_id,
            "firmware_version": request.firmware_version,
            "hardware_version": request.hardware_version,
            "device_token": 'auth_token_placeholder',  # Placeholder for the device token
        }
    )
    _ensure_device_config(request.device_id)
    return ApiResponse(data=DeviceConnectResponse(
        token=_devices[request.device_id]["device_token"],
        config_version=_config_versions.get(request.device_id, 1),
    ).model_dump(exclude_none=True))

@router.post("/register", response_model=ApiResponse)
async def register_device(request: DeviceRegisterRequest) -> ApiResponse:
    token = _devices.get(request.device_id, {}).get("device_token") or (
        f"token_{secrets.token_urlsafe(24)}"
    )
    _devices[request.device_id] = {
        **request.model_dump(),
        "device_token": token,
        "registered_at": now_ms(),
    }
    _ensure_device_config(request.device_id)
    return ApiResponse(data={"device_id": request.device_id, "device_token": token})


@router.post("/detail", response_model=ApiResponse)
async def device_detail(request: DeviceDetailRequest) -> ApiResponse:
    device = _devices.get(request.device_id, {})
    session = device_registry.touch(request.device_id)
    return ApiResponse(
        data={
            "device_id": request.device_id,
            "name": _ensure_device_config(request.device_id).get("nickname", "Spirit"),
            "online": session is not None,
            "firmware_version": device.get("firmware_version"),
            "config_version": _config_versions.get(request.device_id, 1),
        }
    )


@router.post("/config/get", response_model=ApiResponse)
async def device_config_get(request: DeviceConfigGetRequest) -> ApiResponse:
    config = _ensure_device_config(request.device_id)
    return ApiResponse(data={**config, "config_version": _config_versions.get(request.device_id, 1)})


@router.post("/config/update", response_model=ApiResponse)
async def device_config_update(request: DeviceConfigUpdateRequest) -> ApiResponse:
    config = _ensure_device_config(request.device_id)
    config.update(request.config)
    _config_versions[request.device_id] = _config_versions.get(request.device_id, 1) + 1
    return ApiResponse(data={"config_version": _config_versions[request.device_id]})


def _ensure_device_config(device_id: str) -> dict[str, Any]:
    if device_id not in _configs:
        _configs[device_id] = dict(DEFAULT_CONFIG)
        _config_versions[device_id] = 1
    return _configs[device_id]
