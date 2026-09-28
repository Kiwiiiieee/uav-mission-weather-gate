from __future__ import annotations

from datetime import datetime

from drone_weather.decision import evaluate_mission
from drone_weather.models import Location, MissionRequest


def make_forecast(**overrides):
    values = {
        "temperature_2m": [18.0, 19.0],
        "relative_humidity_2m": [40.0, 45.0],
        "apparent_temperature": [18.0, 19.0],
        "precipitation_probability": [0.0, 0.0],
        "precipitation": [0.0, 0.0],
        "rain": [0.0, 0.0],
        "snowfall": [0.0, 0.0],
        "weather_code": [0, 0],
        "pressure_msl": [1013.0, 1012.0],
        "cloud_cover": [10.0, 20.0],
        "visibility": [20000.0, 20000.0],
        "wind_speed_10m": [3.0, 4.0],
        "wind_direction_10m": [20.0, 25.0],
        "wind_gusts_10m": [5.0, 6.0],
    }
    values.update(overrides)
    values["time"] = ["2026-06-01T10:00", "2026-06-01T11:00"]
    return {"elevation": 900.0, "hourly": values}


def test_clear_weather_is_go():
    request = MissionRequest(location_name="Ankara", start_time=datetime(2026, 6, 1, 10), duration_hours=1)
    result = evaluate_mission(request, Location(name="Ankara", latitude=39.9, longitude=32.8), make_forecast(), None)
    assert result.decision.value == "GO"


def test_thunderstorm_is_no_go():
    request = MissionRequest(location_name="Ankara", start_time=datetime(2026, 6, 1, 10), duration_hours=1)
    forecast = make_forecast(weather_code=[95, 95], wind_gusts_10m=[4.0, 5.0])
    result = evaluate_mission(request, Location(name="Ankara", latitude=39.9, longitude=32.8), forecast, None)
    assert result.decision.value == "NO_GO"
