'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Loader2, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTenant } from '@/contexts/tenant-context';

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

export default function ForgotPasswordPage() {
  const tenant = useTenant();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to send reset link');
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset link. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Default branding configuration
  const primaryColor = tenant.primary_color || '#34D399';
  const accentColor = tenant.accent_color || '#1FA574';
  const bgColor = tenant.background_color || '#FFFFFF';
  const cardColor = tenant.login_card_color || '#FFFFFF';
  const borderRadius = tenant.login_border_radius || '0';
  const cardMaxWidth = tenant.login_card_max_width || '440px';
  const cardPadding = tenant.login_card_padding || '2.5rem 3rem 3rem';
  const bgImageUrl = tenant.login_bg_image_url;

  const textColor = tenant.login_text_color || (cardColor && isLightColor(cardColor) ? '#1a1a1a' : '#ffffff');
  const cardIsLight = isLightColor(cardColor);
  const mutedTextColor = cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)';
  const subtitleColor = cardIsLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)';

  const cardRadius = `${borderRadius}px`;
  const inputRadius = `${borderRadius}px`;
  const buttonRadius = `${borderRadius}px`;
  const focusRingColor = `${accentColor}33`;

  const inputStyle: React.CSSProperties = {
    borderRadius: inputRadius,
    backgroundColor: tenant.login_input_color || '#F4F4F4',
    border: 'none',
    color: textColor,
    '--tw-ring-color': focusRingColor,
  } as React.CSSProperties;

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{
        backgroundColor: bgColor,
        backgroundImage: bgImageUrl ? `url(${bgImageUrl})` : undefined,
        backgroundSize: bgImageUrl ? 'cover' : undefined,
        backgroundPosition: bgImageUrl ? 'center' : undefined,
        backgroundRepeat: bgImageUrl ? 'no-repeat' : undefined,
        fontFamily: tenant.font_family || undefined,
      }}
    >
      {tenant.font_url && (
        <link rel="stylesheet" href={tenant.font_url} />
      )}
      {/* Card */}
      <div
        className="w-full"
        style={{
          maxWidth: cardMaxWidth,
          padding: cardPadding,
          backgroundColor: cardColor,
          borderRadius: cardRadius,
          border: 'none',
          color: textColor,
        }}
      >
        {success ? (
          <>
            <div className="mb-6 flex justify-center">
              <div className="rounded-full bg-green-100 p-3">
                <CheckCircle className="h-12 w-12 text-green-600" />
              </div>
            </div>
            <div className="mb-6 text-center">
              <h1 className="text-2xl font-bold" style={{ color: textColor }}>
                Check your email
              </h1>
              <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
                We&apos;ve sent a password reset link to <strong>{email}</strong>
              </p>
            </div>
            <Link
              href="/auth/login"
              className="flex h-11 w-full items-center justify-center px-4 text-sm font-medium text-white hover:opacity-90 transition-all"
              style={{
                backgroundColor: primaryColor,
                borderRadius: buttonRadius,
              }}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to login
            </Link>
          </>
        ) : (
          <>
            {(tenant.logo_rectangle_url || tenant.logo_url || tenant.logo_emoji) && (
              <div className="mb-6 flex items-center justify-center">
                {tenant.logo_rectangle_url ? (
                  <img
                    src={tenant.logo_rectangle_url}
                    alt={tenant.tab_title}
                    className="h-24 max-w-full object-contain"
                  />
                ) : tenant.logo_url ? (
                  <img
                    src={tenant.logo_url}
                    alt={tenant.tab_title}
                    className="h-12 w-12 rounded-xl object-contain"
                  />
                ) : (
                  <div
                    className="flex h-12 w-12 items-center justify-center rounded-xl text-white font-bold text-xl"
                    style={{ backgroundColor: primaryColor }}
                  >
                    {tenant.logo_emoji || 'N'}
                  </div>
                )}
              </div>
            )}
            <div className="mb-6 text-center">
              <h1 className="text-2xl font-bold" style={{ color: textColor }}>
                Reset your password
              </h1>
              <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
                Enter your email and we&apos;ll send you a link to reset your password
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
                  style={{ color: textColor }}
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
                    'focus:outline-none focus:ring-2',
                    'disabled:cursor-not-allowed disabled:opacity-50'
                  )}
                  style={inputStyle}
                />
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                className={cn(
                  'flex h-11 w-full items-center justify-center px-4 text-sm font-medium text-white',
                  'transition-all',
                  'focus:outline-none focus:ring-2 focus:ring-offset-2'
                )}
                style={{
                  backgroundColor: primaryColor,
                  borderRadius: buttonRadius,
                  '--tw-ring-color': primaryColor,
                } as React.CSSProperties}
                onMouseEnter={(e) => {
                  if (!isLoading) {
                    e.currentTarget.style.backgroundColor = accentColor;
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = primaryColor;
                }}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  'Send reset link'
                )}
              </button>
            </form>

            {/* Back to login */}
            <div className="mt-6 text-center">
              <Link
                href="/auth/login"
                className="inline-flex items-center gap-1 text-sm font-medium hover:underline"
                style={{ color: primaryColor }}
              >
                <ArrowLeft size={14} />
                Back to login
              </Link>
            </div>
          </>
        )}
      </div>
      {tenant.show_powered_by && (
        <p className="mt-4 text-center text-xs" style={{ color: subtitleColor }}>
          Powered by NEXUS
        </p>
      )}
      {tenant.login_footer_text && (
        <p className="mt-4 text-center text-xs" style={{ color: subtitleColor }}>
          {tenant.login_footer_text}
        </p>
      )}
    </div>
  );
}
