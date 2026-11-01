/**
 * Photoreal glass job cards. Physical transmission + iridescence, lit by RoomEnvironment
 * (a procedural studio, so no HDR download). Each card is a bevelled glass slab with the
 * job "printed" on its face. Cards never pass through each other: layouts are relaxed with
 * an oriented-box collision solver, and the same solver runs every frame (see cardPhysics.js).
 *
 * mode="story": layout and camera follow progress.current (0..1), tied to scroll on the landing page:
 *   orbital ring -> fetched wall -> shortlist (misses fall away) -> read grid -> ranked stack
 * mode="fan":   five cards fanned like a hand, the calm idle visual in the app.
 */
import { Component, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { H, W, fanLayout, ringLayout, separate, storyLayouts } from "./cardPhysics";

const JOBS = [
  ["MERN Stack Developer", "Nimbus Labs", 91],
  ["Frontend Engineer", "Kestrel", 84],
  ["AI Engineer", "Orbitly", 78],
  ["Full Stack Developer", "Fernwood", 72],
  ["React Developer", "Lumen Pay", 66],
  ["Python Developer", "Tidewater", 58],
  ["Node.js Engineer", "Quarry", 55],
  ["Data Analyst", "Marlowe", 41],
  ["DevOps Engineer", "Stackline", 37],
  ["iOS Developer", "Paperkite", 22],
  ["QA Engineer", "Brightfold", 30],
  ["Java Developer", "Osprey", 26],
  ["UI Designer", "Halcyon", 19],
  ["Site Reliability", "Northbeam", 33],
  ["Product Analyst", "Copperleaf", 28],
];
const PAPER = "#eef0f4";

/* ---------- geometry, materials, textures (built once) ---------- */

function cardGeometry() {
  const r = 0.09, w = W - 0.04, h = H - 0.04;
  const s = new THREE.Shape();
  s.moveTo(-w / 2 + r, -h / 2);
  s.lineTo(w / 2 - r, -h / 2);
  s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
  s.lineTo(w / 2, h / 2 - r);
  s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
  s.lineTo(-w / 2 + r, h / 2);
  s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
  s.lineTo(-w / 2, -h / 2 + r);
  s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
  const g = new THREE.ExtrudeGeometry(s, {
    depth: 0.035, bevelEnabled: true, bevelThickness: 0.022, bevelSize: 0.02, bevelSegments: 5, curveSegments: 12,
  });
  g.center();
  return g;
}

const glass = (overrides = {}) =>
  new THREE.MeshPhysicalMaterial({
    color: "#ffffff", transmission: 1, thickness: 0.45, roughness: 0.06, ior: 1.5,
    clearcoat: 1, clearcoatRoughness: 0.04, iridescence: 0.35, iridescenceIOR: 1.3,
    attenuationColor: "#dbe2ff", attenuationDistance: 3, specularIntensity: 1, envMapIntensity: 1.25,
    ...overrides,
  });

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.roundRect(x, y, w, h, r);
}

function labelTexture([title, company, score], highlight) {
  const c = document.createElement("canvas");
  c.width = 768;
  c.height = 480;
  const g = c.getContext("2d");
  const ink = highlight ? "#ffffff" : "#0b0e14";
  const sub = highlight ? "rgba(255,255,255,0.75)" : "#697186";
  const faint = highlight ? "rgba(255,255,255,0.22)" : "rgba(11,14,20,0.08)";
  const font = (w, px) => `${w} ${px}px Archivo, system-ui, sans-serif`;

  g.fillStyle = faint;
  roundRect(g, 52, 52, 76, 76, 20);
  g.fill();
  g.fillStyle = ink;
  g.font = font(700, 36);
  g.textAlign = "center";
  g.fillText(company[0], 90, 104);
  g.textAlign = "left";
  g.fillStyle = sub;
  g.font = font(600, 30);
  g.fillText(company, 150, 100);

  g.fillStyle = ink;
  let size = 54;
  do g.font = font(700, size--); while (g.measureText(title).width > 660 && size > 30);
  g.fillText(title, 52, 222);

  g.fillStyle = faint;
  [[52, 262, 300], [52, 300, 420], [52, 338, 240]].forEach(([x, y, w]) => { roundRect(g, x, y, w, 18, 9); g.fill(); });

  g.fillStyle = score >= 75 ? "#d9f57e" : score >= 55 ? "#e0e6ff" : "#e2e5ea";
  roundRect(g, 532, 368, 186, 70, 35);
  g.fill();
  g.fillStyle = "#0b0e14";
  g.font = font(700, 38);
  g.textAlign = "center";
  g.fillText(`${score}% fit`, 625, 416);

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

function shadowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  grad.addColorStop(0, "rgba(11,14,20,0.55)");
  grad.addColorStop(0.5, "rgba(11,14,20,0.18)");
  grad.addColorStop(1, "rgba(11,14,20,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}


/** Studio floor: a fine grid that fades out radially, for a clean technical look. */
function floorTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 1024;
  const g = c.getContext("2d");
  g.strokeStyle = "rgba(74,82,99,0.55)";
  g.lineWidth = 1.2;
  for (let x = 0; x <= 1024; x += 32) {
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 1024); g.stroke();
    g.beginPath(); g.moveTo(0, x); g.lineTo(1024, x); g.stroke();
  }
  g.globalCompositeOperation = "destination-in";
  const fade = g.createRadialGradient(512, 512, 0, 512, 512, 512);
  fade.addColorStop(0, "rgba(0,0,0,0.5)");
  fade.addColorStop(0.55, "rgba(0,0,0,0.18)");
  fade.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = fade;
  g.fillRect(0, 0, 1024, 1024);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 8;
  return tex;
}

const smooth = (t) => t * t * (3 - 2 * t);

// Camera per story stage [y, z]: settle in, pull back for the wall, lean in to read, rise over the stack.
const CAMERA = [
  [0.35, 7.8],
  [0.05, 8.7],
  [-0.1, 8.1],
  [0.3, 6.9],
  [1.05, 7.3],
];

/** Studio lighting from a procedural room (no HDR file), set once when the renderer is created. */
function setupStudio({ gl, scene }) {
  const pmrem = new THREE.PMREMGenerator(gl);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.035).texture;
  pmrem.dispose(); // the texture outlives the generator; the renderer frees it on unmount
  scene.background = new THREE.Color(PAPER);
  gl.toneMappingExposure = 1.05;
  gl.transmissionResolutionScale = 0.6; // lower-res refraction buffer: big GPU saving, invisible difference
}

function Cards({ mode, progress, reduced }) {
  const group = useRef(null);
  const cards = useRef([]);
  const blobs = useRef(null);
  const spin = useRef(0);
  const { size, viewport } = useThree();
  const wide = size.width >= 1024;
  const story = mode === "story";

  const jobs = story ? JOBS : JOBS.slice(0, 5);
  const assets = useMemo(() => {
    const geo = cardGeometry();
    const clear = glass();
    const signal = glass({ color: "#7d93ff", attenuationColor: "#2747f5", attenuationDistance: 0.55, iridescence: 0.5 });
    const labels = jobs.map((j, i) => labelTexture(j, i === 0));
    return { geo, clear, signal, labels, shadow: shadowTexture(), floor: floorTexture() };
  }, [jobs]);
  useEffect(
    () => () => {
      Object.values(assets).flat().forEach((a) => a.dispose?.());
    },
    [assets],
  );

  const layouts = useMemo(() => (story ? storyLayouts(jobs.length) : [fanLayout()]), [story, jobs.length]);
  const scratch = useRef(null); // per-frame working objects, allocated once

  useFrame((state, dt) => {
    const live = (scratch.current ??= {
      ring: ringLayout(jobs.length, 0),
      target: new THREE.Vector3(),
      rot: new THREE.Quaternion(),
      wobble: new THREE.Quaternion(),
      e: new THREE.Euler(),
      bodies: [],
    });
    const t = state.clock.elapsedTime;
    const float = reduced ? 0 : 1;
    const k = 1 - Math.exp(-(reduced ? 1000 : 4.5) * dt);

    // Which two layouts are we between? Slot 0 of the story is the live, slowly turning ring.
    let from = layouts[0], to = layouts[0], local = 0;
    if (story) {
      const p = THREE.MathUtils.clamp(progress?.current ?? 0, 0, 1);
      const steps = layouts.length - 1;
      const seg = Math.min(steps - 1, Math.floor(p * steps));
      local = smooth(p * steps - seg);
      spin.current += dt * 0.14 * float * (1 - Math.min(1, p * 4)); // the ring slows to a stop as it unrolls
      ringLayout(jobs.length, spin.current, live.ring);
      from = seg === 0 ? live.ring : layouts[seg];
      to = layouts[seg + 1];

      const [y0, z0] = CAMERA[seg], [y1, z1] = CAMERA[seg + 1];
      const cam = state.camera;
      cam.position.y = THREE.MathUtils.damp(cam.position.y, THREE.MathUtils.lerp(y0, y1, local), 3, dt);
      cam.position.z = THREE.MathUtils.damp(cam.position.z, THREE.MathUtils.lerp(z0, z1, local), 3, dt);
      cam.lookAt(0, 0, 0);
    }

    live.bodies.length = 0;
    cards.current.forEach((mesh, i) => {
      if (!mesh) return;
      const a = from[i], b = to[i];
      live.target.lerpVectors(a.p, b.p, local);
      live.target.y += Math.sin(t * 0.8 + i * 1.7) * 0.035 * float;
      live.rot.slerpQuaternions(a.q, b.q, local);
      live.e.set(Math.sin(t * 0.6 + i) * 0.02 * float, Math.cos(t * 0.5 + i) * 0.025 * float, 0);
      live.rot.multiply(live.wobble.setFromEuler(live.e));
      const s = THREE.MathUtils.lerp(a.s, b.s, local);

      mesh.position.lerp(live.target, k);
      mesh.quaternion.slerp(live.rot, k);
      mesh.scale.setScalar(THREE.MathUtils.lerp(mesh.scale.x, s, k));
      mesh.visible = mesh.scale.x > 0.01;
      live.bodies.push({ p: mesh.position, q: mesh.quaternion, s: mesh.scale.x });
    });
    // Contact: cards in flight push each other aside instead of passing through.
    separate(live.bodies, { iterations: 2, margin: 0.015 });

    if (blobs.current && !reduced) blobs.current.position.y = Math.sin(t * 0.4) * 0.12; // slow drift, never into the cards

    // Pointer parallax on the whole rig.
    if (group.current) {
      const g = group.current;
      g.rotation.y = THREE.MathUtils.damp(g.rotation.y, state.pointer.x * 0.16 * float, 3, dt);
      g.rotation.x = THREE.MathUtils.damp(g.rotation.x, -state.pointer.y * 0.08 * float, 3, dt);
    }
  });

  // Frame the rig: on wide screens the story sits right of the copy; on phones it shrinks and lifts.
  const offsetX = story && wide ? viewport.width * 0.18 : 0;
  const scale = story ? (wide ? 1 : Math.min(1, viewport.width / 5.4)) : Math.min(1.25, viewport.width / 4.2);
  const offsetY = story && !wide ? 1.35 : 0;
  // Coloured forms sit well behind every layout, so they show through the glass but never touch a card.
  const blobZ = story ? -5.2 : -2.8;

  return (
    <group position={[offsetX, offsetY, 0]} scale={scale}>
      <group ref={group}>
        {jobs.map((_, i) => (
          <group key={i} ref={(el) => (cards.current[i] = el)} position={[0, -5, -2]} scale={0.001}>
            <mesh geometry={assets.geo} material={i === 0 ? assets.signal : assets.clear} />
            <mesh position={[0, 0, 0.042]}>
              <planeGeometry args={[W - 0.06, H - 0.06]} />
              <meshBasicMaterial map={assets.labels[i]} transparent toneMapped={false} depthWrite={false} />
            </mesh>
          </group>
        ))}
      </group>

      {/* Backdrop forms: parked behind and around every layout, so they show through the glass but never sit on a card. */}
      <group position={[0, 0, blobZ]}>
        <group ref={blobs}>
          <mesh position={story ? [4.4, 2.9, 0] : [-2.9, 0.9, 0]}>
            <sphereGeometry args={[story ? 1.3 : 0.75, 64, 64]} />
            <meshPhysicalMaterial color="#2747f5" roughness={0.16} clearcoat={1} clearcoatRoughness={0.08} />
          </mesh>
          <mesh position={story ? [5.4, -1.3, -0.4] : [2.9, -0.5, -0.4]}>
            <sphereGeometry args={[story ? 0.62 : 0.5, 64, 64]} />
            <meshPhysicalMaterial color="#d9f57e" roughness={0.28} clearcoat={0.6} />
          </mesh>
        </group>
      </group>

      <mesh position={[0, -2.2, -1]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[18, 12]} />
        <meshBasicMaterial map={assets.floor} transparent depthWrite={false} />
      </mesh>
      <mesh position={[0, -2.18, -0.6]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[9, 4.5]} />
        <meshBasicMaterial map={assets.shadow} transparent opacity={0.3} depthWrite={false} />
      </mesh>
      <directionalLight position={[3, 5, 4]} intensity={1.4} />
    </group>
  );
}

class WebGLBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export default function GlassCards({ mode = "fan", progress, active = true, className = "" }) {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return (
    <div className={className} aria-hidden>
      <WebGLBoundary>
        <Canvas
          dpr={[1, 1.75]}
          camera={{ position: [0, 0.35, mode === "fan" ? 4.6 : 7.8], fov: 35 }}
          gl={{ antialias: true, powerPreference: "high-performance" }}
          frameloop={active ? (reduced ? "demand" : "always") : "never"}
          onCreated={setupStudio}
        >
          <Cards mode={mode} progress={progress} reduced={reduced} />
        </Canvas>
      </WebGLBoundary>
    </div>
  );
}
