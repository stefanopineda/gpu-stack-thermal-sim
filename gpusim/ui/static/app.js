/* gpusim visualizer. The solver stays on the server; this file drives the
 * controls and hands results to the 3D scene and the network view. */
import { CaseScene, faceFanLabel } from "./scene.js";
import { renderNetwork } from "./network.js";
import { SEAL_TEXT, TIPS, installTips } from "./tips.js";

const FACES = ["front", "top", "rear", "bottom", "side"];
const RADIATOR_FACES = ["front", "top", "bottom"];
const SEAL_FOR_FACE = { front: "front", top: "top", bottom: "bottom", side: "side", rear: "rear_slots" };
const FILTER_FACES = ["front", "top", "bottom"];
const DEFAULT_SEALS = { front: 3, top: 3, bottom: 4, side: 5, seams: 4, rear_slots: 3 };

const state = {
  presets: null,
  build: null,
  solution: null,
  compare: null,
  face: "front",
  selectedMount: null,
  unitF: false,
  demo: null,
  demoTimer: null,
  net: "off",
  scene: null,
};

const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (v == null || v === false) return;
    if (k === "class") node.className = v;
    else if (k === "tip") node.setAttribute("data-tip", v);
    else if (k.startsWith("on")) node[k] = v;
    else if (k === "value") node.value = v;
    else if (k === "checked") node.checked = v;
    else node.setAttribute(k, v === true ? "" : v);
  });
  kids.flat().forEach((kid) => kid != null && node.append(kid.nodeType ? kid : document.createTextNode(String(kid))));
  return node;
};

function fmt(c) {
  if (c == null || Number.isNaN(c)) return "—";
  if (state.unitF) return `${((c * 9) / 5 + 32).toFixed(1)} °F`;
  return `${c.toFixed(1)} °C`;
}

function tempColor(c) {
  const t = Math.max(55, Math.min(100, c ?? 70));
  const stops = [
    [55, [61, 122, 219]],
    [75, [90, 168, 112]],
    [85, [224, 161, 90]],
    [100, [226, 75, 59]],
  ];
  let i = 0;
  while (i < stops.length - 2 && t > stops[i + 1][0]) i += 1;
  const [t0, a] = stops[i];
  const [t1, b] = stops[i + 1];
  const u = (t - t0) / (t1 - t0 || 1);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * u)).join(",")})`;
}

const caseOf = () => state.presets.cases.find((c) => c.id === state.build.case);
const cardOf = (id) => state.presets.cards.find((c) => c.id === id);
const fanOf = (id) => state.presets.fans.find((f) => f.id === id);

/* ------------------------------------------------------------------ boot */

async function boot() {
  installTips($("tip"));
  state.presets = await (await fetch("/api/presets")).json();
  applyStaticTips();
  buildStartScreen();
  $("home").onclick = () => {
    stopDemo();
    $("app").classList.add("hidden");
    $("start").classList.remove("hidden");
  };
  document.querySelectorAll("#facebar button").forEach((b) => (b.onclick = () => setFace(b.dataset.face)));
  document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => setView(b.dataset.view)));
  document.querySelectorAll("[data-net]").forEach((b) => (b.onclick = () => setNet(b.dataset.net)));
  $("unit-toggle").onclick = () => {
    state.unitF = !state.unitF;
    $("unit-toggle").textContent = state.unitF ? "°C" : "°F";
    renderResults();
  };
  $("present-toggle").onclick = () => document.body.classList.toggle("present");
  $("compare-toggle").onclick = toggleCompare;
  $("demo-toggle").onclick = () => startDemo();
  $("demo-next").onclick = () => stepDemo(1);
  $("demo-prev").onclick = () => stepDemo(-1);
  $("demo-close").onclick = stopDemo;
  $("demo-auto").onchange = syncDemoTimer;
  $("opt-run").onclick = runOptimal;
  window.addEventListener("keydown", onKey);

  const params = new URLSearchParams(location.search);
  if (params.get("net")) setNet(params.get("net"), true);
  if (params.get("face")) state.face = params.get("face");
  if (params.get("present") === "1") document.body.classList.add("present");
  const start = params.get("start");
  const template = params.get("template");
  const demo = params.get("demo");
  let pending = null;
  if (demo === "mike-bradley" || demo === "mock" || start === "mock") {
    pending = loadBuild("mike-bradley-powerhouse").then(() => (demo ? startDemo("mike-bradley-demo") : null));
  } else if (demo === "stefano") {
    pending = loadBuild("meshify2xl-stefano").then(() => startDemo("stefano-demo"));
  } else if (template) pending = loadBuild(template);
  else if (start === "meshify") pending = loadBuild("meshify2xl-stefano");
  else if (start === "9000") pending = loadBuild("corsair-9000d-sample");
  if (pending && demo === "1") pending.then(() => startDemo());
  if (pending && params.get("view")) pending.then(() => setView(params.get("view")));
}

function applyStaticTips() {
  const legend = $("legend").querySelectorAll("span");
  [TIPS.legendIntake, TIPS.legendExhaust, TIPS.legendBlank, TIPS.legendGpu].forEach((t, i) => legend[i]?.setAttribute("data-tip", t));
  $("pressure-readout").dataset.tip = TIPS.casePa;
  $("ambient-readout").dataset.tip = TIPS.ambient;
  document.querySelector("[data-view]").parentElement.dataset.tip = TIPS.view;
  $("net-seg").dataset.tip = TIPS.network;
  $("opt-run").dataset.tip = TIPS.optimize;
  $("compare-toggle").dataset.tip = TIPS.compare;
  $("demo-toggle").dataset.tip = TIPS.demo;
  $("present-toggle").dataset.tip = TIPS.present;
  $("unit-toggle").dataset.tip = "Display in Fahrenheit or Celsius. The model always works in Celsius.";
}

function buildStartScreen() {
  $("quick-meshify").onclick = () => loadBuild("meshify2xl-stefano");
  $("quick-9000").onclick = () => loadBuild("corsair-9000d-sample");
  const grid = $("template-grid");
  grid.innerHTML = "";
  const order = [
    "corsair-9000d-sample",
    "meshify2xl-stefano",
    "generic-atx-sample",
    "generic-matx-sample",
    "generic-eatx-sample",
    "phanteks-enthoo-sample",
  ];
  const builds = state.presets.builds;
  order
    .map((id) => builds.find((b) => b.id === id))
    .filter(Boolean)
    .forEach((b) => {
      const kase = state.presets.cases.find((c) => c.id === b.case);
      grid.append(
        el(
          "button",
          { type: "button", onclick: () => loadBuild(b.id), tip: b.notes },
          el("b", {}, b.name),
          el("span", {}, `${kase ? kase.name : b.case} · ${kase ? kase.horizontal_slots : "?"} slots`),
        ),
      );
    });
  const mock = builds.find((b) => b.illustrative_mock);
  if (mock) {
    grid.append(
      el(
        "button",
        { type: "button", class: "mock", onclick: () => (location.href = "/?demo=mike-bradley") },
        el("b", {}, mock.name),
        el("span", {}, "Illustrative mock — not a measurement or claim about anyone's real build. Opens the demo."),
      ),
    );
  }
  const sel = $("scratch-case");
  sel.innerHTML = "";
  state.presets.cases.forEach((c) => sel.append(el("option", { value: c.id }, c.name)));
  sel.value = "generic-atx";
  $("from-scratch").onclick = () => scratch(sel.value);
}

async function loadBuild(id) {
  state.build = await (await fetch(`/api/build/${id}`)).json();
  enterApp();
  await solveNow();
}

function scratch(caseId) {
  const kase = state.presets.cases.find((c) => c.id === caseId);
  state.build = {
    id: "scratch",
    name: `From scratch · ${kase.name}`,
    case: caseId,
    ambient_c: 25,
    altitude_m: 0,
    gpus: [gpuTemplate("gpu1", "1", "rtx-pro-6000-blackwell-maxq")],
    mounts: kase.mounts.map((m) => ({ id: m.id, panel: m.panel, size_mm: m.size_mm, fan: null, state: "blanked", direction: "intake", duty: 1 })),
    radiator: { model: null, panel: "top", direction: "exhaust", arrangement: "push", fan: "generic-120", fan_count: 3, fan_duty: 1 },
    cpu: { power_w: 150, cooling: "air", cooler_fan: "generic-140", cooler_fan_count: 1, cooler_duty: 0.8 },
    shroud: { mode: "off", fan: "noctua-nf-a14-ippc-3000", count: 2, duty: 1 },
    seals: { ...DEFAULT_SEALS },
    filters: { front: "fine" },
    obstruction: "low",
    cables: "clean",
    psu_location: "bottom_shroud",
    psu_fan: "down",
    drive_cage: "removed",
    side_panel: kase.side_panel === "mesh" ? "mesh" : "tempered_glass",
    brackets_removed: false,
    room_reingestion_c: 0,
    buoyancy: false,
    open_air: false,
    illustrative_mock: false,
    notes: "",
  };
  enterApp();
  solveNow();
}

function gpuTemplate(id, slot, card) {
  const c = cardOf(card);
  return {
    id, slot, card, fan_curve: "stock", custom_curve: null,
    power_limit_w: c ? c.tbp_w : 300, memory_clock_offset_mhz: 0, core_clock_offset_mhz: 0, undervolt_mv: 0,
  };
}

function enterApp() {
  $("start").classList.add("hidden");
  $("app").classList.remove("hidden");
  if (!state.scene) {
    state.scene = new CaseScene($("scene"), $("labels"), {
      onPickMount: (id, panel) => {
        state.selectedMount = id;
        setFace(panel);
      },
      onPickGpu: () => setFace("gpus"),
      onMoveFan: moveFan,
      onMoveGpu: (id, slot) => {
        const gpu = state.build.gpus.find((g) => g.id === id);
        if (gpu) gpu.slot = slot;
        changed();
      },
    });
  }
  state.build.seals = { ...DEFAULT_SEALS, ...(state.build.seals || {}) };
  state.build.filters = state.build.filters || {};
  $("build-name").textContent = state.build.name || state.build.id;
  $("mock-banner").classList.toggle("hidden", !state.build.illustrative_mock);
  renderPanel();
  renderResults();
}

/* ------------------------------------------------------------------ layout */

function setFace(face) {
  state.face = face;
  renderPanel();
  renderInset();
  state.scene?.update(sceneCtx());
}

function setView(view) {
  document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  state.scene?.setView(view);
}

function setNet(mode, quiet) {
  if (!["off", "split", "full"].includes(mode)) return;
  state.net = mode;
  document.querySelectorAll("[data-net]").forEach((b) => b.classList.toggle("on", b.dataset.net === mode));
  const stage = $("stage");
  stage.classList.remove("net-off", "net-split", "net-full");
  stage.classList.add(`net-${mode}`);
  document.body.classList.remove("net-off", "net-split", "net-full");
  document.body.classList.add(`net-${mode}`);
  if (!quiet) renderResults();
}

/* ------------------------------------------------------------------ panels */

function renderPanel() {
  document.querySelectorAll("#facebar button").forEach((b) => b.classList.toggle("on", b.dataset.face === state.face));
  renderFacebar();
  const root = $("panel");
  root.innerHTML = "";
  if (FACES.includes(state.face)) root.append(...facePanel(state.face));
  else if (state.face === "internals") root.append(...internalsPanel());
  else root.append(...gpusPanel());
}

function mountsOn(face) {
  const kase = caseOf();
  const ids = kase.mounts.filter((l) => l.panel === face).map((l) => l.id);
  return ids.map((id) => {
    let mount = state.build.mounts.find((m) => m.id === id);
    if (!mount) {
      const layout = kase.mounts.find((l) => l.id === id);
      mount = { id, panel: face, size_mm: layout.size_mm, fan: null, state: "blanked", direction: "intake", duty: 1 };
      state.build.mounts.push(mount);
    }
    return mount;
  });
}

const defaultDir = (face) => (face === "rear" || face === "top" ? "exhaust" : "intake");

function fanOptions(size, current, extra = true) {
  const fans = state.presets.fans.filter((f) => f.size_mm === size).sort((a, b) => b.static_pressure_mmh2o - a.static_pressure_mmh2o).slice(0, 10);
  const opts = [];
  if (extra) {
    opts.push(el("option", { value: "__blanked" }, "— blanked —"));
    opts.push(el("option", { value: "__empty" }, "— empty hole —"));
  }
  fans.forEach((f) =>
    opts.push(el("option", { value: f.id }, `${f.name} · ${f.airflow_cfm.toFixed(0)} CFM · ${f.static_pressure_mmh2o} mmH₂O · ${f.rpm_max} rpm`)),
  );
  if (current && !fans.some((f) => f.id === current) && fanOf(current)) {
    const f = fanOf(current);
    opts.push(el("option", { value: f.id }, `${f.name} · ${f.airflow_cfm.toFixed(0)} CFM`));
  }
  return opts;
}

function facePanel(face) {
  const kase = caseOf();
  const mounts = mountsOn(face);
  const out = [];
  const title = face[0].toUpperCase() + face.slice(1);
  out.push(el("h2", {}, `${title} panel`));
  const label = faceFanLabel(face, mounts, state.presets);
  out.push(el("p", { class: "sub" }, `${kase.name} · ${kase.fan_support?.[face] || "no published fan support"}${label ? ` · ${label}` : ""}`));

  const fanMounts = mounts.filter((m) => m.state !== "radiator");
  if (fanMounts.length) {
    out.push(el("h3", {}, "Fans"));
    if (fanMounts.length > 1) {
      const size = fanMounts[0].size_mm;
      const sel = el("select", { tip: TIPS.setAll }, fanOptions(size, null));
      sel.value = fanMounts.find((m) => m.fan)?.fan || fanOptions(size, null, false)[0]?.value || "__blanked";
      const dirBtn = el("button", { type: "button", class: `dir ${defaultDir(face)}`, tip: TIPS.direction }, defaultDir(face));
      dirBtn.onclick = () => {
        const next = dirBtn.textContent === "intake" ? "exhaust" : "intake";
        dirBtn.textContent = next;
        dirBtn.className = `dir ${next}`;
      };
      const apply = el("button", { type: "button", tip: TIPS.setAll }, `Set all ${fanMounts.length}`);
      apply.onclick = () => {
        fanMounts.forEach((m) => setMountFan(m, sel.value, dirBtn.textContent, face));
        changed(true);
      };
      out.push(el("div", { class: "row" }, sel, dirBtn, apply));
    }
    fanMounts.forEach((m) => {
      const sel = el("select", { tip: TIPS.fanSelect }, fanOptions(m.size_mm, m.fan));
      sel.value = m.state === "fan" && m.fan ? m.fan : m.state === "empty" ? "__empty" : "__blanked";
      sel.onchange = () => {
        setMountFan(m, sel.value, m.state === "fan" ? m.direction : defaultDir(face), face);
        changed(true);
      };
      const dir = el("button", { type: "button", class: `dir ${m.state === "fan" ? m.direction : ""}`, tip: TIPS.direction, disabled: m.state !== "fan" }, m.state === "fan" ? m.direction : "—");
      dir.onclick = () => {
        m.direction = m.direction === "intake" ? "exhaust" : "intake";
        changed(true);
      };
      const duty = el("input", { type: "number", min: 0, max: 100, step: 5, value: Math.round((m.duty ?? 1) * 100), tip: TIPS.duty, disabled: m.state !== "fan" });
      duty.onchange = () => {
        m.duty = Math.max(0, Math.min(1, Number(duty.value) / 100));
        changed();
      };
      const row = el("div", { class: `mount-row${state.selectedMount === m.id ? " sel" : ""}` }, el("span", { class: "mid" }, `${m.id.replace(`${face}-`, "#")} · ${m.size_mm}`), sel, dir, duty);
      row.onclick = (ev) => {
        if (ev.target.tagName === "DIV" || ev.target.tagName === "SPAN") {
          state.selectedMount = m.id;
          renderPanel();
          state.scene?.update(sceneCtx());
        }
      };
      out.push(row);
    });
    out.push(el("p", { class: "fine" }, "Fan · direction · speed %. Click a fan in the 3D view or the face inset to find it here; drag it onto another mount to move it."));
  }

  // Seal and filter.
  const sealKey = SEAL_FOR_FACE[face];
  out.push(el("h3", {}, face === "rear" ? "Rear slots and shroud" : "Seal and filter"));
  if (face === "side") {
    const side = el("select", { tip: TIPS.side }, ["tempered_glass", "mesh", "removed"].map((v) => el("option", { value: v }, v.replace("_", " "))));
    side.value = state.build.side_panel || "tempered_glass";
    side.onchange = () => {
      state.build.side_panel = side.value;
      if (side.value === "removed") state.build.seals.side = 1;
      else if (side.value === "mesh") state.build.seals.side = Math.min(state.build.seals.side ?? 3, 3);
      else state.build.seals.side = 5;
      changed(true);
    };
    out.push(el("label", { tip: TIPS.side }, "Side panel", side));
  }
  if (face === "rear") {
    out.push(checkbox("Slot brackets removed", "brackets_removed", TIPS.brackets));
  }
  if (sealKey) out.push(sealSlider(sealKey, face === "rear" ? "Rear slot openings" : `${title} panel`));
  if (FILTER_FACES.includes(face)) {
    const filt = el("select", { tip: TIPS.filter }, ["none", "fine", "dense"].map((v) => el("option", { value: v }, v)));
    filt.value = state.build.filters[face] || "none";
    filt.onchange = () => {
      state.build.filters[face] = filt.value;
      changed();
    };
    out.push(el("label", { tip: TIPS.filter }, "Dust filter", filt));
  }
  if (face === "rear") out.push(...shroudControls());
  if (RADIATOR_FACES.includes(face)) out.push(...radiatorControls(face));
  return out;
}

function setMountFan(m, value, direction, face) {
  if (value === "__blanked") {
    m.state = "blanked";
    m.fan = null;
  } else if (value === "__empty") {
    m.state = "empty";
    m.fan = null;
  } else {
    m.state = "fan";
    m.fan = value;
    m.direction = direction || defaultDir(face);
    m.duty = m.duty ?? 1;
  }
}

function sealSlider(key, label) {
  const level = state.build.seals[key] ?? DEFAULT_SEALS[key] ?? 3;
  const name = el("span", { class: "seal-name" }, SEAL_TEXT[level]);
  const input = el("input", { type: "range", min: 1, max: 5, step: 1, value: level, tip: TIPS.seal });
  input.oninput = () => {
    state.build.seals[key] = Number(input.value);
    name.textContent = SEAL_TEXT[input.value];
    changed();
  };
  return el("label", { tip: TIPS.seal }, `${label} · seal level (1 open … 5 sealed)`, input, name);
}

function checkbox(label, key, tip, obj = state.build, after) {
  const input = el("input", { type: "checkbox", checked: !!obj[key] });
  input.onchange = () => {
    obj[key] = input.checked;
    after?.();
    changed(true);
  };
  return el("label", { class: "check", tip }, input, label);
}

function selectField(label, obj, key, options, tip, after) {
  const sel = el("select", { tip }, options.map(([v, t]) => el("option", { value: v }, t)));
  sel.value = obj[key] ?? options[0][0];
  sel.onchange = () => {
    obj[key] = sel.value;
    after?.();
    changed(true);
  };
  return el("label", { tip }, label, sel);
}

function numberField(label, obj, key, tip, opts = {}) {
  const input = el("input", { type: "number", value: obj[key] ?? 0, step: opts.step ?? 1, min: opts.min, max: opts.max, tip });
  input.onchange = () => {
    obj[key] = opts.scale ? Number(input.value) / opts.scale : Number(input.value);
    changed();
  };
  if (opts.scale) input.value = Math.round((obj[key] ?? 0) * opts.scale);
  return el("label", { tip }, label, input);
}

function shroudControls() {
  const s = state.build.shroud;
  const fans = state.presets.fans.filter((f) => f.size_mm >= 120);
  return [
    selectField("Rear exhaust shroud", s, "mode", [["off", "off"], ["on", "on (with fans)"], ["passive", "passive duct"]], TIPS.shroud),
    el(
      "div",
      { class: "row" },
      selectField("Shroud fan", s, "fan", fans.map((f) => [f.id, f.name]), TIPS.shroudFan),
      numberField("Count", s, "count", TIPS.shroudFan, { min: 0, max: 4 }),
      numberField("Speed %", s, "duty", TIPS.duty, { scale: 100, min: 0, max: 100, step: 5 }),
    ),
  ];
}

function radiatorControls(face) {
  const rad = state.build.radiator;
  const here = !!rad.model && rad.panel === face;
  const out = [el("h3", {}, "Radiator")];
  const toggle = el("input", { type: "checkbox", checked: here });
  toggle.onchange = () => {
    if (toggle.checked) placeRadiator(face, rad.model || state.presets.radiators[0].id);
    else removeRadiator();
    changed(true);
  };
  out.push(el("label", { class: "check", tip: TIPS.radiator }, toggle, `Radiator on the ${face}`));
  if (!here) {
    if (rad.model) out.push(el("p", { class: "fine" }, `The radiator is on the ${rad.panel}. Ticking this moves it here.`));
    return out;
  }
  const models = state.presets.radiators.map((r) => [r.id, `${r.name} · ${r.thickness_mm} mm`]);
  out.push(selectField("Model", rad, "model", models, TIPS.radiator, () => placeRadiator(face, rad.model)));
  out.push(selectField("Direction", rad, "direction", [["exhaust", "exhaust"], ["intake", "intake"]], TIPS.radDir));
  const radFans = state.presets.fans.filter((f) => f.size_mm === 120 || f.size_mm === 140);
  out.push(
    el(
      "div",
      { class: "row" },
      selectField("Radiator fans", rad, "fan", radFans.map((f) => [f.id, f.name]), TIPS.radFans),
      numberField("Count", rad, "fan_count", TIPS.radFans, { min: 1, max: 4 }),
    ),
  );
  if (state.build.cpu?.cooling !== "water") out.push(el("p", { class: "fine warn" }, "CPU is air-cooled: this radiator carries no heat (set CPU to water under Internals)."));
  return out;
}

function placeRadiator(face, model) {
  const rad = state.build.radiator;
  state.build.mounts.forEach((m) => {
    if (m.state === "radiator") m.state = "blanked";
  });
  rad.model = model;
  rad.panel = face;
  const r = state.presets.radiators.find((x) => x.id === model);
  const count = r ? r.fan_count : 3;
  rad.fan_count = rad.fan_count || count;
  if (!rad.fan) rad.fan = r?.default_fan || "generic-120";
  mountsOn(face)
    .slice(0, count)
    .forEach((m) => {
      m.state = "radiator";
      m.fan = null;
    });
}

function removeRadiator() {
  state.build.radiator.model = null;
  state.build.mounts.forEach((m) => {
    if (m.state === "radiator") m.state = "blanked";
  });
  if (state.build.cpu?.cooling === "water") state.build.cpu.cooling = "air";
}

function internalsPanel() {
  const b = state.build;
  const cpu = (b.cpu ||= { power_w: 150, cooling: "air" });
  const out = [el("h2", {}, "Internals"), el("p", { class: "sub" }, "Inside the case: CPU, obstructions, PSU, environment.")];
  out.push(
    selectField(
      "Case",
      b,
      "case",
      state.presets.cases.map((c) => [c.id, c.name]),
      "Case preset: dimensions, slots and mounts are cited on the preset file.",
      () => {
        const kase = caseOf();
        b.mounts = kase.mounts.map((mt) => b.mounts.find((x) => x.id === mt.id) || { id: mt.id, panel: mt.panel, size_mm: mt.size_mm, fan: null, state: "blanked", direction: "intake", duty: 1 });
      },
    ),
  );
  out.push(el("h3", {}, "CPU"));
  const coolBtns = ["air", "water"].map((mode) => {
    const btn = el("button", { type: "button", class: cpu.cooling === mode ? "on" : "", tip: TIPS.cpuCooling }, mode === "air" ? "Air-cooled" : "Water (AIO)");
    btn.onclick = () => {
      cpu.cooling = mode;
      if (mode === "water" && !b.radiator.model) placeRadiator("top", state.presets.radiators[0].id);
      changed(true);
    };
    return btn;
  });
  out.push(el("div", { class: "seg", tip: TIPS.cpuCooling }, ...coolBtns));
  out.push(numberField("CPU heat, W", cpu, "power_w", TIPS.cpuPower, { min: 0, step: 5 }));
  if (cpu.cooling === "air") {
    cpu.cooler_fan ||= "generic-140";
    const fans = state.presets.fans.filter((f) => f.size_mm === 120 || f.size_mm === 140);
    out.push(
      el(
        "div",
        { class: "row" },
        selectField("Tower cooler fan", cpu, "cooler_fan", fans.map((f) => [f.id, f.name]), TIPS.cpuFan),
        numberField("Fans", cpu, "cooler_fan_count", TIPS.cpuFan, { min: 1, max: 2 }),
        numberField("Speed %", cpu, "cooler_duty", TIPS.duty, { scale: 100, min: 0, max: 100, step: 5 }),
      ),
    );
  } else {
    out.push(el("p", { class: "fine" }, b.radiator.model ? `Heat goes out through the radiator on the ${b.radiator.panel} (${b.radiator.direction}).` : "Needs a radiator: add one on the front, top or bottom face."));
  }
  out.push(el("h3", {}, "Internal resistance"));
  out.push(el("div", { class: "row" },
    selectField("Obstruction", b, "obstruction", [["low", "low ×1.0"], ["medium", "medium ×2.5"], ["high", "high ×6.0"]], TIPS.obstruction),
    selectField("Cables", b, "cables", [["clean", "clean ×1.0"], ["cluttered", "cluttered ×2.0"]], TIPS.cables),
  ));
  out.push(el("div", { class: "row" },
    selectField("Drive cage", b, "drive_cage", [["removed", "removed"], ["present", "in the intake path"]], TIPS.cage),
    selectField("PSU", b, "psu_location", [["bottom_shroud", "bottom, shrouded"], ["open", "bottom, open"]], TIPS.psu),
    selectField("PSU fan", b, "psu_fan", [["down", "down"], ["up", "up"]], TIPS.psuFan),
  ));
  out.push(sealSlider("seams", "Panel seams"));
  out.push(el("h3", {}, "Environment"));
  out.push(el("div", { class: "row" },
    numberField("Ambient °C", b, "ambient_c", TIPS.ambient, { step: 0.5 }),
    numberField("Altitude m", b, "altitude_m", TIPS.altitude, { step: 50 }),
    numberField("Wall re-ingest °C", b, "room_reingestion_c", TIPS.reingest, { step: 0.5 }),
  ));
  out.push(checkbox("Buoyancy (stack effect)", "buoyancy", TIPS.buoyancy));
  return out;
}

function gpusPanel() {
  const b = state.build;
  const kase = caseOf();
  const out = [el("h2", {}, "GPUs"), el("p", { class: "sub" }, `${kase.horizontal_slots} horizontal slots${kase.vertical_positions.length ? ` + vertical ${kase.vertical_positions.map((v) => v.id).join(", ")}` : ""}. Card 1 is nearest the CPU; fan faces point down.`)];
  const spacing = ["stacked", "gap1", "gap2", "gap3"].map((sp, i) => {
    const btn = el("button", { type: "button", tip: TIPS.spacing }, i === 0 ? "Stack" : `+${i}`);
    btn.onclick = () => {
      respace(i);
      changed(true);
    };
    return btn;
  });
  out.push(el("div", { class: "row", tip: TIPS.spacing }, el("span", { class: "fine" }, "Spacing"), ...spacing));
  const results = Object.fromEntries((state.solution?.cards || []).map((c) => [c.id, c]));
  const slots = [];
  for (let s = 1; s <= kase.horizontal_slots; s += 1) slots.push([String(s), `slot ${s}`]);
  kase.vertical_positions.forEach((v) => slots.push([v.id, `vertical ${v.id}`]));
  const cardOpts = [];
  const blowers = state.presets.cards.filter((c) => c.cooler !== "flow_through");
  const through = state.presets.cards.filter((c) => c.cooler === "flow_through");
  const group = (label, list) => el("optgroup", { label }, list.map((c) => el("option", { value: c.id }, `${c.name}${c.template ? " (template)" : ""} · ${c.tbp_w} W`)));
  cardOpts.push(group("Blower (rear-bracket exhaust)", blowers), group("Flow-through (exhaust up into the next card)", through));
  b.gpus.forEach((g, index) => {
    const res = results[g.id];
    const card = cardOf(g.card);
    const head = el(
      "div",
      { class: "head" },
      el("b", {}, `${g.id} · ${String(g.slot).startsWith("v") ? `vertical ${g.slot}` : `slot ${g.slot}`}`),
      el("span", { class: "t", style: `color:${tempColor(res?.t_die_c)}` }, res ? fmt(res.t_die_c) : "…"),
    );
    const cardSel = el("select", { tip: TIPS.card }, cardOpts.map((o) => o.cloneNode(true)));
    cardSel.value = g.card;
    cardSel.onchange = () => {
      g.card = cardSel.value;
      g.power_limit_w = cardOf(g.card)?.tbp_w ?? g.power_limit_w;
      changed(true);
    };
    const slotSel = el("select", { tip: TIPS.slot }, slots.map(([v, t]) => el("option", { value: v }, t)));
    slotSel.value = String(g.slot);
    slotSel.onchange = () => {
      g.slot = slotSel.value;
      changed(true);
    };
    const curve = el("select", { tip: TIPS.curve }, [
      el("option", { value: "stock" }, "Stock"),
      el("option", { value: "custom_accelerated" }, "Custom Accelerated (0 % @ 25 °C → 100 % @ 70 °C)"),
      el("option", { value: "custom" }, "Custom points"),
    ]);
    curve.value = g.fan_curve === "maxq_aggressive" ? "custom_accelerated" : g.fan_curve;
    curve.onchange = () => {
      g.fan_curve = curve.value;
      if (curve.value === "custom" && !g.custom_curve) g.custom_curve = [[30, 0.3], [60, 0.55], [75, 0.8], [90, 1]];
      changed(true);
    };
    const box = el(
      "div",
      { class: "box gpu-card" },
      head,
      el("div", {}, el("span", { class: `pill${card?.cooler === "flow_through" ? " ft" : ""}` }, card?.cooler === "flow_through" ? "flow-through" : "blower"), " ", res ? el("span", { class: "fine" }, `${res.flow_cfm.toFixed(1)} CFM · duty ${Math.round(res.duty * 100)}% · ${res.power_w.toFixed(0)} W${res.throttle ? " · THROTTLE" : ""}`) : ""),
      el("label", { tip: TIPS.card }, "Card", cardSel),
      el("div", { class: "row" }, el("label", { tip: TIPS.slot }, "Slot", slotSel), numberField("Power limit W", g, "power_limit_w", TIPS.power, { min: 50, step: 5 })),
      el("label", { tip: TIPS.curve }, "GPU fan curve", curve),
    );
    if (g.fan_curve === "custom") {
      const pts = el("input", { type: "text", value: (g.custom_curve || []).map(([t, d]) => `${t}:${d}`).join(", "), tip: TIPS.customCurve });
      pts.onchange = () => {
        const parsed = pts.value.split(",").map((p) => p.split(":").map(Number)).filter((p) => p.length === 2 && p.every(Number.isFinite));
        if (parsed.length >= 2) {
          g.custom_curve = parsed;
          changed();
        }
      };
      box.append(el("label", { tip: TIPS.customCurve }, "Custom curve °C:duty", pts));
    }
    const adv = el(
      "details",
      {},
      el("summary", {}, "Clocks and voltage (approximations)"),
      el("div", { class: "row" },
        numberField("Mem MHz", g, "memory_clock_offset_mhz", TIPS.memOffset, { step: 50 }),
        numberField("Core MHz", g, "core_clock_offset_mhz", TIPS.coreOffset, { step: 15 }),
        numberField("Undervolt mV", g, "undervolt_mv", TIPS.undervolt, { step: 5 }),
      ),
    );
    box.append(adv);
    if (b.gpus.length > 1) {
      const del = el("button", { type: "button" }, "Remove");
      del.onclick = () => {
        b.gpus.splice(index, 1);
        changed(true);
      };
      box.append(del);
    }
    out.push(box);
  });
  const add = el("button", { type: "button" }, "Add card");
  add.onclick = addGpu;
  out.push(add);
  return out;
}

function respace(gaps) {
  const kase = caseOf();
  const horiz = state.build.gpus.filter((g) => !String(g.slot).startsWith("v")).sort((a, b) => Number(a.slot) - Number(b.slot));
  let cursor = 1;
  horiz.forEach((g) => {
    const width = cardOf(g.card)?.slots || 2;
    if (cursor + width - 1 <= kase.horizontal_slots) g.slot = String(cursor);
    cursor += width + gaps;
  });
}

function addGpu() {
  const kase = caseOf();
  const used = new Set();
  state.build.gpus.forEach((g) => {
    if (String(g.slot).startsWith("v")) return;
    const w = cardOf(g.card)?.slots || 2;
    for (let s = Number(g.slot); s < Number(g.slot) + w; s += 1) used.add(s);
  });
  const card = state.build.gpus[0]?.card || "rtx-pro-6000-blackwell-maxq";
  const w = cardOf(card)?.slots || 2;
  let slot = null;
  for (let s = 1; s + w - 1 <= kase.horizontal_slots; s += 1) {
    let free = true;
    for (let k = s; k < s + w; k += 1) if (used.has(k)) free = false;
    if (free) {
      slot = String(s);
      break;
    }
  }
  if (!slot) slot = kase.vertical_positions.find((v) => !state.build.gpus.some((g) => g.slot === v.id))?.id;
  if (!slot) return;
  let n = state.build.gpus.length + 1;
  while (state.build.gpus.some((g) => g.id === `gpu${n}`)) n += 1;
  state.build.gpus.push(gpuTemplate(`gpu${n}`, slot, card));
  changed(true);
}

function moveFan(fromId, toId) {
  const from = state.build.mounts.find((m) => m.id === fromId);
  const to = state.build.mounts.find((m) => m.id === toId) || mountsOn(caseOf().mounts.find((l) => l.id === toId)?.panel || "front").find((m) => m.id === toId);
  if (!from || !to || from.state !== "fan" || to.state === "radiator") return;
  const keep = { fan: to.fan, state: to.state, direction: to.direction, duty: to.duty };
  to.fan = from.fan;
  to.state = "fan";
  to.direction = from.direction;
  to.duty = from.duty;
  Object.assign(from, keep);
  state.selectedMount = to.id;
  state.face = caseOf().mounts.find((l) => l.id === toId)?.panel || state.face;
  changed(true);
}

function renderFacebar() {
  const b = state.build;
  const kase = caseOf();
  FACES.forEach((face) => {
    const mounts = b.mounts.filter((m) => kase.mounts.some((l) => l.id === m.id && l.panel === face));
    const fans = mounts.filter((m) => m.state === "fan");
    const intake = fans.filter((m) => m.direction === "intake").length;
    const exhaust = fans.length - intake;
    const parts = [];
    if (intake) parts.push(`${intake} in`);
    if (exhaust) parts.push(`${exhaust} out`);
    if (b.radiator?.model && b.radiator.panel === face) parts.push(`rad ${b.radiator.direction}`);
    if (face === "rear" && b.shroud?.mode !== "off") parts.push(`shroud ${b.shroud.mode}`);
    if (face === "side") parts.push(b.side_panel === "tempered_glass" ? "glass" : b.side_panel);
    const level = b.seals?.[SEAL_FOR_FACE[face]];
    if (level) parts.push(`seal ${level}`);
    $(`fb-${face}`).textContent = parts.join(" · ") || (kase.mounts.some((l) => l.panel === face) ? "blanked" : "no mounts");
  });
  $("fb-internals").textContent = `CPU ${b.cpu?.cooling || "?"} ${Math.round(b.cpu?.power_w ?? 0)} W · ${b.obstruction}`;
  $("fb-gpus").textContent = `${b.gpus.length} card${b.gpus.length === 1 ? "" : "s"}`;
}

/* ------------------------------------------------------------------ solve + results */

let timer = null;
function changed(rerenderPanel = false) {
  if (rerenderPanel) renderPanel();
  else renderFacebar();
  state.scene?.update(sceneCtx());
  renderInset();
  clearTimeout(timer);
  timer = setTimeout(solveNow, 160);
}

async function solveNow() {
  $("ambient-readout").textContent = `ambient ${fmt(Number(state.build.ambient_c))}`;
  try {
    const res = await fetch("/api/solve", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(state.build) });
    const body = await res.json();
    if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
    state.solution = body;
  } catch (err) {
    state.solution = { error: String(err.message || err), cards: [], branches: [], notes: [] };
  }
  renderResults();
  if (state.face === "gpus") renderPanel();
}

function sceneCtx() {
  return {
    build: state.build,
    kase: caseOf(),
    solution: state.solution && !state.solution.error ? state.solution : null,
    presets: state.presets,
    selectedMount: state.selectedMount,
    fmt,
    tempColor,
  };
}

function renderResults() {
  if (!state.build) return;
  renderReadout();
  state.scene?.update(sceneCtx());
  renderInset();
  if (state.net !== "off") renderNetwork($("netview"), { solution: state.solution, build: state.build, presets: state.presets, fmt, mode: state.net });
  if (state.compare) renderCompare();
  renderFacebar();
}

function renderReadout() {
  const sol = state.solution;
  const root = $("readout");
  if (!sol || sol.error) {
    root.innerHTML = "";
    root.append(el("p", { class: "warn" }, sol ? sol.error : "Solving…"));
    return;
  }
  const sign = sol.case_pressure_pa >= 0 ? "+" : "−";
  $("pressure-readout").textContent = `case ${sign}${Math.abs(sol.case_pressure_pa).toFixed(1)} Pa`;
  const throttled = sol.cards.some((c) => c.throttle);
  $("hot-readout").textContent = `hottest ${fmt(sol.hottest_die_c)}${throttled ? ` (unthrottled ${fmt(sol.hottest_unthrottled_c)})` : ""}`;
  $("hot-readout").style.color = tempColor(sol.hottest_die_c);
  root.innerHTML = "";
  sol.cards.forEach((c) => {
    const card = cardOf(c.card);
    const plume = (sol.plume || []).find((p) => p.upper === c.id && p.share_of_upper_intake > 0.005);
    root.append(
      el(
        "div",
        { class: "card-row" },
        el("h3", {}, el("span", {}, `${c.id} · ${String(c.slot).startsWith("v") ? c.slot : `slot ${c.slot}`}`), c.throttle ? el("span", { class: "throttle", tip: TIPS.unthrottled }, "THROTTLE") : ""),
        el("div", { class: "temp", style: `color:${tempColor(c.t_die_c)}` }, fmt(c.t_die_c)),
        el("div", { class: "fine", tip: TIPS.unthrottled }, `unthrottled ${fmt(c.t_die_unthrottled_c)} · mem ${fmt(c.t_mem_c)}`),
        el("div", { class: "fine" }, `inlet ${fmt(c.t_in_c)} · exhaust ${fmt(c.t_exh_c)}`),
        el("div", { class: "fine" }, `${c.flow_cfm.toFixed(1)} CFM · fan ${Math.round(c.duty * 100)}% · ${c.power_w.toFixed(0)} W · ${c.gap_state} ${c.gap_mm.toFixed(1)} mm`),
        el("div", { class: "fine" }, `${card ? card.name : c.card} · ${c.fan_curve === "custom_accelerated" ? "Custom Accelerated" : c.fan_curve}`),
        plume ? el("div", { class: "plume-note", tip: "Plume ingestion: this card's fans draw part of the exhaust jet of the flow-through card below it." }, `breathes ${Math.round(plume.share_of_upper_intake * 100)}% of ${plume.lower}'s exhaust (${plume.t_from_c?.toFixed(1)} °C)`) : "",
      ),
    );
  });
  root.append(
    el("p", { class: "fine" }, `Heat ${sol.heat_w.toFixed(0)} W · energy balance ${(sol.energy_error * 100).toFixed(3)}% · mass residual ${sol.residual_kg_s.toExponential(1)} kg/s`),
    ...sol.notes.map((n) => el("p", { class: "fine" }, n)),
  );
}

/* Head-on drawing of the selected face, scaled so every fan is visible. */
function renderInset() {
  const root = $("face-inset");
  if (!state.build || !FACES.includes(state.face)) {
    root.classList.add("hidden");
    return;
  }
  const kase = caseOf();
  const face = state.face;
  const W = kase.width_mm;
  const H = kase.height_mm;
  const D = kase.depth_mm;
  const dims = { front: [W, H], rear: [W, H], top: [D, W], bottom: [D, W], side: [D, H] }[face];
  const map = (l) => {
    switch (face) {
      case "front": return [W - l.z_mm, H - l.y_mm];
      case "rear": return [l.z_mm, H - l.y_mm];
      case "top": return [l.x_mm, l.z_mm];
      case "bottom": return [l.x_mm, W - l.z_mm];
      default: return [l.x_mm, H - l.y_mm];
    }
  };
  const maxW = 250;
  const maxH = 230;
  const s = Math.min(maxW / dims[0], maxH / dims[1]);
  const w = dims[0] * s;
  const h = dims[1] * s;
  const layouts = kase.mounts.filter((l) => l.panel === face);
  const parts = [`<rect x="1" y="1" width="${w - 2}" height="${h - 2}" rx="6" fill="#1c1813" stroke="#6d6254"/>`];
  const rad = state.build.radiator;
  if (rad?.model && rad.panel === face) {
    const on = layouts.filter((l) => state.build.mounts.find((m) => m.id === l.id)?.state === "radiator");
    if (on.length) {
      const xs = on.map((l) => map(l)[0]);
      const ys = on.map((l) => map(l)[1]);
      const r = (on[0].size_mm / 2) * s;
      parts.push(`<rect x="${Math.min(...xs) - r - 4}" y="${Math.min(...ys) - r - 4}" width="${Math.max(...xs) - Math.min(...xs) + 2 * r + 8}" height="${Math.max(...ys) - Math.min(...ys) + 2 * r + 8}" fill="none" stroke="#e0a15a" stroke-width="2" stroke-dasharray="4 3"/>`);
    }
  }
  layouts.forEach((l) => {
    const mnt = state.build.mounts.find((m) => m.id === l.id) || { state: "blanked" };
    const [x, y] = map(l);
    const r = (l.size_mm / 2) * s * 0.94;
    const color = mnt.state === "fan" ? (mnt.direction === "intake" ? "#3c8dff" : "#e24b3b") : mnt.state === "radiator" ? (rad.direction === "intake" ? "#3c8dff" : "#e24b3b") : "#8d877e";
    const fill = mnt.state === "fan" || mnt.state === "radiator" ? color : "none";
    const sel = state.selectedMount === l.id ? ' stroke="#f3efe6" stroke-width="3"' : ` stroke="${color}" stroke-width="1.5"`;
    const fan = fanOf(mnt.fan);
    const tip = `${l.id} · ${l.size_mm} mm · ${mnt.state === "fan" ? `${fan ? fan.name : mnt.fan} · ${mnt.direction} · ${Math.round((mnt.duty ?? 1) * 100)}%` : mnt.state}`;
    parts.push(`<circle class="fan" data-id="${l.id}" data-tip="${tip}" cx="${x * s}" cy="${y * s}" r="${r}" fill="${fill}" fill-opacity="0.75"${sel}/>`);
  });
  const orient = { front: "seen from the front (glass side on the left)", rear: "seen from behind", top: "seen from above (front at left)", bottom: "seen from below", side: "glass side (front at left)" }[face];
  root.innerHTML = `<div>${face[0].toUpperCase() + face.slice(1)} face · ${Math.round(dims[0])} × ${Math.round(dims[1])} mm · ${orient}</div><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${parts.join("")}</svg>`;
  root.classList.remove("hidden");
  root.querySelectorAll("circle.fan").forEach((c) => {
    c.onclick = () => {
      state.selectedMount = c.dataset.id;
      renderPanel();
      renderInset();
      state.scene?.update(sceneCtx());
    };
  });
}

/* ------------------------------------------------------------------ compare, demo, optimize */

function toggleCompare() {
  if (state.compare) {
    state.compare = null;
    $("compare").classList.add("hidden");
    return;
  }
  state.compare = { build: JSON.parse(JSON.stringify(state.build)), solution: state.solution };
  $("compare").classList.remove("hidden");
  renderCompare();
}

function renderCompare() {
  const a = state.compare.solution;
  const b = state.solution;
  if (!a || !b || a.error || b.error) return;
  const n = Math.max(a.cards.length, b.cards.length);
  let rows = "";
  for (let i = 0; i < n; i += 1) {
    const ca = a.cards[i];
    const cb = b.cards[i];
    const d = ca && cb ? cb.t_die_c - ca.t_die_c : null;
    rows += `<tr><td>${cb ? cb.id : ca.id}</td><td>${ca ? fmt(ca.t_die_c) : "—"}</td><td>${cb ? fmt(cb.t_die_c) : "—"}</td><td>${d == null ? "—" : (d > 0 ? "+" : "") + d.toFixed(1)}</td></tr>`;
  }
  $("compare").innerHTML = `
    <div><h2>A · frozen: ${state.compare.build.name}</h2>
      <table><tr><th>Card</th><th>A</th><th>B (live)</th><th>Δ</th></tr>${rows}</table></div>
    <div><h2>B · live: ${state.build.name}</h2>
      <p class="fine">Case A ${a.case_pressure_pa.toFixed(1)} Pa · B ${b.case_pressure_pa.toFixed(1)} Pa. Edit the live build; A stays until you press Compare again.</p></div>`;
}

async function startDemo(id) {
  const choice = id || (state.build && state.build.illustrative_mock ? "mike-bradley-demo" : "stefano-demo");
  state.demo = { id: choice, index: 0 };
  $("demo-bar").classList.remove("hidden");
  await loadDemoStep();
}

function stopDemo() {
  state.demo = null;
  clearInterval(state.demoTimer);
  $("demo-bar").classList.add("hidden");
}

async function stepDemo(delta) {
  if (!state.demo) return startDemo();
  const scenario = state.presets.scenarios.find((s) => s.id === state.demo.id);
  state.demo.index = Math.max(0, Math.min(scenario.steps.length - 1, state.demo.index + delta));
  await loadDemoStep();
}

async function loadDemoStep() {
  const res = await fetch("/api/scenario", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ scenario_id: state.demo.id, step: state.demo.index }),
  });
  const body = await res.json();
  state.build = body.optimal ? body.optimal.build : body.build;
  if (body.scenario.illustrative_mock) state.build.illustrative_mock = true;
  $("demo-title").textContent = body.step.title;
  $("demo-points").textContent = (body.step.talking_points || []).join(" ");
  const scenario = state.presets.scenarios.find((s) => s.id === state.demo.id);
  $("demo-count").textContent = `${state.demo.index + 1} / ${scenario.steps.length}`;
  enterApp();
  await solveNow();
  syncDemoTimer();
}

function syncDemoTimer() {
  clearInterval(state.demoTimer);
  if (!$("demo-auto").checked || !state.demo) return;
  state.demoTimer = setInterval(() => stepDemo(1), 9000);
}

function onKey(ev) {
  if (ev.target.matches("input, select, textarea")) return;
  if (!state.demo) return;
  if (ev.key === "ArrowRight") stepDemo(1);
  if (ev.key === "ArrowLeft") stepDemo(-1);
  if (ev.key === "Escape") stopDemo();
}

async function runOptimal() {
  const btn = $("opt-run");
  btn.textContent = "Searching…";
  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cards: state.build.gpus.length, case: state.build.case, mc: 30 }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || "search failed");
    state.build = body.build;
    state.build.name = `Optimal · ${body.description.layout}, shroud ${body.description.shroud}, ${body.description.pressure}, ${body.description.leakage}, ${body.description.fan_curve}`;
    enterApp();
    await solveNow();
  } catch (err) {
    alertBox(String(err.message || err));
  } finally {
    btn.textContent = "Optimize";
  }
}

function alertBox(text) {
  $("readout").prepend(el("p", { class: "warn" }, text));
}

// Handle for scripted checks (headless screenshots, OBS macros). Not an API.
window.gpusim = { state, setFace, setNet, setView, changed, loadBuild, respace, solveNow };

boot();
