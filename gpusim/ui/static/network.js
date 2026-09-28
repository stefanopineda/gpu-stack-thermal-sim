/* Resistor-network view. Layer 1: airflow (pressure = voltage, volumetric
 * flow = current). Layer 2: per-card thermal chain (temperature = voltage,
 * heat = current), driven by the mass flow layer 1 solved. */

const FAN_KINDS = new Set(["fan", "shroud-fan", "radiator", "blower", "gpu-fan", "cpu-cooler"]);
const NAMES = {
  fan: "fan impedance + fan",
  "shroud-fan": "shroud fans",
  radiator: "radiator core + fans",
  blower: "blower + fin channel",
  "gpu-fan": "axial fans + fin channel",
  "cpu-cooler": "CPU tower fin stack + fan",
  leak: "seal resistance",
  sealed: "seal resistance ∞",
  gap: "inter-card slot resistance",
  spill: "internal resistance (zone → case)",
  "cpu-exit": "internal resistance (cooler → case)",
  bracket: "bracket vent resistance",
  recirc: "exhaust short-circuit",
  plume: "plume → room",
  "rear-slot": "open rear slots",
  reingest: "rear-slot reingestion",
  "shroud-leak": "shroud shell leak",
  orifice: "open mount",
  blank: "blanked mount",
  "up-exit": "flow-through exhaust (up)",
};

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
const kfmt = (k) => (k == null ? "∞" : k >= 1e4 ? k.toExponential(1) : k.toFixed(0));

function leftSide(br) {
  const text = `${br.id} ${br.label}`.toLowerCase();
  if (br.kind === "radiator") return /front|bottom/.test(text);
  return /front|bottom|side/.test(text) && !/rear/.test(text);
}

function panelOf(br) {
  const m = /^(?:mount|leak)-([a-z]+)/.exec(br.id);
  return m ? m[1] : br.kind;
}

/* Collapse identical parallel branches (e.g. three front fans) into one symbol. */
function groupBranches(branches) {
  const groups = new Map();
  branches.forEach((br) => {
    if (br.kind === "plume-ingest") return;
    const key = `${br.kind}|${br.a}|${br.b}|${panelOf(br)}`;
    if (!groups.has(key)) groups.set(key, { ...br, count: 0, flow_total: 0, members: [] });
    const g = groups.get(key);
    g.count += 1;
    g.flow_total += br.flow_cfm;
    g.members.push(`${br.id} ${br.flow_cfm.toFixed(1)} CFM`);
  });
  return [...groups.values()];
}

export function renderNetwork(el, ctx) {
  const { solution, build, fmt, mode } = ctx;
  if (!solution || solution.error || !solution.branches) {
    el.innerHTML = `<p class="warn">${esc(solution?.error || "Solving…")}</p>`;
    return;
  }
  const full = mode === "full";
  el.innerHTML = `
    <div class="net-head">
      <h2>How the number is made</h2>
      <p>Two coupled solves. <b>Layer 1</b> is the airflow network: static pressure is voltage, volumetric flow is current,
      every branch obeys <code>ΔP = k·Q·|Q|</code> (orifice <code>k = ρ / (2 C<sub>d</sub>² A²)</code>), a fan adds a
      pressure source <code>P<sub>fan</sub>(Q)·(N/N<sub>ref</sub>)²</code>, and mass balances at every node (Kirchhoff's current law).
      <b>Layer 2</b> is each card's thermal network: the mass flow from layer 1 sets <code>R<sub>conv</sub> = 1 / (ε·ṁ·c<sub>p</sub>)</code>
      with <code>ε = 1 − e<sup>−NTU</sup></code>, <code>h</code> from <code>Nu = C·Re<sup>m</sup>·Pr<sup>1/3</sup></code>.
      Temperatures then set each GPU's fan duty and the air density, and layer 1 is solved again until both settle.</p>
    </div>
    <div class="net-layer"><h3>Layer 1 · airflow network <span class="fine">(pressure = voltage, flow = current; Pa, CFM)</span></h3>${airflowSvg(solution, build, full)}</div>
    <div class="net-layer"><h3>Layer 2 · thermal network per card <span class="fine">(temperature = voltage, heat = current; °C, W, K/W)</span></h3>${thermalSvg(solution, fmt, full, Object.fromEntries((ctx.presets?.cards || []).map((c) => [c.id, c.name])))}</div>
    <p class="fine net-foot">Mass residual ${solution.residual_kg_s.toExponential(1)} kg/s (plume overlay ${(
      solution.advection_residual_kg_s || 0
    ).toExponential(1)}). Energy in vs enthalpy out ${(solution.energy_error * 100).toFixed(3)} %. Hover any element for its assumption.</p>`;
}

function airflowSvg(sol, build, full) {
  const cards = sol.cards || [];
  const nodes = new Set();
  sol.branches.forEach((br) => {
    nodes.add(br.a);
    nodes.add(br.b);
  });
  const groups = groupBranches(sol.branches);
  const W = 1000;
  const laneH = 56;
  const railL = 30;
  const railR = W - 30;

  // Which node/side each room-connected branch uses, so lanes can be counted first.
  const railUse = {};
  groups.forEach((g) => {
    if (g.a !== "amb" && g.b !== "amb") return;
    const inner = g.a === "amb" ? g.b : g.a;
    g._inner = inner;
    g._side = leftSide(g) ? "L" : "R";
    (railUse[`${inner}|${g._side}`] ||= []).push(g);
  });
  const lanesDown = (node) => Math.max(railUse[`${node}|L`]?.length || 0, railUse[`${node}|R`]?.length || 0);
  const pos = {};
  pos.case = { x: 330, y: 58 };
  if (nodes.has("cpu")) pos.cpu = { x: 560, y: 58 };
  const topBand = 58 + Math.max(lanesDown("case"), lanesDown("cpu")) * laneH;
  const rowH = 104;
  const top = topBand + 70;
  cards.forEach((c, i) => {
    pos[`cin-${c.id}`] = { x: 450, y: top + i * rowH };
    pos[`cex-${c.id}`] = { x: 720, y: top + i * rowH };
  });
  const midY = top + ((cards.length - 1) * rowH) / 2;
  pos.gpu = { x: 220, y: midY + 10 };
  if (nodes.has("plenum")) pos.plenum = { x: 840, y: midY };
  if (nodes.has("plume")) pos.plume = { x: 840, y: midY };
  const bottomLane = top + (cards.length - 1) * rowH + 70;
  const gpuLanes = railUse["gpu|L"]?.length || 0;
  const H = Math.max(bottomLane + 70, pos.gpu.y + (gpuLanes / 2) * laneH + 60);

  const parts = [];
  parts.push(`<line x1="${railL}" y1="26" x2="${railL}" y2="${H - 8}" class="rail"/>`);
  parts.push(`<line x1="${railR}" y1="26" x2="${railR}" y2="${H - 8}" class="rail"/>`);
  parts.push(`<text x="${railL - 4}" y="16" class="rail-t">room air · 0 Pa · ${(sol.node_temp?.amb ?? 25).toFixed(1)} °C</text>`);
  parts.push(`<text x="${railR + 4}" y="16" class="rail-t" text-anchor="end">room air · 0 Pa</text>`);

  const laneIndex = {};
  let bottomUsed = 0;
  groups.forEach((g) => {
    if (g._inner) {
      const pn = pos[g._inner];
      if (!pn) return;
      const key = `${g._inner}|${g._side}`;
      const n = railUse[key].length;
      const k = (laneIndex[key] = (laneIndex[key] ?? -1) + 1);
      const downward = g._inner === "case" || g._inner === "cpu";
      const y = downward ? pn.y + k * laneH : pn.y + (k - (n - 1) / 2) * laneH;
      const railX = g._side === "L" ? railL : railR;
      const elbowX = pn.x + (g._side === "L" ? -46 : 46);
      const inward = g.a === "amb";
      const pts = [pn, { x: elbowX, y }, { x: railX, y }];
      parts.push(branchSvg(g, inward ? pts.slice().reverse() : pts, full, { seg: inward ? 0 : 1 }));
      return;
    }
    const p1 = pos[g.a];
    const p2 = pos[g.b];
    if (!p1 || !p2) return;
    if ((g.kind === "rear-slot" || g.kind === "reingest") && g.a === "gpu") {
      const y = bottomLane + bottomUsed * laneH;
      bottomUsed += 1;
      parts.push(branchSvg(g, [p1, { x: p1.x, y }, { x: p2.x, y }, p2], full, { seg: 1 }));
      return;
    }
    let bend = 0;
    if (/^cex-/.test(g.a) && (g.b === "gpu" || g.b === "case")) bend = g.b === "case" ? -1 : 1;
    // Several brackets converge on the plenum; keep their symbols near their own card.
    const t = g.kind === "bracket" ? 0.34 : g.kind === "gap" ? 0.58 : 0.5;
    parts.push(branchSvg(g, [p1, p2], full, { bend, t }));
  });

  (sol.plume || []).forEach((p) => {
    const a = pos[p.from_node];
    const b = pos[p.to_node];
    if (!a || !b) return;
    const cx = (a.x + b.x) / 2;
    const cy = (a.y + b.y) / 2;
    const tip = `Plume ingestion (special coupling term, not a resistor): ${p.upper} draws φ = ${(p.phi * 100).toFixed(0)} % of its fan-side intake ` +
      `from ${p.lower}'s exhaust jet, φ(gap) = φmax·exp(−gap/L), gap ${p.gap_mm.toFixed(1)} mm. Mass ${p.flow_cfm.toFixed(1)} CFM at ` +
      `${p.t_from_c?.toFixed(1)} °C, capped by the jet. The same mass is taken off the zone streams, so every node still balances.`;
    parts.push(
      `<g class="plume" data-tip="${esc(tip)}"><path d="M${a.x},${a.y} Q${cx},${cy + 10} ${b.x + 12},${b.y + 8}" class="plume-path" marker-end="url(#arrow-plume)"/>` +
        `<text x="${cx}" y="${cy + 4}" text-anchor="middle" class="plume-t">plume ${(p.share_of_upper_intake * 100).toFixed(0)}%</text></g>`,
    );
  });

  Object.entries(pos).forEach(([name, p]) => {
    const P = sol.pressures?.[name];
    const T = sol.node_temp?.[name];
    const card = /^c(in|ex)-/.test(name) || name === "plenum" || name === "plume";
    const label = name === "gpu" ? "GPU zone" : name === "case" ? "main case" : name === "cpu" ? "CPU cooler out" : name.replace("cin-", "inlet ").replace("cex-", "exhaust ");
    const tip = `Node ${label}: gauge pressure ${P?.toFixed(2)} Pa, air ${T?.toFixed(1)} °C. Mass in = mass out (residual ${(sol.node_residual?.[name] ?? 0).toExponential(1)} kg/s).`;
    const ty = card ? p.y + 24 : p.y - 14;
    const vy = card ? p.y + 40 : p.y + 24;
    parts.push(
      `<g class="node" data-tip="${esc(tip)}"><circle cx="${p.x}" cy="${p.y}" r="8"/>` +
        `<text x="${p.x}" y="${ty}" text-anchor="middle" class="node-t">${esc(label)}</text>` +
        `<text x="${p.x}" y="${vy}" text-anchor="middle" class="node-v">${P?.toFixed(1)} Pa · ${T?.toFixed(1)} °C</text></g>`,
    );
  });
  const defs = `<defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrowhead"/></marker>
    <marker id="arrow-plume" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#ff8a3d"/></marker>
  </defs>`;
  return `<svg viewBox="0 0 ${W} ${H}" class="net-svg" preserveAspectRatio="xMidYMin meet">${defs}${parts.join("")}</svg>`;
}

/* One branch along a polyline (or a bowed curve). The symbol sits on segment
 * opts.seg (default: the longest), with the solved flow direction arrowed. */
function branchSvg(g, pts, full, opts = {}) {
  const cfm = g.count > 1 ? g.flow_total : g.flow_cfm;
  const width = Math.min(1 + Math.abs(cfm) / 25, 5);
  const sealed = g.kind === "sealed";
  const isFan = FAN_KINDS.has(g.kind) && g.fan !== false;
  const name = NAMES[g.kind] || g.kind;
  const count = g.count > 1 ? ` ×${g.count}` : "";
  const flowText = sealed ? "R = ∞ · 0 CFM" : `${Math.abs(cfm).toFixed(1)} CFM`;
  const dp = g.dp_pa == null || sealed ? "" : ` · ${Math.abs(g.dp_pa).toFixed(1)} Pa`;
  const formula = sealed
    ? "Solid glass or metal (seal level 5): open area 0, so the branch is removed; resistance is infinite and no air passes."
    : isFan
      ? `P_a − P_b = k·Q·|Q| − P_fan(Q), with k = ${kfmt(g.k)} Pa/(m³/s)² for the mount/core and the fan curve scaled by (N/N_ref)².`
      : `ΔP = k·Q·|Q|, k = ${kfmt(g.k)} Pa/(m³/s)².`;
  const tip = `${g.role || name}${count ? ` (${g.count} in parallel)` : ""}. ${g.label}. ${formula} Flow ${flowText}${dp}.` +
    (g.count > 1 ? ` Members: ${g.members.join(", ")}.` : "");
  // Branch a→b; pts may run either way. Flow direction decides the arrow.
  const first = pts[0];
  const last = pts[pts.length - 1];
  let d;
  let mid;
  let ang;
  let arrowSeg = null;
  if (opts.bend) {
    const dx = last.x - first.x;
    const dy = last.y - first.y;
    const len = Math.hypot(dx, dy) || 1;
    const c = { x: (first.x + last.x) / 2 - (dy / len) * opts.bend * 70, y: (first.y + last.y) / 2 + (dx / len) * opts.bend * 70 };
    d = `M${first.x},${first.y} Q${c.x},${c.y} ${last.x},${last.y}`;
    mid = { x: 0.25 * first.x + 0.5 * c.x + 0.25 * last.x, y: 0.25 * first.y + 0.5 * c.y + 0.25 * last.y };
    ang = (Math.atan2(dy, dx) * 180) / Math.PI;
  } else {
    d = "M" + pts.map((p) => `${p.x},${p.y}`).join(" L");
    let seg = opts.seg;
    if (seg == null) {
      let best = -1;
      for (let i = 0; i < pts.length - 1; i += 1) {
        const l = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y);
        if (l > best) {
          best = l;
          seg = i;
        }
      }
    }
    const a = pts[seg];
    const b = pts[seg + 1];
    const t = opts.t ?? 0.5;
    mid = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
    ang = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
    arrowSeg = [a, b];
  }
  // Callers always pass points from node a to node b.
  const forward = (g.flow_m3s ?? 0) >= 0;
  let arrow = "";
  if (arrowSeg && !sealed && Math.abs(cfm) >= 0.05) {
    const [a, b] = forward ? arrowSeg : [arrowSeg[1], arrowSeg[0]];
    const t0 = { x: a.x + (b.x - a.x) * 0.8, y: a.y + (b.y - a.y) * 0.8 };
    const t1 = { x: a.x + (b.x - a.x) * 0.86, y: a.y + (b.y - a.y) * 0.86 };
    arrow = `<line x1="${t0.x}" y1="${t0.y}" x2="${t1.x}" y2="${t1.y}" class="flowdir" marker-end="url(#arrow)"/>`;
  }
  const flip = ang > 90 || ang < -90;
  const lineCls = sealed ? "wire sealed" : "wire";
  const symbol = sealed ? openSymbol() : isFan ? fanSymbol() : resistorSymbol();
  const short = `${shortName(g)}${count}`;
  const value = full ? `${flowText}${dp}` : flowText;
  return `<g class="branch k-${g.kind}" data-tip="${esc(tip)}">
    <path d="${d}" class="${lineCls}" style="stroke-width:${width}"/>${arrow}
    <g transform="translate(${mid.x},${mid.y}) rotate(${flip ? ang + 180 : ang})">${symbol}
      <text y="-14" text-anchor="middle" class="br-t">${esc(short)}</text>
      <text y="${isFan ? 27 : 23}" text-anchor="middle" class="br-v">${esc(value)}</text>
    </g></g>`;
}

function shortName(g) {
  if (g.kind === "leak" || g.kind === "sealed") {
    const face = /^leak-([a-z_]+)/.exec(g.id)?.[1] || "";
    return `${face.replace("_", " ")} seal${g.kind === "sealed" ? " ∞" : ""}`;
  }
  const map = { gap: "slot gap", spill: "internal", bracket: "bracket", "up-exit": "up-exit" };
  if (g.kind === "fan" || g.kind === "blank" || g.kind === "orifice") return `${panelOf(g)} ${g.kind === "fan" ? "fan" : g.kind}`;
  return map[g.kind] || NAMES[g.kind] || g.kind;
}

function resistorSymbol() {
  return `<rect x="-20" y="-7" width="40" height="14" class="sym-bg"/><polyline points="-20,0 -15,-6 -9,6 -3,-6 3,6 9,-6 15,6 20,0" class="sym"/>`;
}

function fanSymbol() {
  return `<rect x="-24" y="-12" width="48" height="24" class="sym-bg"/><circle cx="-8" r="10" class="sym fan"/><path d="M-14,0 L-2,0 M-6,-4 L-2,0 L-6,4" class="sym"/>` +
    `<polyline points="4,0 7,-5 11,5 15,-5 19,5 22,0" class="sym"/>`;
}

function openSymbol() {
  return `<rect x="-16" y="-9" width="32" height="18" class="sym-bg"/><text y="6" text-anchor="middle" class="inf">∞</text>`;
}

function thermalSvg(sol, fmt, full, names = {}) {
  const cards = sol.cards || [];
  const W = 1100;
  const rowH = 212;
  const H = 20 + cards.length * rowH;
  const parts = [];
  const cols = { zone: 70, inlet: 300, hs: 640, die: 930 };
  cards.forEach((c, i) => {
    const d = c.thermal || {};
    const y = 64 + i * rowH;
    const yb = y + 62;
    const tIn = d.t_inlet_used_c ?? c.t_in_c;
    const rConv = d.r_conv_k_per_w;
    const eq =
      rConv == null
        ? "fan stalled: no convection through the fins"
        : `T_die = T_in + Q_ch·R_conv + P_die·R_tim = ${tIn.toFixed(1)} + ${d.q_channel_w.toFixed(0)}×${rConv.toFixed(3)} + ${d.p_die_w.toFixed(0)}×${d.r_tim_k_per_w.toFixed(3)} = ${d.t_die_c.toFixed(1)} °C`;
    const plume = d.plume_from
      ? `+ ${(d.plume_share_of_intake * 100).toFixed(0)} % of ${d.plume_from}'s exhaust at ${d.plume_source_temp_c?.toFixed(1)} °C`
      : "";
    const mixTip = `Inlet air: GPU-zone air at ${d.t_zone_c?.toFixed(1)} °C${plume ? `, ${plume}` : ", no plume from below"}, plus ${d.inlet_heat_captured_w?.toFixed(1)} W of shroud/backplate heat captured in the gap. ` +
      "The plume share is the rev 4 coupling term φ(gap) = φmax·exp(−gap/L).";
    const convTip = `Convective resistance heatsink → air, R_conv = 1/(ε·ṁ·c_p) = 1/(${d.epsilon?.toFixed(2)} × ${((d.mass_kg_s || 0) * 1000).toFixed(1)} g/s × 1007 J/(kg·K)) = ${rConv?.toFixed(3)} K/W. ` +
      `ṁ comes from layer 1 (${c.flow_cfm.toFixed(1)} CFM at ${Math.round(c.duty * 100)} % fan duty). ε-NTU with Nu = C·Re^m·Pr^1/3.`;
    const extTip = `Parallel path heatsink → GPU zone through the shroud and backplate, R_ext = ${d.r_ext_k_per_w?.toFixed(2)} K/W, carrying ${d.q_ext_w?.toFixed(1)} W. ` +
      "A share of it is captured by the inlet of the card that breathes that gap.";
    const timTip = `Die → heatsink, TIM + spreading, R_tim = ${d.r_tim_k_per_w} K/W, carrying the die power ${d.p_die_w?.toFixed(0)} W.`;
    const memTip = `Memory → heatsink, R_mem = ${d.r_mem_k_per_w} K/W, carrying ${d.p_mem_w?.toFixed(0)} W.`;
    const node = (x, yy, label, t, tip) =>
      `<g class="tnode" data-tip="${esc(tip)}"><circle cx="${x}" cy="${yy}" r="8"/><text x="${x}" y="${yy - 14}" text-anchor="middle" class="node-t">${label}</text>` +
      `<text x="${x}" y="${yy + 24}" text-anchor="middle" class="node-v">${t}</text></g>`;
    const res = (x1, x2, yy, label, value, tip, below = false) =>
      `<g class="branch" data-tip="${esc(tip)}"><line x1="${x1}" y1="${yy}" x2="${x2}" y2="${yy}" class="wire"/>` +
      `<g transform="translate(${(x1 + x2) / 2},${yy})">${resistorSymbol()}<text y="${below ? 24 : -13}" text-anchor="middle" class="br-t">${label}</text>` +
      `<text y="${below ? 40 : 24}" text-anchor="middle" class="br-v">${value}</text></g></g>`;
    const name = names[c.card] || c.card;
    parts.push(`<text x="8" y="${y - 38}" class="row-t">${c.id} · ${esc(name)} · ${c.cooler === "flow_through" ? "flow-through" : "blower"} · slot ${c.slot}${c.throttle ? " · THROTTLE (die shown at the throttled equilibrium)" : ""}</text>`);
    parts.push(
      `<g class="branch mix" data-tip="${esc(mixTip)}"><line x1="${cols.zone}" y1="${y}" x2="${cols.inlet}" y2="${y}" class="wire mixwire"/>` +
        `<text x="${(cols.zone + cols.inlet) / 2}" y="${y - 10}" text-anchor="middle" class="br-t">inlet mixing</text>` +
        `<text x="${(cols.zone + cols.inlet) / 2}" y="${y + 20}" text-anchor="middle" class="br-v">${esc(plume || "zone air only")}</text></g>`,
    );
    parts.push(res(cols.inlet, cols.hs, y, "GPU convective resistance R_conv", rConv == null ? "∞" : `${rConv.toFixed(3)} K/W · ${d.q_channel_w?.toFixed(0)} W`, convTip));
    parts.push(res(cols.hs, cols.die, y, "R_tim (die → heatsink)", `${d.r_tim_k_per_w} K/W · ${d.p_die_w?.toFixed(0)} W`, timTip));
    parts.push(
      `<g class="branch" data-tip="${esc(extTip)}"><polyline points="${cols.hs - 16},${y} ${cols.hs - 16},${yb} ${cols.zone},${yb} ${cols.zone},${y}" class="wire thin" fill="none"/>` +
        `<g transform="translate(${(cols.hs + cols.zone) / 2},${yb})">${resistorSymbol()}<text y="24" text-anchor="middle" class="br-t">R_ext shroud / backplate → zone</text>` +
        `<text y="40" text-anchor="middle" class="br-v">${d.r_ext_k_per_w?.toFixed(2)} K/W · ${d.q_ext_w?.toFixed(1)} W</text></g></g>`,
    );
    parts.push(
      `<g class="branch" data-tip="${esc(memTip)}"><polyline points="${cols.hs + 16},${y} ${cols.hs + 16},${yb} ${cols.die},${yb}" class="wire thin" fill="none"/>` +
        `<g transform="translate(${(cols.hs + cols.die) / 2 + 8},${yb})">${resistorSymbol()}<text y="24" text-anchor="middle" class="br-t">R_mem</text>` +
        `<text y="40" text-anchor="middle" class="br-v">${d.r_mem_k_per_w} K/W · ${d.p_mem_w?.toFixed(0)} W</text></g></g>`,
    );
    parts.push(node(cols.zone, y, "GPU zone air", fmt(d.t_zone_c), `GPU-zone air temperature from the layer-1 advection balance: ${d.t_zone_c?.toFixed(2)} °C.`));
    parts.push(node(cols.inlet, y, "card inlet", fmt(tIn), mixTip));
    parts.push(node(cols.hs, y, "heatsink", fmt(d.t_heatsink_c), `Heatsink metal. Heat in = board power ${c.power_w.toFixed(0)} W; out = fins (Q_ch) + shroud/backplate (Q_ext).`));
    parts.push(node(cols.die, y, "die", fmt(d.t_die_c), `Die temperature. ${eq}.`));
    parts.push(
      `<g class="tnode" data-tip="${esc(memTip)}"><circle cx="${cols.die}" cy="${yb}" r="6"/>` +
        `<text x="${cols.die + 14}" y="${yb + 5}" class="node-v">memory ${fmt(c.t_mem_c)}</text></g>`,
    );
    parts.push(`<text x="${cols.zone - 20}" y="${yb + 72}" class="eq">${esc(eq)}</text>`);
  });
  return `<svg viewBox="0 0 ${W} ${H}" class="net-svg" preserveAspectRatio="xMidYMin meet">${parts.join("")}</svg>`;
}
