from gpusim.calib import global_curve
from gpusim.cite import CitationError, validate_citations
from gpusim.models import GpuCfg
from gpusim.library import load_library
from gpusim.physics import duty_at


REQUIRED_FANS = [
    "noctua-140-redux-1700",
    "noctua-nf-p14s-redux-1500",
    "noctua-nf-p12-redux-1700",
    "noctua-nf-a14-ippc-3000",
    "arctic-p12-pwm-pst",
    "corsair-af120-elite",
    "corsair-af140-elite",
    "corsair-ll120",
    "corsair-ll140",
    "corsair-rs120",
    "corsair-rs140",
    "generic-120",
    "generic-140",
    "generic-170",
    "corsair-af120-rgb-elite",
    "silverstone-rm52-included-140",
    "silverstone-rm52-included-80",
]

REQUIRED_CARDS = {
    "rtx-pro-6000-blackwell-maxq": ("blower", 300, 2),
    "rtx-pro-6000-blackwell-workstation": ("flow_through", 600, 2),
    "rtx-5090-fe": ("flow_through", 575, 2),
    "rtx-3090-fe": ("flow_through", 350, 3),
    "custom-blower-300w": ("blower", 300, 2),
}


def test_library_loads_required_presets():
    lib = load_library()
    for fan_id in REQUIRED_FANS:
        assert fan_id in lib.fans
    for card_id, (cooler, watts, slots) in REQUIRED_CARDS.items():
        card = lib.cards[card_id]
        assert card.cooler == cooler, card_id
        assert card.tbp_w == watts, card_id
        assert card.slots == slots, card_id
    assert lib.cards["custom-blower-300w"].template is True
    for case_id in (
        "meshify2xl",
        "corsair-9000d",
        "generic-atx",
        "generic-matx",
        "generic-eatx",
        "phanteks-enthoo-elite-server",
        "silverstone-rm52",
    ):
        assert case_id in lib.cases
    assert lib.cases["meshify2xl"].horizontal_slots == 9
    assert lib.cases["meshify2xl"].vertical_slots == 3
    assert lib.cases["phanteks-enthoo-elite-server"].horizontal_slots == 12
    rm52 = lib.cases["silverstone-rm52"]
    assert rm52.horizontal_slots == 8
    assert rm52.vertical_slots == 0
    assert rm52.depth_mm == 605
    assert rm52.height_mm == 440
    assert rm52.width_mm == 220
    assert rm52.external_volume_l == 58.56
    assert "silverstone-rm52-4x-maxq" in lib.builds
    assert "meshify2xl-stefano" in lib.builds
    mike = lib.builds["mike-bradley-dengen-x-station"]
    assert {g.card for g in mike.gpus} == {"rtx-pro-6000-blackwell-workstation"}
    assert {g.power_limit_w for g in mike.gpus} == {275}
    assert "79 °C" in mike.notes  # his published top-card reading
    assert {"stefano-demo", "mike-bradley-demo"} <= set(lib.scenarios)


def test_stock_curve_caps_and_custom_accelerated_is_linear_25_to_70():
    lib = load_library()
    curves = lib.cards["rtx-pro-6000-blackwell-maxq"].fan_curves
    assert duty_at(curves["stock"], 90) == 0.70
    assert duty_at(curves["stock"], 100) == 0.70
    accel = global_curve("custom_accelerated")
    assert duty_at(accel, 25) == 0.0
    assert duty_at(accel, 20) == 0.0
    assert abs(duty_at(accel, 47.5) - 0.5) < 1e-9
    assert duty_at(accel, 70) == 1.0
    assert duty_at(accel, 90) == 1.0


def test_maxq_aggressive_is_an_alias_of_custom_accelerated():
    gpu = GpuCfg(id="g", slot="1", card="rtx-pro-6000-blackwell-maxq", fan_curve="maxq_aggressive")
    assert gpu.fan_curve == "custom_accelerated"


def test_scaled_140_redux_is_flagged_approximate():
    fan = load_library().fans["noctua-140-redux-1700"]
    assert fan.approximate is True
    assert fan.rpm_max == 1700
    assert 145 < fan.airflow_m3h < 160
    assert 2.3 < fan.static_pressure_mmh2o < 2.6


def test_ippc_uses_datasheet_static_pressure():
    fan = load_library().fans["noctua-nf-a14-ippc-3000"]
    assert fan.static_pressure_mmh2o == 10.52
    assert fan.airflow_m3h == 269.3
    assert "6.58" in fan.notes


def test_rm52_preloads_included_fans_and_solves_four_maxq():
    from gpusim.solve import solve

    lib = load_library()
    fan140 = lib.fans["silverstone-rm52-included-140"]
    fan80 = lib.fans["silverstone-rm52-included-80"]
    assert fan140.approximate is True and fan140.size_mm == 140
    assert fan80.approximate is True and fan80.size_mm == 80
    assert fan140.airflow_cfm == 64.34 and fan140.static_pressure_mmh2o == 1.55
    assert fan80.airflow_m3h == 43.2 and fan80.static_pressure_mmh2o == 1.6
    build = lib.builds["silverstone-rm52-4x-maxq"]
    assert [g.card for g in build.gpus] == ["rtx-pro-6000-blackwell-maxq"] * 4
    assert [g.slot for g in build.gpus] == ["1", "3", "5", "7"]
    fans = {(m.id, m.fan, m.direction, m.state) for m in build.mounts}
    assert ("rear-140", "silverstone-rm52-included-140", "exhaust", "fan") in fans
    assert ("rear-80-1", "silverstone-rm52-included-80", "exhaust", "fan") in fans
    assert ("rear-80-2", "silverstone-rm52-included-80", "exhaust", "fan") in fans
    front = [m for m in build.mounts if m.panel == "front"]
    assert len(front) == 6
    assert all(m.fan == "noctua-nf-p12-redux-1700" and m.state == "fan" and m.direction == "intake" for m in front)
    layout = {m.id: m for m in lib.cases["silverstone-rm52"].mounts}
    # Cage fans are on the outer face, stacked over the slot exhaust. The
    # internal intakes stay in the front bay, ahead of a 267 mm card bracketed
    # on the 560 mm I/O panel.
    assert layout["rear-80-1"].x_mm == layout["rear-80-2"].x_mm == 605
    assert layout["rear-80-1"].z_mm == layout["rear-80-2"].z_mm
    assert layout["rear-80-1"].y_mm < layout["rear-80-2"].y_mm < layout["rear-140"].y_mm
    assert layout["front-1"].x_mm == 0
    assert 80 < layout["front-4"].x_mm < 560 - 267
    assert lib.fans["noctua-nf-p12-redux-1700"].approximate is False
    assert lib.fans["noctua-nf-p12-redux-1700"].airflow_cfm == 70.75
    sol = solve(build, lib, do_throttle=False, outer=8)
    assert sol.converged
    assert len(sol.cards) == 4
    assert all(c.t_die_unthrottled_c > 25 for c in sol.cards)


def test_bare_number_without_citation_is_rejected():
    try:
        validate_citations({"width_mm": 10}, "bad.yaml")
    except CitationError:
        return
    raise AssertionError("uncited number should fail")


def test_every_listed_fan_size_has_mounts():
    """If a case says a face takes 120 or 140 mm fans, the picker must be able to offer them."""
    import re

    lib = load_library()
    for case in lib.cases.values():
        for face in ("front", "top", "rear", "bottom"):
            listed = {int(size) for size in re.findall(r"(?:×|/)(120|140)\b", case.fan_support.get(face, ""))}
            modelled = {m.size_mm for m in case.mounts if m.panel == face}
            assert listed <= modelled, f"{case.id} {face}: lists {sorted(listed)} mm, mounts {sorted(modelled)} mm"
