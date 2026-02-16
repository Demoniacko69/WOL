from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class WakeRequest(BaseModel):
    mac: str
    broadcast: str | list[str] | None = None

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        value = value.strip().upper()
        if not MAC_REGEX.match(value):
            raise ValueError("Invalid MAC address format. Use AA:BB:CC:DD:EE:FF")
        return value


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mac: str
    ip: str | None = Field(default=None, max_length=255)
    broadcasts: list[str] | None = None
    shutdown_url: str | None = Field(default=None, max_length=500)

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, value: str) -> str:
        value = value.strip().upper()
        if not MAC_REGEX.match(value):
            raise ValueError("Invalid MAC address format. Use AA:BB:CC:DD:EE:FF")
        return value


class ScheduleCreate(BaseModel):
    device_id: int
    cron: str = Field(
        description="Cron expression with 5 fields, e.g. '0 7 * * 1-5'",
        min_length=9,
        max_length=100,
    )
    broadcasts: list[str] | None = None


class ApiMessage(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] | None = None
