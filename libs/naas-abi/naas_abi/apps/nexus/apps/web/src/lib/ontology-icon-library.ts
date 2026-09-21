import { ONTOLOGY_TOPIC_GLYPHS } from './ontology-topic-glyphs';
import { ICON_LIBRARY_PATH } from './ontology-icon-library-version';
import type { OntologyTopicSubject } from './ontology-topic-icon';

export const ICON_PREFIX = 'material-symbols-light:';
export const SUGGESTED_ICONS = Object.keys(ONTOLOGY_TOPIC_GLYPHS);
export type IconTarget = { kind: string; resource_id: string };
export function iconTarget(subject: OntologyTopicSubject): IconTarget | null {
  if (subject.id && subject.type) return { kind: subject.type, resource_id: subject.id };
  return subject.path ? { kind: 'file', resource_id: subject.path } : null;
}
export const iconTargetKey = (target: IconTarget) => JSON.stringify([target.kind, target.resource_id]);
export const iconLabel = (name: string) => name.replaceAll('-', ' ');
export function searchIconNames(names: string[], query: string) {
  const words = query.toLowerCase().trim().split(/[\s_-]+/).filter(Boolean);
  return words.length ? names.filter(name => words.every(word => name.includes(word))) : names;
}
export function validIconPaths(value: unknown): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.length <= 64 && value.every(path =>
    typeof path === 'string' && path.length <= 60000 && /^[MmLlHhVvCcSsQqTtAaZz0-9eE+.,\s-]+$/.test(path));
}
export function pickerPosition(rect: { left: number; bottom: number }, viewport: { width: number; height: number }) {
  const width = Math.min(360, Math.max(0, viewport.width - 24));
  const maxHeight = Math.min(480, Math.max(0, viewport.height - 24));
  return { width, maxHeight, left: Math.max(12, Math.min(rect.left, viewport.width - width - 12)),
    top: Math.max(12, Math.min(rect.bottom + 8, viewport.height - maxHeight - 12)) };
}

type Catalog = { names: string[]; chunkSize: number; index: Map<string, number> };
let catalogPromise: Promise<Catalog> | null = null;
const paths = new Map<string, readonly string[]>(Object.entries(ONTOLOGY_TOPIC_GLYPHS));
const batches = new Map<number, Promise<void>>();
export const cachedIconPaths = (name: string) => paths.get(name);
export function loadIconCatalog(): Promise<Catalog> {
  if (!catalogPromise) catalogPromise = (async () => {
    const response = await fetch(`${ICON_LIBRARY_PATH}/index.json`);
    if (!response.ok) throw new Error('Could not load the icon library.');
    const data: { names?: unknown; chunkSize?: unknown } = await response.json();
    if (!Array.isArray(data.names) || data.names.length > 50000 || data.names.some(name => typeof name !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) || data.chunkSize !== 128) throw new Error('The icon library could not be read.');
    const names = data.names as string[];
    return { names, chunkSize: 128, index: new Map(names.map((name, index) => [name, Math.floor(index / 128)])) };
  })().catch(error => { catalogPromise = null; throw error; });
  return catalogPromise;
}
export async function loadIconPaths(names: string[]) {
  const missing = [...new Set(names)].filter(name => !paths.has(name));
  if (!missing.length) return;
  const catalog = await loadIconCatalog();
  if (missing.some(name => !catalog.index.has(name))) throw new Error('This icon is not available in the library.');
  const ids = [...new Set(missing.map(name => catalog.index.get(name)!))];
  await Promise.all(ids.map(id => {
    let pending = batches.get(id);
    if (!pending) {
      pending = (async () => {
        const response = await fetch(`${ICON_LIBRARY_PATH}/${id}.json`);
        if (!response.ok) throw new Error('Could not load these icons.');
        const data: unknown = await response.json();
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('These icons could not be read.');
        const expected = catalog.names.slice(id * catalog.chunkSize, (id + 1) * catalog.chunkSize);
        for (const name of expected) if (!validIconPaths((data as Record<string, unknown>)[name])) throw new Error('These icons could not be read.');
        for (const name of expected) paths.set(name, (data as Record<string, string[]>)[name]);
      })().catch(error => { batches.delete(id); throw error; });
      batches.set(id, pending);
    }
    return pending;
  }));
}
