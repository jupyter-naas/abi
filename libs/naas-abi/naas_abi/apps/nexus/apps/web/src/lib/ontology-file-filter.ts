import type { DictionaryTerm } from './ontology-dictionary-tree';

export type DictionaryFile = {path: string; name: string; moduleName: string};
export function dictionaryFiles(current: string): string[] {
  return [...new Set(new URLSearchParams(current).getAll('dictionaryFile').filter(Boolean))];
}
export function dictionaryFilesRoute(current: string, paths: string[]) {
  const params = new URLSearchParams(current);
  params.delete('dictionaryFile');
  [...new Set(paths)].sort().forEach(path => params.append('dictionaryFile', path));
  return params;
}
/** File selections are OR-ed; term kind and text search are applied afterwards. */
export function filterTermsByFiles(terms: DictionaryTerm[], paths: string[]): DictionaryTerm[] {
  if (!paths.length) return terms;
  const selected = new Set(paths);
  return terms.filter(term => term.sources?.some(source => selected.has(source.path)));
}
