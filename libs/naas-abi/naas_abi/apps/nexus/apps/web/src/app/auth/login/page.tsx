'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

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
  const { login, isLoading, error, clearError, isAuthenticated } = useAuthStore();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
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
    const errors: { email?: string; password?: string } = {};
    if (!email.trim()) {
      errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Enter a valid email address';
    }
    if (!password) {
      errors.password = 'Password is required';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    
    const success = await login(email, password);
    if (success) {
      router.push('/');
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
  const primaryColor = '#34D399';
  const accentColor = '#1FA574';
  const bgColor = '#FFFFFF';
  const cardColor = '#FFFFFF';
  const borderRadius = '0';
  const cardMaxWidth = '440px';
  const cardPadding = '2.5rem 3rem 3rem';

  // Smart text color: auto-detect from card color
  const textColor = cardColor && isLightColor(cardColor) ? '#1a1a1a' : '#ffffff';
  const cardIsLight = isLightColor(cardColor);
  const mutedTextColor = cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)';
  const subtitleColor = cardIsLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)';

  const cardRadius = `${borderRadius}px`;
  const inputRadius = `${borderRadius}px`;
  const buttonRadius = `${borderRadius}px`;

  const inputStyle: React.CSSProperties = {
    borderRadius: inputRadius,
    backgroundColor: '#F4F4F4',
    border: 'none',
    color: textColor,
  };
  
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{
        backgroundColor: bgColor,
      }}
    >
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
          
          {/* Password */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label
                htmlFor="password"
                className="text-sm font-medium"
                style={{ color: textColor }}
              >
                Password
              </label>
              <Link
                href="/auth/forgot-password"
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
                  ...(fieldErrors.password
                    ? { border: '1px solid #ef4444', backgroundColor: '#fee2e2' }
                    : {}),
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
              <p id="password-error" className="text-xs text-destructive">
                {fieldErrors.password}
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
                Signing in...
              </>
            ) : (
              'Sign in'
            )}
          </button>
        </form>
        
        {/* Sign up link */}
        <p className="mt-6 text-center text-sm" style={{ color: mutedTextColor }}>
          Don&apos;t have an account?{' '}
          <Link
            href="/auth/register"
            className="font-medium hover:underline"
            style={{ color: primaryColor }}
          >
            Sign up
          </Link>
        </p>
      </div>
      {/* 
      Commented out - can be enabled if needed:
      
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

      <p className="mt-4 text-center text-xs" style={{ color: subtitleColor }}>
        Powered by NEXUS
      </p>
      */}
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
