'use client';

import { useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { policyDriven, policyOfSearch, withPolicy } from './settings-policy';

/**
 * A link inside a workspace's Settings that keeps the policy picked in the column (`?policy=`):
 * to a page the policy drives (Access › Features, Core Services, Modules and every page under
 * Features, their instance pages included), it carries it; to any other page, it is left as is.
 * Without it, a Back link or a row would land on "<W> access" and the next switch would write the
 * workspace's offer instead of the policy picked.
 */
export function usePolicyHref(): (href: string) => string {
  const policy = policyOfSearch(useSearchParams());
  return useCallback((href: string) => (policy && policyDriven(href) ? withPolicy(href, policy) : href), [policy]);
}
