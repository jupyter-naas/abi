import { redirect } from 'next/navigation';

/**
 * Legacy Explore entry point.
 * Composer at /graph/explore-next is the only Explore UI; keep this route as a redirect
 * so old bookmarks and deep links do not 404.
 */
export default function LegacyExploreRedirect({
  params,
}: {
  params: { workspaceId: string };
}) {
  redirect(`/workspace/${params.workspaceId}/graph/explore-next`);
}
