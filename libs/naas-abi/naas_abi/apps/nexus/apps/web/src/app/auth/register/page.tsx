'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, AlertCircle, Check, X } from 'lucide-react';
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

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading, error, clearError, isAuthenticated } = useAuthStore();
  const tenant = useTenant();
  
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
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
    
    // Validate fields
    if (!name.trim()) {
      alert('Please enter your full name');
      return;
    }
    if (!email.trim()) {
      alert('Please enter your email address');
      return;
    }
    if (!isPasswordValid) {
      alert('Please ensure your password meets all requirements');
      return;
    }
    if (!passwordsMatch) {
      alert('Passwords do not match');
      return;
    }
    
    const success = await register(email, password, name);
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
      className="flex min-h-screen flex-col items-center justify-center px-4 py-8"
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
      {/* Register Card */}
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
          <h1 className="text-2xl font-bold" style={{ color: textColor }}>
            Create an account
          </h1>
          <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
            Get started for free
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
            <label htmlFor="name" className="text-sm font-medium" style={{ color: textColor }}>
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
                'focus:outline-none focus:ring-2',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              style={inputStyle}
            />
          </div>
          
          {/* Email */}
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium" style={{ color: textColor }}>
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
          
          {/* Password */}
          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium" style={{ color: textColor }}>
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
                  'focus:outline-none focus:ring-2',
                  'disabled:cursor-not-allowed disabled:opacity-50'
                )}
                style={inputStyle}
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
            <label htmlFor="confirmPassword" className="text-sm font-medium" style={{ color: textColor }}>
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
                Creating account...
              </>
            ) : (
              'Create account'
            )}
          </button>
        </form>
        
        {/* Sign in link */}
        <p className="mt-6 text-center text-sm" style={{ color: mutedTextColor }}>
          Already have an account?{' '}
          <Link href="/auth/login" className="font-medium hover:underline" style={{ color: primaryColor }}>
            Sign in
          </Link>
        </p>
      </div>
      {tenant.show_terms_footer && (
        <p className="mt-8 text-center text-sm" style={{ color: subtitleColor }}>
          By creating an account, you agree to our{' '}
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

function PasswordCheck({ ok, label, primaryColor }: { ok: boolean; label: string; primaryColor: string }) {
  return (
    <div className={cn('flex items-center gap-1')} style={{ color: ok ? primaryColor : 'rgba(0,0,0,0.4)' }}>
      {ok ? <Check size={12} /> : <X size={12} />}
      <span>{label}</span>
    </div>
  );
}
