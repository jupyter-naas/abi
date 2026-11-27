'use client';

import { useCallback, useEffect, useState } from 'react';
import { Globe, Image as ImageIcon, LogIn, Network, RefreshCw } from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { Card } from '@/components/ui/card';
import {
  siteIdentitySections,
  siteName,
  type SiteIdentity,
  type SiteSection,
  type SiteValue,
} from './general-model';
import '@/app/account/profile/profile.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import './general.css';

const SECTION_ICONS: Record<SiteSection['id'], typeof Globe> = {
  identity: Globe,
  logo: ImageIcon,
  'sign-in': LogIn,
  addresses: Network,
};

function Value({ value }: { value: SiteValue }) {
  switch (value.kind) {
    case 'unset':
      return <span className="platform-general-unset">—</span>;
    case 'text':
      return <span className="platform-general-text">{value.text}</span>;
    case 'url':
      return (
        <a className="platform-general-link" href={value.url} target="_blank" rel="noopener noreferrer">
          {value.url}
        </a>
      );
    case 'image':
      return (
        <span className="platform-general-image">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={value.url} alt="" className="platform-general-image-preview" />
          <a className="platform-general-link" href={value.url} target="_blank" rel="noopener noreferrer">
            {value.url}
          </a>
        </span>
      );
    case 'color':
      return (
        <span className="platform-general-color">
          <span className="platform-general-swatch" style={{ backgroundColor: value.color }} aria-hidden />
          <code>{value.color}</code>
        </span>
      );
    case 'flag':
      return <span className="platform-general-text">{value.on ? 'Shown' : 'Hidden'}</span>;
  }
}

/**
 * Platform Settings › General: the site's identity, the same for every organization
 * on this deployment. Read from the configuration (`tenant:`), so it changes there.
 */
export default function PlatformGeneralPage() {
  const [site, setSite] = useState<SiteIdentity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiUrl()}/api/tenant`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setSite((await response.json()) as SiteIdentity);
    } catch {
      setError('The site identity could not be read.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const webAddress = typeof window === 'undefined' ? '' : window.location.origin;
  const sections = site
    ? siteIdentitySections(site, {
        webAddress,
        apiAddress: getApiUrl(),
      })
    : [];

  return (
    <div className="platform-general-page">
      <OrgSettingsPageHeader
        title="General"
        subtitle="The identity every organization on this platform shares: name, logo, sign-in page and addresses"
        actions={
          <button
            type="button"
            className="org-settings-users-secondary-button"
            data-action="refresh"
            onClick={() => void load()}
            disabled={loading}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        }
      />

      {site ? (
        <div className="account-profile-avatar-section" data-platform-identity="">
          <div className="account-profile-avatar-wrapper">
            {site.logo_url?.trim() ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={site.logo_url} alt="Platform logo" className="account-profile-avatar-image platform-general-logo" />
            ) : (
              <div
                className="account-profile-avatar-placeholder platform-general-logo"
                style={{ backgroundColor: site.primary_color, color: '#fff' }}
                data-platform-initial=""
              >
                {site.logo_emoji?.trim() || siteName(site).charAt(0).toUpperCase()}
              </div>
            )}
          </div>
          <div className="min-w-0">
            <h3 className="account-profile-avatar-info-name">{siteName(site)}</h3>
            <p className="account-profile-avatar-info-email">
              {webAddress ? `${webAddress.replace(/^https?:\/\//, '')} · ` : ''}Shared by every organization
            </p>
            <p className="account-profile-avatar-info-hint">
              Set in the platform configuration, under <code>tenant:</code>, and applied at the next start. An
              organization&apos;s own logo and colors, in its Branding settings, take over inside it.
            </p>
          </div>
        </div>
      ) : null}

      {loading && !site ? <div className="org-settings-loading">Loading…</div> : null}
      {error ? <p className="org-settings-footnote">{error}</p> : null}

      {sections.map((section) => {
        const Icon = SECTION_ICONS[section.id];
        return (
          <Card
            key={section.id}
            title={
              <span className="flex items-center gap-2">
                <Icon size={16} className="text-muted-foreground" />
                {section.title}
              </span>
            }
          >
            <dl className="platform-general-rows">
              {section.rows.map((row) => (
                <div key={row.label} className="platform-general-row">
                  <dt className="platform-general-label">
                    {row.label}
                    {row.key ? <code className="platform-general-key">{row.key}</code> : null}
                  </dt>
                  <dd className="platform-general-value">
                    <Value value={row.value} />
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        );
      })}
    </div>
  );
}
