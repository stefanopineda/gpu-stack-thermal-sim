/* 3D case view. Case frame in mm: x = depth (0 front → D rear), y = height
 * (0 floor → H top), z = width (0 motherboard tray → W glass side). The scene
 * works in metres. The root group is mirrored in x so that, looking through
 * the glass, the front of the case is on the right and the rear I/O on the
 * left — the way a real ATX board sits. Fans are flat discs lying in the plane
 * of their panel, so a 3/4 camera shows them as ovals on their face. No text
 * is drawn over the scene; hovering an object reports it instead. */
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
  front34: new THREE.Vector3(0.62, 0.38, 1.0),
  side: new THREE.Vector3(0, 0.08, 1.0),
  rear34: new THREE.Vector3(-0.7, 0.4, 1.0),
};

const RADIATOR_PANELS = ["front", "top", "bottom"];
const m = (mm) => mm / 1000;

export class CaseScene {
  constructor(canvas, labelsEl, callbacks = {}) {
    this.canvas = canvas;
    this.labelsEl = labelsEl;
    this.cb = callbacks;
    this.view = "front34";
    this._setDir(VIEWS.front34);
    this.zoom = 1;
    this.orbit = null;
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
    this.root.scale.x = -1; // front on the right as seen through the glass
    this.scene.add(this.root);
    this.drag = null;
    this.labels = [];
    canvas.addEventListener("pointerdown", (ev) => this._down(ev));
    canvas.addEventListener("pointerup", (ev) => this._up(ev));
    canvas.addEventListener("pointermove", (ev) => (this.orbit ? this._orbitMove(ev) : this._hover(ev)));
    canvas.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        this.zoom = Math.min(2.5, Math.max(0.35, this.zoom * Math.pow(1.0015, ev.deltaY)));
        this._frame();
      },
      { passive: false },
    );
    canvas.addEventListener("dblclick", () => this.setView(this.view));
    canvas.addEventListener("pointerleave", () => this.cb.onHover?.(null));
    const loop = () => {
      this._resize();
      this.renderer.render(this.scene, this.camera);
      this._placeLabels();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  setView(name) {
    if (VIEWS[name]) {
      this.view = name;
      this._setDir(VIEWS[name]);
      this.zoom = 1;
    }
    this._frame();
  }

  /* Camera direction as azimuth (around the vertical axis) and elevation. */
  _setDir(v) {
    const d = v.clone().normalize();
    this.az = Math.atan2(d.x, d.z);
    this.el = Math.asin(d.y);
  }

  _dir() {
    return new THREE.Vector3(Math.sin(this.az) * Math.cos(this.el), Math.sin(this.el), Math.cos(this.az) * Math.cos(this.el));
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
    this.root.position.x = m(ctx.kase.depth_mm);
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
    const board = this._board();
    const add = (geo, mat, x, y, z, tip) => {
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      mesh.userData = { kind: "part", tip };
      this.root.add(mesh);
      return mesh;
    };
    const boardTip = "Motherboard: ASUS Pro WS WRX90E-SAGE SE layout (EEB 12 × 13 in, sTR5 socket, 8 DIMM slots, 7 PCIe 5.0 x16). Schematic, not a drawing.";
    const bx = board.rear - board.depth / 2;
    const by = board.top - board.height / 2;
    add(new THREE.BoxGeometry(board.depth, board.height, 0.003), new THREE.MeshStandardMaterial({ color: 0x2c5a4c, roughness: 0.8, emissive: 0x0d2019 }), bx, by, 0.012, boardTip);
    // sTR5 socket and retention frame.
    const sx = board.rear - board.depth * 0.46;
    const sy = board.top - 0.1;
    add(new THREE.BoxGeometry(0.078, 0.078, 0.01), new THREE.MeshStandardMaterial({ color: 0xa9b0b5, metalness: 0.7, roughness: 0.35 }), sx, sy, 0.019, "sTR5 socket (Threadripper PRO)");
    // Eight DIMM slots, four each side of the socket, running top to bottom.
    const dimm = new THREE.MeshStandardMaterial({ color: 0x6b7178, roughness: 0.5, metalness: 0.3 });
    for (let k = 0; k < 4; k += 1) {
      for (const side of [-1, 1]) {
        add(new THREE.BoxGeometry(0.006, 0.133, 0.03), dimm, sx + side * (0.058 + k * 0.0095), sy, 0.029, "DDR5 RDIMM slot (8 on WRX90E-SAGE SE)");
      }
    }
    // VRM heatsinks above the socket and along the I/O edge.
    const vrm = new THREE.MeshStandardMaterial({ color: 0x55504a, metalness: 0.5, roughness: 0.5 });
    add(new THREE.BoxGeometry(0.15, 0.022, 0.028), vrm, sx, board.top - 0.02, 0.028, "VRM heatsink");
    add(new THREE.BoxGeometry(0.03, 0.12, 0.03), vrm, board.rear - 0.03, board.top - 0.09, 0.03, "VRM heatsink / rear I/O shroud");
    // Seven PCIe x16 slots, lined up with case slots 1–7.
    const pcie = new THREE.MeshStandardMaterial({ color: 0xc9c2b6, roughness: 0.6 });
    const slots = Math.min(7, kase.horizontal_slots);
    for (let s = 1; s <= slots; s += 1) {
      add(new THREE.BoxGeometry(0.089, 0.0075, 0.011), pcie, board.rear - 0.044 - 0.0445, this.slotY(s) + 0.004, 0.019, `PCIe 5.0 x16 slot ${s}`);
    }

    // CPU cooler on the socket.
    const cpu = build.cpu || { cooling: "water", power_w: 150 };
    if (cpu.cooling === "air") {
      add(
        new THREE.BoxGeometry(0.11, 0.15, 0.15),
        new THREE.MeshStandardMaterial({ color: 0xb9c2c8, roughness: 0.35, metalness: 0.6 }),
        sx, sy, 0.014 + 0.075,
        `CPU tower cooler, ${Math.round(cpu.power_w)} W into the case air`,
      );
      // Fan on the front face of the tower, blowing toward the rear.
      this._fanDisc(new THREE.Vector3(sx - 0.055 - 0.008, sy, 0.089), new THREE.Vector3(-1, 0, 0), 0.07, "exhaust", {
        kind: "part",
        tip: "CPU cooler fan",
      });
    } else {
      add(new THREE.BoxGeometry(0.07, 0.07, 0.03), new THREE.MeshStandardMaterial({ color: 0x3a3632, roughness: 0.5 }), sx, sy, 0.035, `AIO pump on the CPU, ${Math.round(cpu.power_w)} W to the radiator`);
    }

    // PSU and its shroud, bottom rear.
    const n = kase.horizontal_slots;
    const lowest = this.slotY(n) - m(kase.slot_pitch_mm);
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
      { kind: "part", tip: `PSU, bottom rear${shrouded ? ", under the PSU shroud" : ""}, fan ${psuFanUp ? "up" : "down"}` },
      0.006,
    );
    this._label(new THREE.Vector3(D - 0.1, 0.13, W / 2), `PSU${shrouded ? " (shrouded)" : ""} · fan ${psuFanUp ? "up" : "down"}`, "tag");
  }

  /* ASUS Pro WS WRX90E-SAGE SE, EEB 12 × 13 in: schematic placement. */
  _board() {
    const { H, D } = this._dims();
    const height = Math.min(0.305, H - 0.12);
    const depth = Math.min(0.33, D - 0.08);
    return { top: H - 0.03, height, depth, rear: D - 0.012 };
  }

  /* Slot 1 sits about 158 mm below the board's top edge (ATX slot positions). */
  slotY(s) {
    const k = this.ctx.kase;
    const slot1 = Math.min(m(k.top_slot_y_mm), this._board().top - 0.158);
    return slot1 - (s - 1) * m(k.slot_pitch_mm);
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
    const layouts = activeLayouts(kase, build.patterns);
    const byMount = Object.fromEntries((build.mounts || []).map((mt) => [mt.id, mt]));
    layouts.forEach((layout) => {
      const mount = byMount[layout.id] || { id: layout.id, state: "blanked" };
      if (mount.state === "radiator") return;
      // An unused side-wall mount is just glass: draw nothing rather than a ring
      // that reads as a fan.
      if (layout.panel === "side" && mount.state !== "fan") return;
      const { pos, normal } = this._face(layout.panel, layout);
      const r = m(layout.size_mm) / 2;
      // Sit flush on the panel, the disc's thickness inside the case.
      const center = pos.clone().add(normal.clone().multiplyScalar(-0.007 + 0.002));
      const dir = mount.state === "fan" ? mount.direction : "blank";
      const fan = presets.fans.find((f) => f.id === mount.fan);
      const tip =
        mount.state === "fan"
          ? `${cap(layout.panel)} fan: ${fan ? fan.name : mount.fan} · ${mount.direction} · ${Math.round((mount.duty ?? 1) * 100)} % speed`
          : mount.state === "empty"
            ? `${cap(layout.panel)} ${layout.size_mm} mm mount: open hole, no fan`
            : `${cap(layout.panel)} ${layout.size_mm} mm mount: cover plate (plugged)`;
      const g = this._fanDisc(center, normal, r * 0.96, dir, { kind: "fan", id: mount.id, panel: layout.panel, tip });
      if (this.ctx.selectedMount === mount.id) g.scale.setScalar(1.08);
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
    const onPanel = activeLayouts(kase, build.patterns).filter((l) => l.panel === panel);
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
    slab.userData = { kind: "radiator", tip: `Radiator: ${model.name}, ${rad.direction}, fans on its inner face` };
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
        tip: `Radiator fan: ${fan ? fan.name : "fan"}, ${rad.direction}`,
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
      const index = kase.vertical_positions.findIndex((p) => p.id === slot);
      if (index < 0) return null;
      // Vertical brackets sit side by side at the rear, next to the glass:
      // v1 nearest the glass, one slot pitch apart. The card stands on edge
      // beside the middle of the horizontal stack.
      const z = W - 0.012 - T / 2 - index * m(kase.slot_pitch_mm);
      const y = this.slotY(Math.min(4, kase.horizontal_slots)) - Hc / 2 + 0.03;
      return {
        vertical: true,
        center: new THREE.Vector3(D - 0.012 - L / 2, y, z),
        size: [L, Hc, T],
        fanNormal: new THREE.Vector3(0, 0, 1),
        exhaustNormal: new THREE.Vector3(0, 0, -1),
      };
    }
    const s = Number(slot);
    // The card's PCB sits at the slot; the cooler hangs below it (fan face down).
    const ySlot = this.slotY(s) + 0.008;
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
      const order = this.ctx.order?.[gpu.id];
      const where = box.vertical ? `vertical ${gpu.slot}` : `slot ${gpu.slot}`;
      const tip = `GPU ${order ?? ""} · ${card ? card.name : gpu.card} · ${where}` +
        (res ? ` · ${fmt(res.t_die_c)}${res.throttle ? " (throttling)" : ""} · ${res.flow_cfm.toFixed(0)} CFM` : "");
      mesh.userData = { kind: "gpu", id: gpu.id, tip };
      this.root.add(mesh);
      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(geo),
        new THREE.LineBasicMaterial({ color: box.vertical ? 0xf3efe6 : 0x14120e }),
      );
      edge.position.copy(box.center);
      this.root.add(edge);
      // Fan face: one blower eye, or two axial fans.
      const through = card?.cooler === "flow_through";
      const L = box.size[0];
      const halfT = (box.vertical ? box.size[2] : box.size[1]) / 2;
      const fanCenters = through ? [-L / 2 + 0.07, L / 2 - 0.07] : [-L / 2 + 0.05];
      fanCenters.forEach((dx) => {
        const c = box.center.clone().add(new THREE.Vector3(dx, 0, 0)).add(box.fanNormal.clone().multiplyScalar(halfT + 0.002));
        this._fanDisc(c, box.fanNormal, through ? 0.045 : 0.03, "gpu", { kind: "gpu", id: gpu.id, tip });
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
    const top = this.slotY(1) + 0.03;
    const bottom = this.slotY(kase.horizontal_slots) - m(kase.slot_pitch_mm);
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
        tip: `Rear shroud fan: ${fan ? fan.name : "fan"}`,
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
    const dir = this._dir();
    const vfov = (this.camera.fov * Math.PI) / 180;
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
    const fit = Math.min(vfov, hfov);
    const dist = ((sphere.radius * 1.02) / Math.sin(fit / 2)) * this.zoom;
    this.camera.position.copy(sphere.center.clone().add(dir.multiplyScalar(dist)));
    this.camera.near = Math.max(dist - sphere.radius * 2, 0.005);
    this.camera.far = dist + sphere.radius * 3;
    this.camera.lookAt(sphere.center);
    this.camera.updateProjectionMatrix();
  }

  project(v) {
    this.root.updateMatrixWorld(true);
    const p = v.clone().applyMatrix4(this.root.matrixWorld).project(this.camera);
    return { x: (p.x + 1) / 2, y: (1 - p.y) / 2, z: p.z };
  }

  _label() {
    // Text overlays were removed in rev 4.1: stats live in the side panel and
    // details appear on hover.
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

  _hover(ev) {
    if (this.drag) return;
    const rect = this.canvas.getBoundingClientRect();
    const pointer = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(pointer, this.camera);
    const hit = ray.intersectObjects(this.root.children, true).find((h) => h.object.userData && h.object.userData.tip);
    this.cb.onHover?.(hit ? hit.object.userData.tip : null, ev);
  }

  _down(ev) {
    const data = this._pick(ev);
    this.drag = data ? { data, x: ev.clientX, y: ev.clientY } : null;
    if (!data) {
      // Empty space: drag to orbit the case.
      this.orbit = { x: ev.clientX, y: ev.clientY, az: this.az, el: this.el };
      try {
        this.canvas.setPointerCapture(ev.pointerId);
      } catch {
        // synthetic events have no capturable pointer
      }
      this.canvas.style.cursor = "grabbing";
    }
  }

  _orbitMove(ev) {
    const o = this.orbit;
    this.az = o.az - (ev.clientX - o.x) * 0.008;
    this.el = Math.max(-1.3, Math.min(1.3, o.el + (ev.clientY - o.y) * 0.006));
    this._frame();
  }

  _up(ev) {
    if (this.orbit) {
      this.orbit = null;
      this.canvas.style.cursor = "";
      return;
    }
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
      activeLayouts(this.ctx.kase, this.ctx.build.patterns).forEach((layout) => {
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

const cap = (s) => s[0].toUpperCase() + s.slice(1);

/* Mounts that exist for the chosen fan pattern on each face (default: first). */
export function activeLayouts(kase, patterns = {}) {
  const options = {};
  kase.mounts.forEach((l) => {
    if (!l.pattern) return;
    (options[l.panel] ||= []);
    if (!options[l.panel].includes(l.pattern)) options[l.panel].push(l.pattern);
  });
  return kase.mounts.filter((l) => {
    if (!l.pattern) return true;
    const chosen = options[l.panel].includes(patterns?.[l.panel]) ? patterns[l.panel] : options[l.panel][0];
    return l.pattern === chosen;
  });
}

export function facePatterns(kase, panel) {
  const out = [];
  kase.mounts.forEach((l) => {
    if (l.panel === panel && l.pattern && !out.includes(l.pattern)) out.push(l.pattern);
  });
  return out;
}

/* "Front ×8 · all Corsair AF120 RGB ELITE · 65.6 CFM · intake" when every fan
 * on a face matches; otherwise a short breakdown. */
export function faceFanLabel(panel, mounts, presets) {
  const fans = mounts.filter((mt) => mt.state === "fan" && mt.fan);
  const title = panel[0].toUpperCase() + panel.slice(1);
  if (!fans.length) {
    const blanks = mounts.filter((mt) => mt.state !== "radiator").length;
    return blanks ? `${title}: ${blanks} cover plate${blanks > 1 ? "s" : ""}, no fans` : "";
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
  const tail = others > 0 ? ` (+${others} plugged)` : "";
  if (entries.length === 1) {
    const head = fans.length > 1 ? `${title} fans ×${fans.length}` : `${title} fan`;
    return `${head}: ${describe(entries[0][0], fans.length > 1)}${tail}`;
  }
  return `${title}: ` + entries.map((g) => `${g.length}× ${describe(g[0], false)}`).join("; ") + tail;
}
