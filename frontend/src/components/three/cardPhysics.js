/**
 * Card layouts and collision for the glass-card scene. Pure three.js math, no rendering,
 * so it is unit-tested directly.
 *
 * Each card is an oriented box (OBB). Two cards collide when the separating-axis test
 * finds no gap on any of the 15 candidate axes (3 + 3 face normals, 9 edge cross products).
 * The fix is the physical one: push both apart along the axis of least penetration.
 * Every static layout is relaxed this way once, and the scene runs the same solver each
 * frame, so cards slide past each other mid-transition instead of passing through.
 */
import * as THREE from "three";

export const W = 1.6, H = 1, D = 0.08; // outer size of one glass slab, bevel included
export const KEPT = [0, 1, 2, 3]; // the shortlist, in rank order

export const pose = (x, y, z, rx = 0, ry = 0, rz = 0, s = 1) => ({
  p: new THREE.Vector3(x, y, z),
  q: new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz)),
  s,
});

/* ---------- separating-axis test ---------- */

const A = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
const B = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
const T = new THREE.Vector3(), L = new THREE.Vector3(), best = new THREE.Vector3();

function axes(q, out) {
  out[0].set(1, 0, 0).applyQuaternion(q);
  out[1].set(0, 1, 0).applyQuaternion(q);
  out[2].set(0, 0, 1).applyQuaternion(q);
}

/** Penetration of card b into card a: {depth, axis (a→b, shared vector)} or null if apart. */
export function penetration(a, b, margin = 0) {
  axes(a.q, A);
  axes(b.q, B);
  const ea = [(W / 2) * a.s + margin, (H / 2) * a.s + margin, (D / 2) * a.s + margin];
  const eb = [(W / 2) * b.s + margin, (H / 2) * b.s + margin, (D / 2) * b.s + margin];
  T.subVectors(b.p, a.p);
  let depth = Infinity;

  const separated = () => {
    const len = L.length();
    if (len < 1e-6) return false; // parallel edges give no axis
    L.multiplyScalar(1 / len);
    const ra = ea[0] * Math.abs(A[0].dot(L)) + ea[1] * Math.abs(A[1].dot(L)) + ea[2] * Math.abs(A[2].dot(L));
    const rb = eb[0] * Math.abs(B[0].dot(L)) + eb[1] * Math.abs(B[1].dot(L)) + eb[2] * Math.abs(B[2].dot(L));
    const d = T.dot(L);
    const overlap = ra + rb - Math.abs(d);
    if (overlap <= 0) return true;
    if (overlap < depth) {
      depth = overlap;
      best.copy(L).multiplyScalar(d < 0 ? -1 : 1);
    }
    return false;
  };

  for (let i = 0; i < 3; i++) if ((L.copy(A[i]), separated())) return null;
  for (let i = 0; i < 3; i++) if ((L.copy(B[i]), separated())) return null;
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) if ((L.crossVectors(A[i], B[j]), separated())) return null;
  return { depth, axis: best };
}

/** Pushes overlapping cards apart. Cards scaled to ~0 are ignored. Returns collisions found in the last pass. */
export function separate(bodies, { iterations = 1, margin = 0 } = {}) {
  let hits = 0;
  for (let it = 0; it < iterations; it++) {
    hits = 0;
    for (let i = 0; i < bodies.length; i++) {
      const a = bodies[i];
      if (a.s < 0.05) continue;
      for (let j = i + 1; j < bodies.length; j++) {
        const b = bodies[j];
        if (b.s < 0.05) continue;
        const hit = penetration(a, b, margin);
        if (!hit) continue;
        hits++;
        const push = hit.depth / 2 + 1e-4;
        a.p.addScaledVector(hit.axis, -push);
        b.p.addScaledVector(hit.axis, push);
      }
    }
    if (hits === 0) break;
  }
  return hits;
}

const relax = (layout, margin = 0.06) => (separate(layout, { iterations: 80, margin }), layout);

/* ---------- layouts ---------- */

// Hero: an orbital ring, tilted toward the viewer. Spacing leaves a clear gap between neighbours.
const RING = { radius: 2.2, scale: 0.5, center: new THREE.Vector3(0.5, 0.2, -1.2), tilt: new THREE.Quaternion().setFromEuler(new THREE.Euler(0.32, 0, -0.18)) };
const _q = new THREE.Quaternion(), _e = new THREE.Euler();

/** Writes the ring pose for time-angle `spin` into `out` (array of poses, reused every frame). */
export function ringLayout(n, spin, out = Array.from({ length: n }, () => pose(0, 0, 0))) {
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 + spin;
    out[i].p.set(Math.sin(a) * RING.radius, Math.sin(a * 3) * 0.16, Math.cos(a) * RING.radius)
      .applyQuaternion(RING.tilt).add(RING.center);
    out[i].q.copy(RING.tilt).multiply(_q.setFromEuler(_e.set(0, a, 0)));
    out[i].s = RING.scale;
  }
  return out;
}

// Wall slots (4 columns × 4 rows). The shortlist sits in the centre 2×2, so the match is never at an edge.
const WALL_SLOTS = [5, 6, 9, 10, 0, 1, 2, 3, 4, 7, 8, 11, 12, 13, 14];

export function storyLayouts(n) {
  const wall = [], shortlist = [], read = [], stack = [];
  for (let i = 0; i < n; i++) {
    const slot = WALL_SLOTS[i], col = slot % 4, row = Math.floor(slot / 4);
    wall.push(pose((col - 1.5) * 1.2, (1.5 - row) * 0.78, -0.8, 0, -0.06, 0, 0.66));

    const k = KEPT.indexOf(i);
    const gone = pose((col - 1.5) * 1.2, -6, -2.4, 1.4, 0, 0, 0.001);
    if (k >= 0) {
      shortlist.push(pose((k - 1.5) * 1.2, 0.15, 0.1, 0, -0.06, 0, 0.64));
      read.push(pose(((k % 2) - 0.5) * 1.75, k < 2 ? 0.58 : -0.58, 0.35, 0, ((k % 2) - 0.5) * -0.16, 0, 0.95));
      stack.push(pose(k * 0.16, 0.62 - k * 0.42, -k * 0.62, -0.32, -0.42, 0.04, k === 0 ? 1.12 : 1));
    } else {
      // Misses drop away in a staggered fall, tumbling slightly.
      shortlist.push(pose((col - 1.5) * 1.2, -3.4 - row * 0.7, -1.2 - row * 0.4, 1.1, (col - 1.5) * 0.12, 0, 0.6));
      read.push(gone);
      stack.push(gone);
    }
  }
  return [null, relax(wall), relax(shortlist), relax(read), relax(stack)]; // slot 0 is the live ring
}

export function fanLayout() {
  return relax([0, -1, 1, -2, 2].map((o) => pose(o * 0.66, -Math.abs(o) * 0.1, -Math.abs(o) * 0.34, 0.06, o * 0.1, -o * 0.08)));
}
