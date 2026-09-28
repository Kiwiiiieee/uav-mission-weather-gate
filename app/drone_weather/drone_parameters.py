from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt


KT_TO_MPS = 0.514444
FT_TO_M = 0.3048
HP_TO_W = 745.7


@dataclass(frozen=True)
class DroneParameters:
    """Read-only TB2-class inputs mirrored from the MATLAB ICE model."""

    name: str = "TB2-class ICE mission model"
    source_file: str = "tb2_ice_masoodwei_calibrated_mission.m"
    gravity_mps2: float = 9.81
    rho_sl_kgpm3: float = 1.225
    t0_k: float = 288.15
    p0_pa: float = 101325.0
    gas_constant: float = 287.05
    gamma_air: float = 1.4
    mtow_kg: float = 700.0
    mass0_kg: float = 700.0
    fuel_mass0_kg: float = 240.0
    wingspan_m: float = 12.0
    length_m: float = 6.5
    wing_area_m2: float = 9.27
    cl_max: float = 1.80
    cd0: float = 0.035
    oswald: float = 0.80
    eta_prop: float = 0.80
    bsfc_kg_per_kwh: float = 0.32
    lhv_j_per_kg: float = 43e6
    co2_kg_per_kg_fuel: float = 3.16
    idle_power_fraction: float = 0.18
    engine_power_hp: float = 100.0
    max_speed_ktas: float = 110.0
    cruise_speed_ktas: float = 90.0
    operational_altitude_ft: float = 16000.0

    @property
    def engine_power_w(self) -> float:
        return self.engine_power_hp * HP_TO_W

    @property
    def max_speed_mps(self) -> float:
        return self.max_speed_ktas * KT_TO_MPS

    @property
    def cruise_speed_mps(self) -> float:
        return self.cruise_speed_ktas * KT_TO_MPS

    @property
    def operational_altitude_m(self) -> float:
        return self.operational_altitude_ft * FT_TO_M

    @property
    def aspect_ratio(self) -> float:
        return self.wingspan_m**2 / self.wing_area_m2

    @property
    def induced_drag_k(self) -> float:
        return 1.0 / (pi * self.oswald * self.aspect_ratio)

    @property
    def sea_level_stall_speed_mps(self) -> float:
        return sqrt(
            2.0
            * self.mass0_kg
            * self.gravity_mps2
            / (self.rho_sl_kgpm3 * self.wing_area_m2 * self.cl_max)
        )

    @property
    def takeoff_reference_speed_mps(self) -> float:
        return 1.2 * self.sea_level_stall_speed_mps


TB2 = DroneParameters()


def as_public_dict() -> dict[str, float | str]:
    return {
        "name": TB2.name,
        "source_file": TB2.source_file,
        "mass0_kg": TB2.mass0_kg,
        "fuel_mass0_kg": TB2.fuel_mass0_kg,
        "wingspan_m": TB2.wingspan_m,
        "wing_area_m2": TB2.wing_area_m2,
        "engine_power_hp": TB2.engine_power_hp,
        "cruise_speed_mps": TB2.cruise_speed_mps,
        "max_speed_mps": TB2.max_speed_mps,
        "operational_altitude_m": TB2.operational_altitude_m,
        "sea_level_stall_speed_mps": TB2.sea_level_stall_speed_mps,
        "takeoff_reference_speed_mps": TB2.takeoff_reference_speed_mps,
    }
