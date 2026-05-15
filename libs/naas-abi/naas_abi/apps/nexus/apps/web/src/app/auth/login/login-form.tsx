'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
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
  const { login, requestMagicLink, isLoading, error, clearError, isAuthenticated } = useAuthStore();
  const tenant = useTenant();

  const [email, setEmail] = useState(searchParams.get('email') ?? '');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [mounted, setMounted] = useState(false);
  const [passwordAuthEnabled, setPasswordAuthEnabled] = useState<boolean | null>(() => {
    if (typeof window === 'undefined') return null;
    const cached = window.sessionStorage.getItem('nexus-password-auth-enabled');
    if (cached === 'true') return true;
    if (cached === 'false') return false;
    return null;
  });
  const [linkSent, setLinkSent] = useState(false);

  useEffect(() => {
    setMounted(true);
    fetch(`${getApiUrl()}/api/auth/config`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        const enabled = Boolean(d.password_auth_enabled ?? false);
        setPasswordAuthEnabled(enabled);
        try {
          window.sessionStorage.setItem('nexus-password-auth-enabled', String(enabled));
        } catch {
          // sessionStorage can be unavailable (private mode, SSR); ignore.
        }
      })
      .catch(() => setPasswordAuthEnabled((prev) => (prev === null ? false : prev)));
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      router.push('/');
    }
  }, [mounted, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    const errors: { email?: string; password?: string } = {};
    if (!email.trim()) {
      errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Enter a valid email address';
    }
    if (passwordAuthEnabled && !password) {
      errors.password = 'Password is required';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (passwordAuthEnabled) {
      const workspaceId = await login(email, password);
      if (workspaceId) {
        router.push(`/workspace/${workspaceId}/chat`);
      }
    } else {
      const success = await requestMagicLink(email);
      if (success) setLinkSent(true);
    }
  };

  if (!mounted || passwordAuthEnabled === null) {
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
          <TypingWelcome textColor={textColor} mutedColor={mutedTextColor} />
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

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
                if (fieldErrors.email) setFieldErrors((fe) => ({ ...fe, email: undefined }));
              }}
              placeholder="you@example.com"
              required
              disabled={isLoading}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                'focus:outline-none focus:ring-2 focus:ring-primary/20',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              aria-invalid={!!fieldErrors.email}
              aria-describedby={fieldErrors.email ? 'email-error' : undefined}
              style={{
                ...inputStyle,
                ...(fieldErrors.email
                  ? { border: '1px solid #ef4444', backgroundColor: '#fee2e2' }
                  : {}),
              }}
            />
            {fieldErrors.email && (
              <p id="email-error" className="text-xs text-destructive">
                {fieldErrors.email}
              </p>
            )}
          </div>

          {passwordAuthEnabled && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-sm font-medium" style={{ color: textColor }}>
                  Password
                </label>
                <Link href="/auth/forgot-password" className="text-sm hover:underline" style={{ color: primaryColor }}>
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) setFieldErrors((fe) => ({ ...fe, password: undefined }));
                  }}
                  placeholder="Enter your password"
                  required
                  disabled={isLoading}
                  className={cn(
                    'flex h-11 w-full px-4 py-2 pr-10 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-primary/20',
                    'disabled:cursor-not-allowed disabled:opacity-50'
                  )}
                  aria-invalid={!!fieldErrors.password}
                  aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                  style={{
                    ...inputStyle,
                    ...(fieldErrors.password ? { border: '1px solid #ef4444', backgroundColor: '#fee2e2' } : {}),
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: mutedTextColor }}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {fieldErrors.password && (
                <p id="password-error" className="text-xs text-destructive">{fieldErrors.password}</p>
              )}
            </div>
          )}

          {linkSent && !passwordAuthEnabled && (
            <p className="text-center text-sm text-emerald-600">
              If an account exists for <strong>{email}</strong>, a sign-in link is on its way.
            </p>
          )}

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
            onMouseEnter={(e) => { if (!isLoading) e.currentTarget.style.backgroundColor = accentColor; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = primaryColor; }}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {passwordAuthEnabled ? 'Signing in...' : 'Sending magic link...'}
              </>
            ) : (
              passwordAuthEnabled ? 'Sign in' : 'Send magic link'
            )}
          </button>
        </form>
      </div>
      {tenant.show_terms_footer && (
        <p className="mt-8 text-center text-sm" style={{ color: subtitleColor }}>
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

function TypingWelcome({ textColor, mutedColor }: { textColor: string; mutedColor: string }) {
  const phrases = [
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
  }, [display, isDeleting, phraseIndex, prePause]);

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
