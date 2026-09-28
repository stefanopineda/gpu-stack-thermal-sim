/* 3D case view. Case frame in mm: x = depth (0 front → D rear), y = height
 * (0 floor → H top), z = width (0 motherboard tray → W glass side). The scene
 * works in metres. Fans are flat discs lying in the plane of their panel, so a
 * 3/4 camera shows them as ovals on the face they belong to. */
import * as THREE from "./vendor/three.module.js";

const COLORS = {
  intake: 0x3c8dff,
  exhaust: 0xe24b3b,
  blank: 0x8d877e,
  shell: 0x2a241c,
  edge: 0xf0e2cf,
  psu: 0x2d2a26,
  shroudOn: 0xb8433a,
  shroudPassive: 0x8d877e,
  mobo: 0x1f3b35,
};

const VIEWS = {
  front34: new THREE.Vector3(-0.62, 0.42, 1.0),
  side: new THREE.Vector3(0, 0.08, 1.0),
  rear34: new THREE.Vector3(0.7, 0.4, 1.0),
};

const RADIATOR_PANELS = ["front", "top", "bottom"];
const m = (mm) => mm / 1000;

export class CaseScene {
  constructor(canvas, labelsEl, callbacks = {}) {
    this.canvas = canvas;
    this.labelsEl = labelsEl;
    this.cb = callbacks;
    this.view = "front34";
    this.ctx = null;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#0c0b09");
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.02, 30);
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const key = new THREE.DirectionalLight(0xfff2e0, 0.95);
    key.position.set(-2, 3, 4);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0xbcd4ff, 0.35);
    rim.position.set(3, 1, -2);
    this.scene.add(rim);
    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.drag = null;
    this.labels = [];
    canvas.addEventListener("pointerdown", (ev) => this._down(ev));
    canvas.addEventListener("pointerup", (ev) => this._up(ev));
    const loop = () => {
      this._resize();
      this.renderer.render(this.scene, this.camera);
      this._placeLabels();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  setView(name) {
    if (VIEWS[name]) this.view = name;
    this._frame();
  }

  update(ctx) {
    this.ctx = ctx;
    while (this.root.children.length) {
      const child = this.root.children.pop();
      child.traverse?.((o) => {
        o.geometry?.dispose?.();
        if (o.material?.map) o.material.map.dispose();
        o.material?.dispose?.();
      });
    }
    this.labels = [];
    if (!ctx || !ctx.build || !ctx.kase) return;
    this._shell();
    this._internals();
    this._mounts();
    this._radiator();
    this._gpus();
    this._shroud();
    this._frame();
  }

  /* ------------------------------------------------------------ geometry */

  _dims() {
    const k = this.ctx.kase;
    return { W: m(k.width_mm), H: m(k.height_mm), D: m(k.depth_mm) };
  }

  _shell() {
    const { W, H, D } = this._dims();
    const geo = new THREE.BoxGeometry(D, H, W);
    const shell = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: COLORS.shell, transparent: true, opacity: 0.12, roughness: 0.9, depthWrite: false }),
    );
    shell.position.set(D / 2, H / 2, W / 2);
    this.root.add(shell);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: COLORS.edge }));
    edges.position.copy(shell.position);
    this.root.add(edges);
    // Mesh-textured front and top, so the faces read as faces.
    const mesh = this._meshTexture();
    const front = new THREE.Mesh(
      new THREE.PlaneGeometry(W, H),
      new THREE.MeshBasicMaterial({ map: mesh, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false }),
    );
    front.rotation.y = -Math.PI / 2;
    front.position.set(-0.001, H / 2, W / 2);
    this.root.add(front);
    const top = new THREE.Mesh(
      new THREE.PlaneGeometry(D, W),
      new THREE.MeshBasicMaterial({ map: this._meshTexture(), transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false }),
    );
    top.rotation.x = -Math.PI / 2;
    top.position.set(D / 2, H + 0.001, W / 2);
    this.root.add(top);
  }

  _meshTexture() {
    const c = document.createElement("canvas");
    c.width = 64;
    c.height = 64;
    const g = c.getContext("2d");
    g.fillStyle = "rgba(0,0,0,0)";
    g.fillRect(0, 0, 64, 64);
    g.fillStyle = "rgba(240,226,207,0.55)";
    for (let y = 2; y < 64; y += 6) for (let x = (y / 6) % 2 ? 5 : 2; x < 64; x += 6) g.fillRect(x, y, 2, 2);
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(6, 8);
    return tex;
  }

  _internals() {
    const { build, kase } = this.ctx;
    const { W, H, D } = this._dims();
    // Motherboard on the tray (E-ATX-sized plate, clipped to the case).
    const moboW = Math.min(0.305, D - 0.08);
    const moboH = Math.min(0.33, H - 0.12);
    const mobo = new THREE.Mesh(
      new THREE.BoxGeometry(moboW, moboH, 0.004),
      new THREE.MeshStandardMaterial({ color: COLORS.mobo, transparent: true, opacity: 0.6, roughness: 0.8 }),
    );
    mobo.position.set(D - 0.012 - moboW / 2, H - 0.03 - moboH / 2, 0.012);
    this.root.add(mobo);

    // CPU cooler.
    const cpu = build.cpu || { cooling: "water", power_w: 150 };
    const cx = D - 0.012 - moboW * 0.45;
    const cy = H - 0.03 - moboH * 0.28;
    if (cpu.cooling === "air") {
      const tower = new THREE.Mesh(
        new THREE.BoxGeometry(0.11, 0.15, 0.15),
        new THREE.MeshStandardMaterial({ color: 0xb9c2c8, roughness: 0.35, metalness: 0.6 }),
      );
      tower.position.set(cx, cy, 0.014 + 0.075);
      this.root.add(tower);
      this._fanDisc(new THREE.Vector3(cx - 0.055 - 0.013, cy, 0.089), new THREE.Vector3(-1, 0, 0), 0.07, "exhaust", {
        kind: "cpu",
      });
      this._label(new THREE.Vector3(cx, cy + 0.1, 0.09), `CPU tower · ${Math.round(cpu.power_w)} W`, "tag");
    } else {
      const pump = new THREE.Mesh(
        new THREE.BoxGeometry(0.07, 0.07, 0.03),
        new THREE.MeshStandardMaterial({ color: 0x3a3632, roughness: 0.5 }),
      );
      pump.position.set(cx, cy, 0.03);
      this.root.add(pump);
      this._label(new THREE.Vector3(cx, cy + 0.06, 0.04), `CPU · AIO pump · ${Math.round(cpu.power_w)} W to radiator`, "tag");
    }

    // PSU and its shroud, bottom rear.
    const n = kase.horizontal_slots;
    const lowest = m(kase.top_slot_y_mm - n * kase.slot_pitch_mm);
    const shrouded = kase.psu_shroud && build.psu_location !== "open";
    const shroudTop = Math.max(0.1, Math.min(lowest - m(kase.psu_shroud_clearance_mm || 40), H * 0.36));
    if (shrouded) {
      const box = new THREE.Mesh(
        new THREE.BoxGeometry(D - 0.004, shroudTop, W - 0.004),
        new THREE.MeshStandardMaterial({ color: 0x3a332b, transparent: true, opacity: 0.28, depthWrite: false }),
      );
      box.position.set(D / 2, shroudTop / 2, W / 2);
      this.root.add(box);
      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(D - 0.004, shroudTop, W - 0.004)),
        new THREE.LineBasicMaterial({ color: 0x6d6254 }),
      );
      edge.position.copy(box.position);
      this.root.add(edge);
    }
    const psu = new THREE.Mesh(
      new THREE.BoxGeometry(0.17, 0.086, 0.15),
      new THREE.MeshStandardMaterial({ color: COLORS.psu, roughness: 0.6, metalness: 0.3 }),
    );
    psu.position.set(D - 0.012 - 0.085, 0.012 + 0.043, W / 2);
    this.root.add(psu);
    const psuFanUp = build.psu_fan === "up";
    this._fanDisc(
      new THREE.Vector3(D - 0.012 - 0.085, psuFanUp ? 0.012 + 0.087 : 0.011, W / 2),
      new THREE.Vector3(0, psuFanUp ? 1 : -1, 0),
      0.06,
      "blank",
      { kind: "psu" },
      0.006,
    );
    this._label(new THREE.Vector3(D - 0.1, 0.13, W / 2), `PSU${shrouded ? " (shrouded)" : ""} · fan ${psuFanUp ? "up" : "down"}`, "tag");
  }

  _face(panel, layout) {
    const { W, H, D } = this._dims();
    const x = m(layout.x_mm);
    const y = m(layout.y_mm);
    const z = m(layout.z_mm);
    switch (panel) {
      case "front":
        return { pos: new THREE.Vector3(0, y, z), normal: new THREE.Vector3(-1, 0, 0) };
      case "rear":
        return { pos: new THREE.Vector3(D, y, z), normal: new THREE.Vector3(1, 0, 0) };
      case "top":
        return { pos: new THREE.Vector3(x, H, z), normal: new THREE.Vector3(0, 1, 0) };
      case "bottom":
        return { pos: new THREE.Vector3(x, 0, z), normal: new THREE.Vector3(0, -1, 0) };
      case "side":
        return { pos: new THREE.Vector3(x, y, W), normal: new THREE.Vector3(0, 0, 1) };
      default:
        return { pos: new THREE.Vector3(x, y, z), normal: new THREE.Vector3(1, 0, 0) };
    }
  }

  _fanDisc(center, normal, radius, dir, userData, thickness = 0.014) {
    if (dir === "gpu") return this._gpuFan(center, normal, radius, userData);
    const color = dir === "intake" ? COLORS.intake : dir === "exhaust" ? COLORS.exhaust : COLORS.blank;
    const blank = dir !== "intake" && dir !== "exhaust";
    const group = new THREE.Group();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal.clone().normalize());
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(radius, radius, thickness, 40),
      new THREE.MeshStandardMaterial({
        color,
        transparent: blank,
        opacity: blank ? 0.35 : 0.92,
        roughness: 0.5,
        depthWrite: !blank,
      }),
    );
    body.quaternion.copy(q);
    body.userData = userData;
    group.add(body);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, Math.max(radius * 0.05, 0.003), 8, 48),
      new THREE.MeshBasicMaterial({ color: blank ? 0xc9c1b6 : 0xf3efe6 }),
    );
    ring.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal.clone().normalize()));
    ring.position.copy(normal.clone().multiplyScalar(thickness / 2 + 0.001));
    ring.userData = userData;
    group.add(ring);
    if (!blank) {
      const hub = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 0.32, radius * 0.32, thickness * 1.15, 24),
        new THREE.MeshStandardMaterial({ color: 0x1a1714, roughness: 0.7 }),
      );
      hub.quaternion.copy(q);
      hub.userData = userData;
      group.add(hub);
      // Arrow: into the case for intake, out for exhaust.
      const sign = dir === "intake" ? -1 : 1;
      const cone = new THREE.Mesh(
        new THREE.ConeGeometry(radius * 0.28, radius * 0.55, 20),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 }),
      );
      cone.quaternion.copy(
        new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal.clone().multiplyScalar(sign).normalize()),
      );
      cone.position.copy(normal.clone().multiplyScalar(sign * (thickness / 2 + radius * 0.3)));
      cone.userData = userData;
      group.add(cone);
    }
    group.position.copy(center);
    this.root.add(group);
    return group;
  }

  /* A GPU's own fan: dark disc with a light rim, so it never reads as a case fan. */
  _gpuFan(center, normal, radius, userData) {
    const group = new THREE.Group();
    const disc = new THREE.Mesh(
      new THREE.CircleGeometry(radius, 32),
      new THREE.MeshBasicMaterial({ color: 0x1b1916, side: THREE.DoubleSide }),
    );
    disc.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal.clone().normalize()));
    disc.userData = userData;
    group.add(disc);
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.0025, 6, 40),
      new THREE.MeshBasicMaterial({ color: 0xd9cfc2 }),
    );
    ring.quaternion.copy(disc.quaternion);
    group.add(ring);
    group.position.copy(center);
    this.root.add(group);
    return group;
  }

  _mounts() {
    const { build, kase, presets } = this.ctx;
    const byId = Object.fromEntries(kase.mounts.map((l) => [l.id, l]));
    const groups = {};
    (build.mounts || []).forEach((mount) => {
      const layout = byId[mount.id];
      if (!layout || mount.state === "radiator") return;
      const { pos, normal } = this._face(layout.panel, layout);
      const r = m(layout.size_mm) / 2;
      // Sit flush on the panel, the disc's thickness inside the case.
      const center = pos.clone().add(normal.clone().multiplyScalar(-0.007 + 0.002));
      const dir = mount.state === "fan" ? mount.direction : "blank";
      const selected = this.ctx.selectedMount === mount.id;
      const g = this._fanDisc(center, normal, r * 0.96, dir, { kind: "fan", id: mount.id, panel: layout.panel });
      if (selected) g.scale.setScalar(1.08);
      const key = layout.panel;
      (groups[key] ||= []).push({ mount, layout, pos, normal });
    });
    Object.entries(groups).forEach(([panel, items]) => {
      const fans = items.filter((i) => i.mount.state === "fan");
      const text = faceFanLabel(panel, items.map((i) => i.mount), presets);
      if (!text) return;
      const anchor = new THREE.Vector3();
      (fans.length ? fans : items).forEach((i) => anchor.add(i.pos));
      anchor.multiplyScalar(1 / (fans.length || items.length));
      anchor.add(items[0].normal.clone().multiplyScalar(0.06));
      this._label(anchor, text, `tag face-tag face-${panel}`);
    });
  }

  _radiator() {
    const { build, kase, presets } = this.ctx;
    const rad = build.radiator;
    if (!rad || !rad.model) return;
    const model = presets.radiators.find((r) => r.id === rad.model);
    if (!model) return;
    const panel = RADIATOR_PANELS.includes(rad.panel) ? rad.panel : "top";
    const { W, H, D } = this._dims();
    const t = m(model.thickness_mm);
    const len = m(model.length_mm);
    const wid = m(model.width_mm);
    const onPanel = kase.mounts.filter((l) => l.panel === panel);
    const radMounts = (build.mounts || []).filter((mt) => mt.state === "radiator" && onPanel.some((l) => l.id === mt.id));
    const layouts = (radMounts.length ? radMounts.map((mt) => onPanel.find((l) => l.id === mt.id)) : onPanel).filter(Boolean);
    const mean = (key) => layouts.reduce((s, l) => s + m(l[key]), 0) / Math.max(layouts.length, 1);
    let size;
    let pos;
    let inward;
    if (panel === "top") {
      size = [Math.min(len, D - 0.04), t, wid];
      pos = new THREE.Vector3(layouts.length ? mean("x_mm") : D / 2, H - t / 2 - 0.004, layouts.length ? mean("z_mm") : W / 2);
      inward = new THREE.Vector3(0, -1, 0);
    } else if (panel === "front") {
      size = [t, Math.min(len, H - 0.04), wid];
      pos = new THREE.Vector3(t / 2 + 0.004, layouts.length ? mean("y_mm") : H / 2, layouts.length ? mean("z_mm") : W / 2);
      inward = new THREE.Vector3(1, 0, 0);
    } else {
      size = [Math.min(len, D - 0.04), t, wid];
      pos = new THREE.Vector3(layouts.length ? mean("x_mm") : D / 2, t / 2 + 0.004, layouts.length ? mean("z_mm") : W / 2);
      inward = new THREE.Vector3(0, 1, 0);
    }
    const geo = new THREE.BoxGeometry(...size);
    const slab = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: this._finTexture(panel), roughness: 0.6, metalness: 0.3 }));
    slab.position.copy(pos);
    slab.userData = { kind: "radiator" };
    this.root.add(slab);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: 0xe0a15a }));
    edge.position.copy(pos);
    this.root.add(edge);
    // Fans sit directly on the radiator's inner face.
    const count = rad.fan_count || model.fan_count || 3;
    const fan = presets.fans.find((f) => f.id === (rad.fan || model.default_fan));
    const r = m(fan ? fan.size_mm : model.fan_size_mm) / 2;
    const along = panel === "front" ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const span = panel === "front" ? size[1] : size[0];
    const faceOffset = (panel === "front" ? size[0] : size[1]) / 2 + 0.008;
    for (let i = 0; i < count; i += 1) {
      const u = (i + 0.5) / count - 0.5;
      const c = pos.clone().add(along.clone().multiplyScalar(u * span)).add(inward.clone().multiplyScalar(faceOffset));
      this._fanDisc(c, inward.clone().multiplyScalar(-1), r * 0.95, rad.direction === "intake" ? "intake" : "exhaust", {
        kind: "radiator",
      });
    }
    const labelAt = pos.clone().add(inward.clone().multiplyScalar(faceOffset + 0.05));
    this._label(
      labelAt,
      `Radiator ${model.name} · ${count}× ${fan ? fan.name : "fan"} · ${rad.direction}`,
      "tag rad-tag",
    );
  }

  _finTexture(panel) {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 32;
    const g = c.getContext("2d");
    g.fillStyle = "#cfd6db";
    g.fillRect(0, 0, 256, 32);
    g.strokeStyle = "#7c8a93";
    g.lineWidth = 1;
    for (let x = 2; x < 256; x += 4) {
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, 32);
      g.stroke();
    }
    g.strokeStyle = "#e0a15a";
    g.lineWidth = 3;
    g.strokeRect(1.5, 1.5, 253, 29);
    const tex = new THREE.CanvasTexture(c);
    if (panel === "front") tex.rotation = Math.PI / 2;
    return tex;
  }

  cardBox(gpu, card) {
    const kase = this.ctx.kase;
    const { W, D } = this._dims();
    const L = m(card?.length_mm || 267);
    const T = m(card?.thickness_mm || 37);
    const Hc = m(card?.height_mm || 111);
    const slot = String(gpu.slot);
    if (slot.toLowerCase().startsWith("v")) {
      const v = kase.vertical_positions.find((p) => p.id === slot);
      if (!v) return null;
      const z = Math.min(m(v.z_mm), W - T / 2 - 0.01);
      return {
        vertical: true,
        center: new THREE.Vector3(D - 0.012 - L / 2, m(v.y_mm), z),
        size: [L, Hc, T],
        fanNormal: new THREE.Vector3(0, 0, 1),
        exhaustNormal: new THREE.Vector3(0, 0, -1),
      };
    }
    const s = Number(slot);
    const ySlot = m(kase.top_slot_y_mm - (s - 1) * kase.slot_pitch_mm);
    return {
      vertical: false,
      center: new THREE.Vector3(D - 0.012 - L / 2, ySlot - T / 2, 0.02 + Hc / 2),
      size: [L, T, Hc],
      fanNormal: new THREE.Vector3(0, -1, 0),
      exhaustNormal: new THREE.Vector3(0, 1, 0),
    };
  }

  _gpus() {
    const { build, solution, presets, fmt, tempColor } = this.ctx;
    const cards = Object.fromEntries((solution?.cards || []).map((c) => [c.id, c]));
    const plumeByLower = Object.fromEntries((solution?.plume || []).map((p) => [p.lower, p]));
    (build.gpus || []).forEach((gpu) => {
      const card = presets.cards.find((c) => c.id === gpu.card);
      const box = this.cardBox(gpu, card);
      if (!box) return;
      const res = cards[gpu.id];
      const geo = new THREE.BoxGeometry(...box.size);
      const mesh = new THREE.Mesh(
        geo,
        new THREE.MeshStandardMaterial({
          color: new THREE.Color(tempColor(res ? res.t_die_c : 60)),
          roughness: 0.45,
          metalness: 0.2,
          transparent: box.vertical,
          opacity: box.vertical ? 0.78 : 1,
        }),
      );
      mesh.position.copy(box.center);
      mesh.userData = { kind: "gpu", id: gpu.id };
      this.root.add(mesh);
      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: 0x14120e }));
      edge.position.copy(box.center);
      this.root.add(edge);
      // Fan face: one blower eye, or two axial fans.
      const through = card?.cooler === "flow_through";
      const L = box.size[0];
      const halfT = (box.vertical ? box.size[2] : box.size[1]) / 2;
      const fanCenters = through ? [-L / 2 + 0.07, L / 2 - 0.07] : [-L / 2 + 0.05];
      fanCenters.forEach((dx) => {
        const c = box.center.clone().add(new THREE.Vector3(dx, 0, 0)).add(box.fanNormal.clone().multiplyScalar(halfT + 0.002));
        this._fanDisc(c, box.fanNormal, through ? 0.045 : 0.03, "gpu", { kind: "gpu", id: gpu.id });
      });
      // Flow-through exhaust plume above the card; stronger when the card above breathes it.
      if (through) {
        const plume = plumeByLower[gpu.id];
        const share = plume ? plume.share_of_upper_intake : 0.15;
        const h = 0.05;
        const cone = new THREE.Mesh(
          new THREE.CylinderGeometry(0.035, 0.07, h, 24, 1, true),
          new THREE.MeshBasicMaterial({
            color: 0xe24b3b,
            transparent: true,
            opacity: 0.18 + 0.5 * share,
            side: THREE.DoubleSide,
            depthWrite: false,
          }),
        );
        cone.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), box.exhaustNormal));
        cone.position.copy(
          box.center.clone().add(new THREE.Vector3(L / 2 - 0.09, 0, 0)).add(box.exhaustNormal.clone().multiplyScalar(halfT + h / 2)),
        );
        this.root.add(cone);
      }
      const t = res ? fmt(res.t_die_c) : "…";
      const thr = res && res.throttle ? " · THROTTLE" : "";
      const plumeNote = (solution?.plume || []).find((p) => p.upper === gpu.id && p.share_of_upper_intake > 0.01);
      const extra = plumeNote ? ` · breathes ${Math.round(plumeNote.share_of_upper_intake * 100)}% of ${plumeNote.lower}'s exhaust` : "";
      const at = box.center.clone().add(new THREE.Vector3(-L / 2 - 0.01, 0, box.vertical ? 0 : box.size[2] / 2));
      this._label(at, `${gpu.id} · ${t}${thr}${extra}`, "tag gpu-tag" + (res?.throttle ? " hot" : ""));
    });
  }

  _shroud() {
    const { build, kase, presets } = this.ctx;
    const mode = build.shroud?.mode || "off";
    if (mode === "off") return;
    const { W, D } = this._dims();
    const top = m(kase.top_slot_y_mm) + 0.02;
    const bottom = m(kase.top_slot_y_mm - kase.horizontal_slots * kase.slot_pitch_mm) - 0.01;
    const h = Math.max(top - bottom, 0.08);
    const depth = 0.07;
    const wid = Math.min(W * 0.8, 0.2);
    const geo = new THREE.BoxGeometry(depth, h, wid);
    const box = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({
        color: mode === "on" ? COLORS.shroudOn : COLORS.shroudPassive,
        transparent: true,
        opacity: 0.55,
        roughness: 0.5,
      }),
    );
    box.position.set(D + depth / 2, bottom + h / 2, wid / 2 + 0.01);
    this.root.add(box);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: 0xf0c8b8 }));
    edge.position.copy(box.position);
    this.root.add(edge);
    const count = mode === "on" ? Math.max(0, build.shroud.count || 0) : 0;
    const fan = presets.fans.find((f) => f.id === build.shroud.fan);
    const r = Math.min(m(fan ? fan.size_mm : 140) / 2, h / (2 * Math.max(count, 1)) - 0.003, wid / 2 - 0.005);
    for (let i = 0; i < count; i += 1) {
      const y = bottom + ((i + 0.5) / count) * h;
      this._fanDisc(new THREE.Vector3(D + depth - 0.006, y, box.position.z), new THREE.Vector3(1, 0, 0), r, "exhaust", {
        kind: "shroud",
      });
    }
    const label = mode === "on" ? `Rear shroud · ${count}× ${fan ? fan.name : "fan"}` : "Rear duct (passive)";
    this._label(new THREE.Vector3(D + depth + 0.03, top + 0.02, box.position.z), label, "tag shroud-tag");
  }

  /* ------------------------------------------------------------ camera, labels */

  _resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) return;
    const size = this.renderer.getSize(new THREE.Vector2());
    if (size.x !== w || size.y !== h) {
      this.renderer.setSize(w, h, false);
      this._frame();
    }
  }

  _frame() {
    const canvas = this.canvas;
    const aspect = (canvas.clientWidth || 1600) / Math.max(canvas.clientHeight || 900, 1);
    this.camera.aspect = aspect;
    this.root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(this.root);
    if (box.isEmpty()) return;
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const dir = VIEWS[this.view].clone().normalize();
    const vfov = (this.camera.fov * Math.PI) / 180;
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
    const fit = Math.min(vfov, hfov);
    const dist = (sphere.radius * 1.02) / Math.sin(fit / 2);
    this.camera.position.copy(sphere.center.clone().add(dir.multiplyScalar(dist)));
    this.camera.near = Math.max(dist - sphere.radius * 2, 0.01);
    this.camera.far = dist + sphere.radius * 3;
    this.camera.lookAt(sphere.center);
    this.camera.updateProjectionMatrix();
  }

  project(v) {
    const p = v.clone().project(this.camera);
    return { x: (p.x + 1) / 2, y: (1 - p.y) / 2, z: p.z };
  }

  _label(pos, text, cls) {
    this.labels.push({ pos, text, cls });
  }

  _placeLabels() {
    const layer = this.labelsEl;
    if (!layer) return;
    if (layer.childElementCount !== this.labels.length || layer.dataset.sig !== this._sig()) {
      layer.innerHTML = "";
      this.labels.forEach((l) => {
        const div = document.createElement("div");
        div.className = l.cls;
        div.textContent = l.text;
        layer.appendChild(div);
      });
      layer.dataset.sig = this._sig();
    }
    const w = layer.clientWidth;
    const h = layer.clientHeight;
    const placed = [];
    this.labels.forEach((l, i) => {
      const el = layer.children[i];
      const p = this.project(l.pos);
      if (p.z > 1 || p.x < -0.1 || p.x > 1.1 || p.y < -0.1 || p.y > 1.1) {
        el.style.display = "none";
        return;
      }
      el.style.display = "";
      let x = p.x * w;
      let y = p.y * h;
      // Nudge down until it does not sit on a label already placed.
      const bw = el.offsetWidth || 120;
      const bh = el.offsetHeight || 18;
      x = Math.min(Math.max(x, bw / 2 + 4), w - bw / 2 - 4);
      for (let k = 0; k < 12; k += 1) {
        const hit = placed.find((b) => Math.abs(b.x - x) < (b.w + bw) / 2 && Math.abs(b.y - y) < (b.h + bh) / 2);
        if (!hit) break;
        y = hit.y + (hit.h + bh) / 2 + 2;
      }
      y = Math.min(Math.max(y, bh / 2 + 2), h - bh / 2 - 2);
      placed.push({ x, y, w: bw, h: bh });
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
    });
  }

  _sig() {
    return this.labels.map((l) => l.cls + l.text).join("|");
  }

  /* ------------------------------------------------------------ picking */

  _pick(ev) {
    const rect = this.canvas.getBoundingClientRect();
    const pointer = new THREE.Vector2(
      ((ev.clientX - rect.left) / rect.width) * 2 - 1,
      -((ev.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const ray = new THREE.Raycaster();
    ray.setFromCamera(pointer, this.camera);
    const hits = ray.intersectObjects(this.root.children, true);
    const hit = hits.find((h) => h.object.userData && (h.object.userData.kind === "fan" || h.object.userData.kind === "gpu"));
    return hit ? hit.object.userData : null;
  }

  _down(ev) {
    const data = this._pick(ev);
    this.drag = data ? { data, x: ev.clientX, y: ev.clientY } : null;
  }

  _up(ev) {
    const drag = this.drag;
    this.drag = null;
    if (!drag || !this.ctx) return;
    const moved = Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y) > 6;
    if (!moved) {
      if (drag.data.kind === "fan") this.cb.onPickMount?.(drag.data.id, drag.data.panel);
      if (drag.data.kind === "gpu") this.cb.onPickGpu?.(drag.data.id);
      return;
    }
    const rect = this.canvas.getBoundingClientRect();
    const nx = (ev.clientX - rect.left) / rect.width;
    const ny = (ev.clientY - rect.top) / rect.height;
    if (drag.data.kind === "fan") {
      let best = null;
      let bestD = 1e9;
      this.ctx.kase.mounts.forEach((layout) => {
        const p = this.project(this._face(layout.panel, layout).pos);
        const d = (p.x - nx) ** 2 + (p.y - ny) ** 2;
        if (d < bestD) {
          bestD = d;
          best = layout;
        }
      });
      if (best && bestD < 0.01 && best.id !== drag.data.id) this.cb.onMoveFan?.(drag.data.id, best.id);
    }
    if (drag.data.kind === "gpu") {
      const kase = this.ctx.kase;
      const gpu = this.ctx.build.gpus.find((g) => g.id === drag.data.id);
      const card = this.ctx.presets.cards.find((c) => c.id === gpu?.card);
      const slots = [];
      for (let s = 1; s <= kase.horizontal_slots; s += 1) slots.push(String(s));
      kase.vertical_positions.forEach((v) => slots.push(v.id));
      let best = null;
      let bestD = 1e9;
      slots.forEach((slot) => {
        const box = this.cardBox({ slot }, card);
        if (!box) return;
        const p = this.project(box.center);
        const d = (p.x - nx) ** 2 + (p.y - ny) ** 2;
        if (d < bestD) {
          bestD = d;
          best = slot;
        }
      });
      if (best && bestD < 0.02) this.cb.onMoveGpu?.(drag.data.id, best);
    }
  }
}

/* "Front ×8 · all Corsair AF120 RGB ELITE · 65.6 CFM · intake" when every fan
 * on a face matches; otherwise a short breakdown. */
export function faceFanLabel(panel, mounts, presets) {
  const fans = mounts.filter((mt) => mt.state === "fan" && mt.fan);
  const title = panel[0].toUpperCase() + panel.slice(1);
  if (!fans.length) {
    const blanks = mounts.filter((mt) => mt.state !== "radiator").length;
    return blanks ? `${title}: ${blanks} empty / blanked` : "";
  }
  const key = (mt) => `${mt.fan}|${mt.direction}|${Math.round((mt.duty ?? 1) * 100)}`;
  const groups = {};
  fans.forEach((mt) => (groups[key(mt)] ||= []).push(mt));
  const describe = (mt, all) => {
    const f = presets.fans.find((x) => x.id === mt.fan);
    const name = f ? f.name : mt.fan;
    const spec = f ? ` · ${f.airflow_cfm.toFixed(1)} CFM · ${f.static_pressure_mmh2o} mmH₂O` : "";
    const duty = (mt.duty ?? 1) < 0.999 ? ` · ${Math.round(mt.duty * 100)}%` : "";
    return `${all ? "all " : ""}${name}${spec}${duty} · ${mt.direction}`;
  };
  const entries = Object.values(groups);
  const others = mounts.length - fans.length - mounts.filter((mt) => mt.state === "radiator").length;
  const tail = others > 0 ? ` (+${others} blanked)` : "";
  if (entries.length === 1) {
    const head = fans.length > 1 ? `${title} fans ×${fans.length}` : `${title} fan`;
    return `${head}: ${describe(entries[0][0], fans.length > 1)}${tail}`;
  }
  return `${title}: ` + entries.map((g) => `${g.length}× ${describe(g[0], false)}`).join("; ") + tail;
}
