'use client';

import { useState, useEffect } from 'react';
import { Save, ExternalLink, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useOrganizationStore } from '@/stores/organization';

// Form styling aligned with reference login: clear labels, generous input padding, primary focus ring
const inputClass =
  'w-full rounded-lg border border-input bg-muted/30 px-4 py-3 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20';
const labelClass = 'mb-2 block text-sm font-medium text-foreground';

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
          className="h-10 w-10 shrink-0 cursor-pointer rounded-lg border border-input bg-background p-0.5"
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

export default function BrandingPage() {
  const { organizations, fetchOrganizations, updateOrganization } = useOrganizationStore();
  const org = organizations[0];

  // Branding form state
  const [primaryColor, setPrimaryColor] = useState('#34D399');
  const [accentColor, setAccentColor] = useState('#1FA574');
  const [backgroundColor, setBackgroundColor] = useState('#FFFFFF');
  const [logoUrl, setLogoUrl] = useState('');
  const [logoRectangleUrl, setLogoRectangleUrl] = useState('');
  const [logoEmoji, setLogoEmoji] = useState('');

  // Login page form state
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

  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchOrganizations();
  }, [fetchOrganizations]);

  // Load from org
  useEffect(() => {
    if (org) {
      setPrimaryColor(org.primaryColor || '#34D399');
      setAccentColor(org.accentColor || '#1FA574');
      setBackgroundColor(org.backgroundColor || '#FFFFFF');
      setFontFamily(org.fontFamily || '');
      setFontUrl(org.fontUrl || '');
      setLogoUrl(org.logoUrl || '');
      setLogoRectangleUrl(org.logoRectangleUrl || '');
      setLogoEmoji(org.logoEmoji || '');
      setLoginCardMaxWidth(org.loginCardMaxWidth || '');
      setLoginCardPadding(org.loginCardPadding || '');
      setLoginCardColor(org.loginCardColor || '');
      setLoginTextColor(org.loginTextColor || '');
      setLoginInputColor(org.loginInputColor || '');
      setLoginBorderRadius(org.loginBorderRadius || '');
      setLoginBgImageUrl(org.loginBgImageUrl || '');
      setShowTermsFooter(org.showTermsFooter ?? true);
      setShowPoweredBy(org.showPoweredBy ?? true);
      setLoginFooterText(org.loginFooterText || '');
      setFontFamily(org.fontFamily || '');
      setFontUrl(org.fontUrl || '');
      setLoginCardMaxWidth(org.loginCardMaxWidth || '');
      setLoginCardPadding(org.loginCardPadding || '');
      setDefaultTheme(org.defaultTheme || '');
    }
  }, [org]);

  const handleSave = async () => {
    if (!org) return;
    setLoading(true);
    await updateOrganization(org.id, {
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
    setLoading(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    
    // Dispatch event so layout re-fetches
    window.dispatchEvent(new Event('org-branding-updated'));
  };

  if (!org) {
    return (
      <div className="text-center text-muted-foreground py-12">
        Loading organization...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Branding</h2>
          <p className="text-sm text-muted-foreground">
            Match your login page to your brand (e.g. corporate colours, card layout, footer).
          </p>
        </div>
        <a
          href={`/org/${org.slug}/auth/login`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-input bg-muted/30 px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
        >
          <Eye size={14} />
          Preview Login Page
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Brand colours — reference: primary = buttons/links, accent = hover */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Brand colours
        </h3>
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Primary colour"
            value={primaryColor}
            onChange={setPrimaryColor}
            placeholder="#34D399"
            hint="Buttons, links, focus border. e.g. #34D399"
          />
          <ColorInput
            label="Accent colour"
            value={accentColor}
            onChange={setAccentColor}
            placeholder="#1FA574"
            hint="Hover state for primary button. e.g. #1FA574"
          />
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Logo (square)</label>
            <input
              type="text"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://..."
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
              placeholder="https://..."
              className={inputClass}
            />
            <p className="text-xs text-muted-foreground">Wide logo for login header</p>
          </div>
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
            <p className="text-xs text-muted-foreground">CSS font-family (e.g. from reference login)</p>
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
            <p className="text-xs text-muted-foreground">Optional: stylesheet URL to load the font (Typekit, Google Fonts)</p>
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

        {(logoUrl || logoRectangleUrl) && (
          <div className="flex flex-wrap items-center gap-4 rounded-lg border border-dashed border-muted-foreground/30 p-4">
            {logoUrl && (
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Square</p>
                <img src={logoUrl} alt="Square logo" className="h-12 w-12 rounded-lg object-contain" />
              </div>
            )}
            {logoRectangleUrl && (
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Rectangle</p>
                <img src={logoRectangleUrl} alt="Rectangle logo" className="h-12 max-w-[200px] object-contain" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Login page — background */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Login page — background
        </h3>
        <div className="grid gap-6 sm:grid-cols-2">
          <ColorInput
            label="Page background colour"
            value={backgroundColor}
            onChange={setBackgroundColor}
            placeholder="#FFFFFF"
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
          <div className="rounded-lg border border-dashed border-muted-foreground/30 p-2">
            <p className="mb-1 text-xs text-muted-foreground">Preview</p>
            <img src={loginBgImageUrl} alt="Background" className="h-24 w-full rounded object-cover" />
          </div>
        )}
      </div>

      {/* Login page — card and inputs */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
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
              value={loginBorderRadius || '16'}
              onChange={(e) => setLoginBorderRadius(e.target.value)}
              className="flex-1"
            />
            <input
              type="text"
              value={loginBorderRadius}
              onChange={(e) => setLoginBorderRadius(e.target.value)}
              placeholder="16"
              className="w-20 rounded-lg border border-input bg-muted/30 px-3 py-2.5 text-center text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
            <span className="text-sm text-muted-foreground">px</span>
          </div>
          <p className="text-xs text-muted-foreground">0 = sharp, 16 = rounded</p>
        </div>
      </div>

      {/* Workspace Theme */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Workspace Theme
        </h3>
        <p className="text-sm text-muted-foreground">
          Force a theme when users log in through this organization&apos;s login page.
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { value: 'light', label: 'Light', desc: 'Always light mode' },
            { value: 'dark', label: 'Dark', desc: 'Always dark mode' },
            { value: '', label: 'System', desc: 'Follow user preference' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setDefaultTheme(opt.value)}
              className={cn(
                'rounded-lg border p-4 text-left transition-all',
                defaultTheme === opt.value
                  ? 'border-blue-500 bg-blue-500/10 ring-1 ring-blue-500'
                  : 'hover:bg-muted'
              )}
            >
              <div className="flex items-center gap-2">
                <div
                  className={cn(
                    'h-4 w-4 rounded-full border-2',
                    defaultTheme === opt.value
                      ? 'border-blue-500 bg-blue-500'
                      : 'border-muted-foreground'
                  )}
                />
                <span className="text-sm font-medium">{opt.label}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{opt.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="space-y-6 rounded-xl border bg-card p-6">
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
          <p className="text-xs text-muted-foreground">Optional line below the login card (e.g. copyright, disclaimer)</p>
        </div>
        <div className="space-y-4">
          <label className="flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={showTermsFooter}
              onChange={(e) => setShowTermsFooter(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <div>
              <p className="text-sm font-medium">Show Terms & Privacy</p>
              <p className="text-xs text-muted-foreground">By signing in, you agree to our Terms of Service and Privacy Policy</p>
            </div>
          </label>
          <label className="flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={showPoweredBy}
              onChange={(e) => setShowPoweredBy(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <div>
              <p className="text-sm font-medium">Show &quot;Powered by NEXUS&quot;</p>
              <p className="text-xs text-muted-foreground">Attribution below the login card</p>
            </div>
          </label>
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={loading}
          className={cn(
            'flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
            saved
              ? 'bg-primary/20 text-primary'
              : 'bg-primary text-primary-foreground hover:opacity-90'
          )}
        >
          <Save size={16} />
          {saved ? 'Saved!' : loading ? 'Saving...' : 'Save changes'}
        </button>
      </div>
    </div>
  );
}
