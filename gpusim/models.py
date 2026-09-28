"""Runtime models. Numeric citation checks happen on the raw YAML before this."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FanModel(_Base):
    id: str
    name: str
    size_mm: int
    thickness_mm: float = 25
    rpm_min: float
    rpm_max: float
    airflow_m3h: float
    airflow_cfm: float
    static_pressure_mmh2o: float
    noise_dba: float | None = None
    power_w: float | None = None
    pq_m3h: list[float]
    pq_mmh2o: list[float]
    approximate: bool = False
    notes: str = ""


class CardModel(_Base):
    id: str
    name: str
    template: bool = False
    tbp_w: float
    slots: int = 2
    length_mm: float
    height_mm: float
    thickness_mm: float
    blower: bool = True
    throttle_c: float = 88.0
    cutoff_c: float = 90.0
    fan_curves: dict[str, list[list[float]]]
    notes: str = ""


class RadiatorModel(_Base):
    id: str
    name: str
    size_mm: int
    thickness_mm: float
    length_mm: float
    width_mm: float
    fan_count: int
    fan_size_mm: int
    fpi: float
    default_fan: str
    notes: str = ""


class MountLayout(_Base):
    id: str
    panel: str
    size_mm: int
    x_mm: float = 0
    y_mm: float = 0
    z_mm: float = 0


class VerticalPos(_Base):
    id: str
    y_mm: float
    z_mm: float


class CaseModel(_Base):
    id: str
    name: str
    width_mm: float
    height_mm: float
    depth_mm: float
    internal_volume_l: float
    external_volume_l: float | None = None
    motherboards: list[str]
    horizontal_slots: int
    vertical_slots: int = 0
    slot_pitch_mm: float = 20.32
    top_slot_y_mm: float
    vertical_positions: list[VerticalPos] = Field(default_factory=list)
    airflow_layout: str = "mixed"  # direct_front_to_gpu | mixed
    psu_shroud: bool = True
    psu_location: str = "bottom"
    side_panel: str = "tempered_glass"
    filters: list[str] = Field(default_factory=list)
    front_mesh: bool = False
    gpu_max_length_mm: float
    cpu_cooler_max_mm: float
    fan_support: dict[str, str] = Field(default_factory=dict)
    radiator_support: dict[str, str] = Field(default_factory=dict)
    mounts: list[MountLayout]
    leak_areas_m2: dict[str, float]
    rear_slot_area_m2: float = 0.0015
    clearance_above_top_mm: float = 30.0
    notes: str = ""
    dimension_note: str = ""


class GpuCfg(_Base):
    id: str
    slot: str
    card: str
    fan_curve: str = "stock"
    custom_curve: list[list[float]] | None = None
    power_limit_w: float = 300
    memory_clock_offset_mhz: float = 0
    core_clock_offset_mhz: float = 0
    undervolt_mv: float = 0
    gap_override: str | None = None


class MountCfg(_Base):
    id: str
    panel: str
    size_mm: int
    fan: str | None = None
    state: str = "blanked"  # fan | empty | blanked | radiator
    direction: str = "intake"  # intake | exhaust
    duty: float = 1.0


class RadiatorCfg(_Base):
    model: str | None = None
    panel: str = "top"
    direction: str = "exhaust"
    arrangement: str = "push"
    cpu_power_w: float = 150
    fan: str | None = None
    fan_count: int = 3
    fan_duty: float = 1.0


class ShroudCfg(_Base):
    mode: str = "off"  # off | on | passive
    fan: str = "noctua-nf-a14-ippc-3000"
    count: int = 2
    duty: float = 1.0


class BuildCfg(_Base):
    id: str
    name: str
    case: str
    ambient_c: float = 25.0
    altitude_m: float = 0.0
    gpus: list[GpuCfg]
    mounts: list[MountCfg] = Field(default_factory=list)
    radiator: RadiatorCfg = Field(default_factory=RadiatorCfg)
    shroud: ShroudCfg = Field(default_factory=ShroudCfg)
    seals: dict[str, int] = Field(default_factory=dict)
    filters: dict[str, str] = Field(default_factory=dict)
    obstruction: str = "low"
    cables: str = "clean"
    psu_location: str = "bottom_shroud"
    psu_fan: str = "down"
    drive_cage: str = "removed"
    side_panel: str = "tempered_glass"
    brackets_removed: bool = True
    room_reingestion_c: float = 0.0
    buoyancy: bool = False
    open_air: bool = False
    illustrative_mock: bool = False
    notes: str = ""


class ScenarioStep(_Base):
    id: str
    title: str
    talking_points: list[str]
    layout: str = "keep"
    pressure: str | None = None
    shroud: str | None = None
    leakage: str | None = None
    fan_curve: str | None = None
    advance_s: float = 18


class Scenario(_Base):
    id: str
    title: str
    illustrative_mock: bool = False
    base_build: str
    disclaimer: str = ""
    steps: list[ScenarioStep]
