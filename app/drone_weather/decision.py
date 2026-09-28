from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
from typing import Any

from drone_weather.drone_parameters import TB2, DroneParameters, as_public_dict
from drone_weather.models import ConstraintCheck, FlightDecision, MissionRequest, MissionResponse, Recommendation, WeatherWindow, Location
from drone_weather.open_meteo import merge_air_quality, slice_hourly_window
from drone_weather.performance import best_range_speed, steady_level_performance


NO_GO_WEATHER_CODES = {48, 66, 67, 75, 82, 86, 95, 96, 99}
CAUTION_WEATHER_CODES = {45, 51, 53, 55, 61, 63, 65, 71, 73, 80, 81, 85}


@dataclass(frozen=True)
class WeatherPolicy:
    steady_wind_no_go_fraction_of_cruise: float = 0.35
    steady_wind_watch_fraction_of_cruise: float = 0.25
    gust_no_go_fraction_of_cruise: float = 0.45
    gust_watch_fraction_of_cruise: float = 0.35
    crosswind_no_go_fraction_of_takeoff: float = 0.35
    crosswind_watch_fraction_of_takeoff: float = 0.25
    visibility_no_go_m: float = 3000.0
    visibility_watch_m: float = 8000.0
    temp_no_go_low_c: float = -20.0
    temp_no_go_high_c: float = 45.0
    temp_watch_low_c: float = -10.0
    temp_watch_high_c: float = 35.0
    precipitation_no_go_mmh: float = 2.0
    precipitation_watch_mmh: float = 0.2
    snow_no_go_cmph: float = 0.5
    snow_watch_cmph: float = 0.1
    humidity_watch_percent: float = 90.0
    pm10_no_go_ugpm3: float = 150.0
    pm10_watch_ugpm3: float = 80.0
    dust_no_go_ugpm3: float = 150.0
    dust_watch_ugpm3: float = 80.0


def evaluate_mission(
    request: MissionRequest,
    location: Location,
    forecast: dict[str, Any],
    air_quality: dict[str, Any] | None,
    drone: DroneParameters = TB2,
    policy: WeatherPolicy = WeatherPolicy(),
) -> MissionResponse:
    samples = merge_air_quality(slice_hourly_window(forecast, request), air_quality)
    worst = summarize_worst(samples)
    checks = build_checks(worst, request, drone, policy)
    recommendation = build_recommendation(worst, request, drone, checks)
    decision = decide(checks)
    score = score_checks(checks)
    return MissionResponse(
        decision=decision,
        score=score,
        location=location,
        drone=as_public_dict(),
        checks=checks,
        recommendation=recommendation,
        weather=WeatherWindow(
            start_time=samples[0]["time"],
            end_time=samples[-1]["time"],
            samples=samples,
            worst=worst,
            raw_open_meteo=forecast,
            raw_air_quality=air_quality,
        ),
        notes=[
            "Drone parameters are mirrored from the existing MATLAB model and are not modified by this app.",
            "Open-Meteo does not provide building, tree, wire, or local obstacle clearance. Add GIS/DEM/obstacle data before using the terrain result operationally.",
            "This is an academic mission-readiness filter, not an operational flight authorization system.",
        ],
    )


def summarize_worst(samples: list[dict[str, Any]]) -> dict[str, Any]:
    def max_of(key: str, default: float = 0.0) -> float:
        values = [row.get(key) for row in samples if row.get(key) is not None]
        return max(values) if values else default

    def min_of(key: str, default: float = 0.0) -> float:
        values = [row.get(key) for row in samples if row.get(key) is not None]
        return min(values) if values else default

    return {
        "max_temperature_2m_c": max_of("temperature_2m"),
        "min_temperature_2m_c": min_of("temperature_2m"),
        "max_apparent_temperature_c": max_of("apparent_temperature"),
        "max_relative_humidity_percent": max_of("relative_humidity_2m"),
        "max_precipitation_probability_percent": max_of("precipitation_probability"),
        "max_precipitation_mmh": max_of("precipitation"),
        "max_rain_mmh": max_of("rain"),
        "max_snowfall_cmph": max_of("snowfall"),
        "min_visibility_m": min_of("visibility", 100000.0),
        "max_wind_speed_mps": max_of("wind_speed_10m"),
        "max_wind_gust_mps": max_of("wind_gusts_10m"),
        "dominant_wind_direction_deg": direction_at_max(samples),
        "max_weather_code": int(max_of("weather_code")),
        "max_cloud_cover_percent": max_of("cloud_cover"),
        "max_pm10_ugpm3": max_of("pm10"),
        "max_pm25_ugpm3": max_of("pm2_5"),
        "max_dust_ugpm3": max_of("dust"),
    }


def direction_at_max(samples: list[dict[str, Any]]) -> float:
    best = max(samples, key=lambda row: row.get("wind_speed_10m") or -1)
    return float(best.get("wind_direction_10m") or 0.0)


def build_checks(
    worst: dict[str, Any],
    request: MissionRequest,
    drone: DroneParameters,
    policy: WeatherPolicy,
) -> list[ConstraintCheck]:
    cruise = drone.cruise_speed_mps
    takeoff = drone.takeoff_reference_speed_mps
    rel = abs(angle_diff_deg(worst["dominant_wind_direction_deg"], request.route_heading_deg))
    crosswind = worst["max_wind_speed_mps"] * abs(__import__("math").sin(radians(rel)))

    checks = [
        numeric_check(
            "Steady wind",
            worst["max_wind_speed_mps"],
            policy.steady_wind_watch_fraction_of_cruise * cruise,
            policy.steady_wind_no_go_fraction_of_cruise * cruise,
            "m/s",
            lower_is_better=True,
        ),
        numeric_check(
            "Wind gust",
            worst["max_wind_gust_mps"],
            policy.gust_watch_fraction_of_cruise * cruise,
            policy.gust_no_go_fraction_of_cruise * cruise,
            "m/s",
            lower_is_better=True,
        ),
        numeric_check(
            "Crosswind component",
            crosswind,
            policy.crosswind_watch_fraction_of_takeoff * takeoff,
            policy.crosswind_no_go_fraction_of_takeoff * takeoff,
            "m/s",
            lower_is_better=True,
        ),
        numeric_check(
            "Precipitation",
            worst["max_precipitation_mmh"],
            policy.precipitation_watch_mmh,
            policy.precipitation_no_go_mmh,
            "mm/h",
            lower_is_better=True,
        ),
        numeric_check(
            "Snowfall",
            worst["max_snowfall_cmph"],
            policy.snow_watch_cmph,
            policy.snow_no_go_cmph,
            "cm/h",
            lower_is_better=True,
        ),
        numeric_check(
            "Visibility",
            worst["min_visibility_m"],
            policy.visibility_watch_m,
            policy.visibility_no_go_m,
            "m",
            lower_is_better=False,
        ),
        temperature_check(worst, policy),
        weather_code_check(worst["max_weather_code"]),
        humidity_check(worst, policy),
        particulate_check("PM10 or smoke/dust proxy", worst["max_pm10_ugpm3"], policy.pm10_watch_ugpm3, policy.pm10_no_go_ugpm3),
        particulate_check("Dust aerosol proxy", worst["max_dust_ugpm3"], policy.dust_watch_ugpm3, policy.dust_no_go_ugpm3),
        altitude_check(request, drone),
    ]
    return checks


def numeric_check(
    name: str,
    measured: float,
    watch: float,
    fail: float,
    units: str,
    lower_is_better: bool,
) -> ConstraintCheck:
    if lower_is_better:
        status = "FAIL" if measured >= fail else "WATCH" if measured >= watch else "PASS"
        limit = fail
    else:
        status = "FAIL" if measured <= fail else "WATCH" if measured <= watch else "PASS"
        limit = fail
    return ConstraintCheck(
        name=name,
        status=status,
        measured=round(measured, 3),
        limit=round(limit, 3),
        units=units,
        message=f"{name} is {status.lower()} against the derived TB2-class threshold.",
    )


def temperature_check(worst: dict[str, Any], policy: WeatherPolicy) -> ConstraintCheck:
    low = worst["min_temperature_2m_c"]
    high = worst["max_temperature_2m_c"]
    if low <= policy.temp_no_go_low_c or high >= policy.temp_no_go_high_c:
        status = "FAIL"
    elif low <= policy.temp_watch_low_c or high >= policy.temp_watch_high_c:
        status = "WATCH"
    else:
        status = "PASS"
    return ConstraintCheck(
        name="Ambient temperature",
        status=status,
        measured=f"{low:.1f} to {high:.1f}",
        limit=f"{policy.temp_no_go_low_c:.0f} to {policy.temp_no_go_high_c:.0f}",
        units="deg C",
        message="Temperature is evaluated as an airframe, fuel-system, propulsion-cooling, and density-risk proxy.",
    )


def weather_code_check(code: int) -> ConstraintCheck:
    if code in NO_GO_WEATHER_CODES:
        status = "FAIL"
    elif code in CAUTION_WEATHER_CODES:
        status = "WATCH"
    else:
        status = "PASS"
    return ConstraintCheck(
        name="WMO weather code",
        status=status,
        measured=code,
        limit="No fog, freezing rain, heavy snow, severe showers, or thunderstorm codes",
        units=None,
        message="Open-Meteo WMO code is used as the compact severe-weather classifier.",
    )


def humidity_check(worst: dict[str, Any], policy: WeatherPolicy) -> ConstraintCheck:
    humidity = worst["max_relative_humidity_percent"]
    visibility = worst["min_visibility_m"]
    status = "WATCH" if humidity >= policy.humidity_watch_percent and visibility <= policy.visibility_watch_m else "PASS"
    return ConstraintCheck(
        name="Humidity and fog tendency",
        status=status,
        measured=f"{humidity:.0f}% RH, {visibility:.0f} m visibility",
        limit=f"{policy.humidity_watch_percent:.0f}% RH with reduced visibility",
        units=None,
        message="High humidity is treated as a caution only when visibility also degrades.",
    )


def particulate_check(name: str, measured: float, watch: float, fail: float) -> ConstraintCheck:
    status = "FAIL" if measured >= fail else "WATCH" if measured >= watch else "PASS"
    return ConstraintCheck(
        name=name,
        status=status,
        measured=round(measured, 3),
        limit=fail,
        units="ug/m^3",
        message="Air-quality data is used as a visibility and engine-ingestion risk proxy when available.",
    )


def altitude_check(request: MissionRequest, drone: DroneParameters) -> ConstraintCheck:
    altitude = request.mission_altitude_m or 0.0
    status = "FAIL" if altitude > drone.operational_altitude_m else "PASS"
    return ConstraintCheck(
        name="Mission altitude",
        status=status,
        measured=round(altitude, 1),
        limit=round(drone.operational_altitude_m, 1),
        units="m",
        message="Requested mission altitude is checked against the TB2-class operational altitude from the MATLAB model.",
    )


def decide(checks: list[ConstraintCheck]) -> FlightDecision:
    if any(check.status == "FAIL" for check in checks):
        return FlightDecision.NO_GO
    if any(check.status in {"WATCH", "UNKNOWN"} for check in checks):
        return FlightDecision.CAUTION
    return FlightDecision.GO


def score_checks(checks: list[ConstraintCheck]) -> int:
    score = 100
    for check in checks:
        if check.status == "FAIL":
            score -= 22
        elif check.status == "WATCH":
            score -= 9
        elif check.status == "UNKNOWN":
            score -= 3
    return max(0, min(100, score))


def build_recommendation(
    worst: dict[str, Any],
    request: MissionRequest,
    drone: DroneParameters,
    checks: list[ConstraintCheck],
) -> Recommendation:
    route_heading = request.route_heading_deg
    wind_dir = worst["dominant_wind_direction_deg"]
    wind_speed = worst["max_wind_speed_mps"]
    relative = angle_diff_deg(wind_dir, route_heading)
    headwind = wind_speed * cos(radians(relative))
    altitude_candidates = [
        altitude
        for altitude in [500.0, 1000.0, 1500.0, 2000.0, 3000.0, 4000.0, request.mission_altitude_m or 3000.0]
        if altitude <= drone.operational_altitude_m
    ]
    speed = min(max(best_range_speed(request.mission_altitude_m or 3000.0, drone) + max(headwind, 0.0) * 0.25, 1.3 * drone.sea_level_stall_speed_mps), 0.92 * drone.max_speed_mps)
    best_altitude = min(
        set(altitude_candidates),
        key=lambda alt: fuel_per_km(speed, alt, headwind, drone),
    )
    perf = steady_level_performance(speed, best_altitude, drone.mass0_kg - 0.25 * drone.fuel_mass0_kg, drone)
    estimated_fuel = perf["fuel_flow_kgps"] * request.duration_hours * 3600.0
    estimated_energy_mj = estimated_fuel * drone.lhv_j_per_kg / 1e6
    fail_present = any(check.status == "FAIL" for check in checks)
    watch_present = any(check.status == "WATCH" for check in checks)
    latest_return = 0.0 if fail_present else max(0.0, request.duration_hours * 60.0 - request.reserve_minutes)

    rationale = [
        f"Suggested true airspeed is based on best-range speed plus a headwind allowance of {max(headwind, 0.0):.1f} m/s.",
        f"Suggested altitude minimizes estimated fuel per kilometer among candidate altitudes within {drone.operational_altitude_m:.0f} m.",
    ]
    if watch_present:
        rationale.append("Caution checks are present, so the return duration keeps the requested reserve margin.")
    if fail_present:
        rationale.append("At least one no-go check failed, so latest return time is set to zero.")

    return Recommendation(
        suggested_altitude_m=round(best_altitude, 1),
        suggested_true_airspeed_mps=round(speed, 2),
        estimated_fuel_kg=round(estimated_fuel, 2),
        estimated_energy_mj=round(estimated_energy_mj, 2),
        latest_return_minutes=round(latest_return, 1),
        rationale=rationale,
    )


def fuel_per_km(speed_mps: float, altitude_m: float, headwind_mps: float, drone: DroneParameters) -> float:
    perf = steady_level_performance(speed_mps, altitude_m, drone.mass0_kg - 0.25 * drone.fuel_mass0_kg, drone)
    ground_speed = max(15.0, speed_mps - headwind_mps)
    return 1000.0 * perf["fuel_flow_kgps"] / ground_speed


def angle_diff_deg(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0
