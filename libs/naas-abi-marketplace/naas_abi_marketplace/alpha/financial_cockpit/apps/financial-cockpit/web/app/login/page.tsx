import { LoginOptions } from '@/components/auth/LoginOptions';
import { Logo } from '@/components/brand/Logo';
import { getBrand } from '@/lib/config/loadConfig';

export const dynamic = 'force-dynamic';

export default function LoginPage() {
  const brand = getBrand();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'var(--bg)' }}
    >
      <div className="glass rounded-xl p-12 max-w-md w-full mx-4 glow">
        <div className="text-center mb-8">
          <div className="inline-block mb-4">
            <Logo size={40} />
          </div>
          <h1 className="text-2xl font-bold mb-2">{brand.name}</h1>
          <p className="text-sm text-[var(--text-muted)]">
            Accès restreint
          </p>
        </div>
        <LoginOptions />
      </div>
    </div>
  );
}
