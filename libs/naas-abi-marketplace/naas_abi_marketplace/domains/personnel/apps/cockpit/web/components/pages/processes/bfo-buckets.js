/** BFO palette populated from config.yaml before the graph mounts. */
export const BFO_BUCKETS = [];
export const BFO_SEVEN = [];
export const BFO_BY_TYPE = {};

export function configureBfoBuckets(configured) {
  if (!Array.isArray(configured) || !configured.length) return;
  BFO_BUCKETS.splice(0, BFO_BUCKETS.length, ...configured);
  BFO_SEVEN.splice(
    0,
    BFO_SEVEN.length,
    ...BFO_BUCKETS.filter((bucket) =>
      ["Material Entity", "Process", "Temporal Region", "Site", "Quality", "Realizable", "GDC"].includes(
        bucket.type
      )
    )
  );
  for (const key of Object.keys(BFO_BY_TYPE)) delete BFO_BY_TYPE[key];
  Object.assign(
    BFO_BY_TYPE,
    Object.fromEntries(BFO_BUCKETS.map((bucket) => [bucket.type, bucket]))
  );
}

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
