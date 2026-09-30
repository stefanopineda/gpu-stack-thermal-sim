"""Runtime models. Numeric citation checks happen on the raw YAML before this."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Rev 3 called the fast curve `maxq_aggressive`. Rev 4 renames it to
# `custom_accelerated` (0 % at 25 °C → 100 % at 70 °C, linear) and keeps the
# old name as an alias so saved builds and API clients keep working.
FAN_CURVE_ALIASES = {"maxq_aggressive": "custom_accelerated", "aggressive": "custom_accelerated"}


def canonical_curve(name: str | None) -> str | None:
    if name is None:
        return None
    return FAN_CURVE_ALIASES.get(str(name), str(name))


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
    # blower: radial fan, exhaust out the rear bracket.
    # flow_through: axial fans on the fan face; air leaves up through the
    # backplate side into the gap above, plus a smaller share out the bracket.
    cooler: str = "blower"
    throttle_c: float = 88.0
    cutoff_c: float = 90.0
    fan_curves: dict[str, list[list[float]]]
    # floor: fan face toward the PSU. cpu: fan face toward the CPU.
    # both: fan face toward the floor plus a backplate/end opening (inlet_split).
    inlet_faces: str = "both"
    inlet_split: float = 0.75
    notes: str = ""
    # A card added through the API can borrow the calibrated cooler physics of
    # an existing card type (gpusim/calib.py) instead of shipping its own block.
    calibration_from: str | None = None
    tuning_overrides: dict[str, float] = Field(default_factory=dict)

    @property
    def flow_through(self) -> bool:
        return self.cooler == "flow_through"


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
    # Alternative fan patterns on one face (e.g. "3x140" or "4x120"). A build
    # uses one pattern per face; mounts of the other pattern do not exist.
    pattern: str | None = None


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
    # Open distance from the bottom of the lowest occupied slot to the PSU shroud.
    psu_shroud_clearance_mm: float = 40.0
    vertical_inlet_gap_mm: float = 28.0
    notes: str = ""
    dimension_note: str = ""

    def face_patterns(self, panel: str) -> list[str]:
        seen: list[str] = []
        for m in self.mounts:
            if m.panel == panel and m.pattern and m.pattern not in seen:
                seen.append(m.pattern)
        return seen

    def active_mounts(self, patterns: dict[str, str] | None = None) -> list[MountLayout]:
        """Mounts that exist for the chosen pattern on each face (default: the first)."""
        patterns = patterns or {}
        out = []
        for m in self.mounts:
            if m.pattern is None:
                out.append(m)
                continue
            options = self.face_patterns(m.panel)
            chosen = patterns.get(m.panel)
            if chosen not in options:
                chosen = options[0]
            if m.pattern == chosen:
                out.append(m)
        return out


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

    @field_validator("fan_curve", mode="before")
    @classmethod
    def _alias_curve(cls, value):
        return canonical_curve(value) or "stock"


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
    panel: str = "top"  # front | top | bottom (rear kept for old builds)
    # Where the radiator sits along its panel: front, center, or rear (slid
    # back). Drawing only; the airflow branch does not depend on it.
    offset: str = "center"
    direction: str = "exhaust"
    arrangement: str = "push"
    # Rev 3 kept the CPU load here. Rev 4 reads BuildCfg.cpu; this field is
    # only used to migrate an old build that has no `cpu` block.
    cpu_power_w: float | None = None
    fan: str | None = None
    fan_count: int = 3
    fan_duty: float = 1.0


class ShroudCfg(_Base):
    mode: str = "off"  # off | on | passive
    # open: printed plenum (orientation A) pulls interior inter-card gaps and
    # the GPU mouths. taped: orientation B, suction only through the GPU
    # exhaust openings, plus a crack between stacked cards.
    intake: str = "open"  # open | taped
    fan: str = "noctua-nf-a14-ippc-3000"
    count: int = 2
    duty: float = 1.0

    @field_validator("intake")
    @classmethod
    def _intake(cls, value: str) -> str:
        if value not in ("open", "taped"):
            raise ValueError("shroud.intake must be 'open' or 'taped'")
        return value


class CpuCfg(_Base):
    """CPU heat and how it leaves the case.

    water: the package heat rides the radiator branch (needs a radiator).
    air: the heat goes into the case air through a tower cooler, whose fan and
    fin stack are a branch in the flow network. The rear mount pulls from the
    cooler outlet.
    """

    power_w: float = 150.0
    cooling: str = "water"  # water | air
    cooler_fan: str = "generic-140"
    # Which fans the tower cooler has: both (push-pull, the stock default),
    # top only, or bottom only. On a Threadripper board the bottom fan can
    # crowd the first GPU, so some builders run the top fan alone.
    cooler_fans: str = "both"
    # Legacy count, kept so old builds load; cooler_fans decides the count.
    cooler_fan_count: int = 2
    # up: fins run bottom → top (sTR5 / SP6 towers on WRX90 boards, the
    # default); rear: classic front → back tower.
    cooler_airflow: str = "up"
    cooler_duty: float = 0.8
    # Tower fin-stack loss, Pa/(m³/s)². None → calib.GLOBAL["cpu_heatsink_k"].
    heatsink_k: float | None = None

    @property
    def fan_count(self) -> int:
        return 2 if self.cooler_fans == "both" else 1


class BuildCfg(_Base):
    id: str
    name: str
    case: str
    ambient_c: float = 25.0
    altitude_m: float = 0.0
    gpus: list[GpuCfg]
    mounts: list[MountCfg] = Field(default_factory=list)
    radiator: RadiatorCfg = Field(default_factory=RadiatorCfg)
    cpu: CpuCfg = Field(default_factory=CpuCfg)
    shroud: ShroudCfg = Field(default_factory=ShroudCfg)
    seals: dict[str, int] = Field(default_factory=dict)
    filters: dict[str, str] = Field(default_factory=dict)
    # Face → fan pattern, when the case offers more than one (see MountLayout).
    patterns: dict[str, str] = Field(default_factory=dict)
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

    @model_validator(mode="before")
    @classmethod
    def _migrate_cpu(cls, data):
        """Rev 3 builds have no `cpu` block. Take the load off the radiator."""
        if not isinstance(data, dict) or data.get("cpu") is not None:
            return data
        data = dict(data)
        rad = data.get("radiator") or {}
        if hasattr(rad, "model_dump"):
            rad = rad.model_dump()
        power = rad.get("cpu_power_w")
        has_rad = bool(rad.get("model"))
        data["cpu"] = {
            "power_w": 150.0 if power is None else float(power),
            "cooling": "water" if has_rad else "air",
        }
        return data


class ScenarioStep(_Base):
    id: str
    title: str
    talking_points: list[str]
    layout: str = "keep"
    pressure: str | None = None
    shroud: str | None = None
    # open | taped. Applied after the layout. None leaves the build's intake.
    shroud_intake: str | None = None
    leakage: str | None = None
    fan_curve: str | None = None
    # Swap every card to this model (power limit follows the card's TBP).
    card: str | None = None
    # Pin every GPU fan to one duty (0–1), e.g. a unified fan setting.
    fan_duty: float | None = None
    # Set every card's power limit, W.
    power_limit_w: float | None = None
    advance_s: float = 18

    @field_validator("fan_curve", mode="before")
    @classmethod
    def _alias_curve(cls, value):
        return canonical_curve(value)


class Scenario(_Base):
    id: str
    title: str
    illustrative_mock: bool = False
    base_build: str
    disclaimer: str = ""
    steps: list[ScenarioStep]
