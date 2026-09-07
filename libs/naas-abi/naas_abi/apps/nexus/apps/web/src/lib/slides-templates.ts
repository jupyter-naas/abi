export type SlidesTemplateSlide = {
  index: number;
  id?: string | null;
  eyebrow: string;
  title: string;
};

export type SlidesTemplateAsset = {
  name: string;
  kind: string;
};

export type SlidesSeedTemplate = {
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
  slides: SlidesTemplateSlide[];
  assets: SlidesTemplateAsset[];
};

/**
 * Which source a seed came from, as the API reported it.
 *
 * Falls back to the prefix on the id, and to '' for a bare id, which is what
 * a deck created before namespaces existed still carries. No default source
 * name here: the set of sources is configuration, and guessing one would put
 * a wrong label on a real template.
 */
export function templateNamespace(template: Pick<SlidesSeedTemplate, 'id' | 'source'>): string {
  const explicit = (template.source || '').trim();
  if (explicit) return explicit;
  const cut = template.id.indexOf('/');
  return cut > 0 ? template.id.slice(0, cut) : '';
}

/**
 * Whether the catalog draws on more than one source.
 *
 * A prefix exists to disambiguate. On the install that configures nothing,
 * every row would read the same prefix, which tells the reader nothing and
 * spends picker width saying it.
 */
export function templateNamespacesAreAmbiguous(
  templates: Pick<SlidesSeedTemplate, 'id' | 'source'>[],
): boolean {
  const seen = new Set(templates.map(templateNamespace).filter(Boolean));
  return seen.size > 1;
}

/** Sidebar line: eyebrow plus section title from the seed outline. */
export function templateSlideLabel(slide: Pick<SlidesTemplateSlide, 'eyebrow' | 'title'>): string {
  const eyebrow = (slide.eyebrow || '').trim();
  const title = (slide.title || '').trim();
  if (eyebrow && title && eyebrow.toLowerCase() !== title.toLowerCase()) {
    return `${eyebrow}: ${title}`;
  }
  return title || eyebrow || 'Untitled slide';
}

export function templateAssetLabel(asset: Pick<SlidesTemplateAsset, 'name' | 'kind'>): string {
  const name = (asset.name || '').trim() || 'asset';
  return asset.kind === 'embedded' ? `${name} (embedded)` : name;
}
