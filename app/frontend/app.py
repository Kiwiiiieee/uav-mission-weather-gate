from __future__ import annotations

from datetime import datetime, time
from typing import Any

import httpx
import streamlit as st


API_BASE = "http://127.0.0.1:8001"


st.set_page_config(page_title="TB2 Mission Weather Gate", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #f7f8f5; color: #1d2320; }
    [data-testid="stHeader"] { background: rgba(247,248,245,0.92); }
    .block-container { padding-top: 1.4rem; max-width: 1240px; }
    .metric-band { border-top: 1px solid #cfd7cd; border-bottom: 1px solid #cfd7cd; padding: 0.6rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


def post_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{API_BASE}/api/mission/evaluate", json=payload, timeout=35.0)
    response.raise_for_status()
    return response.json()


def get_drone() -> dict[str, Any]:
    response = httpx.get(f"{API_BASE}/api/drone", timeout=10.0)
    response.raise_for_status()
    return response.json()


left, right = st.columns([0.64, 0.36], gap="large")

with left:
    st.title("TB2 Mission Weather Gate")
    st.caption("Open-Meteo forecast screening for the calibrated ICE mission model")

with right:
    try:
        drone = get_drone()
        st.metric("Cruise speed", f"{drone['cruise_speed_mps']:.1f} m/s")
        st.metric("Operational altitude", f"{drone['operational_altitude_m']:.0f} m")
    except Exception:
        st.warning("Start the FastAPI backend on port 8000.")

st.divider()

form_col, result_col = st.columns([0.34, 0.66], gap="large")

with form_col:
    st.subheader("Mission Input")
    location_mode = st.segmented_control("Location mode", ["Place name", "Coordinates"], default="Place name")
    payload: dict[str, Any] = {}
    if location_mode == "Place name":
        payload["location_name"] = st.text_input("Location", value="Ankara")
    else:
        payload["latitude"] = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=39.9334, step=0.01)
        payload["longitude"] = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=32.8597, step=0.01)
        payload["location_name"] = st.text_input("Label", value="Custom coordinates")

    date_value = st.date_input("Mission date", value=datetime.now().date())
    time_value = st.time_input("Mission start time", value=time(hour=datetime.now().hour, minute=0))
    start_dt = datetime.combine(date_value, time_value)
    payload["start_time"] = start_dt.isoformat()
    payload["duration_hours"] = st.slider("Mission duration (hours)", 0.5, 24.0, 2.0, 0.5)
    payload["mission_altitude_m"] = st.slider("Planned altitude (m)", 0, 4876, 3000, 50)
    payload["route_heading_deg"] = st.slider("Route heading (deg)", 0, 359, 0, 1)
    payload["reserve_minutes"] = st.slider("Return reserve (minutes)", 0, 120, 20, 5)

    submitted = st.button("Evaluate Mission", type="primary", use_container_width=True)

with result_col:
    st.subheader("Decision")
    if submitted:
        try:
            result = post_evaluation(payload)
            decision = result["decision"]
            score = result["score"]
            if decision == "GO":
                st.success(f"Mission Approved | mission readiness score {score}/100")
            elif decision == "CAUTION":
                st.warning(f"Proceed with Caution | mission readiness score {score}/100")
            else:
                st.error(f"Mission Rejected | mission readiness score {score}/100")

            loc = result["location"]
            st.caption(f"{loc['name']} | lat {loc['latitude']:.4f}, lon {loc['longitude']:.4f}")

            rec = result["recommendation"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Suggested altitude", f"{rec['suggested_altitude_m']:.0f} m")
            c2.metric("Suggested TAS", f"{rec['suggested_true_airspeed_mps']:.1f} m/s")
            c3.metric("Estimated fuel", f"{rec['estimated_fuel_kg']:.1f} kg")
            c4.metric("Latest return", f"{rec['latest_return_minutes']:.0f} min")

            st.markdown("#### Constraint Checks")
            st.dataframe(
                [
                    {
                        "Check": check["name"],
                        "Status": check["status"],
                        "Measured": check["measured"],
                        "Limit": check["limit"],
                        "Units": check["units"],
                        "Message": check["message"],
                    }
                    for check in result["checks"]
                ],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("#### Weather Window")
            st.dataframe(result["weather"]["samples"], use_container_width=True, hide_index=True)

            st.markdown("#### Recommendation Notes")
            for item in rec["rationale"]:
                st.write(f"- {item}")
            for note in result["notes"]:
                st.caption(note)

            with st.expander("Raw Open-Meteo JSON"):
                st.json(result["weather"]["raw_open_meteo"])
        except httpx.ConnectError:
            st.error("FastAPI backend is not running. Start it with: uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000")
        except httpx.HTTPStatusError as exc:
            st.error(exc.response.text)
        except Exception as exc:
            st.error(str(exc))
    else:
        st.info("Enter a location and mission window, then evaluate.")
