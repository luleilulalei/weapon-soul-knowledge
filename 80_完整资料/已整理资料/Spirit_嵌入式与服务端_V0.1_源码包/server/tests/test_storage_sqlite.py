from sqlalchemy.dialects import sqlite
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.schema import CreateIndex, CreateTable

from usaki_server.storage.sqlite import Device, DeviceReportRow


def test_device_tables_compile_for_sqlite() -> None:
    dialect = sqlite.dialect()

    device_ddl = str(CreateTable(Device.__table__).compile(dialect=dialect))
    report_ddl = str(CreateTable(DeviceReportRow.__table__).compile(dialect=dialect))
    report_indexes = {
        str(CreateIndex(index).compile(dialect=dialect))
        for index in DeviceReportRow.__table__.indexes
    }

    assert "CREATE TABLE devices" in device_ddl
    assert "capabilities JSON" in device_ddl
    assert "last_seen_at DATETIME" in device_ddl
    assert "metrics JSON" in report_ddl
    assert "FOREIGN KEY(device_id) REFERENCES devices (device_id) ON DELETE CASCADE" in report_ddl
    assert (
        "CREATE INDEX idx_device_reports_device_time "
        "ON device_reports (device_id, reported_at)"
    ) in report_indexes


def test_device_upsert_compiles_for_sqlite() -> None:
    dialect = sqlite.dialect()
    stmt = insert(Device).values(
        device_id="device-001",
        state="online",
        firmware_version="0.1.0",
        capabilities=["mic"],
    )
    upsert = stmt.on_conflict_do_update(
        index_elements=[Device.device_id],
        set_={"state": stmt.excluded.state},
    )

    compiled = str(upsert.compile(dialect=dialect))

    assert "INSERT INTO devices" in compiled
    assert "ON CONFLICT (device_id) DO UPDATE SET state = excluded.state" in compiled
