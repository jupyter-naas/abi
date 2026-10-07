/**
 * The "Graph" view of a search: the people found and the organizations and
 * schools that tie them (GET <api>/search/network), drawn as an SVG network.
 * No dependencies: a small force layout, then plain SVG with wheel zoom and
 * drag to pan.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const PERSON_RADIUS = 18;

function initials(name) {
  return String(name || "")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/**
 * Positions for every node, ``{ id: { x, y } }``. Deterministic: the same
 * network always lands the same way, so a reload does not reshuffle it.
 * Fruchterman-Reingold: every pair repels, every edge pulls, and the step
 * shrinks as the layout cools.
 */
export function layoutNetwork(nodes, edges, { size = 1000, iterations = 300 } = {}) {
  const count = nodes.length;
  if (!count) return {};
  const index = new Map(nodes.map((node, i) => [node.id, i]));
  const ideal = Math.sqrt((size * size) / count);
  const x = new Float64Array(count);
  const y = new Float64Array(count);
  // Start on a circle (people outside, organizations inside) rather than at random.
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / count;
    const radius = (node.kind === "person" ? 0.45 : 0.2) * size;
    x[i] = size / 2 + radius * Math.cos(angle);
    y[i] = size / 2 + radius * Math.sin(angle);
  });
  const links = edges
    .map((edge) => [index.get(edge.source), index.get(edge.target)])
    .filter(([a, b]) => a !== undefined && b !== undefined);

  const dx = new Float64Array(count);
  const dy = new Float64Array(count);
  let temperature = size / 10;
  const cooling = temperature / (iterations + 1);
  for (let step = 0; step < iterations; step += 1) {
    dx.fill(0);
    dy.fill(0);
    for (let i = 0; i < count; i += 1) {
      for (let j = i + 1; j < count; j += 1) {
        let ox = x[i] - x[j];
        let oy = y[i] - y[j];
        let distance = Math.hypot(ox, oy);
        if (distance < 0.01) {
          // Two nodes on the same spot: part them along a fixed direction.
          ox = 0.01 * ((i % 7) - 3 || 1);
          oy = 0.01 * ((j % 5) - 2 || 1);
          distance = Math.hypot(ox, oy);
        }
        const push = (ideal * ideal) / distance;
        dx[i] += (ox / distance) * push;
        dy[i] += (oy / distance) * push;
        dx[j] -= (ox / distance) * push;
        dy[j] -= (oy / distance) * push;
      }
    }
    for (const [a, b] of links) {
      const ox = x[a] - x[b];
      const oy = y[a] - y[b];
      const distance = Math.hypot(ox, oy) || 0.01;
      const pull = (distance * distance) / ideal;
      dx[a] -= (ox / distance) * pull;
      dy[a] -= (oy / distance) * pull;
      dx[b] += (ox / distance) * pull;
      dy[b] += (oy / distance) * pull;
    }
    for (let i = 0; i < count; i += 1) {
      const length = Math.hypot(dx[i], dy[i]);
      if (length > 0) {
        const move = Math.min(length, temperature);
        x[i] += (dx[i] / length) * move;
        y[i] += (dy[i] / length) * move;
      }
      // Gravity keeps islands (people tied to nobody shown) from drifting off.
      x[i] += (size / 2 - x[i]) * 0.01;
      y[i] += (size / 2 - y[i]) * 0.01;
    }
    temperature = Math.max(temperature - cooling, 0.5);
  }
  return Object.fromEntries(nodes.map((node, i) => [node.id, { x: x[i], y: y[i] }]));
}

/** Side of an organization's square: bigger when it ties more of the people shown. */
export function organizationSize(people = 1) {
  return Math.min(56, 18 + 6 * Math.sqrt(Math.max(1, people)));
}

function svg(tag, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value !== undefined && value !== null) element.setAttribute(name, String(value));
  }
  return element;
}

/**
 * Draw ``payload`` (nodes and edges) into ``host``. ``personHref(slug)`` is
 * where a person's node leads.
 */
export function mountPeopleNetwork(host, payload, { personHref }) {
  const nodes = payload.nodes || [];
  const edges = payload.edges || [];
  if (!nodes.length) {
    host.innerHTML = `<p class="stats">Nobody to draw.</p>`;
    return;
  }
  const positions = layoutNetwork(nodes, edges);
  const points = Object.values(positions);
  const pad = 80;
  const minX = Math.min(...points.map((p) => p.x)) - pad;
  const minY = Math.min(...points.map((p) => p.y)) - pad;
  const width = Math.max(...points.map((p) => p.x)) + pad - minX;
  const height = Math.max(...points.map((p) => p.y)) + pad - minY;
  let view = { x: minX, y: minY, width, height };

  host.innerHTML = `
    <div class="network-legend" aria-hidden="true">
      <span><i class="legend-line legend-worked_for"></i>Worked for</span>
      <span><i class="legend-line legend-client_of"></i>Client</span>
      <span><i class="legend-line legend-studied_at"></i>Studied at</span>
      <span><i class="legend-box legend-organization"></i>Organization</span>
      <span><i class="legend-box legend-school"></i>School</span>
    </div>`;
  const root = svg("svg", {
    class: "people-network",
    role: "img",
    "aria-label": `Network of ${payload.nodes.filter((n) => n.kind === "person").length} people`,
  });
  const setView = () =>
    root.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`);
  setView();

  const defs = svg("defs");
  root.appendChild(defs);
  const edgeLayer = svg("g", { class: "network-edges" });
  const nodeLayer = svg("g", { class: "network-nodes" });
  root.append(edgeLayer, nodeLayer);

  for (const edge of edges) {
    const a = positions[edge.source];
    const b = positions[edge.target];
    if (!a || !b) continue;
    edgeLayer.appendChild(
      svg("line", {
        class: `network-edge network-edge-${edge.relation}`,
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
      }),
    );
  }

  nodes.forEach((node, i) => {
    const { x, y } = positions[node.id];
    if (node.kind === "person") {
      const link = svg("a", { href: personHref(node.slug), class: "network-person" });
      const title = svg("title");
      title.textContent = node.headline ? `${node.label} — ${node.headline}` : node.label;
      link.appendChild(title);
      link.appendChild(svg("circle", { cx: x, cy: y, r: PERSON_RADIUS, class: "network-person-disc" }));
      const text = svg("text", { x, y: y + 4, class: "network-person-initials", "text-anchor": "middle" });
      text.textContent = initials(node.label);
      link.appendChild(text);
      if (node.photo_url) {
        const clipId = `network-clip-${i}`;
        const clip = svg("clipPath", { id: clipId });
        clip.appendChild(svg("circle", { cx: x, cy: y, r: PERSON_RADIUS }));
        defs.appendChild(clip);
        const image = svg("image", {
          href: node.photo_url,
          x: x - PERSON_RADIUS,
          y: y - PERSON_RADIUS,
          width: PERSON_RADIUS * 2,
          height: PERSON_RADIUS * 2,
          "clip-path": `url(#${clipId})`,
          preserveAspectRatio: "xMidYMid slice",
        });
        // A portrait that fails leaves the initials underneath.
        image.addEventListener("error", () => image.remove());
        link.appendChild(image);
      }
      link.appendChild(svg("circle", { cx: x, cy: y, r: PERSON_RADIUS, class: "network-person-ring" }));
      const label = svg("text", {
        x,
        y: y + PERSON_RADIUS + 14,
        class: "network-label",
        "text-anchor": "middle",
      });
      label.textContent = node.label;
      link.appendChild(label);
      nodeLayer.appendChild(link);
      return;
    }
    const side = organizationSize(node.people);
    const group = svg("g", { class: `network-org network-${node.kind}` });
    const title = svg("title");
    title.textContent = `${node.label} · ${node.people} ${node.people === 1 ? "person" : "people"}`;
    group.appendChild(title);
    group.appendChild(svg("rect", { x: x - side / 2, y: y - side / 2, width: side, height: side }));
    const label = svg("text", {
      x,
      y: y + side / 2 + 14,
      class: "network-label network-org-label",
      "text-anchor": "middle",
    });
    label.textContent = node.label;
    group.appendChild(label);
    nodeLayer.appendChild(group);
  });

  // Wheel zooms round the pointer; dragging the background pans.
  root.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const box = root.getBoundingClientRect();
      const fx = (event.clientX - box.left) / box.width;
      const fy = (event.clientY - box.top) / box.height;
      const factor = Math.exp(Math.sign(event.deltaY) * 0.12);
      const nextWidth = Math.min(Math.max(view.width * factor, width / 8), width * 3);
      const nextHeight = (nextWidth / view.width) * view.height;
      view = {
        x: view.x + (view.width - nextWidth) * fx,
        y: view.y + (view.height - nextHeight) * fy,
        width: nextWidth,
        height: nextHeight,
      };
      setView();
    },
    { passive: false },
  );
  let drag = null;
  root.addEventListener("pointerdown", (event) => {
    if (event.target.closest("a")) return;
    drag = { x: event.clientX, y: event.clientY, view: { ...view } };
    root.setPointerCapture(event.pointerId);
    root.classList.add("is-panning");
  });
  root.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const box = root.getBoundingClientRect();
    const scale = view.width / box.width;
    view = {
      ...view,
      x: drag.view.x - (event.clientX - drag.x) * scale,
      y: drag.view.y - (event.clientY - drag.y) * scale,
    };
    setView();
  });
  const stop = () => {
    drag = null;
    root.classList.remove("is-panning");
  };
  root.addEventListener("pointerup", stop);
  root.addEventListener("pointercancel", stop);

  host.appendChild(root);
  const caption = document.createElement("p");
  caption.className = "network-caption";
  caption.textContent = "Scroll to zoom, drag to move. Select a person to open their profile.";
  host.appendChild(caption);
}
