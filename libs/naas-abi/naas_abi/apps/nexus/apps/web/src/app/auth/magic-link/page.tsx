'use client';

import { Suspense, useEffect, useMemo, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import { shouldSkipMagicLinkConfirmation } from '@/lib/auth-session';

function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

/** Login-page styling tokens from tenant branding. */
function useLoginBrand() {
  const tenant = useTenant();
  const primaryColor = tenant.primary_color || '#34D399';
  const accentColor = tenant.accent_color || '#1FA574';
  const bgColor = tenant.background_color || '#FFFFFF';
  const cardColor = tenant.login_card_color || '#FFFFFF';
  const borderRadius = `${tenant.login_border_radius || '0'}px`;
  const cardMaxWidth = tenant.login_card_max_width || '440px';
  const cardPadding = tenant.login_card_padding || '2.5rem 3rem 3rem';
  const cardIsLight = isLightColor(cardColor);
  const textColor =
    tenant.login_text_color || (cardIsLight ? '#1a1a1a' : '#ffffff');
  const mutedTextColor = cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)';
  const buttonTextColor = isLightColor(primaryColor) ? '#1a1a1a' : '#ffffff';

  return {
    tenant,
    primaryColor,
    accentColor,
    bgColor,
    cardColor,
    borderRadius,
    cardMaxWidth,
    cardPadding,
    textColor,
    mutedTextColor,
    buttonTextColor,
  };
}

function BrandShell({
  children,
}: {
  children: ReactNode;
}) {
  const brand = useLoginBrand();
  const { tenant } = brand;

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{
        backgroundColor: brand.bgColor,
        backgroundImage: tenant.login_bg_image_url
          ? `url(${tenant.login_bg_image_url})`
          : undefined,
        backgroundSize: tenant.login_bg_image_url ? 'cover' : undefined,
        backgroundPosition: tenant.login_bg_image_url ? 'center' : undefined,
        backgroundRepeat: tenant.login_bg_image_url ? 'no-repeat' : undefined,
        fontFamily: tenant.font_family || undefined,
      }}
    >
      {tenant.font_url && <link rel="stylesheet" href={tenant.font_url} />}
      <div
        className="w-full text-center"
        style={{
          maxWidth: brand.cardMaxWidth,
          padding: brand.cardPadding,
          backgroundColor: brand.cardColor,
          borderRadius: brand.borderRadius,
          color: brand.textColor,
        }}
      >
        {(tenant.logo_rectangle_url || tenant.logo_url || tenant.logo_emoji) && (
          <div className="mb-6 flex items-center justify-center">
            {tenant.logo_rectangle_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logo_rectangle_url}
                alt={tenant.tab_title}
                className="h-24 max-w-full object-contain"
              />
            ) : tenant.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logo_url}
                alt={tenant.tab_title}
                className="h-12 w-12 object-contain"
                style={{ borderRadius: brand.borderRadius }}
              />
            ) : (
              <div
                className="flex h-12 w-12 items-center justify-center text-xl font-bold text-white"
                style={{
                  backgroundColor: brand.primaryColor,
                  borderRadius: brand.borderRadius,
                }}
              >
                {tenant.logo_emoji || 'N'}
              </div>
            )}
          </div>
        )}
        {children}
      </div>
      {tenant.login_footer_text && (
        <p className="mt-6 text-center text-xs" style={{ color: brand.mutedTextColor }}>
          {tenant.login_footer_text}
        </p>
      )}
    </div>
  );
}

function MagicLinkPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const brand = useLoginBrand();
  const { verifyMagicLink, isLoading, error, clearError, isAuthenticated } = useAuthStore();

  const token = searchParams.get('token');
  const redirect = useMemo(() => {
    const requested = searchParams.get('redirect');
    if (!requested || !requested.startsWith('/')) {
      return '/';
    }
    return requested;
  }, [searchParams]);

  const handleConfirmSignIn = () => {
    if (!token || isLoading) {
      return;
    }
    clearError();
    verifyMagicLink(token).then((ok) => {
      if (ok) {
        router.replace(redirect);
      }
    });
  };

  useEffect(() => {
    if (shouldSkipMagicLinkConfirmation(token, isAuthenticated)) {
      router.replace(redirect);
    }
  }, [token, isAuthenticated, router, redirect]);

  if (!token) {
    return (
      <BrandShell>
        <div className="mb-4 flex justify-center text-destructive">
          <AlertCircle className="h-8 w-8" />
        </div>
        <h1 className="text-lg font-semibold" style={{ color: brand.textColor }}>
          Invalid magic link
        </h1>
        <p className="mt-2 text-sm" style={{ color: brand.mutedTextColor }}>
          This link is missing a token. Request a new sign-in link.
        </p>
        <Link
          href="/auth/login"
          className="mt-4 inline-block text-sm font-medium underline"
          style={{ color: brand.primaryColor }}
        >
          Back to sign in
        </Link>
      </BrandShell>
    );
  }

  return (
    <BrandShell>
      <h1 className="text-lg font-semibold" style={{ color: brand.textColor }}>
        Confirm sign-in
      </h1>
      <p className="mt-2 text-sm" style={{ color: brand.mutedTextColor }}>
        To continue, click the button below to confirm your sign-in request.
      </p>
      <button
        type="button"
        onClick={handleConfirmSignIn}
        disabled={isLoading}
        style={{
          borderRadius: brand.borderRadius,
          backgroundColor: brand.primaryColor,
          color: brand.buttonTextColor,
        }}
        className="mt-4 inline-flex w-full items-center justify-center px-4 py-2.5 text-sm font-medium transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = brand.accentColor;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = brand.primaryColor;
        }}
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Verifying...
          </>
        ) : (
          'Click to confirm sign-in'
        )}
      </button>
      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      <Link
        href="/auth/login"
        className="mt-4 inline-block text-sm font-medium underline"
        style={{ color: brand.primaryColor }}
      >
        Back to sign in
      </Link>
    </BrandShell>
  );
}

function MagicLinkPageFallback() {
  const brand = useLoginBrand();
  return (
    <BrandShell>
      <div className="mb-4 flex justify-center">
        <Loader2
          className="h-8 w-8 animate-spin"
          style={{ color: brand.primaryColor }}
        />
      </div>
      <h1 className="text-lg font-semibold" style={{ color: brand.textColor }}>
        Loading magic link
      </h1>
      <p className="mt-2 text-sm" style={{ color: brand.mutedTextColor }}>
        Please wait while we prepare sign-in.
      </p>
    </BrandShell>
  );
}

export default function MagicLinkPage() {
  return (
    <Suspense fallback={<MagicLinkPageFallback />}>
      <MagicLinkPageContent />
    </Suspense>
  );
}
