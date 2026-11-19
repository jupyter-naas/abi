export function LoadingScreen({ label = "Loading" }: { label?: string }) {
  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <span className="loading-spinner" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
