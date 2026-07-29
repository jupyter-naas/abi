import Link from 'next/link';

type NotAvailablePageProps = {
  params: {
    workspaceId: string;
  };
  searchParams?: {
    from?: string;
  };
};

export default function WorkspaceFeatureNotAvailablePage({
  params,
  searchParams,
}: NotAvailablePageProps) {
  const fallbackPath = `/workspace/${params.workspaceId}/chat`;

  const blockedPath = searchParams?.from ? decodeURIComponent(searchParams.from) : null;

  return (
    <div className="flex h-full w-full items-center justify-center bg-background p-6">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-foreground">Feature not available</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Your workspace role does not grant access to this section yet.
        </p>
        {blockedPath ? (
          <p className="mt-2 text-xs text-muted-foreground">Blocked path: {blockedPath}</p>
        ) : null}
        <div className="mt-6">
          <Link
            href={fallbackPath}
            className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Go to an available section
          </Link>
        </div>
      </div>
    </div>
  );
}
