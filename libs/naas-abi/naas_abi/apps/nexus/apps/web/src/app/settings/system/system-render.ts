/** The System app's tests mount components with the shared helpers. */
import { badgeVariants } from '@/components/ui/badge';

export * from '@/lib/testing/mount';

const BADGE_VARIANTS = ['neutral', 'primary', 'success', 'info', 'destructive', 'warning', 'outline'] as const;

/** The kit badge variant an element is drawn with (how a test reads a status tone). */
export function badgeVariant(el: Element | null | undefined): string | null {
  if (!el) return null;
  const has = new Set(el.className.split(/\s+/));
  return BADGE_VARIANTS.find((v) => badgeVariants({ variant: v }).split(' ').every((c) => has.has(c))) ?? null;
}
