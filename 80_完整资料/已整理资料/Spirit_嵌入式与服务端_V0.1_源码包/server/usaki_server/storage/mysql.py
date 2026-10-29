from __future__ import annotations

# Backward-compatible import path. The service now uses SQLite storage.
from usaki_server.storage.sqlite import (  # noqa: F401
    Base,
    Device,
    DeviceReportRow,
    init_database,
    list_devices,
    save_device_report,
)
