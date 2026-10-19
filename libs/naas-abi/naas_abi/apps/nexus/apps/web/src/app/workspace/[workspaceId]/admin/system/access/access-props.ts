import type { IamAdminApi } from '@/lib/iam-admin/api';

/** What every Access view gets: the API, and which `iam:*` actions the caller may perform
 *  (`GET /api/iam/admin/access`), so a view shows only the buttons that will answer. */
export type AccessViewProps = {
  api: IamAdminApi;
  can: (action: string) => boolean;
  /** Bumped by the header's refresh button. */
  nonce?: number;
};
