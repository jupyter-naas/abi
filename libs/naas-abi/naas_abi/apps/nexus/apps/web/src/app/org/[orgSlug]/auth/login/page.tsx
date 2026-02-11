'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore, OrganizationBranding } from '@/stores/organization';

/**
 * Returns true if a hex color is "light" (should use dark text).
 */
function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  // Perceived luminance formula
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

export default function OrgLoginPage() {
  const router = useRouter();
  const params = useParams();
  const orgSlug = params.orgSlug as string;

  const { login, isLoading, error, clearError, isAuthenticated, logout, user } = useAuthStore();
  const { fetchBranding, brandingLoading, brandingError } = useOrganizationStore();
  const { setTheme } = useTheme();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [branding, setBranding] = useState<OrganizationBranding | null>(null);
  const [shouldCheckAuth, setShouldCheckAuth] = useState(true);
  const [wrongOrgWarning, setWrongOrgWarning] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch org branding on mount
  useEffect(() => {
    if (orgSlug) {
      fetchBranding(orgSlug).then((b) => {
        if (b) setBranding(b);
      });
    }
  }, [orgSlug, fetchBranding]);

  // Check if user is already authenticated with valid access to this org
  useEffect(() => {
    if (!mounted || !isAuthenticated || !shouldCheckAuth) return;

    const verifyOrgAccess = async () => {
      try {
        // Fetch user's organizations to verify access
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch('/api/organizations');
        
        if (!response.ok) {
          // If token is invalid, logout and let them login fresh
          logout();
          setShouldCheckAuth(false);
          return;
        }

        const orgs = await response.json();
        const hasAccess = orgs.some((org: any) => org.slug === orgSlug);

        if (hasAccess) {
          // User has access to this org, redirect to workspace picker
          router.push(`/org/${orgSlug}/workspace`);
        } else {
          // User is logged in but doesn't have access to this org
          // Show warning and let them logout to login with correct account
          setWrongOrgWarning(true);
          setShouldCheckAuth(false);
        }
      } catch (err) {
        console.error('Failed to verify org access:', err);
        // On error, just let them stay on login page
        setShouldCheckAuth(false);
      }
    };

    verifyOrgAccess();
  }, [mounted, isAuthenticated, shouldCheckAuth, router, orgSlug, logout]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    const success = await login(email, password);
    if (success) {
      // Apply org's preferred theme on login (light/dark/system)
      if (branding?.defaultTheme) {
        setTheme(branding.defaultTheme);
      }
      router.push(`/org/${orgSlug}/workspace`);
    }
  };

  // Show loading state during hydration
  if (!mounted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Dynamic styles based on org branding
  const primaryColor = branding?.primaryColor || '#34D399';
  const bgColor = branding?.backgroundColor;
  const cardColor = branding?.loginCardColor;
  // Allow 0px; default to 0 if undefined/null
  const borderRadius = branding?.loginBorderRadius ?? '0';
  const bgImageUrl = branding?.loginBgImageUrl;
  const inputColor = branding?.loginInputColor;

  // Smart text color: explicit override OR auto-detect from card color
  const textColor = branding?.loginTextColor
    || (cardColor && isLightColor(cardColor) ? '#1a1a1a' : undefined);

  // Determine if the card surface is light or dark to pick muted colors accordingly
  const cardIsLight = cardColor ? isLightColor(cardColor) : false;
  // Muted text: same family as textColor, just softer
  const mutedTextColor = textColor
    ? (cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)')
    : undefined;
  const subtitleColor = textColor
    ? (cardIsLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)')
    : undefined;

  // Computed border radius values
  const cardRadius = borderRadius != null ? `${borderRadius}px` : undefined;
  const inputRadius = borderRadius != null ? `${borderRadius}px` : undefined;
  const buttonRadius = borderRadius != null ? `${borderRadius}px` : undefined;

  // Input styles: when custom input color is set, use white text
  const inputTextColor = inputColor ? '#ffffff' : textColor || undefined;
  const inputPlaceholderColor = inputColor
    ? 'rgba(255,255,255,0.5)'
    : undefined;
  const inputStyle: React.CSSProperties = {
    borderRadius: inputRadius || undefined,
    backgroundColor: inputColor || undefined,
    border: inputColor ? 'none' : undefined,
    color: inputTextColor,
  };

  // Card size from reference: 440px max-width, 2.5rem 3rem 3rem padding
  const cardMaxWidth = branding?.loginCardMaxWidth || '440px';
  const cardPadding = branding?.loginCardPadding || '2.5rem 3rem 3rem';

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{
        backgroundColor: bgColor || undefined,
        backgroundImage: bgImageUrl ? `url(${bgImageUrl})` : undefined,
        backgroundSize: bgImageUrl ? 'cover' : undefined,
        backgroundPosition: bgImageUrl ? 'center' : undefined,
        backgroundRepeat: bgImageUrl ? 'no-repeat' : undefined,
        fontFamily: branding?.fontFamily || undefined,
      }}
    >
      {branding?.fontUrl && (
        <link rel="stylesheet" href={branding.fontUrl} />
      )}
      {/* Custom placeholder color when input bg is set */}
      {inputPlaceholderColor && (
        <style>{`.org-input::placeholder { color: ${inputPlaceholderColor} !important; }`}</style>
      )}

      {/* Organization not found warning */}
      {brandingError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-yellow-500/10 p-3 text-sm text-yellow-500">
          <AlertCircle size={16} />
          <span>Organization &quot;{orgSlug}&quot; not found. Showing default login.</span>
        </div>
      )}

      {/* Wrong organization warning */}
      {wrongOrgWarning && !brandingError && (
        <div className="mb-4 flex flex-col gap-2 rounded-lg bg-orange-500/10 p-4 text-sm text-orange-500 border border-orange-500/20">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span className="font-medium">You&apos;re logged in as {user?.email}</span>
          </div>
          <p className="text-xs">
            This account doesn&apos;t have access to {branding?.name || orgSlug}. Please log out and sign in with an account that has access to this organization.
          </p>
          <button
            onClick={() => {
              logout();
              setWrongOrgWarning(false);
              setShouldCheckAuth(true);
            }}
            className="mt-2 self-start rounded-md bg-orange-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-600 transition-colors"
          >
            Log out and try again
          </button>
        </div>
      )}

      {/* Login Card — size from branding (reference: 440px, 2.5rem 3rem 3rem) */}
      <div
        className={cn('w-full shadow-lg', !cardRadius && 'rounded-2xl')}
        style={{
          maxWidth: cardMaxWidth,
          padding: cardPadding,
          backgroundColor: cardColor || 'var(--card)',
          borderRadius: cardRadius || undefined,
          border: cardColor ? 'none' : undefined,
          color: textColor || undefined,
        }}
      >
        {/* Org Logo & Name */}
        <div className="mb-6 flex items-center justify-center">
          {brandingLoading ? (
            <Loader2 className="h-8 w-8 animate-spin" style={{ color: mutedTextColor }} />
          ) : branding ? (
            <>
              {branding.logoRectangleUrl ? (
                <img
                  src={branding.logoRectangleUrl}
                  alt={branding.name}
                  className="h-24 max-w-full object-contain"
                />
              ) : (
                <div className="flex items-center gap-3">
                  {branding.logoUrl ? (
                    <img
                      src={branding.logoUrl}
                      alt={branding.name}
                      className="h-12 w-12 rounded-xl object-contain"
                    />
                  ) : (
                    <div
                      className="flex h-12 w-12 items-center justify-center rounded-xl text-white font-bold text-xl"
                      style={{ backgroundColor: primaryColor }}
                    >
                      {branding.logoEmoji || branding.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <span className="text-2xl font-bold" style={{ color: textColor || undefined }}>
                    {branding.name}
                  </span>
                </div>
              )}
            </>
          ) : brandingError ? (
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground font-bold text-lg">
                N
              </div>
              <span className="text-2xl font-bold">NEXUS</span>
            </div>
          ) : null}
        </div>

        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold" style={{ color: textColor || undefined }}>
            Welcome
          </h1>
          <p className="mt-2 text-sm" style={{ color: mutedTextColor || undefined }}>
            Sign in to continue
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email */}
          <div className="space-y-2">
            <label
              htmlFor="email"
              className="text-sm font-medium"
              style={{ color: textColor || undefined }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              disabled={isLoading}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                !inputColor && 'border bg-background',
                !inputRadius && 'rounded-lg',
                !inputColor && 'placeholder:text-muted-foreground',
                inputColor && 'org-input',
                'focus:outline-none focus:ring-2 focus:ring-primary/20',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              style={inputStyle}
            />
          </div>

          {/* Password */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                htmlFor="password"
                className="text-sm font-medium"
                style={{ color: textColor || undefined }}
              >
                Password
              </label>
              <Link
                href={`/org/${orgSlug}/auth/forgot-password`}
                className="text-sm hover:underline"
                style={{ color: primaryColor }}
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                disabled={isLoading}
                className={cn(
                  'flex h-11 w-full px-4 py-2 pr-10 text-sm',
                  !inputColor && 'border bg-background',
                  !inputRadius && 'rounded-lg',
                  !inputColor && 'placeholder:text-muted-foreground',
                  inputColor && 'org-input',
                  'focus:outline-none focus:ring-2 focus:ring-primary/20',
                  'disabled:cursor-not-allowed disabled:opacity-50'
                )}
                style={inputStyle}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: mutedTextColor || undefined }}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading || !email || !password}
            className={cn(
              'flex h-11 w-full items-center justify-center px-4 text-sm font-medium text-white',
              !buttonRadius && 'rounded-lg',
              'hover:opacity-90 transition-all',
              'focus:outline-none focus:ring-2 focus:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
            style={{
              backgroundColor: primaryColor,
              borderRadius: buttonRadius || undefined,
              '--tw-ring-color': primaryColor,
            } as React.CSSProperties}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </button>
        </form>

        {/* Sign up link */}
        <p className="mt-6 text-center text-sm" style={{ color: mutedTextColor || undefined }}>
          Don&apos;t have an account?{' '}
          <Link
            href={`/org/${orgSlug}/auth/register`}
            className="font-medium hover:underline"
            style={{ color: primaryColor }}
          >
            Sign up
          </Link>
        </p>
      </div>

      {/* Footer -- controlled by org config */}
      {(branding?.showTermsFooter ?? true) && (
        <p className="mt-8 text-center text-sm" style={{ color: subtitleColor || 'var(--muted-foreground)' }}>
          By signing in, you agree to our{' '}
          <Link href="/terms" className="hover:underline">
            Terms of Service
          </Link>
          {' '}and{' '}
          <Link href="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
        </p>
      )}

      {/* Powered by NEXUS */}
      {(branding?.showPoweredBy ?? true) && (
        <p className="mt-4 text-center text-xs" style={{ color: subtitleColor || 'rgba(255,255,255,0.3)' }}>
          Powered by NEXUS
        </p>
      )}

      {/* Custom footer text (e.g. © 2026 Acme Corp - Confidential) */}
      {branding?.loginFooterText && (
        <p className="mt-4 text-center text-xs" style={{ color: subtitleColor || 'rgba(255,255,255,0.4)' }}>
          {branding.loginFooterText}
        </p>
      )}
    </div>
  );
}
