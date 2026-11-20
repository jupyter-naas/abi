'use client';

import { AccountMenu } from '../account-menu';

/** The identity row at the bottom of the dock. Clicking it opens the account menu. */
export function DockProfile({ labeled }: { labeled: boolean }) {
  return <AccountMenu labeled={labeled} />;
}
