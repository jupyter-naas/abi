/** What a service view may customize. Everything is optional except identity. */
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import type { PreviewContext } from '../viewers/preview';

export type ServiceGroup = 'Storage' | 'Platform' | 'Streams & logs';

export const SERVICE_GROUPS: ServiceGroup[] = ['Storage', 'Platform', 'Streams & logs'];

export interface Noun {
  one: string;
  many: string;
}

/** An extra listing column after the name. */
export interface Column {
  id: string;
  label: string;
  /** A CSS grid track, e.g. ``"96px"`` or ``"minmax(120px, 0.6fr)"``. */
  width: string;
  align?: 'start' | 'end';
  render: (entry: ResourceEntry) => ReactNode;
}

/** How one depth of the tree is shown (0 = the service root). */
export interface Level {
  noun?: Noun;
  columns?: Column[];
  layout?: 'list' | 'cards';
  /** Card body for ``layout: 'cards'`` (under the title). */
  card?: (entry: ResourceEntry) => ReactNode;
  emptyTitle?: string;
  emptyText?: string;
  /** A banner above the entries (e.g. why this container is read-only). */
  notice?: ReactNode;
  /** A group label per entry; the list shows a separator when it changes (e.g. the day). */
  groupBy?: (entry: ResourceEntry) => string;
}

export interface EditorSpec {
  /** Monaco language for the value of ``id``. */
  language: (id: string, entry?: ResourceEntry) => string;
  /** Initial value of a new entry. */
  template?: (parent: string) => string;
  /** An error message when ``text`` cannot be saved, else ``null``. */
  validate?: (text: string) => string | null;
  namePlaceholder?: string;
  /** Checks a new entry's name; an error message or ``null``. */
  validateName?: (name: string) => string | null;
  allowUpload?: boolean;
  /** A short value: a single field (hidden while typing when ``secret``) instead of Monaco;
   * a function decides per entry (``undefined`` when creating). */
  compact?: boolean | ((entry?: ResourceEntry) => boolean);
  secret?: boolean;
}

export interface CreateProps {
  parent: string;
  busy: boolean;
  /** Writes one entry; resolves false when it failed (the error is already shown). */
  submit: (id: string, body: Blob | string) => Promise<boolean>;
  close: () => void;
}

export interface ServiceView {
  name: string;
  label: string;
  description: string;
  icon: LucideIcon;
  group: ServiceGroup;
  /** Nothing here can be changed (logs, registries): labelled as such in the header. */
  readOnly?: boolean;
  /** What the items are called ("key", "document"...). */
  noun: Noun;
  /** ``entries``: the loaded page, e.g. to derive columns from common keys. */
  level?: (depth: number, parent: string, entries?: ResourceEntry[]) => Level;
  /** False or a reason when nothing can be created at this depth (create stays possible elsewhere). */
  canCreate?: (depth: number, parent: string) => boolean | string;
  entryIcon?: (entry: ResourceEntry) => LucideIcon;
  /** What one entry is called ("folder", "collection"); defaults to ``noun`` for items. */
  nounFor?: (entry: ResourceEntry, depth: number) => Noun;
  /** The label shown for an entry when its name is an opaque id (e.g. a hash); the name stays in the id. */
  title?: (entry: ResourceEntry) => string | null;
  /** The line under a name; defaults to ``attributes.summary``. */
  summary?: (entry: ResourceEntry) => ReactNode;
  /** Small badges after a name. */
  badges?: (entry: ResourceEntry) => ReactNode;
  /** Quick facts at the top of the inspector. */
  facts?: (detail: ResourceDetail) => { label: string; value: ReactNode }[];
  /** A richer preview than the generic one; ``null`` falls back. */
  preview?: (detail: ResourceDetail, ctx: PreviewContext) => ReactNode | null;
  createLabel?: string;
  editor?: EditorSpec;
  /** A creation form replacing the editor (a composer, an upload zone...). */
  create?: (props: CreateProps) => ReactNode;
  /** Files dropped on the browser are written into the open container. */
  acceptsDrops?: boolean;
  /** The entry name for a dropped file (``null`` refuses it with ``dropHint``); defaults to the file name. */
  dropName?: (file: File) => string | null;
  dropHint?: string;
  /** Default inspector width in px for wide previews (tables, graphs), until the user resizes it. */
  inspectorWidth?: number;
  /** The verb for deleting here ("Evict"); defaults to "Delete". */
  deleteLabel?: string;
  /** What deleting ``entry`` does, in one or two sentences. */
  deleteWarning?: (entry: ResourceEntry) => string;
  /** How long a revealed value stays visible. */
  revealSeconds?: number;
}
