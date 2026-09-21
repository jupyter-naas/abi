'use client';

import type { DictionaryFile } from '@/lib/ontology-file-filter';
import { OntologyMultiPicker } from './ontology-multi-picker';

export function OntologyFilePicker({ files, value, ...props }: {
  files: DictionaryFile[];
  value: string[];
  onToggle: (path: string) => void;
  onClear: () => void;
  loading: boolean;
  error: string | null;
}) {
  const label = !value.length ? 'All ontologies' : value.length === 1 ? value[0].split('/').pop()! : `${value.length} ontologies selected`;
  return <OntologyMultiPicker {...props} value={value} label={label} noun="ontologies" allLabel="All ontologies"
    items={files.map(file => ({value: file.path, label: file.path.split('/').pop()!, detail: file.moduleName, title: `${file.name}\n${file.path}`}))} />;
}
