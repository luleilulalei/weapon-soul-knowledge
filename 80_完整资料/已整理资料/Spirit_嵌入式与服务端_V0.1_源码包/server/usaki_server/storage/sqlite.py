from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from usaki_server.config import get_settings
from usaki_server.devices.schemas import DeviceReport
from usaki_server.paths import resolve_project_path


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, server_default="unknown")
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    last_seen_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )


class DeviceReportRow(Base):
    __tablename__ = "device_reports"
    __table_args__ = (
        Index("idx_device_reports_device_time", "device_id", "reported_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reported_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )


def database_path() -> str:
    settings = get_settings()
    path = resolve_project_path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@lru_cache
def _engine():
    return create_engine(
        f"sqlite:///{database_path()}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=_engine(), expire_on_commit=False)


def init_database() -> None:
    Base.metadata.create_all(_engine())


def save_device_report(report: DeviceReport) -> None:
    device_insert = insert(Device).values(
        device_id=report.device_id,
        state=report.state,
        firmware_version=report.firmware_version,
        capabilities=report.capabilities,
    )
    device_upsert = device_insert.on_conflict_do_update(
        index_elements=[Device.device_id],
        set_={
            "state": device_insert.excluded.state,
            "firmware_version": device_insert.excluded.firmware_version,
            "capabilities": device_insert.excluded.capabilities,
            "last_seen_at": func.current_timestamp(),
        },
    )

    with _session_factory().begin() as session:
        session.execute(device_upsert)
        session.add(
            DeviceReportRow(
                device_id=report.device_id,
                state=report.state,
                firmware_version=report.firmware_version,
                capabilities=report.capabilities,
                metrics=report.metrics,
            )
        )


def list_devices() -> list[dict[str, Any]]:
    session_factory = _session_factory()
    with session_factory() as session:
        devices = session.scalars(select(Device).order_by(Device.last_seen_at.desc())).all()

    return [
        {
            "device_id": device.device_id,
            "state": device.state,
            "firmware_version": device.firmware_version,
            "capabilities": device.capabilities or [],
            "first_seen_at": _format_time(device.first_seen_at),
            "last_seen_at": _format_time(device.last_seen_at),
        }
        for device in devices
    ]


def _format_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
