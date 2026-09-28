from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drone_weather.decision import evaluate_mission
from drone_weather.models import MissionRequest
from drone_weather.open_meteo import fetch_weather_bundle


async def main() -> None:
    request = MissionRequest(
        location_name="Ankara",
        start_time=datetime(2026, 5, 30, 12, 0, 0),
        duration_hours=2.0,
        mission_altitude_m=3000.0,
        route_heading_deg=0.0,
    )
    location, forecast, air_quality = await fetch_weather_bundle(request)
    result = evaluate_mission(request, location, forecast, air_quality)
    print(f"{result.decision.value} {result.score}")


if __name__ == "__main__":
    asyncio.run(main())
