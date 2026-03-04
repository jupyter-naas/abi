import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'NEXUS - Sign In',
  description: 'Sign in to your NEXUS account',
};

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted">
      {children}
    </div>
  );
}
