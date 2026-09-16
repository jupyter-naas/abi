import type { PerspectiveCamera, Vector3 } from 'three';
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

/** Flush orbit inertia, then settle exactly: tiny X errors near the pole cause large roll. */
export function settleCameraPose(camera: PerspectiveCamera, controls: OrbitControls, position: Vector3, target: Vector3) {
  const damping = controls.enableDamping;
  controls.enableDamping = false;
  controls.update();
  camera.position.copy(position);
  controls.target.copy(target);
  camera.lookAt(target);
  controls.update();
  controls.enableDamping = damping;
}
