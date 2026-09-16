'use client';

import { useEffect, useRef, useState } from 'react';
import { settleCameraPose } from './camera-pose';
import { LinkTooltip, type LinkHover } from './link-tooltip';
import { segmentDistance } from './graph-model';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { architecture, componentPosition, focusDistance, PLANE_DEPTH, PLANE_WIDTH } from './architecture-model';

type Props = {
  layer: string | null; component: string | null; expanded: boolean; dependencies: boolean;
  command: { type: 'focus' | 'in' | 'out'; sequence: number };
  onSelect: (layer: string, component?: string) => void;
};

export default function ArchitectureScene(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const latest = useRef(props);
  latest.current = props;
  const update = useRef<() => void>(() => {});
  const [hover, setHover] = useState<LinkHover>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const container = host.current;
    if (!container) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }); }
    catch { setError(true); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    // Read the effective theme, including organization and system preferences.
    function readPalette() {
      const style = getComputedStyle(container!);
      const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
      return {
        background: token('--background-hex', '#FCFCFC'),
        card: token('--card-hex', '#FFFFFF'),
        text: token('--foreground-hex', '#18181B'),
        muted: token('--muted-foreground-hex', '#71717A'),
        selected: token('--muted-bg-hex', '#EBEBEE'),
        border: token('--border-hex', '#E3E3E7'),
      };
    }
    let palette = readPalette();
    function layerColor(color: string) {
      const light = new THREE.Color(palette.background).getHSL({ h: 0, s: 0, l: 0 }).l > 0.5;
      return new THREE.Color(color).lerp(new THREE.Color(palette.text), light ? 0.55 : 0).getStyle();
    }
    renderer.setClearColor(palette.background);
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-label', 'Interactive ABI architecture. Use the layer and component buttons for keyboard navigation.');
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 250);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.08;
    controls.minDistance = 4; controls.maxDistance = 150;
    controls.maxPolarAngle = Math.PI * 0.85;
    const planes = new Map<string, THREE.Group>();
    const tiles = new Map<string, THREE.Group>();
    const clickable: THREE.Object3D[] = [];
    const textures: THREE.Texture[] = [];
    const redrawLabels: (() => void)[] = [];
    const lines = new THREE.Group(); scene.add(lines);
    const grid = new THREE.GridHelper(80, 40, palette.border, palette.border);
    grid.material.vertexColors = false;
    grid.material.color.set(palette.border);
    grid.position.y = -0.6; scene.add(grid);
    const boxGeo = new THREE.BoxGeometry(3.35, 0.16, 1.5);
    const edgeGeo = new THREE.EdgesGeometry(boxGeo);
    function label(text: string, detail: string, color: string) {
      const canvas = document.createElement('canvas'); canvas.width = 768; canvas.height = 256;
      const ctx = canvas.getContext('2d')!;
      const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
      function draw() {
        ctx.fillStyle = palette.card; ctx.fillRect(0, 0, 768, 256);
        ctx.fillStyle = layerColor(color); ctx.fillRect(24, 34, 7, 185);
        ctx.font = '500 37px sans-serif';
        let title = text;
        while (ctx.measureText(title).width > 680) title = title.slice(0, -2);
        if (title !== text) title += '…';
        ctx.fillStyle = palette.text; ctx.fillText(title, 52, 105);
        ctx.fillStyle = palette.muted; ctx.font = '28px monospace'; ctx.fillText(detail, 52, 171);
        texture.needsUpdate = true;
      }
      redrawLabels.push(draw); draw();
      textures.push(texture);
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(3.27, 1.42), new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide }));
      mesh.rotation.x = -Math.PI / 2; mesh.position.y = 0.09;
      return mesh;
    }
    function layerLabel(text: string, color: string) {
      // Match texture and plane aspect ratios so the title is never squeezed.
      const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 128;
      const ctx = canvas.getContext('2d')!;
      const texture = new THREE.CanvasTexture(canvas);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
      function draw() {
        ctx.fillStyle = palette.card; ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = layerColor(color); ctx.fillRect(24, 24, 6, 80);
        ctx.fillStyle = palette.text; ctx.font = '500 44px sans-serif';
        ctx.textBaseline = 'middle'; ctx.fillText(text, 52, 64);
        texture.needsUpdate = true;
      }
      redrawLabels.push(draw); draw(); textures.push(texture);
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 0.65), new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide }));
      mesh.rotation.x = -Math.PI / 2;
      return mesh;
    }
    architecture.layers.forEach((layer, index) => {
      const group = new THREE.Group(); group.position.y = (4 - index) * 3;
      planes.set(layer.id, group); scene.add(group);
      const geometry = new THREE.BoxGeometry(PLANE_WIDTH, 0.08, PLANE_DEPTH);
      const surface = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color: layer.color, transparent: true, opacity: 0.09, depthWrite: false }));
      surface.userData = { layer: layer.id }; clickable.push(surface); group.add(surface);
      group.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({ color: layer.color, transparent: true, opacity: 0.6 })));
      const components = architecture.components.filter(c => c.layer === layer.id);
      const title = layerLabel(`0${5 - index}  ${layer.label}`, layer.color);
      title.position.set(-3.1, 0.07, 5);
      title.userData = { layer: layer.id }; group.add(title); clickable.push(title);
      components.forEach((component, i) => {
        const tile = new THREE.Group(); const p = componentPosition(i, components.length, false);
        tile.position.set(p.x, 0.18, p.z); tile.userData = { index: i, count: components.length };
        const box = new THREE.Mesh(boxGeo, new THREE.MeshBasicMaterial({ color: palette.card }));
        box.userData = { layer: layer.id, component: component.id };
        const face = label(component.label, `${component.files} files · ${component.functions} functions`, layer.color);
        face.userData = box.userData;
        const outline = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: layer.color, transparent: true, opacity: 0.48 }));
        tile.add(box, face, outline); group.add(tile); tiles.set(component.id, tile); clickable.push(box, face);
      });
    });
    const cameraGoal = new THREE.Vector3(); const targetGoal = new THREE.Vector3();
    let flying = true; let lastCommand = -1;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function disposeLines() {
      setHover(null);
      for (const child of [...lines.children]) {
        const line = child as THREE.Line;
        line.geometry.dispose(); (line.material as THREE.Material).dispose(); lines.remove(child);
      }
    }
    function sync(forceFit = false) {
      const state = latest.current;
      planes.forEach((plane, id) => {
        plane.visible = !state.layer || state.layer === id;
        plane.scale.set(state.expanded ? 1.2 : 1, 1, state.expanded ? 1.2 : 1);
      });
      tiles.forEach((tile, id) => {
        // Tiles retain their dimensions while the plate expands around them.
        const scale = state.expanded ? 1 / 1.2 : 1;
        tile.scale.set(scale, 1, scale);
        tile.position.y = state.expanded ? 0.7 : 0.18;
        const outline = tile.children[2] as THREE.LineSegments;
        const mat = outline.material as THREE.LineBasicMaterial;
        mat.opacity = id === state.component ? 1 : 0.48;
        (tile.children[0] as THREE.Mesh<THREE.BoxGeometry, THREE.MeshBasicMaterial>).material.color.set(id === state.component ? palette.selected : palette.card);
      });
      scene.updateMatrixWorld(true); disposeLines();
      if (state.dependencies) architecture.edges.forEach(edge => {
        if (state.component && edge.source !== state.component && edge.target !== state.component) return;
        const from = tiles.get(edge.source)!; const to = tiles.get(edge.target)!;
        if (!from.parent?.visible || !to.parent?.visible) return;
        const start = from.getWorldPosition(new THREE.Vector3()); const end = to.getWorldPosition(new THREE.Vector3());
        start.y += 0.15; end.y += 0.15;
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([start, end]), new THREE.LineBasicMaterial({ color: state.component ? palette.text : palette.muted, transparent: true, opacity: state.component ? 0.7 : 0.18 }));
        line.userData.edge = edge;
        lines.add(line);
      });
      grid.visible = !state.layer;
      if (state.command.sequence !== lastCommand) {
        lastCommand = state.command.sequence;
        if (!forceFit && (state.command.type === 'in' || state.command.type === 'out')) {
          targetGoal.copy(controls.target);
          const offset = camera.position.clone().sub(controls.target);
          offset.setLength(THREE.MathUtils.clamp(offset.length() * (state.command.type === 'in' ? 0.8 : 1.25), 4, 150));
          cameraGoal.copy(targetGoal).add(offset);
        } else if (state.layer) {
          const y = planes.get(state.layer)!.position.y;
          const distance = focusDistance(container!.clientWidth, container!.clientHeight, state.expanded);
          targetGoal.set(0, y, 0);
          cameraGoal.set(0, y + distance, 0.001);
        } else {
          targetGoal.set(0, 6, 0);
          const distance = Math.max(30, 27 / camera.aspect);
          cameraGoal.copy(targetGoal).add(new THREE.Vector3(0.35, 1.25, 1).normalize().multiplyScalar(distance));
        }
        flying = true;
      }
    }
    function applyTheme() {
      palette = readPalette();
      renderer.setClearColor(palette.background);
      grid.material.color.set(palette.border);
      architecture.layers.forEach(layer => {
        const group = planes.get(layer.id)!;
        group.traverse(obj => {
          const material = (obj as THREE.Mesh).material;
          if (!material || Array.isArray(material)) return;
          if (material instanceof THREE.LineBasicMaterial || (material instanceof THREE.MeshBasicMaterial && material.transparent && !material.map)) material.color.set(layerColor(layer.color));
        });
      });
      redrawLabels.forEach(draw => draw());
      // Update materials without changing the camera, selection or decomposition.
      sync();
    }
    applyTheme();
    const themeObserver = new MutationObserver(applyTheme);
    for (let ancestor: HTMLElement | null = container; ancestor; ancestor = ancestor.parentElement) {
      themeObserver.observe(ancestor, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] });
    }
    update.current = sync;
    function resize() {
      const width = Math.max(1, container!.clientWidth); const height = Math.max(1, container!.clientHeight);
      renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix();
      lastCommand = -1; sync(true);
    }
    const observer = new ResizeObserver(resize); observer.observe(container);
    resize(); settleCameraPose(camera, controls, cameraGoal, targetGoal);
    const pointer = new THREE.Vector2(); const raycaster = new THREE.Raycaster();
    let down = { x: 0, y: 0 };
    function onDown(e: PointerEvent) { down = { x: e.clientX, y: e.clientY }; }
    function onUp(e: PointerEvent) {
      if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5 || e.button !== 0) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set((e.clientX - rect.left) / rect.width * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(clickable).find(h => h.object.parent?.visible && (h.object.parent?.parent === scene || h.object.parent?.parent?.visible));
      if (hit) latest.current.onSelect(hit.object.userData.layer, hit.object.userData.component);
    }
    function onMove(e: PointerEvent) {
      if (e.buttons) { setHover(null); return; }
      const rect = renderer.domElement.getBoundingClientRect();
      const x = e.clientX - rect.left, y = e.clientY - rect.top;
      let best = 9; let next: LinkHover = null;
      for (const object of lines.children) {
        const line = object as THREE.Line;
        const positions = line.geometry.getAttribute('position');
        const a = new THREE.Vector3().fromBufferAttribute(positions, 0).project(camera);
        const b = new THREE.Vector3().fromBufferAttribute(positions, 1).project(camera);
        if (a.z < -1 || a.z > 1 || b.z < -1 || b.z > 1) continue;
        const distance = segmentDistance(x, y, (a.x + 1) * rect.width / 2, (1 - a.y) * rect.height / 2, (b.x + 1) * rect.width / 2, (1 - b.y) * rect.height / 2);
        if (distance < best) { best = distance; next = { edge: line.userData.edge, x: Math.max(8, Math.min(x + 12, rect.width - 300)), y: Math.max(8, Math.min(y + 12, rect.height - 100)) }; }
      }
      setHover(next);
    }
    function clearHover() { setHover(null); }
    function stopFlight() { flying = false; clearHover(); }
    function contextLost(e: Event) { e.preventDefault(); setError(true); }
    controls.addEventListener('start', stopFlight);
    renderer.domElement.addEventListener('pointermove', onMove);
    renderer.domElement.addEventListener('pointerleave', clearHover);
    renderer.domElement.addEventListener('pointerdown', onDown);
    renderer.domElement.addEventListener('pointerup', onUp);
    renderer.domElement.addEventListener('webglcontextlost', contextLost);
    let frame = 0; let previous = performance.now();
    function animate(now: number) {
      frame = requestAnimationFrame(animate);
      const dt = Math.min((now - previous) / 1000, 0.1); previous = now;
      if (flying) {
        const alpha = reducedMotion ? 1 : 1 - Math.exp(-7 * dt);
        camera.position.lerp(cameraGoal, alpha); controls.target.lerp(targetGoal, alpha);
        camera.lookAt(controls.target);
        if (camera.position.distanceTo(cameraGoal) < 0.005 && controls.target.distanceTo(targetGoal) < 0.005) {
          settleCameraPose(camera, controls, cameraGoal, targetGoal);
          flying = false;
        }
      } else {
        controls.update();
      }
      renderer.render(scene, camera);
    }
    frame = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); themeObserver.disconnect(); controls.dispose(); update.current = () => {};
      renderer.domElement.removeEventListener('pointermove', onMove);
      renderer.domElement.removeEventListener('pointerleave', clearHover);
      renderer.domElement.removeEventListener('pointerdown', onDown); renderer.domElement.removeEventListener('pointerup', onUp);
      renderer.domElement.removeEventListener('webglcontextlost', contextLost);
      scene.traverse(obj => {
        const mesh = obj as THREE.Mesh;
        mesh.geometry?.dispose();
        if (mesh.material) (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach(m => m.dispose());
      });
      textures.forEach(texture => texture.dispose()); renderer.dispose(); renderer.domElement.remove();
    };
  }, []);

  useEffect(() => { update.current(); }, [props.layer, props.component, props.expanded, props.dependencies, props.command]);
  return <div className="infrastructure-scene" ref={host}><LinkTooltip hover={hover} />{error && <div className="infrastructure-scene-error" role="status">3D rendering is unavailable. You can still explore every layer, component and dependency in the panels.</div>}</div>;
}
