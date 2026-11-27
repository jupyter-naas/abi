'use client';

import { Dialog } from '@/components/ui/dialog';
import { AddPeople } from './add-people';

type AddPeopleProps = Parameters<typeof AddPeople>[0];

/**
 * Invite user (Workspace settings › Users › Invite user): the search for a person by name or
 * email, in a modal dialog. Someone of the workspace's organization is added to it (Add to
 * workspace) or added and sent an invitation (Invite & send invitation), then it closes; with no
 * match, Create user opens the create page prefilled. Escape closes the suggestions first, then
 * the dialog.
 */
export function AddPeopleDialog({
  open,
  onClose,
  onAdded,
  ...props
}: AddPeopleProps & { open: boolean; onClose: () => void }) {
  return (
    <Dialog
      open={open}
      size="lg"
      title="Invite user"
      description={
        <>
          Type their name or email. Someone of this workspace&apos;s organization is added to it, with or without
          an invitation; anyone else can be created.
        </>
      }
      onClose={onClose}
    >
      <AddPeople
        {...props}
        autoFocus
        onAdded={async (candidate, emailSent) => {
          await onAdded(candidate, emailSent);
          onClose();
        }}
      />
    </Dialog>
  );
}
