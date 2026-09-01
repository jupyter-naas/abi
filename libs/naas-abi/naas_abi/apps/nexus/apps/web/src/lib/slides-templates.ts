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

export type SlidesTemplateFile = {
  name: string;
  kind: string;
};

export type SlidesSeedTemplate = {
  id: string;
  name: string;
  description: string;
  preview_bg: string;
  preview_panel: string;
  preview_accent: string;
  preview_ink: string;
  slides: SlidesTemplateSlide[];
  assets: SlidesTemplateAsset[];
  files: SlidesTemplateFile[];
};

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
