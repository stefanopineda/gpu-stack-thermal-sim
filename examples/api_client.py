"""Drive gpusim from Python, over HTTP or in-process.

    uv run gpusim ui --no-open-browser --port 8010   # in one terminal
    uv run python examples/api_client.py              # HTTP against :8010
    uv run python examples/api_client.py --offline    # no server, same JSON

Standard library only for the HTTP path, so an agent can copy it anywhere.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8010"
HERE = Path(__file__).resolve().parent / "api"


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read())


def offline(path: str, body: dict) -> dict:
    from gpusim import api

    if path.endswith("/simulate"):
        return api.simulate(api.SimSpec.model_validate(body))
    if path.endswith("/rank"):
        return api.rank(api.RankRequest.model_validate(body))
    return api.sweep(api.SweepRequest.model_validate(body))


def main() -> None:
    call = offline if "--offline" in sys.argv else post

    spec = json.loads((HERE / "simulate_custom_rig.json").read_text())
    one = call("/api/v1/simulate", spec)
    print(one["build_name"], "→ hottest", one["summary"]["hottest_die_c"], "°C")
    for card in one["cards"]:
        print(f"  {card['id']} slot {card['slot']}: {card['t_die_c']} °C, {card['flow_cfm']} CFM")

    # Ask a question an agent would ask: which spacing and curve for these two cards?
    request = {
        "base": {"build": spec["build"], "extra_fans": spec["extra_fans"]},
        "factors": {"spacing": ["gap1", "gap2", "gap3"], "fan_curve": ["stock", "custom_accelerated"]},
    }
    ranked = call("/api/v1/sweep", request)
    best = ranked["results"][0]
    print("best:", best["name"], best["summary"]["hottest_die_c"], "°C")
    print(ranked["accuracy"])


if __name__ == "__main__":
    main()
