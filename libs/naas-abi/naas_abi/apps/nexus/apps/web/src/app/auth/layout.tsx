export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Do not set route-level `metadata.title` here — it overrides tenant
  // `tab_title` from the root layout / TenantProvider (e.g. "AXI AI").
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted">
      {children}
    </div>
  );
}
