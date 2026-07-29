'use client';

import { useState } from 'react';
import { Form } from 'react-aria-components';

import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';

/**
 * Password sign-in — the secondary option offered under the magic-link form.
 * A single shared admin password grants a full-access session; on success the
 * server returns where to redirect.
 */
export function PasswordForm() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    if (!password) {
      setError('Enter your password');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/auth/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = (await response.json().catch(() => null)) as
        | { ok?: boolean; redirectTo?: string; error?: string }
        | null;
      if (!response.ok || !data?.ok) {
        setError(data?.error ?? 'Incorrect password.');
        return;
      }
      window.location.href = data.redirectTo ?? '/';
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Form onSubmit={handleSubmit}>
      <TextField
        name="password"
        label="Password"
        placeholder="••••••••"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
        isRequired
      />
      <Button
        type="submit"
        isDisabled={loading}
        className="w-full min-h-12 mt-4 text-base"
      >
        {loading ? 'Signing in…' : 'Sign in'}
      </Button>
      {error ? (
        <p role="alert" className="text-red-500 text-sm text-center mt-2">
          {error}
        </p>
      ) : null}
    </Form>
  );
}
