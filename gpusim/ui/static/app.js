/* gpusim visualizer. Solver stays on the server. */
const state = {
  presets: null,
  build: null,
  solution: null,
  compare: null,
  selectedMount: null,
  unitF: false,
  demo: null,
  demoTimer: null,
  scene: null,
};

const $ = (id) => document.getElementById(id);

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
  const rgb = a.map((v, k) => Math.round(v + (b[k] - v) * u));
  return `rgb(${rgb.join(",")})`;
}

async function boot() {
  state.presets = await (await fetch("/api/presets")).json();
  fillSelect($("case-select"), state.presets.cases, (c) => [c.id, c.name]);
  const rads = [{ id: "", name: "(none)" }, ...state.presets.radiators];
  fillSelect($("rad-model"), rads, (r) => [r.id, r.name]);
  const shroudFans = state.presets.fans.filter((f) => f.size_mm === 140);
  fillSelect($("shroud-fan"), shroudFans, (f) => [f.id, f.name]);
  $("quick-meshify").onclick = () => quick("meshify2xl-stefano");
  $("quick-9000").onclick = () => quick("mike-bradley-powerhouse");
  $("from-scratch").onclick = () => scratch();
  $("unit-toggle").onclick = () => {
    state.unitF = !state.unitF;
    $("unit-toggle").textContent = state.unitF ? "°C" : "°F";
    render();
  };
  $("present-toggle").onclick = () => document.body.classList.toggle("present");
  $("compare-toggle").onclick = toggleCompare;
  $("demo-toggle").onclick = startDemo;
  $("demo-next").onclick = () => stepDemo(1);
  $("demo-prev").onclick = () => stepDemo(-1);
  $("demo-auto").onchange = syncDemoTimer;
  $("opt-run").onclick = runOptimal;
  $("add-gpu").onclick = addGpu;
  ["ambient", "altitude", "obstruction", "cables", "drive-cage", "side-panel", "brackets", "buoyancy",
    "rad-model", "rad-panel", "rad-dir", "cpu-power", "shroud-mode", "shroud-count", "shroud-fan", "case-select",
  ].forEach((id) => $(id).addEventListener("change", readControls));
  window.addEventListener("keydown", onKey);
}

function fillSelect(el, items, map) {
  el.innerHTML = "";
  items.forEach((item) => {
    const [value, label] = map(item);
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    el.appendChild(opt);
  });
}

async function quick(id) {
  state.build = await (await fetch(`/api/build/${id}`)).json();
  $("start").classList.add("hidden");
  $("app").classList.remove("hidden");
  ensureScene();
  pushControls();
  await solveNow();
}

function scratch() {
  const kase = state.presets.cases.find((c) => c.id === "generic-atx");
  state.build = {
    id: "scratch",
    name: "Build from scratch",
    case: "generic-atx",
    ambient_c: 25,
    altitude_m: 0,
    gpus: [{
      id: "gpu1", slot: "1", card: "rtx-pro-6000-blackwell-maxq", fan_curve: "stock",
      power_limit_w: 300, memory_clock_offset_mhz: 0, core_clock_offset_mhz: 0, undervolt_mv: 0,
    }],
    mounts: kase.mounts.map((m) => ({
      id: m.id, panel: m.panel, size_mm: m.size_mm, fan: null, state: "blanked", direction: "intake", duty: 1,
    })),
    radiator: { model: null, panel: "top", direction: "exhaust", arrangement: "push", cpu_power_w: 120, fan: "generic-120", fan_count: 2, fan_duty: 1 },
    shroud: { mode: "off", fan: "noctua-nf-a14-ippc-3000", count: 2, duty: 1 },
    seals: { front: 3, top: 3, bottom: 3, side: 2, seams: 3, rear_slots: 3 },
    filters: { front: "fine", top: "none", bottom: "none" },
    obstruction: "medium", cables: "clean", psu_location: "bottom_shroud", psu_fan: "down",
    drive_cage: "removed", side_panel: "tempered_glass", brackets_removed: true,
    room_reingestion_c: 0, buoyancy: false, open_air: false, illustrative_mock: false, notes: "",
  };
  $("start").classList.add("hidden");
  $("app").classList.remove("hidden");
  ensureScene();
  pushControls();
  solveNow();
}

function caseOf() {
  return state.presets.cases.find((c) => c.id === state.build.case);
}

function pushControls() {
  const b = state.build;
  $("build-name").textContent = b.name || b.id;
  $("mock-banner").classList.toggle("hidden", !b.illustrative_mock);
  $("case-select").value = b.case;
  $("ambient").value = b.ambient_c;
  $("altitude").value = b.altitude_m;
  $("obstruction").value = b.obstruction;
  $("cables").value = b.cables;
  $("drive-cage").value = b.drive_cage;
  $("side-panel").value = b.side_panel;
  $("brackets").checked = !!b.brackets_removed;
  $("buoyancy").checked = !!b.buoyancy;
  $("rad-model").value = b.radiator?.model || "";
  $("rad-panel").value = b.radiator?.panel || "top";
  $("rad-dir").value = b.radiator?.direction || "exhaust";
  $("cpu-power").value = b.radiator?.cpu_power_w ?? 150;
  $("shroud-mode").value = b.shroud?.mode || "off";
  $("shroud-count").value = b.shroud?.count ?? 2;
  $("shroud-fan").value = b.shroud?.fan || "noctua-nf-a14-ippc-3000";
  renderMounts();
  renderGpus();
  renderSeals();
}

function readControls() {
  const b = state.build;
  if ($("case-select").value !== b.case) {
    b.case = $("case-select").value;
    const kase = caseOf();
    b.mounts = kase.mounts.map((m) => {
      const prev = b.mounts.find((x) => x.id === m.id);
      return prev || { id: m.id, panel: m.panel, size_mm: m.size_mm, fan: null, state: "blanked", direction: "intake", duty: 1 };
    });
  }
  b.ambient_c = Number($("ambient").value);
  b.altitude_m = Number($("altitude").value);
  b.obstruction = $("obstruction").value;
  b.cables = $("cables").value;
  b.drive_cage = $("drive-cage").value;
  b.side_panel = $("side-panel").value;
  b.brackets_removed = $("brackets").checked;
  b.buoyancy = $("buoyancy").checked;
  b.radiator.model = $("rad-model").value || null;
  b.radiator.panel = $("rad-panel").value;
  b.radiator.direction = $("rad-dir").value;
  b.radiator.cpu_power_w = Number($("cpu-power").value);
  b.shroud.mode = $("shroud-mode").value;
  b.shroud.count = Number($("shroud-count").value);
  b.shroud.fan = $("shroud-fan").value;
  b.mounts.forEach((m) => {
    if (m.panel === b.radiator.panel && b.radiator.model) m.state = m.state === "fan" ? "fan" : "radiator";
  });
  scheduleSolve();
}

function topFans(size) {
  return state.presets.fans
    .filter((f) => f.size_mm === size)
    .sort((a, b) => b.static_pressure_mmh2o - a.static_pressure_mmh2o)
    .slice(0, 10);
}

function genericFor(size) {
  return state.presets.fans.find((f) => f.id === `generic-${size}`) || topFans(size)[0];
}

function renderMounts() {
  const root = $("mount-list");
  root.innerHTML = "";
  state.build.mounts.forEach((m) => {
    const box = document.createElement("div");
    box.className = "mount" + (state.selectedMount === m.id ? " selected" : "");
    const dir = m.state === "fan" ? m.direction : m.state;
    box.innerHTML = `<div><span class="swatch ${dir}"></span><b>${m.id}</b> ${m.size_mm} mm · ${dir}</div>`;
    const row = document.createElement("div");
    const add = document.createElement("button");
    add.type = "button";
    add.textContent = m.state === "fan" ? "Remove" : "Add fan";
    add.onclick = () => {
      if (m.state === "fan") {
        m.state = "blanked"; m.fan = null;
      } else {
        const fan = genericFor(m.size_mm);
        m.state = "fan"; m.fan = fan.id; m.direction = m.panel === "rear" || m.panel === "top" ? "exhaust" : "intake";
      }
      state.selectedMount = m.id;
      renderMounts();
      scheduleSolve();
    };
    const flip = document.createElement("button");
    flip.type = "button";
    flip.textContent = "Flip";
    flip.onclick = () => {
      if (m.state !== "fan") return;
      m.direction = m.direction === "intake" ? "exhaust" : "intake";
      renderMounts();
      scheduleSolve();
    };
    const sel = document.createElement("select");
    topFans(m.size_mm).forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = `${f.name} · ${f.static_pressure_mmh2o} mmH₂O · ${f.rpm_max} rpm · ${f.airflow_cfm} CFM`;
      sel.appendChild(opt);
    });
    sel.value = m.fan || "";
    sel.onchange = () => { m.fan = sel.value; m.state = "fan"; scheduleSolve(); };
    row.append(add, flip, sel);
    box.appendChild(row);
    box.onclick = (ev) => {
      if (ev.target.tagName === "BUTTON" || ev.target.tagName === "SELECT") return;
      state.selectedMount = m.id;
      renderMounts();
    };
    root.appendChild(box);
  });
}

function renderGpus() {
  const root = $("gpu-list");
  root.innerHTML = "";
  const kase = caseOf();
  const slots = [];
  for (let s = 1; s <= kase.horizontal_slots; s += 1) slots.push(String(s));
  kase.vertical_positions.forEach((v) => slots.push(v.id));
  state.build.gpus.forEach((g, index) => {
    const box = document.createElement("div");
    box.className = "gpu-edit";
    box.innerHTML = `<b>${g.id}</b> approximation inputs`;
    const slot = document.createElement("select");
    slots.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s; opt.textContent = s.startsWith("v") ? `vertical ${s}` : `slot ${s}`;
      slot.appendChild(opt);
    });
    slot.value = String(g.slot);
    slot.onchange = () => { g.slot = slot.value; scheduleSolve(); };
    const card = document.createElement("select");
    state.presets.cards.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.template ? `${c.name} (template)` : c.name;
      card.appendChild(opt);
    });
    card.value = g.card;
    card.onchange = () => { g.card = card.value; scheduleSolve(); };
    const curve = document.createElement("select");
    ["stock", "maxq_aggressive", "custom"].forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name; opt.textContent = name === "custom" ? "custom curve" : name;
      curve.appendChild(opt);
    });
    curve.value = g.fan_curve;
    curve.onchange = () => {
      g.fan_curve = curve.value;
      if (curve.value === "custom" && !g.custom_curve) {
        g.custom_curve = [[30, 0.3], [60, 0.55], [75, 0.8], [90, 1]];
      }
      scheduleSolve();
    };
    const power = numInput(g.power_limit_w, (v) => { g.power_limit_w = v; });
    const mem = numInput(g.memory_clock_offset_mhz, (v) => { g.memory_clock_offset_mhz = v; });
    const core = numInput(g.core_clock_offset_mhz, (v) => { g.core_clock_offset_mhz = v; });
    const uv = numInput(g.undervolt_mv, (v) => { g.undervolt_mv = v; });
    box.append(" slot ", slot, " card ", card, " curve ", curve);
    box.append(field("Power limit W", power), field("Mem offset MHz", mem), field("Core offset MHz", core), field("Undervolt mV", uv));
    if (state.build.gpus.length > 1) {
      const del = document.createElement("button");
      del.type = "button"; del.textContent = "Remove card";
      del.onclick = () => { state.build.gpus.splice(index, 1); renderGpus(); scheduleSolve(); };
      box.appendChild(del);
    }
    root.appendChild(box);
  });
}

function field(label, input) {
  const wrap = document.createElement("label");
  wrap.textContent = label;
  wrap.appendChild(input);
  return wrap;
}

function numInput(value, onChange) {
  const input = document.createElement("input");
  input.type = "number";
  input.value = value ?? 0;
  input.onchange = () => onChange(Number(input.value));
  return input;
}

function renderSeals() {
  const seals = $("seal-list");
  seals.innerHTML = "";
  const names = ["front", "top", "bottom", "side", "seams", "rear_slots"];
  names.forEach((name) => {
    const label = document.createElement("label");
    label.textContent = `${name} seal 1–5`;
    const input = document.createElement("input");
    input.type = "range"; input.min = 1; input.max = 5; input.value = state.build.seals[name] || 3;
    input.oninput = () => { state.build.seals[name] = Number(input.value); scheduleSolve(); };
    label.appendChild(input);
    seals.appendChild(label);
  });
  const filters = $("filter-list");
  filters.innerHTML = "";
  ["front", "top", "bottom"].forEach((name) => {
    const label = document.createElement("label");
    label.textContent = `${name} filter`;
    const sel = document.createElement("select");
    ["none", "fine", "dense"].forEach((v) => {
      const opt = document.createElement("option"); opt.value = v; opt.textContent = v; sel.appendChild(opt);
    });
    sel.value = (state.build.filters && state.build.filters[name]) || "none";
    sel.onchange = () => { state.build.filters[name] = sel.value; scheduleSolve(); };
    label.appendChild(sel);
    filters.appendChild(label);
  });
}

function addGpu() {
  const kase = caseOf();
  const used = new Set(state.build.gpus.map((g) => String(g.slot)));
  let slot = "1";
  for (let s = 1; s <= kase.horizontal_slots; s += 2) {
    if (!used.has(String(s))) { slot = String(s); break; }
  }
  const n = state.build.gpus.length + 1;
  state.build.gpus.push({
    id: `gpu${n}`, slot, card: "rtx-pro-6000-blackwell-maxq", fan_curve: "stock",
    power_limit_w: 300, memory_clock_offset_mhz: 0, core_clock_offset_mhz: 0, undervolt_mv: 0,
  });
  renderGpus();
  scheduleSolve();
}

let timer = null;
function scheduleSolve() {
  clearTimeout(timer);
  timer = setTimeout(solveNow, 160);
}

async function solveNow() {
  pushAmbient();
  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(state.build),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || "solve failed");
    state.solution = body;
  } catch (err) {
    state.solution = { error: String(err.message || err), cards: [], branches: [], notes: [] };
  }
  render();
}

function pushAmbient() {
  $("ambient-readout").textContent = `ambient ${fmt(Number(state.build.ambient_c))}`;
}

function render() {
  renderReadout();
  draw3d();
  drawLabels();
  if (state.compare) renderCompare();
}

function renderReadout() {
  const sol = state.solution;
  const root = $("readout");
  if (!sol || sol.error) {
    root.innerHTML = `<p class="warn">${sol ? sol.error : "Solving…"}</p>`;
    return;
  }
  const sign = sol.case_pressure_pa >= 0 ? "+" : "−";
  $("pressure-readout").textContent = `case ${sign}${Math.abs(sol.case_pressure_pa).toFixed(1)} Pa`;
  root.innerHTML = `<p class="fine">Energy balance ${(sol.energy_error * 100).toFixed(2)}% · residual ${sol.residual_kg_s.toExponential(1)} kg/s</p>`;
  sol.cards.forEach((c) => {
    const div = document.createElement("div");
    div.className = "card-row";
    div.innerHTML = `
      <h3>${c.id} · slot ${c.slot} ${c.throttle ? '<span class="throttle">THROTTLE</span>' : ""}</h3>
      <div class="temp" style="color:${tempColor(c.t_die_c)}">${fmt(c.t_die_c)}</div>
      <div class="fine">unthrottled ${fmt(c.t_die_unthrottled_c)} · mem ${fmt(c.t_mem_c)} · exhaust ${fmt(c.t_exh_c)}</div>
      <div class="fine">${c.flow_cfm.toFixed(1)} CFM · duty ${(c.duty * 100).toFixed(0)}% · ${c.gap_state} ${c.gap_mm.toFixed(1)} mm · ${c.power_w.toFixed(0)} W</div>`;
    root.appendChild(div);
  });
  const hotBranches = (sol.branches || []).filter((b) => Math.abs(b.flow_cfm) > 1).slice(0, 8);
  hotBranches.forEach((b) => {
    const p = document.createElement("p");
    p.className = "fine";
    p.textContent = `${b.label}: k=${b.k.toExponential(2)} · ${b.flow_cfm.toFixed(1)} CFM · ΔP ${b.dp_pa.toFixed(1)} Pa`;
    root.appendChild(p);
  });
}

function ensureScene() {
  if (state.scene || typeof THREE === "undefined") return;
  const canvas = $("scene");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#0c0b09");
  const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 20);
  scene.add(new THREE.AmbientLight(0xffffff, 0.65));
  const key = new THREE.DirectionalLight(0xfff2e0, 0.9);
  key.position.set(2, 3, 4);
  scene.add(key);
  const root = new THREE.Group();
  scene.add(root);
  state.scene = { renderer, scene, camera, root, drag: null };
  function resize() {
    const w = canvas.clientWidth || canvas.parentElement.clientWidth;
    const h = canvas.clientHeight || 520;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointerup", onPointerUp);
  (function loop() {
    resize();
    renderer.render(scene, camera);
    requestAnimationFrame(loop);
  })();
}

function onPointerDown(ev) {
  if (!state.scene) return;
  const hit = pick(ev);
  if (!hit) return;
  state.scene.drag = hit.object.userData;
}

function onPointerUp(ev) {
  if (!state.scene || !state.scene.drag) return;
  const drag = state.scene.drag;
  state.scene.drag = null;
  const kase = caseOf();
  const rect = $("scene").getBoundingClientRect();
  const nx = (ev.clientX - rect.left) / rect.width;
  const ny = (ev.clientY - rect.top) / rect.height;
  if (drag.kind === "fan") {
    const mounts = kase.mounts;
    let best = null;
    let bestD = 1e9;
    mounts.forEach((m) => {
      const p = project(m.x_mm, m.y_mm, m.z_mm);
      if (!p) return;
      const d = (p.x - nx) ** 2 + (p.y - ny) ** 2;
      if (d < bestD) { bestD = d; best = m; }
    });
    if (best && bestD < 0.04) {
      const moving = state.build.mounts.find((m) => m.id === drag.id);
      const dest = state.build.mounts.find((m) => m.id === best.id);
      if (moving && dest && moving !== dest) {
        const fan = moving.fan; const direction = moving.direction; const duty = moving.duty;
        moving.fan = dest.fan; moving.direction = dest.direction; moving.duty = dest.duty;
        moving.state = dest.state === "fan" ? "fan" : "blanked";
        dest.fan = fan; dest.direction = direction; dest.duty = duty; dest.state = "fan";
        renderMounts();
        scheduleSolve();
      }
    }
  }
  if (drag.kind === "gpu") {
    const slots = slotPoints();
    let best = null; let bestD = 1e9;
    slots.forEach((s) => {
      const p = project(s.x, s.y, s.z);
      if (!p) return;
      const d = (p.x - nx) ** 2 + (p.y - ny) ** 2;
      if (d < bestD) { bestD = d; best = s; }
    });
    if (best && bestD < 0.05) {
      const gpu = state.build.gpus.find((g) => g.id === drag.id);
      if (gpu) { gpu.slot = best.slot; renderGpus(); scheduleSolve(); }
    }
  }
}

function pick(ev) {
  const canvas = $("scene");
  const rect = canvas.getBoundingClientRect();
  const pointer = new THREE.Vector2(
    ((ev.clientX - rect.left) / rect.width) * 2 - 1,
    -((ev.clientY - rect.top) / rect.height) * 2 + 1,
  );
  const ray = new THREE.Raycaster();
  ray.setFromCamera(pointer, state.scene.camera);
  const hits = ray.intersectObjects(state.scene.root.children, true);
  return hits.find((h) => h.object.userData && h.object.userData.id);
}

function project(xMm, yMm, zMm) {
  if (!state.scene) return null;
  const v = new THREE.Vector3(xMm / 1000, yMm / 1000, zMm / 1000);
  v.project(state.scene.camera);
  return { x: (v.x + 1) / 2, y: (1 - v.y) / 2 };
}

function slotPoints() {
  const kase = caseOf();
  const pts = [];
  for (let s = 1; s <= kase.horizontal_slots; s += 1) {
    pts.push({
      slot: String(s),
      x: kase.depth_mm * 0.55,
      y: kase.top_slot_y_mm - (s - 1) * kase.slot_pitch_mm,
      z: kase.width_mm * 0.45,
    });
  }
  kase.vertical_positions.forEach((v) => {
    pts.push({ slot: v.id, x: kase.depth_mm * 0.62, y: v.y_mm, z: v.z_mm });
  });
  return pts;
}

function draw3d() {
  ensureScene();
  if (!state.scene || !state.build) return;
  const { root, camera } = state.scene;
  while (root.children.length) root.remove(root.children[0]);
  const kase = caseOf();
  const w = kase.width_mm / 1000;
  const h = kase.height_mm / 1000;
  const d = kase.depth_mm / 1000;
  const shell = new THREE.Mesh(
    new THREE.BoxGeometry(d, h, w),
    new THREE.MeshStandardMaterial({ color: 0x2a241c, transparent: true, opacity: 0.18, metalness: 0.1, roughness: 0.8 }),
  );
  shell.position.set(d / 2, h / 2, w / 2);
  root.add(shell);
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(d, h, w)),
    new THREE.LineBasicMaterial({ color: 0x6b5e50 }),
  );
  edges.position.copy(shell.position);
  root.add(edges);
  state.build.mounts.forEach((m) => {
    const layout = kase.mounts.find((x) => x.id === m.id);
    if (!layout) return;
    const color = m.state !== "fan" ? 0x8d877e : m.direction === "intake" ? 0x3c8dff : 0xe24b3b;
    const mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(m.size_mm / 2000, m.size_mm / 2000, 0.025, 20),
      new THREE.MeshStandardMaterial({ color, roughness: 0.45 }),
    );
    mesh.rotation.x = Math.PI / 2;
    mesh.position.set(layout.x_mm / 1000, layout.y_mm / 1000, layout.z_mm / 1000);
    mesh.userData = { id: m.id, kind: "fan" };
    root.add(mesh);
  });
  const slots = Object.fromEntries(slotPoints().map((s) => [s.slot, s]));
  (state.solution?.cards || []).forEach((card) => {
    const gpu = state.build.gpus.find((g) => g.id === card.id);
    const at = slots[String(gpu?.slot || card.slot)];
    if (!at) return;
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.26, 0.036, 0.11),
      new THREE.MeshStandardMaterial({ color: tempColor(card.t_die_c), roughness: 0.4 }),
    );
    mesh.position.set(at.x / 1000, at.y / 1000, at.z / 1000);
    mesh.userData = { id: card.id, kind: "gpu" };
    root.add(mesh);
  });
  camera.position.set(d * 0.45, h * 0.55, w + d * 0.85);
  camera.lookAt(d * 0.5, h * 0.45, w * 0.4);
}

function drawLabels() {
  const layer = $("labels");
  layer.innerHTML = "";
  if (!state.solution || !state.solution.branches || !state.scene) return;
  const interesting = state.solution.branches.filter((b) => Math.abs(b.flow_cfm) >= 8 && b.kind !== "bleed");
  interesting.slice(0, 14).forEach((b) => {
    const pos = branchAnchor(b);
    if (!pos) return;
    const p = project(pos.x, pos.y, pos.z);
    if (!p || p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1) return;
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.style.left = `${p.x * 100}%`;
    tag.style.top = `${p.y * 100}%`;
    tag.innerHTML = `<b>${b.flow_cfm.toFixed(0)} CFM</b> ΔP ${b.dp_pa.toFixed(0)} Pa<br>k ${b.k.toExponential(1)}`;
    layer.appendChild(tag);
  });
}

function branchAnchor(br) {
  const kase = caseOf();
  const slots = Object.fromEntries(slotPoints().map((s) => [s.slot, s]));
  const id = br.id || "";
  if (id.startsWith("blower-") || id.startsWith("gap-") || id.startsWith("bracket-")) {
    const gid = id.split("-").slice(1).join("-");
    const gpu = state.build.gpus.find((g) => g.id === gid);
    const at = gpu && slots[String(gpu.slot)];
    if (at) return { x: at.x, y: at.y + 30, z: at.z };
  }
  if (id.startsWith("mount-")) {
    const mid = id.slice(6);
    const layout = kase.mounts.find((m) => m.id === mid);
    if (layout) return { x: layout.x_mm, y: layout.y_mm + 20, z: layout.z_mm };
  }
  if (id === "radiator") return { x: kase.depth_mm * 0.5, y: kase.height_mm - 30, z: kase.width_mm * 0.5 };
  if (id.startsWith("shroud")) return { x: kase.depth_mm - 20, y: kase.top_slot_y_mm, z: kase.width_mm * 0.5 };
  return null;
}

async function toggleCompare() {
  if (state.compare) {
    state.compare = null;
    $("compare").classList.add("hidden");
    return;
  }
  state.compare = {
    build: JSON.parse(JSON.stringify(state.build)),
    solution: state.solution,
  };
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
    <div><h2>A · saved</h2><p class="fine">${state.compare.build.name}</p>
      <table><tr><th>Card</th><th>A</th><th>B (live)</th><th>Δ</th></tr>${rows}</table></div>
    <div><h2>B · live</h2><p class="fine">${state.build.name}</p>
      <p>Case A ${a.case_pressure_pa.toFixed(1)} Pa · B ${b.case_pressure_pa.toFixed(1)} Pa</p>
      <p class="fine">Edit the live build. A stays put until you leave compare.</p></div>`;
}

async function startDemo() {
  const choice = state.build && state.build.illustrative_mock ? "mike-bradley-demo" : "stefano-demo";
  state.demo = { id: choice, index: 0 };
  $("demo-bar").classList.remove("hidden");
  await loadDemoStep();
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
  state.build = body.build;
  if (body.optimal) {
    state.solution = {
      cards: body.optimal.per_card,
      case_pressure_pa: body.optimal.case_pressure_pa,
      energy_error: 0,
      residual_kg_s: 0,
      branches: [],
      notes: [body.optimal.note],
    };
    state.build = body.optimal.build;
  } else {
    state.solution = body.solution;
  }
  $("demo-title").textContent = body.step.title;
  $("demo-points").textContent = (body.step.talking_points || []).join(" ");
  const scenario = state.presets.scenarios.find((s) => s.id === state.demo.id);
  $("demo-count").textContent = `${state.demo.index + 1} / ${scenario.steps.length}`;
  if (body.scenario.disclaimer || body.scenario.illustrative_mock) {
    state.build.illustrative_mock = true;
  }
  pushControls();
  render();
  syncDemoTimer();
}

function syncDemoTimer() {
  clearInterval(state.demoTimer);
  if (!$("demo-auto").checked || !state.demo) return;
  state.demoTimer = setInterval(() => stepDemo(1), 8000);
}

function onKey(ev) {
  if (!state.demo && ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
  if (ev.target.matches("input, select, textarea")) return;
  if (ev.key === "ArrowRight") stepDemo(1);
  if (ev.key === "ArrowLeft") stepDemo(-1);
}

async function runOptimal() {
  $("opt-status").textContent = "Searching…";
  const res = await fetch("/api/optimize", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ cards: Number($("opt-cards").value), case: state.build.case, mc: 30 }),
  });
  const body = await res.json();
  if (!res.ok) {
    $("opt-status").textContent = body.detail || "Search failed";
    return;
  }
  state.build = body.build;
  const mc = body.monte_carlo;
  $("opt-status").textContent = `${body.description.layout}, shroud ${body.description.shroud}, ${body.description.fan_curve}. Hottest ${fmt(body.hottest_unthrottled_c)}` +
    (mc ? ` (band ${fmt(mc.hottest_p05_c)} – ${fmt(mc.hottest_p95_c)})` : "");
  pushControls();
  await solveNow();
}

boot();
