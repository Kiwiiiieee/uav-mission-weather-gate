from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from drone_weather.decision import evaluate_mission
from drone_weather.drone_parameters import as_public_dict
from drone_weather.models import MissionRequest, MissionResponse
from drone_weather.open_meteo import fetch_weather_bundle


app = FastAPI(
    title="TB2 Weather Mission Readiness API",
    version="0.1.0",
    description="Open-Meteo mission readiness evaluator for the TB2-class ICE study.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/drone")
def drone_parameters() -> dict:
    return as_public_dict()


@app.post("/api/mission/evaluate", response_model=MissionResponse)
async def evaluate(request: MissionRequest) -> MissionResponse:
    try:
        location, forecast, air_quality = await fetch_weather_bundle(request)
        return evaluate_mission(request, location, forecast, air_quality)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Weather service request failed: {exc}") from exc
