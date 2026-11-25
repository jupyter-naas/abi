import type { TenantConfig } from '@/contexts/tenant-context';

/** The logo image height when `tenant.logo_height` is unset (the former `h-12`). */
export const DEFAULT_LOGO_HEIGHT = 48;

type TenantLogoFields = Pick<
  TenantConfig,
  'logo_rectangle_url' | 'logo_url' | 'logo_emoji' | 'logo_height' | 'tab_title'
>;

/**
 * The tenant logo of the login and "No workspace yet" pages: the rectangle
 * logo, else the square one, else (with `emojiFallback`) the emoji on a tile.
 * Renders nothing when there is none.
 */
export function TenantLogo({
  tenant,
  radius,
  primaryColor,
  emojiFallback = false,
}: {
  tenant: TenantLogoFields;
  /** Corner radius of the square logo and the emoji tile, a CSS length. */
  radius: string;
  primaryColor: string;
  emojiFallback?: boolean;
}) {
  const height = tenant.logo_height ?? DEFAULT_LOGO_HEIGHT;
  let logo: React.ReactNode = null;
  if (tenant.logo_rectangle_url) {
    logo = (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={tenant.logo_rectangle_url}
        alt={tenant.tab_title}
        className="max-w-full object-contain"
        style={{ height }}
      />
    );
  } else if (tenant.logo_url) {
    // Square at logo_height, shrinking with its card on a narrow screen:
    // the width is capped and the height follows it through the aspect ratio.
    logo = (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={tenant.logo_url}
        alt={tenant.tab_title}
        className="max-w-full object-contain"
        style={{ width: height, maxWidth: '100%', height: 'auto', aspectRatio: '1 / 1', borderRadius: radius }}
      />
    );
  } else if (emojiFallback && tenant.logo_emoji) {
    // logo_height applies to logo images only: the emoji tile stays 48×48.
    logo = (
      <div
        className="flex h-12 w-12 items-center justify-center text-white font-bold text-xl"
        style={{ backgroundColor: primaryColor, borderRadius: radius }}
      >
        {tenant.logo_emoji}
      </div>
    );
  }
  if (!logo) return null;
  return <div className="mb-6 flex items-center justify-center">{logo}</div>;
}

type TenantFooterFields = Pick<
  TenantConfig,
  'login_footer_text' | 'login_footer_link_label' | 'login_footer_link_url'
>;

/** The footer link, when its label and an http(s) URL are both set. */
export function tenantFooterLink(tenant: TenantFooterFields): { label: string; url: string } | null {
  const label = tenant.login_footer_link_label?.trim() ?? '';
  const url = tenant.login_footer_link_url?.trim() ?? '';
  // The API validates the URL; this keeps any other scheme out of the href.
  if (!label || !/^https?:\/\//i.test(url)) return null;
  return { label, url };
}

/**
 * The tenant footer under the card: `login_footer_text`, and the footer link
 * on its own line, opened in a new tab. Renders nothing when neither is set.
 */
export function TenantFooter({
  tenant,
  color,
  className,
}: {
  tenant: TenantFooterFields;
  color: string;
  className?: string;
}) {
  const text = tenant.login_footer_text?.trim();
  const link = tenantFooterLink(tenant);
  if (!text && !link) return null;
  return (
    <p className={`text-center text-caption ${className ?? ''}`.trim()} style={{ color }}>
      {text}
      {text && link ? <br /> : null}
      {link && (
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="whitespace-nowrap hover:underline"
          style={{ color }}
        >
          {link.label}
        </a>
      )}
    </p>
  );
}
