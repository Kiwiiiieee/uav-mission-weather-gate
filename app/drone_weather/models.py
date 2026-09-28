from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class FlightDecision(str, Enum):
    GO = "GO"
    CAUTION = "CAUTION"
    NO_GO = "NO_GO"


class MissionRequest(BaseModel):
    location_name: str | None = Field(default=None, description="Optional city/place name")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_time: datetime
    duration_hours: float = Field(default=2.0, ge=0.5, le=24.0)
    mission_altitude_m: float | None = Field(default=3000.0, ge=0.0, le=4876.8)
    route_heading_deg: float = Field(default=0.0, ge=0.0, lt=360.0)
    reserve_minutes: float = Field(default=20.0, ge=0.0, le=120.0)

    @model_validator(mode="after")
    def require_location(self) -> "MissionRequest":
        has_coords = self.latitude is not None and self.longitude is not None
        has_name = bool(self.location_name and self.location_name.strip())
        if not has_coords and not has_name:
            raise ValueError("Provide either latitude/longitude or a location name.")
        return self


class Location(BaseModel):
    name: str
    latitude: float
    longitude: float
    country: str | None = None
    timezone: str | None = None
    elevation_m: float | None = None


class ConstraintCheck(BaseModel):
    name: str
    status: Literal["PASS", "WATCH", "FAIL", "UNKNOWN"]
    measured: float | str | None = None
    limit: float | str | None = None
    units: str | None = None
    message: str


class Recommendation(BaseModel):
    suggested_altitude_m: float
    suggested_true_airspeed_mps: float
    estimated_fuel_kg: float
    estimated_energy_mj: float
    latest_return_minutes: float
    rationale: list[str]


class WeatherWindow(BaseModel):
    start_time: str
    end_time: str
    samples: list[dict[str, Any]]
    worst: dict[str, Any]
    raw_open_meteo: dict[str, Any]
    raw_air_quality: dict[str, Any] | None = None


class MissionResponse(BaseModel):
    decision: FlightDecision
    score: int
    location: Location
    drone: dict[str, Any]
    checks: list[ConstraintCheck]
    recommendation: Recommendation
    weather: WeatherWindow
    notes: list[str]
