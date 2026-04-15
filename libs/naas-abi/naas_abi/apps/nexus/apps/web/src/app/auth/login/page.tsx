'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';

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

export default function LoginPage() {
  const router = useRouter();
  const { requestMagicLink, isLoading, error, clearError, isAuthenticated } = useAuthStore();
  const tenant = useTenant();
  
  const [email, setEmail] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ email?: string }>({});
  const [linkSent, setLinkSent] = useState(false);
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    setMounted(true);
  }, []);
  
  // Redirect if already authenticated
  useEffect(() => {
    if (mounted && isAuthenticated) {
      router.push('/');
    }
  }, [mounted, isAuthenticated, router]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    
    // Validate fields (inline)
    const errors: { email?: string } = {};
    if (!email.trim()) {
      errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Enter a valid email address';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    
    const success = await requestMagicLink(email);
    if (success) {
      setLinkSent(true);
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

  // Default branding configuration - matches org login style
  const primaryColor = tenant.primary_color || '#34D399';
  const accentColor = tenant.accent_color || '#1FA574';
  const bgColor = tenant.background_color || '#FFFFFF';
  const cardColor = tenant.login_card_color || '#FFFFFF';
  const borderRadius = tenant.login_border_radius || '0';
  const cardMaxWidth = tenant.login_card_max_width || '440px';
  const cardPadding = tenant.login_card_padding || '2.5rem 3rem 3rem';
  const bgImageUrl = tenant.login_bg_image_url;

  // Smart text color: auto-detect from card color
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
      {/* Login Card */}
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
        
        {/* Error Alert */}
        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}
        
        {linkSent ? (
          <div className="space-y-4">
            <div className="flex items-center justify-center text-emerald-500">
              <CheckCircle className="h-12 w-12" />
            </div>
            <p className="text-center text-sm" style={{ color: mutedTextColor }}>
              We sent a magic link to <strong>{email}</strong>. Open it to sign in.
            </p>
            <button
              type="button"
              onClick={() => setLinkSent(false)}
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
            >
              Send another link
            </button>
          </div>
        ) : (
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
              onChange={(e) => {
                setEmail(e.target.value);
                if (fieldErrors.email) setFieldErrors((fe) => ({ ...fe, email: undefined }));
              }}
              placeholder="you@example.com"
              required
              disabled={isLoading}
              className={cn(
                'flex h-11 w-full px-4 py-2 text-sm',
                'focus:outline-none focus:ring-2',
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
                Sending magic link...
              </>
            ) : (
              'Send magic link'
            )}
          </button>
        </form>
        )}
        
        <p className="mt-6 text-center text-sm" style={{ color: mutedTextColor }}>
          Password sign-in is disabled for this workspace.
        </p>
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

// Lightweight typing animation that cycles "Welcome" in multiple languages
function TypingWelcome({ textColor, mutedColor }: { textColor: string; mutedColor: string }) {
  const phrases = [
    'स्वागत है',          // Hindi
    'Welcome',          // English
    'Bienvenue',        // French
    'Bienvenido',       // Spanish
    'Willkommen',       // German
    'Benvenuto',        // Italian
    '欢迎',               // Chinese (Simplified)
    'ようこそ',            // Japanese
    '환영합니다',            // Korean
    'Добро пожаловать',   // Russian
    'Bem-vindo',        // Portuguese
  ];

  const [phraseIndex, setPhraseIndex] = useState(0);
  const [display, setDisplay] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [prePause, setPrePause] = useState(true); // brief blink before each phrase starts
  const [caretOn, setCaretOn] = useState(true);   // discrete caret blink like native UIs

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const current = phrases[phraseIndex];

    const typingSpeed = 75;      // ms per char
    const deletingSpeed = 40;    // ms per char
    const holdDuration = 1000;   // ms to hold full word
    const prePauseDuration = 400; // ms to blink at start of each phrase

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
      setPrePause(true); // blink before starting next phrase
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [display, isDeleting, phraseIndex, prePause]);

  // Discrete caret blink (on/off), independent from typing state
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
