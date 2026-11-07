'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import { getApiUrl } from '@/lib/config';

function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    routeLogin,
    signInWithProvider,
    isLoading,
    error,
    clearError,
    isAuthenticated,
  } = useAuthStore();
  const tenant = useTenant();

  const [email, setEmail] = useState(searchParams.get('email') ?? '');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  // The engine's identity providers: an email routes to one (its organization's
  // verified domain, else the default), and each can be picked directly.
  const [providers, setProviders] = useState<{ name: string; display_name: string }[]>([]);
  const [defaultProvider, setDefaultProvider] = useState<string | null>(null);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const ssoError = ssoErrorMessage(searchParams.get('sso_error'));
  const nextPath = searchParams.get('redirect') ?? undefined;
  // ?provider=<name> (an invitation's sign-in link): that provider, if configured.
  const requestedProvider = searchParams.get('provider');
  const linkedProvider =
    requestedProvider && providers.some((p) => p.name === requestedProvider)
      ? requestedProvider
      : null;

  useEffect(() => {
    setMounted(true);
    fetch(`${getApiUrl()}/api/auth/oidc/providers`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        setProviders(Array.isArray(d.providers) ? d.providers : []);
        setDefaultProvider(typeof d.default_provider === 'string' ? d.default_provider : null);
      })
      .catch(() => setProviders([]))
      .finally(() => setProvidersLoaded(true));
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      router.push('/');
    }
  }, [mounted, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    const address = email.trim();
    if (!address) {
      setFieldError('Email is required');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) {
      setFieldError('Enter a valid email address');
      return;
    }
    setFieldError(null);

    // An invitation's link names the provider: no routing by domain then. Else
    // the organization's verified domain routes, else the default provider.
    const provider = linkedProvider ?? (await routeLogin(address)) ?? defaultProvider;
    if (!provider) {
      setFieldError('Choose how to sign in with one of the providers below.');
      return;
    }
    setRedirecting(true);
    signInWithProvider({ provider, email: address, next: nextPath });
  };

  if (!mounted || !providersLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

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
        {(tenant.logo_rectangle_url || tenant.logo_url || tenant.logo_emoji) && (
          <div className="mb-6 flex items-center justify-center">
            {tenant.logo_rectangle_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logo_rectangle_url}
                alt={tenant.tab_title}
                className="h-12 max-w-full object-contain"
              />
            ) : tenant.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.logo_url}
                alt={tenant.tab_title}
                className="h-12 w-12 object-contain"
                style={{ borderRadius: cardRadius }}
              />
            ) : (
              <div
                className="flex h-12 w-12 items-center justify-center text-white font-bold text-xl"
                style={{ backgroundColor: primaryColor, borderRadius: cardRadius }}
              >
                {tenant.logo_emoji || 'N'}
              </div>
            )}
          </div>
        )}
        <div className="mb-6 text-center">
          <TypingWelcome textColor={textColor} mutedColor={mutedTextColor} />
        </div>

        {ssoError && !error && (
          <div
            className="mb-6 flex items-center gap-2 bg-destructive/10 p-3 text-sm text-destructive"
            style={{ borderRadius: cardRadius }}
          >
            <AlertCircle size={16} />
            <span>{ssoError}</span>
          </div>
        )}

        {error && (
          <div
            className="mb-6 flex items-center gap-2 bg-destructive/10 p-3 text-sm text-destructive"
            style={{ borderRadius: cardRadius }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {providers.length === 0 ? (
          <div
            className="flex items-center gap-2 bg-destructive/10 p-3 text-sm text-destructive"
            style={{ borderRadius: cardRadius }}
          >
            <AlertCircle size={16} />
            <span>No identity provider is configured. Ask an administrator to set one up.</span>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
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
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldError) setFieldError(null);
              }}
              placeholder="you@example.com"
              required
              disabled={isLoading || redirecting}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                'focus:outline-none focus:ring-2 focus:ring-primary/20',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              aria-invalid={!!fieldError}
              aria-describedby={fieldError ? 'email-error' : undefined}
              style={{
                ...inputStyle,
                ...(fieldError
                  ? { border: '1px solid #ef4444', backgroundColor: '#fee2e2' }
                  : {}),
              }}
            />
            {fieldError && (
              <p id="email-error" className="text-xs text-destructive">
                {fieldError}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={redirecting}
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
            onMouseEnter={(e) => { if (!redirecting) e.currentTarget.style.backgroundColor = accentColor; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = primaryColor; }}
          >
            {redirecting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Redirecting...
              </>
            ) : (
              'Continue'
            )}
          </button>
        </form>
        )}

        {providers.length > 0 && (
          <div className="mt-6 space-y-3">
            <div className="flex items-center gap-3 text-xs" style={{ color: mutedTextColor }}>
              <span className="h-px flex-1" style={{ backgroundColor: mutedTextColor, opacity: 0.3 }} />
              or
              <span className="h-px flex-1" style={{ backgroundColor: mutedTextColor, opacity: 0.3 }} />
            </div>
            {providers.map((provider) => (
              <button
                key={provider.name}
                type="button"
                disabled={redirecting}
                onClick={() => {
                  setRedirecting(true);
                  signInWithProvider({ provider: provider.name, email: email.trim() || undefined, next: nextPath });
                }}
                className="flex h-11 w-full items-center justify-center px-4 text-sm font-medium transition-all disabled:opacity-50"
                style={{ borderRadius: buttonRadius, border: `1px solid ${mutedTextColor}`, color: textColor }}
              >
                Continue with {provider.display_name}
              </button>
            ))}
          </div>
        )}
      </div>
      {tenant.show_terms_footer && (
        <p className="mt-8 text-center text-caption" style={{ color: subtitleColor }}>
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
      {tenant.show_powered_by && (
        <p className="mt-4 text-center text-caption" style={{ color: subtitleColor }}>
          Powered by NEXUS
        </p>
      )}
      {tenant.login_footer_text && (
        <p className="mt-4 text-center text-caption" style={{ color: subtitleColor }}>
          {tenant.login_footer_text}
        </p>
      )}
    </div>
  );
}

/** What the login page shows for an identity provider's sign-in that failed. */
export function ssoErrorMessage(code: string | null): string | null {
  if (!code) return null;
  switch (code) {
    case 'email_in_use':
      return 'This email already belongs to another account. Ask an administrator to link them.';
    case 'suspended':
      return 'This account is suspended.';
    case 'expired_request':
      return 'The sign-in expired. Please try again.';
    case 'browser_mismatch':
      return 'The sign-in was started in another browser. Please try again here.';
    case 'provider_unavailable':
      return 'The identity provider cannot be reached right now.';
    case 'no_provider':
      return 'No identity provider is configured.';
    case 'unknown_provider':
      return 'That identity provider is not configured.';
    case 'token_rejected':
      return 'The identity provider\'s sign-in could not be verified. Please try again.';
    case 'sign_in_failed':
      return 'The sign-in failed. Please try again.';
    case 'access_denied':
      return 'The sign-in was cancelled.';
    default:
      return 'The sign-in failed. Please try again.';
  }
}

const TYPING_WELCOME_PHRASES = [
  'स्वागत है',
  'Welcome',
  'Bienvenue',
  'Bienvenido',
  'Willkommen',
  'Benvenuto',
  '欢迎',
  'ようこそ',
  '환영합니다',
  'Добро пожаловать',
  'Bem-vindo',
];

function TypingWelcome({ textColor, mutedColor }: { textColor: string; mutedColor: string }) {
  const phrases = TYPING_WELCOME_PHRASES;

  const [phraseIndex, setPhraseIndex] = useState(0);
  const [display, setDisplay] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [prePause, setPrePause] = useState(true);
  const [caretOn, setCaretOn] = useState(true);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const current = phrases[phraseIndex];

    const typingSpeed = 75;
    const deletingSpeed = 40;
    const holdDuration = 1000;
    const prePauseDuration = 400;

    if (prePause) {
      timer = setTimeout(() => setPrePause(false), prePauseDuration);
    } else if (!isDeleting && display.length < current.length) {
      timer = setTimeout(() => setDisplay(current.slice(0, display.length + 1)), typingSpeed);
    } else if (!isDeleting && display.length === current.length) {
      timer = setTimeout(() => setIsDeleting(true), holdDuration);
    } else if (isDeleting && display.length > 0) {
      timer = setTimeout(() => setDisplay(current.slice(0, display.length - 1)), deletingSpeed);
    } else if (isDeleting && display.length === 0) {
      setIsDeleting(false);
      setPhraseIndex((phraseIndex + 1) % phrases.length);
      setPrePause(true);
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [display, isDeleting, phraseIndex, prePause, phrases]);

  useEffect(() => {
    const id = setInterval(() => setCaretOn(v => !v), 520);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <h1 className="text-2xl font-bold leading-none" style={{ color: textColor }}>
        <span className="inline-block align-baseline">{display}</span>
        <span
          className="ml-0.5 inline-block w-[2px] align-baseline"
          style={{
            backgroundColor: textColor,
            height: '0.9em',
            transform: 'translateY(0.08em)',
            opacity: caretOn ? 0.9 : 0,
          }}
        />
      </h1>
      <p className="mt-2 text-sm" style={{ color: mutedColor }}>
        Sign in to continue
      </p>
    </>
  );
}
