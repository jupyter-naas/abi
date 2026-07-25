/**
 * Which page title applies right now. Kept apart from the React plumbing in
 * shell-title.tsx so it stays testable: the test runner cannot parse JSX while
 * tsconfig keeps jsx: "preserve" for Next.
 */

export interface ShellTitleEntry {
  title?: string;
  subtitle?: string;
  /** The route that registered this title. */
  pathname: string;
}

/**
 * A title only counts for the route that registered it. Routes without a
 * Header (platform admin, for one) must fall through to the caller's fallback
 * rather than inherit the previous page's name.
 */
export function resolveShellTitle(
  entry: ShellTitleEntry | null,
  pathname: string | null
): { title?: string; subtitle?: string } {
  if (!entry || !pathname || entry.pathname !== pathname) return {};
  return { title: entry.title, subtitle: entry.subtitle };
}
