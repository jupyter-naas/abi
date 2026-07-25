'use client';

import { useTenant } from '@/contexts/tenant-context';
import { resolveTypographyPilot } from '@/lib/typography-pilot';

export function useTypographyPilot(): boolean {
  const tenant = useTenant();
  return resolveTypographyPilot(tenant);
}
