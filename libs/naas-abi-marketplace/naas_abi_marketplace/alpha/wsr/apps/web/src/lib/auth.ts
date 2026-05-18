'use client';

const SESSION_KEY = 'wsr_auth';

export function login(email: string, password: string): boolean {
  if (
    email.toLowerCase() === 'demo@example.com' &&
    password === 'wsr1234!'
  ) {
    sessionStorage.setItem(SESSION_KEY, '1');
    return true;
  }
  return false;
}

export function logout(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;
  return sessionStorage.getItem(SESSION_KEY) === '1';
}
