'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, AlertCircle, CheckCircle, ArrowLeft, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

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

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing reset token');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (!token) {
      setError('Invalid or missing reset token');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token, new_password: password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to reset password');
      }

      setSuccess(true);
      
      // Redirect to login after 2 seconds
      setTimeout(() => {
        router.push('/auth/login');
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Default branding configuration
  const primaryColor = '#34D399';
  const accentColor = '#1FA574';
  const bgColor = '#FFFFFF';
  const cardColor = '#FFFFFF';
  const borderRadius = '0';
  const cardMaxWidth = '440px';
  const cardPadding = '2.5rem 3rem 3rem';

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
                Password reset successfully
              </h1>
              <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
                Redirecting you to login...
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="mb-6 text-center">
              <h1 className="text-2xl font-bold" style={{ color: textColor }}>
                Reset your password
              </h1>
              <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
                Enter your new password below
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
              {/* New Password */}
              <div className="space-y-2">
                <label
                  htmlFor="password"
                  className="text-sm font-medium"
                  style={{ color: textColor }}
                >
                  New Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    disabled={isLoading || !token}
                    className={cn(
                      'flex h-11 w-full px-4 py-2 pr-10 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-primary/20',
                      'disabled:cursor-not-allowed disabled:opacity-50'
                    )}
                    style={inputStyle}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    disabled={isLoading || !token}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <label
                  htmlFor="confirmPassword"
                  className="text-sm font-medium"
                  style={{ color: textColor }}
                >
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    id="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    disabled={isLoading || !token}
                    className={cn(
                      'flex h-11 w-full px-4 py-2 pr-10 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-primary/20',
                      'disabled:cursor-not-allowed disabled:opacity-50'
                    )}
                    style={inputStyle}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    disabled={isLoading || !token}
                  >
                    {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
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
                    Resetting...
                  </>
                ) : (
                  'Reset password'
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

      {/* 
      Commented out - can be enabled if needed:
      
      <p className="mt-8 text-center text-sm" style={{ color: subtitleColor }}>
        Need help?{' '}
        <Link href="/support" className="hover:underline">
          Contact support
        </Link>
      </p>

      <p className="mt-4 text-center text-xs" style={{ color: subtitleColor }}>
        Powered by NEXUS
      </p>
      */}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
