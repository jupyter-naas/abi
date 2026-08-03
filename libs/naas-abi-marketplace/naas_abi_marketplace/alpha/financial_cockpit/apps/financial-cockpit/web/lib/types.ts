export type PageId =
  | 'dashboard'
  | 'cash-position'
  | 'treasury'
  | 'financing'
  | 'customer-invoices'
  | 'supplier-invoices'
  | 'expenses'
  | 'procurement'
  | 'pnl'
  | 'balance-sheet'
  | 'cash-flow'
  | 'financial-ratios'
  | 'pnl-budget'
  | 'forecast'
  | 'scenario-analysis'
  | 'cost-centers'
  | 'general-ledger'
  | 'journal-entries'
  | 'fixed-assets'
  | 'financial-close'
  | 'theme';

export type EntityId = string;

/**
 * `owner` is the top role: full access everywhere, hand-maintained in
 * config.yaml, and it can never be edited or removed from the app. `admin` also
 * grants full access to every app but is datastore-managed — owners and admins
 * can create/edit/remove admins, but no one can touch an owner.
 */
export type UserRole = 'owner' | 'admin';

export type EntityType = 'organization' | 'consolidation';

export type SiteConfig = {
  site_id: string;
  name: string;
};

export type CompanyConfig = {
  organization_slug: string;
  display_name: string;
};

export type EntityConfig = {
  entity_id: EntityId;
  display_name: string;
  url_slug: string;
  entity_type?: EntityType;
  sites?: SiteConfig[];
  companies?: CompanyConfig[];
};

/** Banner styles: `info` renders blue, `warning` renders yellow/amber. */
export type BannerType = 'info' | 'warning';

/** Optional notice shown below the top bar on a page, configured in config.yaml. */
export type PageBannerConfig = {
  type: BannerType;
  text: string;
  enabled: boolean;
};

export type PageConfig = {
  page_id: PageId;
  label?: string;
  enabled: boolean;
  banner?: PageBannerConfig;
};

/** Sidebar nav group — collapsible header with nested pages. */
export type NavSectionConfig = {
  section_id: string;
  label: string;
  page_ids: PageId[];
  /**
   * Section that has no subpages: the rail links straight to its single page
   * instead of opening the secondary panel. Keeps the entry in section order.
   */
  direct?: boolean;
};

export type UserConfig = {
  /** Stable opaque UUID — the session identity. */
  user_id: string;
  name: string;
  email: string;
  role?: UserRole;
  allowed_entities?: EntityId[];
  allowed_pages?: PageId[];
  /** Perimeter the user lands on at sign-in (must be within allowed_entities). */
  default_entity_id?: EntityId | null;
};

/** Brand identity (document metadata + logo/favicon assets). */
export type BrandConfig = {
  name: string;
  description?: string;
  logo_src?: string;
  favicon_src?: string;
};

export type AppConfig = {
  schema_version: string;
  brand?: BrandConfig;
  app: {
    default_page: PageId;
    /** Perimeter every user lands on by default (its url_slug/entity_id). */
    default_entity?: EntityId;
    pages: PageConfig[];
    sections: NavSectionConfig[];
  };
  users: UserConfig[];
};

/** Client-safe nav section passed from server layout into PageNav. */
export type NavSection = {
  id: string;
  label: string;
  pageIds: PageId[];
  /** See `NavSectionConfig.direct`. */
  direct?: boolean;
};

export type Dataset<T = Record<string, unknown>> = {
  schema_version: string;
  data_version: string;
  /** Perimeter entity_id from manifest (consolidation or organization). */
  entity_id?: EntityId;
  records: T[];
};

export type EntityManifest = {
  schema_version: string;
  data_version: string;
  entity_id: EntityId;
  layout?: string;
  datasets: {
    entity: string;
    pages: Record<string, string[]>;
  };
};

export type SessionPayload = {
  userId: string;
  displayName: string;
  role?: UserRole;
  allowedEntities: EntityId[];
  allowedPages: PageId[];
};

export type SectionProps = {
  user: UserConfig;
  entity: EntityConfig;
  site: SiteConfig | null;
  company: CompanyConfig | null;
  datasets: Record<string, Dataset>;
};

export const PAGE_IDS = [
  'dashboard',
  'cash-position',
  'treasury',
  'financing',
  'customer-invoices',
  'supplier-invoices',
  'expenses',
  'procurement',
  'pnl',
  'balance-sheet',
  'cash-flow',
  'financial-ratios',
  'pnl-budget',
  'forecast',
  'scenario-analysis',
  'cost-centers',
  'general-ledger',
  'journal-entries',
  'fixed-assets',
  'financial-close',
  'theme',
] as const;

/** Retired page ids still accepted from URLs, users.json, and older manifests. */
const LEGACY_PAGE_IDS: Record<string, PageId> = {
  invoices: 'customer-invoices',
};

export function isPageId(value: string): value is PageId {
  return (PAGE_IDS as readonly string[]).includes(value);
}

/** Map a raw page id (including legacy aliases) to the current PageId. */
export function normalizePageId(value: string): PageId | null {
  const mapped = LEGACY_PAGE_IDS[value] ?? value;
  return isPageId(mapped) ? mapped : null;
}

/** Owner and admin both get full, unscoped access to every app. Client-safe. */
export function isAdminRole(role?: UserRole | null): boolean {
  return role === 'owner' || role === 'admin';
}

/** The protected top role — cannot be edited or removed from the app. */
export function isOwnerRole(role?: UserRole | null): boolean {
  return role === 'owner';
}
