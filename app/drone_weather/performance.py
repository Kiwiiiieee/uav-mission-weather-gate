from __future__ import annotations

from math import exp, sqrt

from drone_weather.drone_parameters import DroneParameters, TB2


def isa_atmosphere(altitude_m: float, drone: DroneParameters = TB2) -> tuple[float, float, float, float]:
    altitude_m = max(0.0, altitude_m)
    if altitude_m <= 11000.0:
        lapse = 0.0065
        temperature_k = drone.t0_k - lapse * altitude_m
        pressure_pa = drone.p0_pa * (temperature_k / drone.t0_k) ** (
            drone.gravity_mps2 / (drone.gas_constant * lapse)
        )
    else:
        temperature_k = 216.65
        p11 = drone.p0_pa * (temperature_k / drone.t0_k) ** (
            drone.gravity_mps2 / (drone.gas_constant * 0.0065)
        )
        pressure_pa = p11 * exp(-drone.gravity_mps2 * (altitude_m - 11000.0) / (drone.gas_constant * temperature_k))
    density = pressure_pa / (drone.gas_constant * temperature_k)
    speed_of_sound = sqrt(drone.gamma_air * drone.gas_constant * temperature_k)
    return temperature_k, pressure_pa, density, speed_of_sound


def steady_level_performance(
    speed_mps: float,
    altitude_m: float,
    mass_kg: float | None = None,
    drone: DroneParameters = TB2,
) -> dict[str, float]:
    mass_kg = drone.mass0_kg if mass_kg is None else mass_kg
    _, _, rho, _ = isa_atmosphere(altitude_m, drone)
    q = 0.5 * rho * speed_mps**2
    lift = mass_kg * drone.gravity_mps2
    cl = lift / max(q * drone.wing_area_m2, 1e-9)
    cd = drone.cd0 + drone.induced_drag_k * cl**2
    drag_n = q * drone.wing_area_m2 * cd
    power_required_w = drag_n * speed_mps / drone.eta_prop
    power_used_w = min(
        max(power_required_w, drone.idle_power_fraction * drone.engine_power_w),
        drone.engine_power_w,
    )
    fuel_flow_kgps = drone.bsfc_kg_per_kwh * (power_used_w / 1000.0) / 3600.0
    return {
        "density_kgpm3": rho,
        "cl": cl,
        "cd": cd,
        "drag_n": drag_n,
        "power_required_w": power_required_w,
        "power_used_w": power_used_w,
        "fuel_flow_kgps": fuel_flow_kgps,
    }


def best_range_speed(altitude_m: float, drone: DroneParameters = TB2) -> float:
    v_min = max(1.35 * stall_speed(altitude_m, drone), 22.0)
    v_max = min(0.95 * drone.max_speed_mps, 60.0)
    if v_max <= v_min:
        return v_min
    best_v = v_min
    best_metric = float("inf")
    for i in range(160):
        speed = v_min + (v_max - v_min) * i / 159
        perf = steady_level_performance(speed, altitude_m, drone.mass0_kg - 0.25 * drone.fuel_mass0_kg, drone)
        if perf["drag_n"] < best_metric:
            best_metric = perf["drag_n"]
            best_v = speed
    return best_v


def stall_speed(altitude_m: float, drone: DroneParameters = TB2) -> float:
    _, _, rho, _ = isa_atmosphere(altitude_m, drone)
    return sqrt(2.0 * drone.mass0_kg * drone.gravity_mps2 / (rho * drone.wing_area_m2 * drone.cl_max))
