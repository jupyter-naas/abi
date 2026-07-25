const ZEN_HOSTS = new Set(['zen.naas.ai', 'nexus.zen.naas.ai']);

export interface TypographyPilotTenant {
  tab_title?: string;
  typography_pilot?: boolean | null;
}

/** True when Inter typography pilot should apply (zen.naas.ai deployment). */
export function resolveTypographyPilot(tenant: TypographyPilotTenant): boolean {
  if (tenant.typography_pilot === true) return true;
  if (typeof window !== 'undefined' && ZEN_HOSTS.has(window.location.hostname)) return true;
  if (process.env.NEXT_PUBLIC_TYPOGRAPHY_PILOT === 'true') return true;
  return tenant.tab_title === 'Zen';
}

export function microTextClass(pilot: boolean): string {
  return pilot ? 'text-micro' : 'text-[10px]';
}

export function captionTextClass(pilot: boolean): string {
  return pilot ? 'text-caption' : 'text-[11px]';
}

/** Bottom nav labels on mobile — micro is illegible on 360px screens. */
export function mobileNavLabelClass(pilot: boolean): string {
  return pilot ? 'text-xs' : microTextClass(pilot);
}

/** Chat panel section headers (AGENTS, RECENT, …) on mobile. */
export function mobileSectionLabelClass(pilot: boolean): string {
  return pilot ? 'text-xs' : captionTextClass(pilot);
}

/** List row primary text on mobile chat panel. */
export function mobileListRowTextClass(pilot: boolean): string {
  return pilot ? 'text-sm leading-snug' : 'text-sm';
}
