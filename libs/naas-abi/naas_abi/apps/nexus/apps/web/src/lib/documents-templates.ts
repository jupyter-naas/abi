import { DEFAULT_DOCUMENTS_TEMPLATE_ID } from './create-documents-project';

export type SectionsTemplateSection = {
  index: number;
  id?: string | null;
  eyebrow: string;
  title: string;
};

export type SectionsTemplateAsset = {
  name: string;
  kind: string;
};

export type DocumentsSeedTemplate = {
  id: string;
  /** Namespace the id is prefixed with. Open set: sources are configured. */
  source?: string;
  /** Tree the seed was read from, for support questions. */
  origin?: string;
  name: string;
  description: string;
  preview_bg: string;
  preview_panel: string;
  preview_accent: string;
  preview_ink: string;
  sections: SectionsTemplateSection[];
  assets: SectionsTemplateAsset[];
  /** True on the row the server uses for a plain New Document click. */
  is_default?: boolean;
};

/**
 * Which source a seed came from, as the API reported it.
 *
 * Falls back to the prefix on the id, and to '' for a bare id, which is what
 * a document created before namespaces existed still carries. No default source
 * name here: the set of sources is configuration, and guessing one would put
 * a wrong label on a real template.
 */
export function templateNamespace(template: Pick<DocumentsSeedTemplate, 'id' | 'source'>): string {
  const explicit = (template.source || '').trim();
  if (explicit) return explicit;
  const cut = template.id.indexOf('/');
  return cut > 0 ? template.id.slice(0, cut) : '';
}

/**
 * Whether the catalog draws on more than one source.
 *
 * The picker uses this to decide whether to insert section headings (ABI,
 * then each configured source). It does not prefix each row with `source/`.
 */
export function templateNamespacesAreAmbiguous(
  templates: Pick<DocumentsSeedTemplate, 'id' | 'source'>[],
): boolean {
  const seen = new Set(templates.map(templateNamespace).filter(Boolean));
  return seen.size > 1;
}

const NAMESPACE_HEADINGS: Record<string, string> = {
  abi: 'ABI',
};

/** Human heading for a source slug. Unknown slugs are title-cased. */
export function templateNamespaceLabel(namespace: string): string {
  const key = namespace.trim().toLowerCase();
  if (!key) return '';
  const known = NAMESPACE_HEADINGS[key];
  if (known) return known;
  return key
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export type SectionsTemplateMenuRow =
  | { kind: 'heading'; id: string; label: string }
  | { kind: 'template'; id: string; label: string; swatch?: string };

export const SLIDES_HOME_BLANK_TEMPLATE_ID = DEFAULT_DOCUMENTS_TEMPLATE_ID;

/**
 * Seed a plain New Document click should send, given the live catalog.
 *
 * Prefers the row the API flagged. Falls back to ABI's own seed when that
 * id is still in the catalog, then to the first remaining row. Callers that
 * have no catalog yet should omit template_id and let the server decide.
 */
export function resolveDocumentsTemplateId(
  templates: Array<Pick<DocumentsSeedTemplate, 'id'> & { is_default?: boolean }>,
  explicit?: string | null,
): string {
  const wanted = (explicit || '').trim();
  if (wanted) return wanted;
  const flagged = templates.find((row) => row.is_default && (row.id || '').trim());
  if (flagged?.id) return flagged.id;
  const ids = templates.map((row) => (row.id || '').trim()).filter(Boolean);
  if (ids.includes(DEFAULT_DOCUMENTS_TEMPLATE_ID)) return DEFAULT_DOCUMENTS_TEMPLATE_ID;
  return ids[0] || DEFAULT_DOCUMENTS_TEMPLATE_ID;
}

export type SectionsHomeTemplateCard = {
  id: string;
  label: string;
  blank?: boolean;
};

/**
 * Home-page template strip: catalog order, with Blank pinned first only when
 * ABI's own seed is still in the payload. A deploy that hid that seed must
 * not keep advertising it.
 */
export function sectionsHomeTemplateCards(
  templates: Array<Pick<DocumentsSeedTemplate, 'id' | 'name'>>,
): SectionsHomeTemplateCard[] {
  if (templates.length === 0) {
    return [{ id: SLIDES_HOME_BLANK_TEMPLATE_ID, label: 'Blank', blank: true }];
  }

  const blankId = SLIDES_HOME_BLANK_TEMPLATE_ID;
  const blankStem = templateStem(blankId);
  const blankInCatalog = templates.some((template) => {
    const id = (template.id || '').trim();
    return id === blankId || templateStem(id) === blankStem;
  });

  const seen = new Set<string>();
  const cards: SectionsHomeTemplateCard[] = [];
  if (blankInCatalog) {
    cards.push({ id: blankId, label: 'Blank', blank: true });
    seen.add(blankId);
    seen.add(blankStem);
  }

  for (const template of templates) {
    const stem = templateStem(template.id);
    if (seen.has(template.id) || seen.has(stem)) continue;
    cards.push({ id: template.id, label: template.name });
    seen.add(template.id);
    seen.add(stem);
  }
  return cards;
}

/**
 * Rows for the New Documents picker: human names only.
 *
 * When more than one source is present, a heading is inserted ahead of each
 * group. Template ids stay on the row so create still sends the real catalog
 * id (`acme/industry-v2`).
 */
export function sectionsTemplateMenuRows(
  templates: Array<
    Pick<DocumentsSeedTemplate, 'id' | 'source' | 'name'> &
      Partial<Pick<DocumentsSeedTemplate, 'preview_accent' | 'preview_bg'>>
  >,
): SectionsTemplateMenuRow[] {
  if (templates.length === 0) return [];
  const showHeadings = templateNamespacesAreAmbiguous(templates);
  if (!showHeadings) {
    return templates.map((template) => ({
      kind: 'template' as const,
      id: template.id,
      label: template.name,
      swatch: template.preview_accent || template.preview_bg,
    }));
  }

  const groups = new Map<string, typeof templates>();
  for (const template of templates) {
    const ns = templateNamespace(template);
    const list = groups.get(ns) ?? [];
    list.push(template);
    if (!groups.has(ns)) groups.set(ns, list);
  }

  const rows: SectionsTemplateMenuRow[] = [];
  for (const [ns, items] of groups) {
    const heading = templateNamespaceLabel(ns);
    if (heading) {
      rows.push({ kind: 'heading', id: `heading:${ns}`, label: heading });
    }
    for (const template of items) {
      rows.push({
        kind: 'template',
        id: template.id,
        label: template.name,
        swatch: template.preview_accent || template.preview_bg,
      });
    }
  }
  return rows;
}

/** Sidebar line: eyebrow plus section title from the seed outline. */
export function templateSectionLabel(section: Pick<SectionsTemplateSection, 'eyebrow' | 'title'>): string {
  const eyebrow = (section.eyebrow || '').trim();
  const title = (section.title || '').trim();
  if (eyebrow && title && eyebrow.toLowerCase() !== title.toLowerCase()) {
    return `${eyebrow}: ${title}`;
  }
  return title || eyebrow || 'Untitled section';
}

export function templateAssetLabel(asset: Pick<SectionsTemplateAsset, 'name' | 'kind'>): string {
  const name = (asset.name || '').trim() || 'asset';
  return asset.kind === 'embedded' ? `${name} (embedded)` : name;
}

export type SectionsTemplatePreview = Pick<
  DocumentsSeedTemplate,
  'preview_bg' | 'preview_panel' | 'preview_accent' | 'preview_ink'
>;

export const DEFAULT_TEMPLATE_PREVIEW: SectionsTemplatePreview = {
  preview_bg: '#f4f4f4',
  preview_panel: '#ffffff',
  preview_accent: '#0072ce',
  preview_ink: '#2d2d2d',
};

function templateStem(id: string): string {
  const cut = id.lastIndexOf('/');
  return cut >= 0 ? id.slice(cut + 1) : id;
}

/** Catalog preview colors for a project template_id, or the seed defaults. */
export function templatePreviewColors(
  templateId: string | null | undefined,
  templates: Array<Pick<DocumentsSeedTemplate, 'id'> & Partial<SectionsTemplatePreview>>,
): SectionsTemplatePreview {
  const wanted = (templateId || '').trim();
  const row = wanted
    ? templates.find((item) => {
        const id = (item.id || '').trim();
        return id === wanted || templateStem(id) === wanted || templateStem(id) === templateStem(wanted);
      })
    : undefined;
  return {
    preview_bg: row?.preview_bg || DEFAULT_TEMPLATE_PREVIEW.preview_bg,
    preview_panel: row?.preview_panel || DEFAULT_TEMPLATE_PREVIEW.preview_panel,
    preview_accent: row?.preview_accent || DEFAULT_TEMPLATE_PREVIEW.preview_accent,
    preview_ink: row?.preview_ink || DEFAULT_TEMPLATE_PREVIEW.preview_ink,
  };
}

/**
 * Catalog name for a project.json template_id.
 *
 * Returns null when the id is empty or not in the catalog. Never invents a
 * name and never falls back to Minimal Light.
 */
export function templateDisplayName(
  templateId: string | null | undefined,
  templates: Array<Pick<DocumentsSeedTemplate, 'id' | 'name'>>,
): string | null {
  const wanted = (templateId || '').trim();
  if (!wanted) return null;
  const row = templates.find((item) => {
    const id = (item.id || '').trim();
    return id === wanted || templateStem(id) === wanted || templateStem(id) === templateStem(wanted);
  });
  const name = (row?.name || '').trim();
  return name || null;
}
