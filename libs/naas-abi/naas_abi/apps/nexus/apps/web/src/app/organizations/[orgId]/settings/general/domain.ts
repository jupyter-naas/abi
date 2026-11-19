export type OrgDomain = {
  domain: string;
  is_verified?: boolean;
};

/**
 * The organization's verified domains, in order and once each: the email domains it
 * proved it owns (Domains), whose people it recognizes. Never the address the site is
 * reached at, which is the platform's (Platform Settings › General).
 */
export function verifiedDomains(domains: OrgDomain[] | null | undefined): string[] {
  const seen = new Set<string>();
  for (const row of domains ?? []) {
    const domain = row.domain.trim().toLowerCase();
    if (row.is_verified && domain) seen.add(domain);
  }
  return [...seen].sort();
}

/** How many domains wait for their DNS record to be verified. */
export function pendingDomainCount(domains: OrgDomain[] | null | undefined): number {
  return (domains ?? []).filter((row) => row.domain.trim() && !row.is_verified).length;
}
