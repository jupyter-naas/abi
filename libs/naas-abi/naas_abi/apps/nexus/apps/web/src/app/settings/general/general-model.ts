/**
 * Platform Settings › General: the site's identity, as `GET /api/tenant` answers it
 * (the `tenant:` block of the configuration). No React: the middleware reads the path.
 */

export const PLATFORM_GENERAL_PATH = '/settings/general';

/** What `GET /api/tenant` answers (the fields this page shows). */
export interface SiteIdentity {
  name?: string | null;
  tab_title: string;
  favicon_url?: string | null;
  og_title?: string | null;
  og_description?: string | null;
  og_image_url?: string | null;
  logo_url?: string | null;
  logo_rectangle_url?: string | null;
  logo_emoji?: string | null;
  primary_color: string;
  accent_color: string;
  background_color: string;
  font_family?: string | null;
  login_card_max_width: string;
  login_card_padding: string;
  login_card_color: string;
  login_text_color?: string | null;
  login_input_color: string;
  login_border_radius: string;
  login_bg_image_url?: string | null;
  show_terms_footer: boolean;
  show_powered_by: boolean;
  login_footer_text?: string | null;
}

export type SiteValue =
  | { kind: 'text'; text: string }
  | { kind: 'url'; url: string }
  | { kind: 'image'; url: string }
  | { kind: 'color'; color: string }
  | { kind: 'flag'; on: boolean }
  | { kind: 'unset' };

export interface SiteRow {
  /** The key under `tenant:` in the configuration, or null for what the deployment decides. */
  key: string | null;
  label: string;
  value: SiteValue;
}

export interface SiteSection {
  id: 'identity' | 'logo' | 'sign-in' | 'addresses';
  title: string;
  rows: SiteRow[];
}

function text(value: string | null | undefined): SiteValue {
  const trimmed = value?.trim();
  return trimmed ? { kind: 'text', text: trimmed } : { kind: 'unset' };
}

function image(value: string | null | undefined): SiteValue {
  const trimmed = value?.trim();
  return trimmed ? { kind: 'image', url: trimmed } : { kind: 'unset' };
}

function color(value: string | null | undefined): SiteValue {
  const trimmed = value?.trim();
  return trimmed ? { kind: 'color', color: trimmed } : { kind: 'unset' };
}

function px(value: string | null | undefined): SiteValue {
  const trimmed = value?.trim();
  if (!trimmed) return { kind: 'unset' };
  return { kind: 'text', text: /^\d+$/.test(trimmed) ? `${trimmed}px` : trimmed };
}

/** The site's name: the configured one, else the tab title. */
export function siteName(site: Pick<SiteIdentity, 'name' | 'tab_title'>): string {
  return site.name?.trim() || site.tab_title.trim();
}

/**
 * The page's sections, in the order an administrator reads them: who the site is,
 * its logo, the sign-in page, and where it is reached. `webAddress` and `apiAddress`
 * are what the browser uses, which the deployment decides.
 */
export function siteIdentitySections(
  site: SiteIdentity,
  { webAddress, apiAddress }: { webAddress: string; apiAddress: string }
): SiteSection[] {
  return [
    {
      id: 'identity',
      title: 'Site identity',
      rows: [
        { key: 'name', label: 'Name', value: site.name?.trim() ? text(site.name) : { kind: 'unset' } },
        { key: 'tab_title', label: 'Tab title', value: text(site.tab_title) },
        { key: 'favicon_url', label: 'Favicon', value: image(site.favicon_url) },
        { key: 'og_title', label: 'Link preview title', value: text(site.og_title) },
        { key: 'og_description', label: 'Link preview description', value: text(site.og_description) },
        { key: 'og_image_url', label: 'Link preview image', value: image(site.og_image_url) },
      ],
    },
    {
      id: 'logo',
      title: 'Default logo',
      rows: [
        { key: 'logo_url', label: 'Square logo', value: image(site.logo_url) },
        { key: 'logo_rectangle_url', label: 'Wide logo', value: image(site.logo_rectangle_url) },
        { key: 'logo_emoji', label: 'Emoji', value: text(site.logo_emoji) },
      ],
    },
    {
      id: 'sign-in',
      title: 'Sign-in page',
      rows: [
        { key: 'primary_color', label: 'Primary color', value: color(site.primary_color) },
        { key: 'accent_color', label: 'Accent color', value: color(site.accent_color) },
        { key: 'background_color', label: 'Background color', value: color(site.background_color) },
        { key: 'login_card_color', label: 'Card color', value: color(site.login_card_color) },
        { key: 'login_text_color', label: 'Text color', value: color(site.login_text_color) },
        { key: 'login_input_color', label: 'Field color', value: color(site.login_input_color) },
        { key: 'login_border_radius', label: 'Corner radius', value: px(site.login_border_radius) },
        { key: 'login_card_max_width', label: 'Card width', value: text(site.login_card_max_width) },
        { key: 'login_card_padding', label: 'Card padding', value: text(site.login_card_padding) },
        { key: 'font_family', label: 'Font', value: text(site.font_family) },
        { key: 'login_bg_image_url', label: 'Background image', value: image(site.login_bg_image_url) },
        { key: 'login_footer_text', label: 'Footer text', value: text(site.login_footer_text) },
        { key: 'show_terms_footer', label: 'Terms line', value: { kind: 'flag', on: site.show_terms_footer } },
        { key: 'show_powered_by', label: '"Powered by" line', value: { kind: 'flag', on: site.show_powered_by } },
      ],
    },
    {
      id: 'addresses',
      title: 'Addresses',
      rows: [
        { key: null, label: 'Web address', value: webAddress ? { kind: 'url', url: webAddress } : { kind: 'unset' } },
        { key: null, label: 'API address', value: apiAddress ? { kind: 'url', url: apiAddress } : { kind: 'unset' } },
      ],
    },
  ];
}
