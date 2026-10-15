'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { Check, Monitor, Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOrganizationStore, type Organization } from '@/stores/organization';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { Checkbox } from '@/components/ui/checkbox';
import { buttonVariants } from '@/components/ui/button';
import { SettingsNotice } from '@/components/settings/settings-ui';
import '../components/org-settings-components.css';
import './branding.css';

const inputClass =
  'h-9 w-full border border-input bg-background px-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/30';
const labelClass = 'mb-2 block text-sm font-medium text-foreground';

export type OrgBrandingSettingsHandle = {
  save: () => Promise<boolean>;
  isDirty: () => boolean;
};

type BrandingSnapshot = {
  primaryColor: string;
  accentColor: string;
  backgroundColor: string;
  logoUrl: string;
  logoRectangleUrl: string;
  logoEmoji: string;
  loginCardColor: string;
  loginTextColor: string;
  loginInputColor: string;
  loginBorderRadius: string;
  loginBgImageUrl: string;
  showTermsFooter: boolean;
  showPoweredBy: boolean;
  loginFooterText: string;
  fontFamily: string;
  fontUrl: string;
  loginCardMaxWidth: string;
  loginCardPadding: string;
  defaultTheme: string;
};

function snapshotFromOrg(org: Organization): BrandingSnapshot {
  return {
    primaryColor: org.primaryColor || '#22c55e',
    accentColor: org.accentColor || '',
    backgroundColor: org.backgroundColor || '',
    logoUrl: org.logoUrl || '',
    logoRectangleUrl: org.logoRectangleUrl || '',
    logoEmoji: org.logoEmoji || '',
    loginCardColor: org.loginCardColor || '',
    loginTextColor: org.loginTextColor || '',
    loginInputColor: org.loginInputColor || '',
    loginBorderRadius: org.loginBorderRadius || '',
    loginBgImageUrl: org.loginBgImageUrl || '',
    showTermsFooter: org.showTermsFooter ?? true,
    showPoweredBy: org.showPoweredBy ?? true,
    loginFooterText: org.loginFooterText || '',
    fontFamily: org.fontFamily || '',
    fontUrl: org.fontUrl || '',
    loginCardMaxWidth: org.loginCardMaxWidth || '',
    loginCardPadding: org.loginCardPadding || '',
    defaultTheme: org.defaultTheme || '',
  };
}

function ColorInput({
  label,
  value,
  onChange,
  placeholder,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  return (
    <div className="space-y-2">
      <label className={labelClass}>{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value || '#000000'}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-10 shrink-0 cursor-pointer border border-input bg-background p-0.5"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || '#000000'}
          className={cn(inputClass, 'flex-1')}
        />
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

type OrgBrandingSettingsProps = {
  orgId: string;
  orgDisplayName: string;
  onDirtyChange?: (dirty: boolean) => void;
};

export const OrgBrandingSettings = forwardRef<
  OrgBrandingSettingsHandle,
  OrgBrandingSettingsProps
>(function OrgBrandingSettings({ orgId, orgDisplayName, onDirtyChange }, ref) {
  const { organizations, fetchOrganizations, updateOrganization } = useOrganizationStore();
  const org = organizations.find((row) => row.id === orgId) ?? null;

  const [primaryColor, setPrimaryColor] = useState('#22c55e');
  const [accentColor, setAccentColor] = useState('');
  const [backgroundColor, setBackgroundColor] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoRectangleUrl, setLogoRectangleUrl] = useState('');
  const [logoEmoji, setLogoEmoji] = useState('');
  const [loginCardColor, setLoginCardColor] = useState('');
  const [loginTextColor, setLoginTextColor] = useState('');
  const [loginInputColor, setLoginInputColor] = useState('');
  const [loginBorderRadius, setLoginBorderRadius] = useState('');
  const [loginBgImageUrl, setLoginBgImageUrl] = useState('');
  const [showTermsFooter, setShowTermsFooter] = useState(true);
  const [showPoweredBy, setShowPoweredBy] = useState(true);
  const [loginFooterText, setLoginFooterText] = useState('');
  const [fontFamily, setFontFamily] = useState('');
  const [fontUrl, setFontUrl] = useState('');
  const [loginCardMaxWidth, setLoginCardMaxWidth] = useState('');
  const [loginCardPadding, setLoginCardPadding] = useState('');
  const [defaultTheme, setDefaultTheme] = useState('');
  const baselineRef = useRef<BrandingSnapshot | null>(null);

  const [uploadingSquare, setUploadingSquare] = useState(false);
  const [uploadingRect, setUploadingRect] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileSquareRef = useRef<HTMLInputElement>(null);
  const fileRectRef = useRef<HTMLInputElement>(null);
  const API_BASE = getApiUrl();

  useEffect(() => {
    void fetchOrganizations();
  }, [fetchOrganizations]);

  const applySnapshot = useCallback((snapshot: BrandingSnapshot) => {
    setPrimaryColor(snapshot.primaryColor);
    setAccentColor(snapshot.accentColor);
    setBackgroundColor(snapshot.backgroundColor);
    setLogoUrl(snapshot.logoUrl);
    setLogoRectangleUrl(snapshot.logoRectangleUrl);
    setLogoEmoji(snapshot.logoEmoji);
    setLoginCardColor(snapshot.loginCardColor);
    setLoginTextColor(snapshot.loginTextColor);
    setLoginInputColor(snapshot.loginInputColor);
    setLoginBorderRadius(snapshot.loginBorderRadius);
    setLoginBgImageUrl(snapshot.loginBgImageUrl);
    setShowTermsFooter(snapshot.showTermsFooter);
    setShowPoweredBy(snapshot.showPoweredBy);
    setLoginFooterText(snapshot.loginFooterText);
    setFontFamily(snapshot.fontFamily);
    setFontUrl(snapshot.fontUrl);
    setLoginCardMaxWidth(snapshot.loginCardMaxWidth);
    setLoginCardPadding(snapshot.loginCardPadding);
    setDefaultTheme(snapshot.defaultTheme);
    baselineRef.current = snapshot;
  }, []);

  useEffect(() => {
    if (org) {
      applySnapshot(snapshotFromOrg(org));
    }
  }, [org, applySnapshot]);

  const currentSnapshot = (): BrandingSnapshot => ({
    primaryColor,
    accentColor,
    backgroundColor,
    logoUrl,
    logoRectangleUrl,
    logoEmoji,
    loginCardColor,
    loginTextColor,
    loginInputColor,
    loginBorderRadius,
    loginBgImageUrl,
    showTermsFooter,
    showPoweredBy,
    loginFooterText,
    fontFamily,
    fontUrl,
    loginCardMaxWidth,
    loginCardPadding,
    defaultTheme,
  });

  const isDirty = useCallback(() => {
    const baseline = baselineRef.current;
    if (!baseline) return false;
    const current = currentSnapshot();
    return (Object.keys(baseline) as (keyof BrandingSnapshot)[]).some(
      (key) => baseline[key] !== current[key]
    );
  }, [
    primaryColor,
    accentColor,
    backgroundColor,
    logoUrl,
    logoRectangleUrl,
    logoEmoji,
    loginCardColor,
    loginTextColor,
    loginInputColor,
    loginBorderRadius,
    loginBgImageUrl,
    showTermsFooter,
    showPoweredBy,
    loginFooterText,
    fontFamily,
    fontUrl,
    loginCardMaxWidth,
    loginCardPadding,
    defaultTheme,
  ]);

  useEffect(() => {
    onDirtyChange?.(isDirty());
  }, [isDirty, onDirtyChange]);

  const save = useCallback(async (): Promise<boolean> => {
    if (!org || !isDirty()) return true;
    const updated = await updateOrganization(org.id, {
      primaryColor: primaryColor || undefined,
      accentColor: accentColor || undefined,
      backgroundColor: backgroundColor || undefined,
      fontFamily: fontFamily || undefined,
      fontUrl: fontUrl || undefined,
      loginCardMaxWidth: loginCardMaxWidth || undefined,
      loginCardPadding: loginCardPadding || undefined,
      logoUrl: logoUrl || undefined,
      logoRectangleUrl: logoRectangleUrl || undefined,
      logoEmoji: logoEmoji || undefined,
      loginCardColor: loginCardColor || undefined,
      loginTextColor: loginTextColor || undefined,
      loginInputColor: loginInputColor || undefined,
      loginBorderRadius: loginBorderRadius !== '' ? loginBorderRadius : undefined,
      loginBgImageUrl: loginBgImageUrl || undefined,
      showTermsFooter,
      showPoweredBy,
      loginFooterText: loginFooterText || undefined,
      defaultTheme: defaultTheme || undefined,
    });
    if (updated) {
      applySnapshot(snapshotFromOrg(updated));
      window.dispatchEvent(new CustomEvent('org-branding-updated'));
      return true;
    }
    return false;
  }, [
    org,
    isDirty,
    updateOrganization,
    primaryColor,
    accentColor,
    backgroundColor,
    fontFamily,
    fontUrl,
    loginCardMaxWidth,
    loginCardPadding,
    logoUrl,
    logoRectangleUrl,
    logoEmoji,
    loginCardColor,
    loginTextColor,
    loginInputColor,
    loginBorderRadius,
    loginBgImageUrl,
    showTermsFooter,
    showPoweredBy,
    loginFooterText,
    defaultTheme,
    applySnapshot,
  ]);

  useImperativeHandle(ref, () => ({ save, isDirty }), [save, isDirty]);

  if (!org) {
    return <div className="org-settings-loading">Loading branding...</div>;
  }

  return (
    <div className="org-settings-branding-page org-settings-branding-embedded">
      {uploadError && <SettingsNotice tone="error">{uploadError}</SettingsNotice>}

      <div className="space-y-6 border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Logo
        </h3>
        {logoUrl || logoRectangleUrl ? (
          <div className="flex flex-wrap items-center gap-6 border border-dashed border-muted-foreground/30 bg-muted/20 p-6">
            {logoRectangleUrl && (
              <div>
                <p className="mb-2 text-xs text-muted-foreground">Rectangle</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={logoRectangleUrl}
                  alt="Rectangle logo"
                  className="h-20 md:h-24 max-w-[360px] object-contain"
                />
              </div>
            )}
            {logoUrl && (
              <div>
                <p className="mb-2 text-xs text-muted-foreground">Square</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={logoUrl} alt="Square logo" className="h-16 w-16 object-contain" />
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-4 border border-dashed border-muted-foreground/30 bg-muted/10 p-6">
            <div className="flex h-16 w-16 items-center justify-center bg-muted text-2xl">
              {logoEmoji || orgDisplayName.charAt(0) || '🏢'}
            </div>
            <p className="text-sm text-muted-foreground">
              Add a square or rectangle logo URL below to see a live preview.
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileSquareRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setUploadError(null);
              if (file.size > 5 * 1024 * 1024) {
                setUploadError('File too large (max 5MB)');
                e.currentTarget.value = '';
                return;
              }
              setUploadingSquare(true);
              try {
                const fd = new FormData();
                fd.append('file', file);
                const res = await authFetch(
                  `/api/organizations/${orgId}/upload-logo-square`,
                  { method: 'POST', body: fd }
                );
                if (!res.ok) {
                  const err = await res.json().catch(() => ({}));
                  throw new Error(err.detail || 'Upload failed');
                }
                const data = await res.json();
                const full = data.logo_url?.startsWith('/')
                  ? `${API_BASE}${data.logo_url}`
                  : data.logo_url;
                if (full) setLogoUrl(full);
                await fetchOrganizations();
              } catch (err: unknown) {
                setUploadError(err instanceof Error ? err.message : 'Upload failed');
              } finally {
                setUploadingSquare(false);
                e.currentTarget.value = '';
              }
            }}
            className="hidden"
          />
          <input
            ref={fileRectRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setUploadError(null);
              if (file.size > 5 * 1024 * 1024) {
                setUploadError('File too large (max 5MB)');
                e.currentTarget.value = '';
                return;
              }
              setUploadingRect(true);
              try {
                const fd = new FormData();
                fd.append('file', file);
                const res = await authFetch(
                  `/api/organizations/${orgId}/upload-logo-rectangle`,
                  { method: 'POST', body: fd }
                );
                if (!res.ok) {
                  const err = await res.json().catch(() => ({}));
                  throw new Error(err.detail || 'Upload failed');
                }
                const data = await res.json();
                const full = data.logo_rectangle_url?.startsWith('/')
                  ? `${API_BASE}${data.logo_rectangle_url}`
                  : data.logo_rectangle_url;
                if (full) setLogoRectangleUrl(full);
                await fetchOrganizations();
              } catch (err: unknown) {
                setUploadError(err instanceof Error ? err.message : 'Upload failed');
              } finally {
                setUploadingRect(false);
                e.currentTarget.value = '';
              }
            }}
            className="hidden"
          />

          <button
            type="button"
            onClick={() => fileSquareRef.current?.click()}
            disabled={uploadingSquare}
            className={buttonVariants({ variant: 'secondary', size: 'sm' })}
            title="Upload square logo"
          >
            {uploadingSquare ? 'Uploading square…' : 'Upload square logo'}
          </button>
          <button
            type="button"
            onClick={() => fileRectRef.current?.click()}
            disabled={uploadingRect}
            className={buttonVariants({ variant: 'secondary', size: 'sm' })}
            title="Upload rectangle logo"
          >
            {uploadingRect ? 'Uploading rectangle…' : 'Upload rectangle logo'}
          </button>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Logo (square)</label>
            <input
              type="text"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://... or /organizations/Acme.png"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Icon / compact logo URL</p>
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Logo (rectangle / full)</label>
            <input
              type="text"
              value={logoRectangleUrl}
              onChange={(e) => setLogoRectangleUrl(e.target.value)}
              placeholder="https://... or /organizations/AcmeWide.png"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Wide logo for login header</p>
          </div>
        </div>

        <div className="max-w-xs space-y-2">
          <label className={labelClass}>Logo emoji fallback</label>
          <input
            type="text"
            value={logoEmoji}
            onChange={(e) => setLogoEmoji(e.target.value)}
            placeholder="e.g. 🏢"
            className={inputClass}
          />
          <p className="text-xs text-muted-foreground">Used when no logo image is set</p>
        </div>
      </div>

      <div className="space-y-6 border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Brand colours
        </h3>
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Primary colour"
            value={primaryColor}
            onChange={setPrimaryColor}
            placeholder="#171C8F"
            hint="Buttons, links, focus border. e.g. #171C8F"
          />
          <ColorInput
            label="Accent colour"
            value={accentColor}
            onChange={setAccentColor}
            placeholder="#0072CE"
            hint="Hover state for primary button. e.g. #0072CE"
          />
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Font family</label>
            <input
              type="text"
              value={fontFamily}
              onChange={(e) => setFontFamily(e.target.value)}
              placeholder="halyard-text, Arial, sans-serif"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">
              CSS font-family (e.g. from reference login)
            </p>
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Font URL</label>
            <input
              type="text"
              value={fontUrl}
              onChange={(e) => setFontUrl(e.target.value)}
              placeholder="https://p.typekit.net/... or Google Fonts CSS URL"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">
              Optional: stylesheet URL to load the font (Typekit, Google Fonts)
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-6 border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Login page — background
        </h3>
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Page background colour"
            value={backgroundColor}
            onChange={setBackgroundColor}
            placeholder="#f0f4f8"
            hint="Fallback when no background image"
          />
          <div className="space-y-2">
            <label className={labelClass}>Background image URL</label>
            <input
              type="text"
              value={loginBgImageUrl}
              onChange={(e) => setLoginBgImageUrl(e.target.value)}
              placeholder="https://..."
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Full-page cover image</p>
          </div>
        </div>
        {loginBgImageUrl && (
          <div className=" border border-dashed border-muted-foreground/30 p-2">
            <p className="mb-1 text-xs text-muted-foreground">Preview</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={loginBgImageUrl} alt="Background" className="h-24 w-full object-cover" />
          </div>
        )}
      </div>

      <div className="space-y-6 border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Login page — card and inputs
        </h3>
        <div className="grid gap-6 sm:grid-cols-3">
          <ColorInput
            label="Card background"
            value={loginCardColor}
            onChange={setLoginCardColor}
            placeholder="#FFFFFF"
            hint="e.g. #FFFFFF (white)"
          />
          <ColorInput
            label="Card text colour"
            value={loginTextColor}
            onChange={setLoginTextColor}
            placeholder="#25282A"
            hint="e.g. #25282A (dark). Auto if empty"
          />
          <ColorInput
            label="Input background"
            value={loginInputColor}
            onChange={setLoginInputColor}
            placeholder="#F4F4F4"
            hint="e.g. #F4F4F4 (light grey, reference) or #B1B3B3 (darker)"
          />
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Card max width</label>
            <input
              type="text"
              value={loginCardMaxWidth}
              onChange={(e) => setLoginCardMaxWidth(e.target.value)}
              placeholder="440px"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Width of the login block (e.g. 440px)</p>
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Card padding</label>
            <input
              type="text"
              value={loginCardPadding}
              onChange={(e) => setLoginCardPadding(e.target.value)}
              placeholder="2.5rem 3rem 3rem"
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">CSS padding (top right bottom left)</p>
          </div>
        </div>
        <div className="space-y-2">
          <label className={labelClass}>Border radius (px)</label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="0"
              max="24"
              value={loginBorderRadius || '0'}
              onChange={(e) => setLoginBorderRadius(e.target.value)}
              className="flex-1"
            />
            <input
              type="text"
              value={loginBorderRadius}
              onChange={(e) => setLoginBorderRadius(e.target.value)}
              placeholder="0"
              className="w-20 border border-input bg-muted/30 px-3 py-2.5 text-center text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
            <span className="text-sm text-muted-foreground">px</span>
          </div>
          <p className="text-xs text-muted-foreground">0 = sharp corners, 16 = corners</p>
        </div>
      </div>

      <div className="space-y-6 border bg-card p-6">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Default Workspace Theme
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Force a specific theme for all workspaces in this organization.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { id: 'light', label: 'Light', desc: 'Always light mode', icon: Sun },
            { id: 'dark', label: 'Dark', desc: 'Always dark mode', icon: Moon },
            { id: 'system', label: 'System', desc: 'Follow user preference', icon: Monitor },
          ].map((t) => {
            const Icon = t.icon;
            const isSelected = defaultTheme === (t.id === 'system' ? '' : t.id);

            return (
              <button
                key={t.id}
                type="button"
                onClick={async () => {
                  const themeValue = t.id === 'system' ? '' : t.id;
                  setDefaultTheme(themeValue);
                  await updateOrganization(org.id, {
                    defaultTheme: themeValue || undefined,
                  });
                  await fetchOrganizations();
                  window.dispatchEvent(new CustomEvent('org-branding-updated'));
                }}
                className={cn(
                  'relative flex flex-col items-start gap-3 border p-4 text-left transition-all',
                  'hover:border-primary/50 hover:bg-muted/50',
                  isSelected ? 'border-primary bg-primary/5' : 'border-border bg-card'
                )}
              >
                {isSelected && (
                  <div className="absolute right-3 top-3">
                    <Check size={16} className="text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center ',
                    isSelected ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                  )}
                >
                  <Icon size={20} />
                </div>
                <div>
                  <p className="font-medium">{t.label}</p>
                  <p className="text-xs text-muted-foreground">{t.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
        <div className=" border border-border bg-muted/30 p-4">
          <p className="text-sm text-muted-foreground">
            Theme changes are saved automatically. Navigate to a workspace in this organization to
            see the theme applied.
          </p>
        </div>
      </div>

      <div className="space-y-6 border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Footer
        </h3>
        <div className="space-y-2">
          <label className={labelClass}>Custom footer text</label>
          <input
            type="text"
            value={loginFooterText}
            onChange={(e) => setLoginFooterText(e.target.value)}
            placeholder="e.g. © 2026 Acme Corp - Confidential"
            className={inputClass}
          />
          <p className="text-xs text-muted-foreground">
            Optional line below the login card (e.g. copyright, disclaimer)
          </p>
        </div>
        <div className="space-y-4">
          <label className="flex cursor-pointer items-center gap-3">
            <Checkbox checked={showTermsFooter} onCheckedChange={setShowTermsFooter} />
            <div>
              <p className="text-sm font-medium">Show Terms & Privacy</p>
              <p className="text-xs text-muted-foreground">
                By signing in, you agree to our Terms of Service and Privacy Policy
              </p>
            </div>
          </label>
          <label className="flex cursor-pointer items-center gap-3">
            <Checkbox checked={showPoweredBy} onCheckedChange={setShowPoweredBy} />
            <div>
              <p className="text-sm font-medium">Show &quot;Powered by NEXUS&quot;</p>
              <p className="text-xs text-muted-foreground">Attribution below the login card</p>
            </div>
          </label>
        </div>
      </div>
    </div>
  );
});
