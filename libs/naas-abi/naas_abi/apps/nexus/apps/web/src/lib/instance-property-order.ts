/** Priority for instance DETAILS property rows. Lower rank is listed first. */
const PRIORITY: Array<[RegExp, number]> = [
  [/^(label|preflabel|preferredlabel|displayname)$/, 0],
  [/^(comment|description)$/, 1],
  [/^(has)?jobtitle$/, 2],
  [/^(has)?engagementtitle$/, 3],
  [/^(has)?(title|role)$/, 4],
];

const REMAINDER = PRIORITY.length;

function compactLocalName(value: string): string {
  const tail = value.split(/[#/]/).filter(Boolean).pop() || value;
  return tail.toLowerCase().replace(/[\s_-]+/g, '');
}

/** Rank a predicate from its URI or display label. Unmatched properties stay after the priority list. */
export function propertyPriority(uri: string, label = ''): number {
  const keys = [compactLocalName(uri), compactLocalName(label)].filter(Boolean);
  for (const [pattern, rank] of PRIORITY) {
    if (keys.some(key => pattern.test(key))) return rank;
  }
  return REMAINDER;
}

export function sortByPropertyPriority<T>(
  items: T[],
  key: (item: T) => { uri?: string; label?: string }
): T[] {
  return items
    .map((item, index) => {
      const { uri = '', label = '' } = key(item);
      return { item, index, rank: propertyPriority(uri, label) };
    })
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map(entry => entry.item);
}

/** Stable sort: label, comment, job/engagement title, then the original remaining order. */
export function sortInstanceProperties<T extends { predicate_uri: string; predicate_label?: string }>(
  rows: T[]
): T[] {
  return sortByPropertyPriority(rows, row => ({
    uri: row.predicate_uri,
    label: row.predicate_label,
  }));
}
