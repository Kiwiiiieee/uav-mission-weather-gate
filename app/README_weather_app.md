# TB2 Weather Mission Readiness App

This mini app adds a Python-only weather mission layer around the existing MATLAB drone model.

The backend fetches Open-Meteo forecast JSON for a user-selected location and time. It evaluates whether the TB2-class ICE mission should proceed based on wind, gusts, precipitation, snow, humidity, temperature, visibility, fog, dust/air quality, and energy impact. The frontend is a Streamlit dashboard that calls the FastAPI backend.

## Setup

Use the bundled Python runtime shown by Codex, or any local Python 3.11+ installation.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_env.ps1
```

## Run Backend

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_backend.ps1
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

## Run Frontend

Open a second terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_frontend.ps1
```

Frontend:

```text
http://localhost:8501
```

## Run Both

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_app.ps1
```

## Main API

```http
POST /api/mission/evaluate
```

The response contains:

- `decision`: `GO`, `CAUTION`, or `NO_GO`
- raw Open-Meteo weather slice for the requested mission window
- constraint checks with measured values and limits
- suggested speed, altitude, fuel use, energy use, and return duration

## Notes

- Drone inputs are mirrored from the existing MATLAB scripts and kept read-only.
- The app does not modify MATLAB mission parameters.
- Open-Meteo does not provide building/tree obstacle clearance. The app reports this as an explicit data gap and only uses available weather/elevation/air-quality signals.
