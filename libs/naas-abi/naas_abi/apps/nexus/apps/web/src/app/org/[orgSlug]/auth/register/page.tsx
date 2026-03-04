'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, AlertCircle, Check, X } from 'lucide-react';
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
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

export default function OrgRegisterPage() {
  const router = useRouter();
  const params = useParams();
  const orgSlug = params.orgSlug as string;

  const { register, isLoading, error, clearError, isAuthenticated } = useAuthStore();
  const { fetchBranding, brandingLoading, brandingError } = useOrganizationStore();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [branding, setBranding] = useState<OrganizationBranding | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch org branding
  useEffect(() => {
    if (orgSlug) {
      fetchBranding(orgSlug).then((b) => {
        if (b) setBranding(b);
      });
    }
  }, [orgSlug, fetchBranding]);

  // Redirect if already authenticated
  useEffect(() => {
    if (mounted && isAuthenticated) {
      router.push(`/org/${orgSlug}/workspace`);
    }
  }, [mounted, isAuthenticated, router, orgSlug]);

  // Password validation
  const passwordChecks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
  };

  const isPasswordValid = Object.values(passwordChecks).every(Boolean);
  const passwordsMatch = password === confirmPassword && password.length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    if (!isPasswordValid) {
      return;
    }

    if (!passwordsMatch) {
      return;
    }

    const success = await register(email, password, name);
    if (success) {
      router.push(`/org/${orgSlug}/workspace`);
    }
  };

  if (!mounted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Dynamic styles based on org branding
  const primaryColor = branding?.primaryColor || '#34D399';
  const accentColor = branding?.accentColor || primaryColor;
  const bgColor = branding?.backgroundColor;
  const cardColor = branding?.loginCardColor;
  const borderRadius = branding?.loginBorderRadius;
  const bgImageUrl = branding?.loginBgImageUrl;
  const inputColor = branding?.loginInputColor;

  const textColor = branding?.loginTextColor
    || (cardColor && isLightColor(cardColor) ? '#1a1a1a' : undefined);

  const cardIsLight = cardColor ? isLightColor(cardColor) : false;
  const mutedTextColor = textColor
    ? (cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)')
    : undefined;
  const subtitleColor = textColor
    ? (cardIsLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)')
    : undefined;

  const cardRadius = borderRadius != null ? `${borderRadius}px` : undefined;
  const inputRadius = borderRadius != null ? `${borderRadius}px` : undefined;
  const buttonRadius = borderRadius != null ? `${borderRadius}px` : undefined;

  const inputTextColor = inputColor ? '#ffffff' : textColor || undefined;
  const inputPlaceholderColor = inputColor ? 'rgba(255,255,255,0.5)' : undefined;
  const inputStyle: React.CSSProperties = {
    borderRadius: inputRadius || undefined,
    backgroundColor: inputColor || undefined,
    border: inputColor ? 'none' : undefined,
    color: inputTextColor,
    '--tw-ring-color': `${accentColor}33`,
  } as React.CSSProperties;

  const cardMaxWidth = branding?.loginCardMaxWidth || '440px';
  const cardPadding = branding?.loginCardPadding || '2.5rem 3rem 3rem';

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4 py-8"
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
      {inputPlaceholderColor && (
        <style>{`.org-input::placeholder { color: ${inputPlaceholderColor} !important; }`}</style>
      )}

      {/* Organization not found warning */}
      {brandingError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-yellow-500/10 p-3 text-sm text-yellow-500">
          <AlertCircle size={16} />
          <span>Organization &quot;{orgSlug}&quot; not found. Showing default registration.</span>
        </div>
      )}

      {/* Register Card */}
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
            Create an account
          </h1>
          <p className="mt-2 text-sm" style={{ color: mutedTextColor || undefined }}>
            Join {branding?.name || 'us'} to get started
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
          {/* Name */}
          <div className="space-y-2">
            <label
              htmlFor="name"
              className="text-sm font-medium"
              style={{ color: textColor || undefined }}
            >
              Full name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="John Doe"
              required
              disabled={isLoading}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                !inputColor && 'border bg-background',
                !inputRadius && 'rounded-lg',
                !inputColor && 'placeholder:text-muted-foreground',
                inputColor && 'org-input',
                'focus:outline-none focus:ring-2',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              style={inputStyle}
            />
          </div>

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
                'focus:outline-none focus:ring-2',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              style={inputStyle}
            />
          </div>

          {/* Password */}
          <div className="space-y-2">
            <label
              htmlFor="password"
              className="text-sm font-medium"
              style={{ color: textColor || undefined }}
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                required
                disabled={isLoading}
                className={cn(
                  'flex h-11 w-full px-4 py-2 pr-10 text-sm',
                  !inputColor && 'border bg-background',
                  !inputRadius && 'rounded-lg',
                  !inputColor && 'placeholder:text-muted-foreground',
                  inputColor && 'org-input',
                  'focus:outline-none focus:ring-2',
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

            {/* Password requirements */}
            {password.length > 0 && (
              <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                <PasswordCheck ok={passwordChecks.length} label="8+ characters" primaryColor={primaryColor} />
                <PasswordCheck ok={passwordChecks.uppercase} label="Uppercase letter" primaryColor={primaryColor} />
                <PasswordCheck ok={passwordChecks.lowercase} label="Lowercase letter" primaryColor={primaryColor} />
                <PasswordCheck ok={passwordChecks.number} label="Number" primaryColor={primaryColor} />
              </div>
            )}
          </div>

          {/* Confirm Password */}
          <div className="space-y-2">
            <label
              htmlFor="confirmPassword"
              className="text-sm font-medium"
              style={{ color: textColor || undefined }}
            >
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              required
              disabled={isLoading}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                !inputColor && 'border bg-background',
                !inputRadius && 'rounded-lg',
                !inputColor && 'placeholder:text-muted-foreground',
                inputColor && 'org-input',
                'focus:outline-none focus:ring-2',
                'disabled:cursor-not-allowed disabled:opacity-50',
                confirmPassword.length > 0 && !passwordsMatch && 'border border-destructive'
              )}
              style={{
                ...inputStyle,
                ...(confirmPassword.length > 0 && !passwordsMatch ? { borderColor: '#ef4444' } : {})
              }}
            />
            {confirmPassword.length > 0 && !passwordsMatch && (
              <p className="text-xs text-destructive">Passwords do not match</p>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading || !name || !email || !isPasswordValid || !passwordsMatch}
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
                Creating account...
              </>
            ) : (
              'Create account'
            )}
          </button>
        </form>

        {/* Sign in link */}
        <p className="mt-6 text-center text-sm" style={{ color: mutedTextColor || undefined }}>
          Already have an account?{' '}
          <Link
            href={`/org/${orgSlug}/auth/login`}
            className="font-medium hover:underline"
            style={{ color: primaryColor }}
          >
            Sign in
          </Link>
        </p>
      </div>

      {/* Footer */}
      {(branding?.showTermsFooter ?? true) && (
        <p className="mt-8 text-center text-sm" style={{ color: subtitleColor || 'var(--muted-foreground)' }}>
          By signing up, you agree to our{' '}
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

      {/* Custom footer text */}
      {branding?.loginFooterText && (
        <p className="mt-4 text-center text-xs" style={{ color: subtitleColor || 'rgba(255,255,255,0.4)' }}>
          {branding.loginFooterText}
        </p>
      )}
    </div>
  );
}

function PasswordCheck({ ok, label, primaryColor }: { ok: boolean; label: string; primaryColor: string }) {
  return (
    <div className={cn('flex items-center gap-1')} style={{ color: ok ? primaryColor : 'rgba(0,0,0,0.4)' }}>
      {ok ? <Check size={12} /> : <X size={12} />}
      <span>{label}</span>
    </div>
  );
}
