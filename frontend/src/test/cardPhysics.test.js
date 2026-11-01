import { describe, expect, it } from "vitest";
import { fanLayout, penetration, pose, ringLayout, separate, storyLayouts } from "../components/three/cardPhysics";

const collisions = (layout) => {
  let n = 0;
  for (let i = 0; i < layout.length; i++)
    for (let j = i + 1; j < layout.length; j++)
      if (layout[i].s > 0.05 && layout[j].s > 0.05 && penetration(layout[i], layout[j])) n++;
  return n;
};

describe("glass card physics", () => {
  it("detects overlap with the separating-axis test, including rotated cards", () => {
    expect(penetration(pose(0, 0, 0), pose(1.5, 0, 0))).not.toBeNull(); // 0.1 overlap along x
    expect(penetration(pose(0, 0, 0), pose(1.7, 0, 0))).toBeNull();
    expect(penetration(pose(0, 0, 0), pose(0, 0, 0.1))).toBeNull(); // parallel, stacked with a gap
    expect(penetration(pose(0, 0, 0), pose(0.3, 0, 0.3, 0, Math.PI / 2))).not.toBeNull(); // perpendicular, crossing
  });

  it("pushes overlapping cards apart along the shallowest axis", () => {
    const cards = [pose(0, 0, 0), pose(0, 0, 0.05)];
    expect(separate(cards, { iterations: 10 })).toBe(0);
    expect(cards[1].p.z - cards[0].p.z).toBeGreaterThanOrEqual(0.08 - 1e-3);
    expect(cards[0].p.x).toBeCloseTo(0);
  });

  it("every layout is collision-free", () => {
    storyLayouts(15).slice(1).forEach((layout) => expect(collisions(layout)).toBe(0));
    expect(collisions(fanLayout())).toBe(0);
    for (let spin = 0; spin < Math.PI * 2; spin += 0.37) expect(collisions(ringLayout(15, spin))).toBe(0);
  });
});
