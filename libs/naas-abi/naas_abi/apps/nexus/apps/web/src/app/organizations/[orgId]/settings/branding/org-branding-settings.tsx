'use client';

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import {
  Check,
  Image as ImageIcon,
  LogIn,
  Monitor,
  Moon,
  Palette,
  PanelBottom,
  RectangleHorizontal,
  Square,
  Sun,
  SunMoon,
  Upload,
  Wallpaper,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { useOrganizationStore, type Organization } from '@/stores/organization';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { Checkbox } from '@/components/ui/checkbox';
import { buttonVariants } from '@/components/ui/button';
import { SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import '../components/org-settings-components.css';
import './branding.css';

// The fields of the other settings pages (Organization › General).
const inputClass = 'org-settings-input';
const labelClass = 'org-settings-field-label';
const hintClass = 'org-settings-field-hint';

/** A section titled as the other settings pages: a 16px icon and a sentence-case title. */
function Section({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Check;
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <SettingsSection
      title={
        <span className="flex items-center gap-2">
          <Icon size={16} className="text-muted-foreground" />
          {title}
        </span>
      }
      description={description}
      bodyClassName="space-y-6 p-4"
    >
      {children}
    </SettingsSection>
  );
}

const LOGO_TYPES = 'image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml';
const LOGO_MAX_BYTES = 5 * 1024 * 1024;

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
      {hint && <p className={hintClass}>{hint}</p>}
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

  /** Upload a square or a wide logo: the API stores it and answers its URL. */
  const uploadLogo = async (kind: 'square' | 'rectangle', input: HTMLInputElement) => {
    const file = input.files?.[0];
    if (!file) return;
    setUploadError(null);
    if (file.size > LOGO_MAX_BYTES) {
      setUploadError('File too large (max 5MB)');
      input.value = '';
      return;
    }
    const setUploading = kind === 'square' ? setUploadingSquare : setUploadingRect;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await authFetch(`/api/organizations/${orgId}/upload-logo-${kind}`, {
        method: 'POST',
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await res.json();
      const url: string | undefined = kind === 'square' ? data.logo_url : data.logo_rectangle_url;
      const full = url?.startsWith('/') ? `${API_BASE}${url}` : url;
      if (full) (kind === 'square' ? setLogoUrl : setLogoRectangleUrl)(full);
      await fetchOrganizations();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      input.value = '';
    }
  };

  return (
    <div className="org-settings-branding-form">
      {uploadError && <SettingsNotice tone="error">{uploadError}</SettingsNotice>}

      <div className="org-settings-branding-logos">
        <Section icon={Square} title="Square logo">
          <div className="org-settings-branding-preview" data-logo-preview="square">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoUrl} alt="Square logo" className="h-16 w-16 object-contain" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center bg-muted text-2xl" data-logo-fallback="">
                {logoEmoji || orgDisplayName.charAt(0) || '🏢'}
              </div>
            )}
          </div>
          <input
            ref={fileSquareRef}
            type="file"
            accept={LOGO_TYPES}
            onChange={(e) => void uploadLogo('square', e.currentTarget)}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileSquareRef.current?.click()}
            disabled={uploadingSquare}
            className={buttonVariants({ variant: 'secondary', size: 'sm' })}
          >
            <Upload size={14} />
            {uploadingSquare ? 'Uploading…' : 'Upload square logo'}
          </button>
          <div className="space-y-2">
            <label className={labelClass} htmlFor="org-logo-square">
              URL
            </label>
            <input
              id="org-logo-square"
              type="text"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://... or /organizations/Acme.png"
              className={inputClass}
            />
            <p className={hintClass}>The icon: the sidebar, the workspace lists, the settings.</p>
          </div>
          <div className="space-y-2">
            <label className={labelClass} htmlFor="org-logo-emoji">
              Emoji fallback
            </label>
            <input
              id="org-logo-emoji"
              type="text"
              value={logoEmoji}
              onChange={(e) => setLogoEmoji(e.target.value)}
              placeholder="e.g. 🏢"
              className={inputClass}
            />
            <p className={hintClass}>Shown when there is no square logo.</p>
          </div>
        </Section>

        <Section icon={RectangleHorizontal} title="Wide logo">
          <div className="org-settings-branding-preview" data-logo-preview="rectangle">
            {logoRectangleUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoRectangleUrl} alt="Wide logo" className="h-16 max-w-full object-contain" />
            ) : (
              <p className={hintClass}>No wide logo: the login page shows the square one.</p>
            )}
          </div>
          <input
            ref={fileRectRef}
            type="file"
            accept={LOGO_TYPES}
            onChange={(e) => void uploadLogo('rectangle', e.currentTarget)}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRectRef.current?.click()}
            disabled={uploadingRect}
            className={buttonVariants({ variant: 'secondary', size: 'sm' })}
          >
            <Upload size={14} />
            {uploadingRect ? 'Uploading…' : 'Upload wide logo'}
          </button>
          <div className="space-y-2">
            <label className={labelClass} htmlFor="org-logo-rectangle">
              URL
            </label>
            <input
              id="org-logo-rectangle"
              type="text"
              value={logoRectangleUrl}
              onChange={(e) => setLogoRectangleUrl(e.target.value)}
              placeholder="https://... or /organizations/AcmeWide.png"
              className={inputClass}
            />
            <p className={hintClass}>The full logo: the login page header.</p>
          </div>
        </Section>
      </div>

      <Section icon={Palette} title="Brand colors">
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Primary color"
            value={primaryColor}
            onChange={setPrimaryColor}
            placeholder="#171C8F"
            hint="Buttons, links, focus border. e.g. #171C8F"
          />
          <ColorInput
            label="Accent color"
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
            <p className={hintClass}>CSS font-family (e.g. from reference login)</p>
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
            <p className={hintClass}>Optional: stylesheet URL to load the font (Typekit, Google Fonts)</p>
          </div>
        </div>
      </Section>

      <Section icon={Wallpaper} title="Login page background">
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Page background color"
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
            <p className={hintClass}>Full-page cover image</p>
          </div>
        </div>
        {loginBgImageUrl && (
          <div className="org-settings-branding-preview">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={loginBgImageUrl} alt="Background" className="h-24 w-full object-cover" />
          </div>
        )}
      </Section>

      <Section icon={LogIn} title="Login card and inputs">
        <div className="grid gap-6 sm:grid-cols-3">
          <ColorInput
            label="Card background"
            value={loginCardColor}
            onChange={setLoginCardColor}
            placeholder="#FFFFFF"
            hint="e.g. #FFFFFF (white)"
          />
          <ColorInput
            label="Card text color"
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
            <p className={hintClass}>Width of the login block (e.g. 440px)</p>
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
            <p className={hintClass}>CSS padding (top right bottom left)</p>
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
              className={cn(inputClass, 'w-20 text-center')}
            />
            <span className="text-sm text-muted-foreground">px</span>
          </div>
          <p className={hintClass}>0 = sharp corners, 16 = corners</p>
        </div>
      </Section>

      <Section
        icon={SunMoon}
        title="Default workspace theme"
        description="Force a theme for every workspace of this organization. Saved at once."
      >
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
        <p className={hintClass}>Open a workspace of this organization to see the theme applied.</p>
      </Section>

      <Section icon={PanelBottom} title="Login page footer">
        <div className="space-y-2">
          <label className={labelClass}>Custom footer text</label>
          <input
            type="text"
            value={loginFooterText}
            onChange={(e) => setLoginFooterText(e.target.value)}
            placeholder="e.g. © 2026 Acme Corp - Confidential"
            className={inputClass}
          />
          <p className={hintClass}>Optional line below the login card (e.g. copyright, disclaimer)</p>
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
      </Section>
    </div>
  );
});
