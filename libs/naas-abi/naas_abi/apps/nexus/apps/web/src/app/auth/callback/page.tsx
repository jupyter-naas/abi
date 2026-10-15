import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import CallbackHandler from './callback-handler';

export const dynamic = 'force-dynamic';

/** Where the API sends the browser once an identity provider signed it in. */
export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
