from __future__ import annotations

import asyncio
import gzip
import json
import socket
import zlib
from datetime import timedelta
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlparse

from dateutil.parser import isoparse

from drone_weather.models import Location, MissionRequest


FORECAST_URL = "http://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "http://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_URL = "http://air-quality-api.open-meteo.com/v1/air-quality"

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "pressure_msl",
    "cloud_cover",
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

AIR_QUALITY_VARIABLES = ["pm10", "pm2_5", "dust"]


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    full_url = f"{url}?{urlencode(params)}"
    parsed = urlparse(full_url)
    if parsed.scheme != "http":
        raise ValueError("This local client intentionally uses plain HTTP to avoid the broken OpenSSL runtime.")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=20) as sock:
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}\r\n"
            "User-Agent: tb2-weather-mission-app/0.1\r\n"
            "Accept: application/json\r\n"
            "Accept-Encoding: gzip, deflate\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)

    raw = b"".join(chunks)
    header_bytes, _, body = raw.partition(b"\r\n\r\n")
    header_text = header_bytes.decode("iso-8859-1", errors="replace")
    status_line = header_text.splitlines()[0] if header_text else ""
    if not (" 200 " in status_line or status_line.endswith(" 200 OK")):
        raise URLError(f"Open-Meteo HTTP request failed: {status_line}")

    lower_headers = header_text.lower()
    if "transfer-encoding: chunked" in lower_headers:
        body = _decode_chunked(body)
    if "content-encoding: gzip" in lower_headers:
        body = gzip.decompress(body)
    elif "content-encoding: deflate" in lower_headers:
        body = zlib.decompress(body)
    return json.loads(body.decode("utf-8"))


def _decode_chunked(body: bytes) -> bytes:
    output = bytearray()
    cursor = 0
    while cursor < len(body):
        line_end = body.find(b"\r\n", cursor)
        if line_end < 0:
            break
        size_text = body[cursor:line_end].split(b";", 1)[0]
        size = int(size_text, 16)
        cursor = line_end + 2
        if size == 0:
            break
        output.extend(body[cursor : cursor + size])
        cursor += size + 2
    return bytes(output)


async def _get_json_async(url: str, params: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_get_json, url, params)


async def resolve_location(request: MissionRequest) -> Location:
    if request.latitude is not None and request.longitude is not None:
        return Location(
            name=request.location_name or "Custom coordinates",
            latitude=request.latitude,
            longitude=request.longitude,
        )

    payload = await _get_json_async(
        GEOCODING_URL,
        {"name": request.location_name, "count": 1, "language": "en", "format": "json"},
    )
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"Open-Meteo geocoding could not find '{request.location_name}'.")
    item = results[0]
    return Location(
        name=item.get("name", request.location_name or "Resolved location"),
        latitude=item["latitude"],
        longitude=item["longitude"],
        country=item.get("country"),
        timezone=item.get("timezone"),
        elevation_m=item.get("elevation"),
    )


async def fetch_weather_bundle(request: MissionRequest) -> tuple[Location, dict[str, Any], dict[str, Any] | None]:
    location = await resolve_location(request)
    start_date = request.start_time.date()
    end_date = (request.start_time + timedelta(hours=request.duration_hours + 6)).date()
    forecast = await _get_json_async(
        FORECAST_URL,
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": ",".join(HOURLY_VARIABLES),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": "auto",
            "wind_speed_unit": "ms",
            "precipitation_unit": "mm",
        },
    )

    air_quality: dict[str, Any] | None = None
    try:
        air_quality = await _get_json_async(
            AIR_QUALITY_URL,
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": ",".join(AIR_QUALITY_VARIABLES),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timezone": "auto",
            },
        )
    except (URLError, TimeoutError, OSError):
        air_quality = None

    location.elevation_m = forecast.get("elevation", location.elevation_m)
    return location, forecast, air_quality


def slice_hourly_window(payload: dict[str, Any], request: MissionRequest) -> list[dict[str, Any]]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    start = request.start_time.replace(tzinfo=None)
    end = start + timedelta(hours=request.duration_hours)
    samples: list[dict[str, Any]] = []
    for index, time_text in enumerate(times):
        sample_time = isoparse(time_text).replace(tzinfo=None)
        if start <= sample_time <= end:
            row = {"time": time_text}
            for key, values in hourly.items():
                if key == "time":
                    continue
                row[key] = values[index] if index < len(values) else None
            samples.append(row)

    if samples:
        return samples

    nearest_index = min(
        range(len(times)),
        key=lambda i: abs((isoparse(times[i]).replace(tzinfo=None) - start).total_seconds()),
    )
    return [
        {
            "time": times[nearest_index],
            **{
                key: values[nearest_index]
                for key, values in hourly.items()
                if key != "time" and nearest_index < len(values)
            },
        }
    ]


def merge_air_quality(samples: list[dict[str, Any]], air_quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not air_quality:
        return samples
    hourly = air_quality.get("hourly") or {}
    air_times = hourly.get("time") or []
    by_time = {}
    for index, time_text in enumerate(air_times):
        by_time[time_text] = {
            key: values[index]
            for key, values in hourly.items()
            if key != "time" and index < len(values)
        }
    for sample in samples:
        sample.update(by_time.get(sample["time"], {}))
    return samples
