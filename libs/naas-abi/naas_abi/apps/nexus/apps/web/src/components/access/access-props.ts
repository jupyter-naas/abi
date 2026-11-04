import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { AccessDirectory } from './access-directory';
import type { AccessScope } from './access-scope';

/** Opens a person's or a group's page (`?section=people&person=<id>`,
 *  `?section=groups&group=<id>`), from wherever a section names them. */
export type AccessNavigation = {
  person: (id: string, label?: string, memberId?: string) => void;
  group: (id: string, label?: string) => void;
};

/** What every section gets: the API, the scope it manages, the people there, and which
 *  actions the caller may perform at that scope (`GET /api/iam/admin/access?scope=`), so a
 *  section shows only the buttons that will answer. */
export type AccessViewProps = {
  api: IamAdminApi;
  can: (action: string) => boolean;
  scope: AccessScope;
  directory: AccessDirectory;
  /** Bumped by the page's refresh button. */
  nonce?: number;
  /** Opens a person's or a group's page; without it, names are not links. */
  open?: AccessNavigation;
};

/** A section of what only the platform administers (service accounts, approvals, the
 *  simulator, the audit): it needs no scope. */
export type PlatformViewProps = Pick<AccessViewProps, 'api' | 'can' | 'nonce'>;
