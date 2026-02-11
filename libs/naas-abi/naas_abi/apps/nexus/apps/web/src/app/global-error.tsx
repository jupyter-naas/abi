'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body style={{ backgroundColor: '#1a1a2e', margin: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', padding: 32 }}>
          <div style={{ maxWidth: 600, textAlign: 'center' }}>
            <h2 style={{ color: '#ff6b6b', fontSize: 24, fontWeight: 'bold', marginBottom: 16 }}>NEXUS Global Error</h2>
            <div style={{ backgroundColor: '#16213e', border: '1px solid #e94560', borderRadius: 8, padding: 16, textAlign: 'left', marginBottom: 16 }}>
              <p style={{ color: '#ff6b6b', fontSize: 14 }}>{error.message}</p>
              <pre style={{ color: '#a8a8a8', fontSize: 11, whiteSpace: 'pre-wrap' }}>{error.stack}</pre>
            </div>
            <button
              onClick={reset}
              style={{ backgroundColor: '#e94560', color: 'white', border: 'none', borderRadius: 6, padding: '8px 20px', fontSize: 14, cursor: 'pointer' }}
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
