from gpusim.cite import CitationError, validate_citations
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
]


def test_library_loads_required_presets():
    lib = load_library()
    for fan_id in REQUIRED_FANS:
        assert fan_id in lib.fans
    assert "rtx-pro-6000-blackwell-maxq" in lib.cards
    assert lib.cards["custom-blower-300w"].template is True
    for case_id in (
        "meshify2xl",
        "corsair-9000d",
        "generic-atx",
        "generic-matx",
        "generic-eatx",
        "phanteks-enthoo-elite-server",
    ):
        assert case_id in lib.cases
    assert lib.cases["meshify2xl"].horizontal_slots == 9
    assert lib.cases["meshify2xl"].vertical_slots == 3
    assert lib.cases["phanteks-enthoo-elite-server"].horizontal_slots == 12
    assert "meshify2xl-stefano" in lib.builds
    assert lib.builds["mike-bradley-powerhouse"].illustrative_mock is True
    assert {"stefano-demo", "mike-bradley-demo"} <= set(lib.scenarios)


def test_stock_curve_caps_and_aggressive_reaches_full_duty():
    lib = load_library()
    curves = lib.cards["rtx-pro-6000-blackwell-maxq"].fan_curves
    assert duty_at(curves["stock"], 90) == 0.70
    assert duty_at(curves["stock"], 100) == 0.70
    assert duty_at(curves["maxq_aggressive"], 70) == 1.0
    assert duty_at(curves["maxq_aggressive"], 60) < 1.0


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


def test_bare_number_without_citation_is_rejected():
    try:
        validate_citations({"width_mm": 10}, "bad.yaml")
    except CitationError:
        return
    raise AssertionError("uncited number should fail")
