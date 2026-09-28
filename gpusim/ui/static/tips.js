/* Hover text for every input. Each entry states the assumption behind it. */

export const SEAL_TEXT = {
  1: "1 · fully open, 100 % open area (panel removed, no filter).",
  2: "2 · open grille / missing slot covers / coarse bare mesh, about 70 % open.",
  3: "3 · typical mesh panel with a dust filter, about 45 % open.",
  4: "4 · restricted: solid panel with seams, vents or small gaps, about 5 % open.",
  5: "5 · sealed: solid glass or metal, or taped. 0 % open, so the branch is removed (infinite resistance).",
};

export const TIPS = {
  seal:
    "Seal level of this interface, 1 = open … 5 = sealed. It sets the open-area fraction of the panel's geometric leak area, " +
    "then an orifice loss k = ρ / (2 Cd² A²). 1 = 100 %, 2 = 70 %, 3 = 45 % (typical mesh + filter), 4 = 5 % (seams), " +
    "5 = 0 % (solid glass/metal or taped: no branch, R = ∞). Percentages are engineering assumptions; Monte Carlo varies them ±20 %.",
  filter:
    "Dust filter on this face's intakes. Adds a quadratic loss in series with each fan: fine ≈ 1.4e4, dense ≈ 4.0e4 Pa/(m³/s)² " +
    "(about 11 Pa and 31 Pa at a 140 mm fan's working flow). Approximate.",
  fanSelect:
    "Fan on this mount. The list is the library filtered to this mount size, sorted by static pressure. Each fan's P–Q curve is " +
    "scaled by the fan laws: Q ∝ RPM, P ∝ RPM². Empty = open hole (orifice). Blanked = cover plate (near-closed).",
  setAll: "Apply one fan model, direction and speed to every mount on this face.",
  direction: "Intake blows into the case; exhaust blows out. The fan is a pressure source in series with its own impedance.",
  duty: "Fan speed as a fraction of the fan's rated maximum RPM. Flow scales with speed, pressure with speed squared.",
  radiator:
    "Radiator on this face (front, top or bottom). Its core is a quadratic loss scaled by thickness/38 mm and FPI/18, with its fans " +
    "in series. With a water-cooled CPU, the CPU heat rides this air stream. Fans sit directly on the radiator (push).",
  radDir: "Radiator as intake heats the incoming air with the CPU load; as exhaust it dumps CPU heat out of the case.",
  radFans: "Fans on the radiator, and how many. They act in parallel (flow adds, pressure does not).",
  cpuPower: "CPU package power while the GPUs are loaded, in watts. It all ends up in the air, through the radiator or the tower cooler.",
  cpuCooling:
    "Water: the CPU heat goes out through the radiator's air stream (needs a radiator). Air: a tower cooler's fan pulls case air " +
    "through its fin stack (a resistance ≈ 2.5e4 Pa/(m³/s)², approximate) and adds the CPU heat to the case air; the rear fan pulls from the cooler outlet.",
  cpuFan: "Tower cooler fan model and count (push-pull = 2). Speed is a fraction of max RPM.",
  obstruction:
    "Internal obstruction between the intake and the cards. k multiplier on the internal branches (GPU zone → case, CPU cooler outlet): " +
    "low 1.0 (open interior), medium 2.5 (a drive cage or big cooler in the path), high 6.0 (cages, brackets, cables). Approximate.",
  cables:
    "Cable management. clean ×1.0, cluttered ×2.0 on the internal branches, and ×1.35 on every card inlet slit (bundles lying across the fans). Approximate.",
  psu: "PSU under a shroud (its own chamber) or open. With no shroud the lowest card's fan sees 1.8× more floor clearance.",
  psuFan: "PSU fan facing down (breathes from outside through the floor) or up (pulls from the case).",
  cage: "Drive cage in the front intake path adds 6e4 Pa/(m³/s)² in series with the front fans. Approximate.",
  side:
    "Side panel. Tempered glass or solid metal = seal level 5 (no leak, R = ∞). Mesh caps the level at 3 (45 %). Removed = level 1 (100 %).",
  brackets:
    "Rear PCIe slot covers removed. Open slot mouths are a leak path at the rear, and with the shroud off part of them re-ingests the " +
    "hot exhaust plume (22 % of the open area, global assumption).",
  shroud:
    "Rear exhaust shroud: a shared plenum over every GPU bracket outlet, outside the case. On = with its fans pulling suction in series " +
    "with the GPU blowers. Passive = the same duct with no fans. Off = bracket outlets see the room and a reingestion path.",
  shroudFan: "Shroud fan model. Default is Stefano's 2× Noctua NF-A14 industrialPPC-3000 (datasheet 10.52 mmH₂O; web page 6.58; Monte Carlo spans both).",
  ambient: "Room air temperature in °C. Everything is solved in Celsius; °F is a display toggle.",
  altitude: "Altitude sets air density (barometric, isothermal). Thinner air carries less heat per CFM.",
  buoyancy: "Stack effect: hot GPU-zone air rising into the case. Usually well under 1 Pa, off by default.",
  reingest: "Case against a wall: its own exhaust warms the air it breathes. Added to ambient, °C.",
  card:
    "GPU model. Blower (Max-Q, custom 300 W): intake on the fan face, exhaust out the rear bracket. Flow-through (PRO 6000 Workstation, " +
    "5090 FE, 3090 FE): intake on the fan face (down), exhaust up through the backplate into the gap above — the card above breathes part of it.",
  slot:
    "Expansion slot. Card 1 is closest to the CPU. The fan face points down: its gap is the card below, or the PSU-shroud clearance. " +
    "Adjacent dual-slot cards leave about 3.6 mm (Max-Q); one empty slot about 24 mm. v1–v3 are vertical positions off to the side.",
  curve:
    "GPU fan speed curve. Stock: the card's own curve (Max-Q caps near 70 % duty even at 88–90 °C). Custom Accelerated: off (0 %) at " +
    "25 °C, rising linearly to 100 % at 70 °C and held there — an assumption modelled on a user fan-curve tool, not a vendor table. " +
    "Custom: your own temperature → duty points.",
  customCurve: "Custom curve points as °C:duty pairs, duty 0–1, e.g. 30:0.3, 60:0.55, 75:0.8, 90:1.",
  power: "Board power limit, W. The card is assumed to sit on this limit under the simulated load. Approximation.",
  memOffset: "Memory clock offset, MHz. Scales the memory power share linearly. Rough approximation, clamped to the power limit.",
  coreOffset: "Core clock offset, MHz. Dynamic power ∝ f·V². Rough approximation, clamped to the power limit.",
  undervolt: "Undervolt in mV from a 1.000 V reference (−100 = 0.90 V). Dynamic ∝ V², static ∝ V^1.3. Rough approximation.",
  spacing: "Re-slot the horizontal cards top-down with 0, 1, 2 or 3 empty slots between them. Vertical cards stay put.",
  legendIntake: "Blue: fan blowing into the case.",
  legendExhaust: "Red: fan blowing out of the case.",
  legendBlank: "Grey: blanked mount (cover plate) or empty hole.",
  legendGpu: "Cards are coloured by die temperature: blue ≤ 55 °C, green 75, amber 85, red ≥ 100.",
  unthrottled:
    "Unthrottled: the steady state if the card kept its full power. Throttled: power is cut until the die sits at the cutoff (90 °C Max-Q / 5090, 93 °C 3090). Both are reported.",
  casePa: "Case static pressure relative to the room. Positive: more intake than exhaust, air leaks out. Negative: air leaks in through every gap.",
  network:
    "Resistor-network view. Layer 1 is the airflow network (pressure = voltage, flow = current). Layer 2 is each card's thermal network, driven by the flow solved in layer 1.",
  view: "Camera: 3/4 front shows the front, top and glass side; 3/4 rear shows the rear and the shroud; side is square to the glass.",
  optimize:
    "Search spacing, shroud, fan direction, sealing and GPU fan curve on the fast solver for this case and card count. Air-cooled only; water blocks are not candidates.",
  compare: "Freeze the current build as A, keep editing B, and see Δ per card.",
  demo: "Step through the saved scenario (arrow keys, or tick auto).",
  present: "Hide the controls for an OBS browser source or window capture.",
};

export function installTips(tipEl) {
  let current = null;
  document.addEventListener("mouseover", (ev) => {
    const host = ev.target.closest ? ev.target.closest("[data-tip]") : null;
    if (!host) {
      tipEl.hidden = true;
      current = null;
      return;
    }
    if (host !== current) {
      current = host;
      tipEl.textContent = host.getAttribute("data-tip");
    }
    tipEl.hidden = false;
  });
  document.addEventListener("mousemove", (ev) => {
    if (tipEl.hidden) return;
    const pad = 16;
    const w = tipEl.offsetWidth;
    const h = tipEl.offsetHeight;
    let x = ev.clientX + pad;
    let y = ev.clientY + pad;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
    tipEl.style.left = `${Math.max(8, x)}px`;
    tipEl.style.top = `${Math.max(8, y)}px`;
  });
}
