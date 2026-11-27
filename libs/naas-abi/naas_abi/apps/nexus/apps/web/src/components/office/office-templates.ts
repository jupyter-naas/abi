import type { OfficeKindId, OfficeTemplatePreview } from './office-kinds';
import {
  resolveDocumentsTemplateId,
  sectionsHomeTemplateCards,
  sectionsTemplateMenuRows,
  templatePreviewColors as documentsPreviewColors,
  templateSectionLabel,
} from '@/lib/documents-templates';
import { DEFAULT_SHEETS_TEMPLATE_ID } from '@/lib/create-sheets-project';
import { DEFAULT_SLIDES_TEMPLATE_ID } from '@/lib/create-slides-project';
import {
  sheetsHomeTemplateCards,
  sheetsTemplateMenuRows,
  templatePreviewColors as sheetsPreviewColors,
  templateTabLabel,
} from '@/lib/sheets-templates';
import {
  slidesHomeTemplateCards,
  slidesTemplateMenuRows,
  templatePreviewColors as slidesPreviewColors,
  templateSlideLabel,
} from '@/lib/slides-templates';

/** Any kind's seed template, as the gallery and the sidebar read it. */
type Template = { id: string; name: string; source?: string; is_default?: boolean } & Partial<OfficeTemplatePreview>;

/** The seed catalog of one kind: its own template library, behind one shape. */
export type OfficeTemplateCatalog = {
  /** Gallery strip: catalog order, Blank where the kind pins it. */
  homeCards: (templates: Template[]) => Array<{ id: string; label: string; blank?: boolean }>;
  /** Sidebar New caret. */
  menuRows: (
    templates: Template[],
  ) => Array<{ kind: 'heading'; id: string; label: string } | { kind: 'template'; id: string; label: string; swatch?: string }>;
  previewColors: (templateId: string | null | undefined, templates: Template[]) => OfficeTemplatePreview;
  /** How a template's first part reads as a cover title. */
  partLabel: (part: { eyebrow: string; title: string }) => string;
  /** Seed a plain New click sends, or undefined to let the server decide. */
  defaultTemplateId: (templates: Template[]) => string | undefined;
};

export const OFFICE_TEMPLATE_CATALOGS: Record<OfficeKindId, OfficeTemplateCatalog> = {
  documents: {
    homeCards: sectionsHomeTemplateCards,
    menuRows: sectionsTemplateMenuRows,
    previewColors: documentsPreviewColors,
    partLabel: templateSectionLabel,
    defaultTemplateId: (templates) => (templates.length > 0 ? resolveDocumentsTemplateId(templates) : undefined),
  },
  sheets: {
    homeCards: sheetsHomeTemplateCards,
    menuRows: sheetsTemplateMenuRows,
    previewColors: sheetsPreviewColors,
    partLabel: templateTabLabel,
    defaultTemplateId: () => DEFAULT_SHEETS_TEMPLATE_ID,
  },
  slides: {
    homeCards: slidesHomeTemplateCards,
    menuRows: slidesTemplateMenuRows,
    previewColors: slidesPreviewColors,
    partLabel: templateSlideLabel,
    defaultTemplateId: () => DEFAULT_SLIDES_TEMPLATE_ID,
  },
};
