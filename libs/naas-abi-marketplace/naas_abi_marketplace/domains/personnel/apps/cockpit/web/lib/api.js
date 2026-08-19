const API = "/api/personnel-cockpit";

/** @param {string} entityId */
export function createApi(entityId) {
  async function loadJson(rel) {
    const res = await fetch(`${API}/entities/${entityId}/${rel}`);
    if (!res.ok) throw new Error(`${rel} → ${res.status}`);
    return res.json();
  }

  async function loadGlobal(name) {
    const res = await fetch(`${API}/globals/${name}`);
    if (!res.ok) throw new Error(`globals/${name} → ${res.status}`);
    return res.json();
  }

  return { loadJson, loadGlobal };
}

export async function loadEntitiesRegistry(loadGlobal, defaults) {
  try {
    const data = await loadGlobal("entities.json");
    return (data.entities || []).filter(
      (entity) => (entity.entity_type || "organization") === "organization"
    );
  } catch {
    return [defaults];
  }
}

export function formatPublishedAt(value) {
  const dateTime = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(value);
  if (dateTime) {
    const [, y, mo, d, h, mi] = dateTime;
    const dt = new Date(Date.UTC(+y, +mo - 1, +d, +h, +mi));
    return `${dt.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })}, ${dt.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
    })} UTC`;
  }
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, y, mo, d] = dateOnly;
    const dt = new Date(Date.UTC(+y, +mo - 1, +d));
    return dt.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  return value;
}

export async function loadLatestPublishedAt(loadJson) {
  const manifest = await loadJson("manifest.json");
  let latest = manifest.data_version || null;
  const pages = manifest.datasets?.pages || {};
  for (const rels of Object.values(pages)) {
    for (const rel of rels) {
      try {
        const data = await loadJson(rel);
        const version = data.data_version;
        if (version && (!latest || version > latest)) latest = version;
      } catch {
        // ignore missing datasets
      }
    }
  }
  return latest;
}
