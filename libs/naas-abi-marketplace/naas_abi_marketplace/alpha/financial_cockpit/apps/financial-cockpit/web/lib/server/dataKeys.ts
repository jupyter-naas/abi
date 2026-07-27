const DEFAULT_R2_DATA_PREFIX = 'data';

export function getR2DataPrefix(): string {
  return process.env.R2_DATA_PREFIX ?? DEFAULT_R2_DATA_PREFIX;
}

/** Map a datastore-relative key to the R2 object key (e.g. entities/foo → data/entities/foo). */
export function toR2ObjectKey(relativeKey: string): string {
  const normalized = relativeKey.replace(/^\/+/, '');
  const prefix = getR2DataPrefix().replace(/\/+$/, '');
  return prefix ? `${prefix}/${normalized}` : normalized;
}

/** Inverse of toR2ObjectKey (e.g. data/entities/foo → entities/foo). */
export function fromR2ObjectKey(objectKey: string): string {
  const prefix = getR2DataPrefix().replace(/\/+$/, '');
  if (prefix && objectKey.startsWith(`${prefix}/`)) {
    return objectKey.slice(prefix.length + 1);
  }
  return objectKey;
}
