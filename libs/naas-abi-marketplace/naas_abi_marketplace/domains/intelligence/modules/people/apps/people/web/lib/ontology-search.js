/** Ranked search over the classes of the ontology graph: by name, id, property, definition. */

export const MAX_CLASS_RESULTS = 8;

function fold(text) {
  return String(text ?? "")
    .normalize("NFKD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** ``personnel:hasEmployeeRole`` → ``has employee role``; the prefix is dropped. */
function localWords(qname) {
  const local = String(qname ?? "").split(":").pop();
  return fold(local.replace(/_/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2"));
}

/** One searchable entry per class node: what it is called, and what it carries. */
export function classSearchEntry(node, detail) {
  const properties = [
    ...(detail?.datatype_properties || []),
    ...(detail?.object_properties_domain || []),
    ...(detail?.object_properties_range || []),
  ].map((item) => ({
    label: item.label || localWords(item.property),
    folded: `${fold(item.label)} ${localWords(item.property)}`,
  }));
  return {
    node,
    label: fold(node.label),
    // The prefix says which vocabulary a class is from. It is matched only when
    // typed in full, or "pers" would return every personnel: class.
    prefix: node.id.includes(":") ? fold(node.id.split(":")[0]) : "",
    local: localWords(node.id),
    definition: fold(detail?.definition || ""),
    properties,
  };
}

/**
 * Rank classes against a query. Every word must match somewhere; the name counts
 * most, then the local id, then a property, then the definition. A word that
 * is exactly a namespace prefix (``personnel``, ``abi``) keeps that namespace.
 */
export function searchClasses(entries, query) {
  const words = fold(query).split(/[^a-z0-9]+/).filter(Boolean);
  if (!words.length) return [];
  const results = [];
  for (const entry of entries) {
    let score = 0;
    let via = "";
    let matchedAll = true;
    for (const word of words) {
      let best = 0;
      if (entry.label.startsWith(word)) best = 8;
      else if (entry.prefix && entry.prefix === word) best = 7;
      else if (entry.label.split(/\s+/).some((part) => part.startsWith(word))) best = 6;
      else if (entry.label.includes(word)) best = 5;
      else if (entry.local.includes(word)) best = 4;
      else {
        const property = entry.properties.find((item) => item.folded.includes(word));
        if (property) {
          best = 2;
          via = via || property.label;
        } else if (entry.definition.includes(word)) best = 1;
      }
      if (!best) {
        matchedAll = false;
        break;
      }
      score += best;
    }
    if (matchedAll) results.push({ node: entry.node, score, via });
  }
  return results
    .sort(
      (a, b) =>
        b.score - a.score ||
        a.node.label.localeCompare(b.node.label, undefined, { sensitivity: "base" }),
    )
    .slice(0, MAX_CLASS_RESULTS);
}
