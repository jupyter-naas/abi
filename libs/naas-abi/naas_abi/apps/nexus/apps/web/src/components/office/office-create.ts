export type OfficeCreateKind = 'document' | 'deck';
export type OfficeCreatePhase = 'creating' | 'opening';

/** Immediate File → New target. Create work runs on this route, not the page you left. */
export function officeCreateHref(
  kind: OfficeCreateKind,
  workspaceId: string,
  templateId?: string,
): string {
  const surface = kind === 'document' ? 'documents' : 'slides';
  const base = `/workspace/${workspaceId}/${surface}/new`;
  const chosen = (templateId || '').trim();
  if (!chosen) return base;
  return `${base}?template=${encodeURIComponent(chosen)}`;
}

export function officeCreateTemplateId(
  search: { get: (key: string) => string | null } | null | undefined,
): string | undefined {
  const raw = (search?.get('template') || '').trim();
  return raw || undefined;
}

export function officeCreateStatus(
  kind: OfficeCreateKind,
  phase: OfficeCreatePhase,
): string {
  if (phase === 'creating') return 'Creating workspace…';
  return kind === 'document' ? 'Opening document…' : 'Opening presentation…';
}
