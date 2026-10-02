/** Shown on Settings > Services pages to users who are not platform superadmins. */
export function ServicesForbidden() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <h2 className="text-lg font-semibold">Forbidden</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        Platform superadmin role required. Set
        <code className="mx-1 bg-muted px-1 py-0.5">is_superadmin: true</code>
        on the matching user in <code className="mx-1 bg-muted px-1 py-0.5">config.local.yaml</code>
        and restart the API to grant access.
      </p>
    </div>
  );
}
