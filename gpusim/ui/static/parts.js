/* Realistic part models for the case view. Everything is procedural (no
 * downloaded meshes): PBR materials, canvas textures, and real part
 * proportions. Colour is used only as a cue — a lit ring on each fan for
 * intake / exhaust / internal, and a temperature light bar on each GPU. */
import * as THREE from "./vendor/three.module.js";

const cache = new Map();
/* Shared geometries, materials and textures are built once and flagged so the
 * scene never disposes them when it rebuilds. */
const once = (key, make) => {
  if (!cache.has(key)) {
    const v = make();
    if (v && v.userData) v.userData.shared = true;
    cache.set(key, v);
  }
  return cache.get(key);
};

export const isShared = (x) => Boolean(x && x.userData && x.userData.shared);

/* ------------------------------------------------------------------ textures */

function canvasTexture(key, w, h, draw, repeat = [1, 1], color = true) {
  return once(`tex:${key}`, () => {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    draw(c.getContext("2d"), w, h);
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(...repeat);
    t.anisotropy = 4;
    if (color) t.colorSpace = THREE.SRGBColorSpace;
    return t;
  });
}

/* Hex-hole perforated steel: white = solid, black = hole (alpha map). */
export function perforation(repeatX, repeatY) {
  const rx = Math.max(1, Math.round(repeatX));
  const ry = Math.max(1, Math.round(repeatY));
  return canvasTexture(`perf:${rx}:${ry}`, 64, 64, (g) => {
    g.fillStyle = "#fff";
    g.fillRect(0, 0, 64, 64);
    g.fillStyle = "#000";
    const r = 9;
    for (let row = 0; row < 3; row += 1) {
      for (let col = 0; col < 3; col += 1) {
        const x = col * 22 + (row % 2 ? 11 : 0);
        const y = row * 21 + 10;
        g.beginPath();
        for (let k = 0; k < 6; k += 1) {
          const a = (Math.PI / 3) * k + Math.PI / 6;
          g.lineTo(x + r * Math.cos(a), y + r * Math.sin(a));
        }
        g.closePath();
        g.fill();
      }
    }
  }, [rx, ry], false);
}

function pcbTexture() {
  return canvasTexture("pcb", 512, 512, (g, w, h) => {
    g.fillStyle = "#16181b";
    g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(120,130,140,0.22)";
    g.lineWidth = 1.2;
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 260; i += 1) {
      let x = rnd() * w;
      let y = rnd() * h;
      g.beginPath();
      g.moveTo(x, y);
      for (let k = 0; k < 4; k += 1) {
        if (rnd() > 0.5) x += (rnd() - 0.5) * 120;
        else y += (rnd() - 0.5) * 120;
        g.lineTo(x, y);
      }
      g.stroke();
    }
    g.fillStyle = "rgba(200,190,160,0.5)";
    for (let i = 0; i < 400; i += 1) g.fillRect(rnd() * w, rnd() * h, 2 + rnd() * 5, 1.5 + rnd() * 3);
  });
}

function finTexture(dense = 3, dark = false) {
  return canvasTexture(`fins${dense}${dark ? "d" : ""}`, 256, 64, (g, w, h) => {
    const grad = g.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, dark ? "#3a3d42" : "#d6dade");
    grad.addColorStop(1, dark ? "#1d1f22" : "#9aa0a6");
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    g.strokeStyle = dark ? "#0a0b0c" : "#5d646b";
    g.lineWidth = 1;
    for (let x = 0.5; x < w; x += dense) {
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, h);
      g.stroke();
    }
  }, [2, 1]);
}

function ventTexture() {
  return canvasTexture("vent", 128, 256, (g, w, h) => {
    g.fillStyle = "#fff";
    g.fillRect(0, 0, w, h);
    g.fillStyle = "#000";
    for (let y = 14; y < h - 10; y += 16) g.fillRect(18, y, w - 36, 8);
  }, [1, 1], false);
}

function honeycomb() {
  return perforation(7, 7);
}

/* ------------------------------------------------------------------ materials */

export const MAT = {
  get steel() { return once("m:steel", () => new THREE.MeshStandardMaterial({ color: 0x19191c, metalness: 0.2, roughness: 0.58 })); },
  get steelMid() { return once("m:steelMid", () => new THREE.MeshStandardMaterial({ color: 0x2a2b2f, metalness: 0.35, roughness: 0.5 })); },
  get alu() { return once("m:alu", () => new THREE.MeshStandardMaterial({ color: 0xc3c7cc, metalness: 0.95, roughness: 0.3 })); },
  get aluDark() { return once("m:aluDark", () => new THREE.MeshStandardMaterial({ color: 0x3b3e43, metalness: 0.75, roughness: 0.36 })); },
  get black() { return once("m:black", () => new THREE.MeshStandardMaterial({ color: 0x0c0d0f, metalness: 0.15, roughness: 0.6 })); },
  get blade() { return once("m:blade", () => new THREE.MeshStandardMaterial({ color: 0x1b1c20, metalness: 0.05, roughness: 0.45, side: THREE.DoubleSide })); },
  get noctua() { return once("m:noctua", () => new THREE.MeshStandardMaterial({ color: 0x3a3c40, metalness: 0.1, roughness: 0.55, side: THREE.DoubleSide })); },
  get beige() { return once("m:beige", () => new THREE.MeshStandardMaterial({ color: 0xd9c7a8, metalness: 0.05, roughness: 0.6, side: THREE.DoubleSide })); },
  get brown() { return once("m:brown", () => new THREE.MeshStandardMaterial({ color: 0x6b3f2a, metalness: 0.05, roughness: 0.5, side: THREE.DoubleSide })); },
  get gpuBody() { return once("m:gpuBody", () => new THREE.MeshStandardMaterial({ color: 0x1f2023, metalness: 0.55, roughness: 0.34 })); },
  get darkFins() { return once("m:darkFins", () => new THREE.MeshStandardMaterial({ map: finTexture(3, true), metalness: 0.4, roughness: 0.55 })); },
  get gold() { return once("m:gold", () => new THREE.MeshStandardMaterial({ color: 0xd8a948, metalness: 1, roughness: 0.28 })); },
  get copper() { return once("m:copper", () => new THREE.MeshStandardMaterial({ color: 0xc27a45, metalness: 1, roughness: 0.3 })); },
  get nickel() { return once("m:nickel", () => new THREE.MeshStandardMaterial({ color: 0xdadde0, metalness: 1, roughness: 0.18 })); },
  get rubber() { return once("m:rubber", () => new THREE.MeshStandardMaterial({ color: 0x0b0b0c, roughness: 0.85 })); },
  get pcb() { return once("m:pcb", () => new THREE.MeshStandardMaterial({ map: pcbTexture(), metalness: 0.2, roughness: 0.55 })); },
  get fins() { return once("m:fins", () => new THREE.MeshStandardMaterial({ map: finTexture(3), metalness: 0.85, roughness: 0.38 })); },
  get glass() {
    return once("m:glass", () => new THREE.MeshPhysicalMaterial({
      color: 0xaebfcc, metalness: 0, roughness: 0.03, transparent: true, opacity: 0.1, clearcoat: 1, clearcoatRoughness: 0.02,
      envMapIntensity: 1.6, side: THREE.DoubleSide, depthWrite: false,
    }));
  },
  get smoke() {
    return once("m:smoke", () => new THREE.MeshPhysicalMaterial({
      color: 0x1b1c20, metalness: 0, roughness: 0.08, transparent: true, opacity: 0.45, clearcoat: 1, side: THREE.DoubleSide, depthWrite: false,
    }));
  },
};

/* Perforated steel. Rendered as a see-through alpha map rather than an alpha
 * test so that, from a distance, it reads as dark mesh instead of shimmering. */
export function meshPanelMaterial(widthM, heightM, opacity = 0.9) {
  const pitch = 0.018; // one 64-px tile ≈ three 6 mm holes
  return new THREE.MeshStandardMaterial({
    color: 0x141518, metalness: 0.3, roughness: 0.5, alphaMap: perforation(widthM / pitch, heightM / pitch),
    transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide,
  });
}

/* Lit accent (fan ring, GPU light bar). */
export function glow(color, intensity = 1.4) {
  return new THREE.MeshStandardMaterial({ color: 0x111111, emissive: new THREE.Color(color), emissiveIntensity: intensity, roughness: 0.4 });
}

export const CUE = { intake: 0x2f86ff, exhaust: 0xff4a3a, internal: 0xffa640 };

/* ------------------------------------------------------------------ helpers */

function box(w, h, d, material) {
  return new THREE.Mesh(once(`g:box:${w}:${h}:${d}`, () => new THREE.BoxGeometry(w, h, d)), material);
}

function cyl(r, h, material, segs = 32) {
  return new THREE.Mesh(once(`g:cyl:${r}:${h}:${segs}`, () => new THREE.CylinderGeometry(r, r, h, segs)), material);
}

export function tag(object, userData) {
  object.traverse((o) => {
    o.userData = userData;
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return object;
}

/* Rotate a part built along +Z so that +Z points along `normal`. */
export function orient(object, normal) {
  object.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal.clone().normalize());
  return object;
}

/* ------------------------------------------------------------------ fans */

function bladeGeometry(r, count) {
  return once(`g:blades:${r}:${count}`, () => {
    const hub = r * 0.3;
    const shape = new THREE.Shape();
    shape.moveTo(hub, -r * 0.08);
    shape.quadraticCurveTo(r * 0.7, -r * 0.22, r * 0.94, -r * 0.05);
    shape.quadraticCurveTo(r * 0.98, r * 0.18, r * 0.7, r * 0.3);
    shape.quadraticCurveTo(r * 0.45, r * 0.24, hub, r * 0.1);
    shape.closePath();
    const one = new THREE.ExtrudeGeometry(shape, { depth: 0.0015, bevelEnabled: false });
    one.rotateX(0.35); // blade pitch
    const parts = [];
    for (let i = 0; i < count; i += 1) {
      const g = one.clone();
      g.rotateZ((2 * Math.PI * i) / count);
      parts.push(g);
    }
    return mergeGeometries(parts);
  });
}

function frameGeometry(size, depth) {
  return once(`g:frame:${size}:${depth}`, () => {
    const h = size / 2;
    const c = size * 0.08;
    const s = new THREE.Shape();
    s.moveTo(-h + c, -h);
    s.lineTo(h - c, -h);
    s.quadraticCurveTo(h, -h, h, -h + c);
    s.lineTo(h, h - c);
    s.quadraticCurveTo(h, h, h - c, h);
    s.lineTo(-h + c, h);
    s.quadraticCurveTo(-h, h, -h, h - c);
    s.lineTo(-h, -h + c);
    s.quadraticCurveTo(-h, -h, -h + c, -h);
    const hole = new THREE.Path();
    hole.absarc(0, 0, h * 0.965, 0, Math.PI * 2, true);
    s.holes.push(hole);
    const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: 0.0008, bevelSize: 0.0008, bevelSegments: 1, curveSegments: 40 });
    g.translate(0, 0, -depth / 2);
    return g;
  });
}

/* A case fan: square frame, blades, hub, and a thin lit ring whose colour says
 * intake / exhaust / internal. Axis is +Z, airflow along `flow` (+1 or −1). */
export function fanModel(sizeM, { cue = null, style = "black", depth = 0.025, blades = 9 } = {}) {
  const g = new THREE.Group();
  const r = (sizeM / 2) * 0.93;
  const frameMat = style === "classic" ? MAT.beige : style === "grey" ? MAT.noctua : MAT.black;
  const bladeMat = style === "classic" ? MAT.brown : style === "grey" ? MAT.noctua : MAT.blade;
  const frame = new THREE.Mesh(frameGeometry(sizeM, depth), frameMat);
  g.add(frame);
  const rotor = new THREE.Mesh(bladeGeometry(r, blades), bladeMat);
  g.add(rotor);
  const hub = cyl(r * 0.3, depth * 0.8, MAT.black, 28);
  hub.rotation.x = Math.PI / 2;
  g.add(hub);
  const cap = cyl(r * 0.2, depth * 0.82, MAT.steelMid, 24);
  cap.rotation.x = Math.PI / 2;
  g.add(cap);
  // Struts on the motor side.
  for (let i = 0; i < 4; i += 1) {
    const s = box(r * 1.05, 0.003, 0.003, MAT.black);
    s.position.z = -depth / 2 + 0.002;
    s.rotation.z = (Math.PI / 4) * (2 * i + 1) * 0.5;
    g.add(s);
  }
  if (cue) {
    // A thin lit ring on both faces: the only colour on an otherwise real fan.
    const mat = glow(cue, 1.2);
    for (const side of [-1, 1]) {
      const ring = new THREE.Mesh(once(`g:ring:${sizeM}`, () => new THREE.TorusGeometry((sizeM / 2) * 0.975, 0.0018, 8, 64)), mat);
      ring.position.z = side * (depth / 2 + 0.0006);
      g.add(ring);
    }
  }
  return g;
}

/* Steel blanking plate over an unused mount. */
export function coverPlate(sizeM) {
  const g = new THREE.Group();
  g.add(box(sizeM * 0.98, sizeM * 0.98, 0.0015, MAT.steelMid));
  return g;
}

/* An open, unfilled mount: just the dark rim of the hole. */
export function openHole(sizeM) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(once(`g:hole:${sizeM}`, () => new THREE.TorusGeometry((sizeM / 2) * 0.95, 0.0022, 8, 48)), MAT.aluDark));
  return g;
}

/* ------------------------------------------------------------------ GPUs */

/* Blower impeller seen through the fan window. */
function blowerWheel(r) {
  const g = new THREE.Group();
  const disc = cyl(r, 0.004, MAT.black, 36);
  disc.rotation.x = Math.PI / 2;
  g.add(disc);
  const blades = once(`g:impeller:${r}`, () => {
    const parts = [];
    for (let i = 0; i < 36; i += 1) {
      const b = new THREE.BoxGeometry(r * 0.32, 0.0012, 0.003);
      b.translate(r * 0.8, 0, 0.0015);
      b.rotateZ((2 * Math.PI * i) / 36 + 0.3);
      parts.push(b);
    }
    return mergeGeometries(parts);
  });
  g.add(new THREE.Mesh(blades, MAT.blade));
  const hub = cyl(r * 0.45, 0.005, MAT.steelMid, 24);
  hub.rotation.x = Math.PI / 2;
  hub.position.z = 0.0025;
  g.add(hub);
  return g;
}

/* A graphics card in local coordinates: X = length (bracket at +X), Y =
 * thickness (fan face at −Y, backplate at +Y), Z = height (PCB edge and gold
 * fingers at −Z toward the board, top edge +Z toward the glass). */
export function gpuModel(card, { L, T, H, tempColor, topInletShare = 0 }) {
  const g = new THREE.Group();
  const through = card?.cooler === "flow_through";
  const hotColor = new THREE.Color(tempColor);
  // PCB and backplate.
  const backplate = box(L * 0.98, 0.0022, H * 0.96, MAT.steel);
  backplate.position.set(-L * 0.01, T / 2 - 0.0011, 0);
  g.add(backplate);
  const pcb = box(L * 0.95, 0.0016, H * 0.93, MAT.pcb);
  pcb.position.set(-L * 0.02, T / 2 - 0.004, -H * 0.01);
  g.add(pcb);
  // Gold fingers, into the slot.
  const fingers = box(0.089, 0.0014, 0.008, MAT.gold);
  fingers.position.set(L / 2 - 0.0885, T / 2 - 0.004, -H / 2 - 0.004);
  g.add(fingers);
  // Rear bracket with vents.
  const bracket = new THREE.Mesh(
    once("g:bracket", () => new THREE.BoxGeometry(0.0012, 1, 1)),
    new THREE.MeshStandardMaterial({ color: 0xb9bdc2, metalness: 0.9, roughness: 0.35, alphaMap: ventTexture(), alphaTest: 0.5 }),
  );
  bracket.scale.set(1, T + 0.004, H + 0.012);
  bracket.position.set(L / 2 + 0.0006, 0, 0.004);
  g.add(bracket);

  if (!through) {
    // Blower: enclosed black shroud, impeller window at the front end.
    const shroud = box(L, T - 0.006, H * 0.97, MAT.black);
    shroud.position.set(0, -0.001, 0);
    g.add(shroud);
    const trim = box(L * 0.96, 0.002, 0.004, MAT.alu);
    trim.position.set(0, -T / 2 + 0.002, H / 2 - 0.004);
    g.add(trim);
    const wheel = blowerWheel(0.034);
    wheel.rotation.x = Math.PI / 2; // face −Y, toward the floor
    wheel.position.set(-L / 2 + 0.055, -T / 2 + 0.002, 0);
    g.add(wheel);
    if (topInletShare > 0) {
      // Max-Q style: part of the blower eye is open through the backplate too.
      const rr = Math.min(0.03, 0.034 * Math.sqrt(topInletShare / Math.max(1 - topInletShare, 0.1)));
      const eye = blowerWheel(rr);
      eye.rotation.x = -Math.PI / 2;
      eye.position.set(-L / 2 + 0.055, T / 2 + 0.0002, 0);
      g.add(eye);
      const rim = new THREE.Mesh(new THREE.TorusGeometry(rr + 0.002, 0.0015, 8, 40), MAT.alu);
      rim.rotation.x = Math.PI / 2;
      rim.position.set(-L / 2 + 0.055, T / 2 + 0.0005, 0);
      g.add(rim);
    }
    const ring = new THREE.Mesh(once("g:blowRing", () => new THREE.TorusGeometry(0.036, 0.0018, 8, 48)), MAT.alu);
    ring.rotation.x = Math.PI / 2;
    ring.position.set(-L / 2 + 0.055, -T / 2 - 0.001, 0);
    g.add(ring);
  } else {
    // Flow-through: gunmetal frame, two axial fans on the fan face, finned
    // cut-outs in the backplate where the exhaust leaves.
    const frame = box(L, T - 0.008, H * 0.98, MAT.gpuBody);
    g.add(frame);
    const r = Math.min(0.05, H * 0.36);
    [-L / 2 + r + 0.012, L / 2 - r - 0.03].forEach((x, i) => {
      if (card.id === "rtx-3090-fe" && i === 1) return;
      const fan = fanModel(r * 2.05, { depth: 0.012, blades: 7 });
      fan.rotation.x = Math.PI / 2; // axis +Z → −Y
      fan.position.set(x, -T / 2 + 0.002, 0);
      g.add(fan);
    });
    // Backplate cut-outs over the fin stacks.
    [-L / 2 + r + 0.012, L / 2 - r - 0.03].forEach((x) => {
      const cut = box(r * 1.7, 0.001, H * 0.6, MAT.darkFins);
      cut.position.set(x, T / 2 + 0.0002, 0);
      g.add(cut);
    });
    if (card.id === "rtx-3090-fe") {
      const rear = fanModel(r * 2.05, { depth: 0.012, blades: 7 });
      rear.rotation.x = -Math.PI / 2;
      rear.position.set(L / 2 - r - 0.03, T / 2 + 0.002, 0);
      g.add(rear);
    }
  }
  // Temperature light bar along the glass-facing top edge.
  const bar = box(L * 0.7, 0.004, 0.0025, glow(hotColor, 1.6));
  bar.position.set(-L * 0.08, 0, H / 2 + 0.001);
  g.add(bar);
  return g;
}

/* ------------------------------------------------------------------ board, CPU */

/* WRX90E-SAGE SE style board in case coordinates (metres): the PCB lies on
 * standoffs just off the tray, rear I/O at `rear`. */
export function motherboardModel({ depth, height, top, rear, slotYs }) {
  const g = new THREE.Group();
  const cx = rear - depth / 2;
  const cy = top - height / 2;
  const pcb = box(depth, height, 0.0016, MAT.pcb);
  pcb.position.set(cx, cy, 0.009);
  g.add(pcb);
  // Rear I/O shroud and VRM heatsinks along the top edge.
  const io = box(0.03, 0.14, 0.032, MAT.aluDark);
  io.position.set(rear - 0.02, top - 0.095, 0.026);
  g.add(io);
  const vrmTop = box(depth * 0.5, 0.024, 0.028, MAT.aluDark);
  vrmTop.position.set(rear - depth * 0.46, top - 0.02, 0.024);
  g.add(vrmTop);
  // Chipset and M.2 heatsinks in the lower board, clear of the PCIe slots.
  const chip = box(0.07, 0.07, 0.012, MAT.alu);
  chip.position.set(rear - depth + 0.06, top - height + 0.055, 0.016);
  g.add(chip);
  // 24-pin and EPS connectors on the front edge.
  const atx = box(0.012, 0.052, 0.014, MAT.black);
  atx.position.set(rear - depth + 0.008, top - 0.12, 0.017);
  g.add(atx);
  // PCIe x16 slots with steel armour.
  slotYs.forEach((y) => {
    const s = box(0.089, 0.0075, 0.011, MAT.black);
    s.position.set(rear - 0.0885, y, 0.0155);
    g.add(s);
    const armour = box(0.09, 0.0086, 0.002, MAT.nickel);
    armour.position.set(rear - 0.0885, y, 0.0215);
    g.add(armour);
  });
  return g;
}

/* sTR5 socket, eight DDR5 RDIMMs, and the cooler (tower or AIO pump). */
export function cpuAreaModel({ cooling, fans, upward, cue }) {
  const g = new THREE.Group();
  const ihs = box(0.072, 0.075, 0.006, MAT.nickel);
  ihs.position.z = 0.004;
  g.add(ihs);
  const frame = box(0.086, 0.09, 0.004, MAT.steelMid);
  frame.position.z = 0.002;
  g.add(frame);
  for (let k = 0; k < 4; k += 1) {
    for (const side of [-1, 1]) {
      const x = side * (0.06 + k * 0.0095);
      const slot = box(0.0062, 0.14, 0.006, MAT.black);
      slot.position.set(x, 0, 0.003);
      g.add(slot);
      const stick = box(0.0045, 0.133, 0.031, MAT.steelMid);
      stick.position.set(x, 0, 0.021);
      g.add(stick);
      const top = box(0.0046, 0.128, 0.003, MAT.alu);
      top.position.set(x, 0, 0.037);
      g.add(top);
    }
  }
  if (cooling === "air") {
    // NH-U14S TR5-SP6 class: fins 150 × 52 mm, 165 mm tall off the board.
    const finsX = 0.15;
    const finsY = 0.052;
    const tall = 0.165;
    const base = box(0.07, 0.07, 0.012, MAT.nickel);
    base.position.z = 0.013;
    g.add(base);
    const count = 58;
    const fin = new THREE.InstancedMesh(
      once("g:cpufin", () => new THREE.BoxGeometry(1, 1, 0.0004)),
      MAT.alu,
      count,
    );
    const mtx = new THREE.Matrix4();
    for (let i = 0; i < count; i += 1) {
      const z = 0.03 + (i / (count - 1)) * (tall - 0.035);
      mtx.compose(new THREE.Vector3(0, 0, z), new THREE.Quaternion(), upward ? new THREE.Vector3(finsX, finsY, 1) : new THREE.Vector3(finsY, finsX, 1));
      fin.setMatrixAt(i, mtx);
    }
    g.add(fin);
    for (let i = 0; i < 6; i += 1) {
      const pipe = cyl(0.003, tall - 0.01, MAT.nickel, 12);
      pipe.rotation.x = Math.PI / 2;
      const off = (i - 2.5) * 0.02;
      pipe.position.set(upward ? off : 0, upward ? 0 : off, tall / 2 + 0.01);
      g.add(pipe);
    }
    const cover = box(upward ? finsX : finsY, upward ? finsY : finsX, 0.004, MAT.alu);
    cover.position.z = tall + 0.004;
    g.add(cover);
    const fanAt = (sign) => {
      const f = fanModel(0.14, { cue, style: "classic", depth: 0.025 });
      // Fan axis along ±Y (up) or ±X (rear), air moving the same way.
      const dir = upward ? new THREE.Vector3(0, sign, 0) : new THREE.Vector3(sign, 0, 0);
      orient(f, dir);
      const off = finsY / 2 + 0.0125;
      f.position.copy(dir.clone().multiplyScalar(off)).add(new THREE.Vector3(0, 0, 0.012 + tall / 2));
      g.add(f);
    };
    if (fans !== "bottom") fanAt(1);
    if (fans !== "top") fanAt(-1);
  } else {
    const pump = cyl(0.036, 0.045, MAT.black, 40);
    pump.rotation.x = Math.PI / 2;
    pump.position.z = 0.03;
    g.add(pump);
    const cap = cyl(0.03, 0.002, MAT.alu, 40);
    cap.rotation.x = Math.PI / 2;
    cap.position.z = 0.053;
    g.add(cap);
  }
  return g;
}

export function radiatorModel(len, width, thick) {
  const g = new THREE.Group();
  const core = box(len - 0.04, thick, width, once("m:radfins", () => new THREE.MeshStandardMaterial({ map: finTexture(2, true), metalness: 0.3, roughness: 0.6 })));
  g.add(core);
  [-1, 1].forEach((s) => {
    const tank = box(0.02, thick + 0.004, width + 0.004, MAT.black);
    tank.position.x = s * (len / 2 - 0.01);
    g.add(tank);
  });
  return g;
}

export function tube(points, radius = 0.0065) {
  const curve = new THREE.CatmullRomCurve3(points);
  return new THREE.Mesh(new THREE.TubeGeometry(curve, 48, radius, 12, false), MAT.rubber);
}

export function psuModel(fanUp) {
  const g = new THREE.Group();
  const shell = box(0.17, 0.086, 0.15, MAT.steel);
  g.add(shell);
  const grille = new THREE.Mesh(
    once("g:psugrille", () => new THREE.PlaneGeometry(0.13, 0.13)),
    new THREE.MeshStandardMaterial({ color: 0x0e0f11, metalness: 0.6, roughness: 0.4, alphaMap: honeycomb(), alphaTest: 0.5, side: THREE.DoubleSide }),
  );
  grille.rotation.x = Math.PI / 2;
  grille.position.y = fanUp ? 0.0435 : -0.0435;
  g.add(grille);
  const fan = fanModel(0.12, { depth: 0.015 });
  fan.rotation.x = Math.PI / 2;
  fan.position.y = fanUp ? 0.033 : -0.033;
  g.add(fan);
  const label = box(0.1, 0.03, 0.0008, new THREE.MeshStandardMaterial({ color: 0x2b2d31, metalness: 0.3, roughness: 0.6 }));
  label.position.set(0, 0.0, 0.0755);
  g.add(label);
  return g;
}

/* ------------------------------------------------------------------ merge (subset of BufferGeometryUtils) */

function mergeGeometries(geos) {
  const out = new THREE.BufferGeometry();
  const attrs = ["position", "normal", "uv"];
  let total = 0;
  const nonIndexed = geos.map((g) => (g.index ? g.toNonIndexed() : g));
  nonIndexed.forEach((g) => (total += g.attributes.position.count));
  attrs.forEach((name) => {
    const size = nonIndexed[0].attributes[name]?.itemSize;
    if (!size) return;
    const arr = new Float32Array(total * size);
    let off = 0;
    nonIndexed.forEach((g) => {
      arr.set(g.attributes[name].array, off);
      off += g.attributes[name].array.length;
    });
    out.setAttribute(name, new THREE.BufferAttribute(arr, size));
  });
  return out;
}
