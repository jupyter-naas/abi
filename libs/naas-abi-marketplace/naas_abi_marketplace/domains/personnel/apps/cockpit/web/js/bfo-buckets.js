/** BFO 7-bucket palette — aligned with Nexus `bfo-buckets.ts`. */
export const BFO_BUCKETS = [
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000040",
    type: "Material Entity",
    label: "Who",
    color: "#3b82f6",
    border: "#2563eb",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000015",
    type: "Process",
    label: "What",
    color: "#22c55e",
    border: "#16a34a",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000008",
    type: "Temporal Region",
    label: "When",
    color: "#a855f7",
    border: "#9333ea",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000029",
    type: "Site",
    label: "Where",
    color: "#f97316",
    border: "#ea580c",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000019",
    type: "Quality",
    label: "How it is",
    color: "#ec4899",
    border: "#db2777",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000017",
    type: "Realizable",
    label: "Why",
    color: "#eab308",
    border: "#ca8a04",
  },
  {
    uri: "http://purl.obolibrary.org/obo/BFO_0000031",
    type: "GDC",
    label: "How we know",
    color: "#06b6d4",
    border: "#0891b2",
  },
  { uri: "http://purl.obolibrary.org/obo/BFO_0000001", type: "Entity", label: "Entity", color: "#6b7280", border: "#4b5563" },
  { uri: "", type: "Unknown", label: "Unknown", color: "#9ca3af", border: "#6b7280" },
];

export const BFO_SEVEN = BFO_BUCKETS.filter((b) =>
  ["Material Entity", "Process", "Temporal Region", "Site", "Quality", "Realizable", "GDC"].includes(
    b.type
  )
);

export const BFO_BY_TYPE = Object.fromEntries(BFO_BUCKETS.map((b) => [b.type, b]));

export function bfoColor(bucketType, { faded = false } = {}) {
  const def = BFO_BY_TYPE[bucketType] || BFO_BY_TYPE.Unknown;
  if (!faded) return def;
  return { ...def, color: fadeHex(def.color, 0.45), border: fadeHex(def.border, 0.45) };
}

function fadeHex(hex, amount) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const int = parseInt(m[1], 16);
  const mix = (c) => Math.round(c + (255 - c) * amount);
  const r = mix((int >> 16) & 255);
  const g = mix((int >> 8) & 255);
  const b = mix(int & 255);
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}
