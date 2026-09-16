import { describe, it, expect } from 'vitest';
import { PerspectiveCamera, Vector3 } from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { settleCameraPose } from './camera-pose';
import { focusDistance, PLANE_WIDTH, PLANE_DEPTH } from './architecture-model';

describe('face-on layer focus', () => {
  for (const y of [0, 3, 6, 9, 12]) {
    it(`settles upright and fits the plane at height ${y}`, () => {
      const camera = new PerspectiveCamera(40, 1000 / 700, 0.1, 250);
      const controls = new OrbitControls(camera);
      controls.enableDamping = true;
      const target = new Vector3(0, y, 0);
      const goal = new Vector3(0, y + focusDistance(1000, 700, false), 0.001);
      // The former transition stopped with this small error, leaving a diagonal view.
      camera.position.copy(goal).add(new Vector3(0.004, 0, 0));
      controls.target.copy(target); controls.update();
      settleCameraPose(camera, controls, goal, target);
      camera.updateMatrixWorld(true);
      const left = new Vector3(-PLANE_WIDTH / 2, y, 0).project(camera);
      const right = new Vector3(PLANE_WIDTH / 2, y, 0).project(camera);
      expect(left.y).toBeCloseTo(right.y, 8);
      expect(left.x).toBeLessThan(right.x);
      for (const x of [-PLANE_WIDTH / 2, PLANE_WIDTH / 2]) for (const z of [-PLANE_DEPTH / 2, PLANE_DEPTH / 2]) {
        const corner = new Vector3(x, y, z).project(camera);
        expect(Math.abs(corner.x)).toBeLessThan(1);
        expect(Math.abs(corner.y)).toBeLessThan(1);
      }
      expect(controls.enableDamping).toBe(true);
    });
  }
});
