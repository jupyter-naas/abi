export type PageId =
  | 'treasury'
  | 'customer-invoices'
  | 'supplier-invoices'
  | 'pnl'
  | 'pnl-adjustments'
  | 'pnl-budget'
  | 'ref-customers'
  | 'ref-suppliers'
  | 'ref-categories'
  | 'theme';

export type EntityId = string;

export type UserRole = 'admin';

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

export type AppConfig = {
  schema_version: string;
  app: {
    name: string;
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
  'treasury',
  'customer-invoices',
  'supplier-invoices',
  'pnl',
  'pnl-adjustments',
  'pnl-budget',
  'ref-customers',
  'ref-suppliers',
  'ref-categories',
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
