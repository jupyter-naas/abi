'use client';

import { useId } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModalBackdrop } from '@/components/ui/dialogs';
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
  const titleId = useId();
  return (
    <ModalBackdrop open={open} onClose={onClose} widthClassName="max-w-2xl">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="border border-border bg-background p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 id={titleId} className="text-base font-semibold text-foreground">
              Invite user
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Type their name or email. Someone of this workspace&apos;s organization is added to it,
              with or without an invitation; anyone else can be created.
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close" data-action="close">
            <X size={16} />
          </Button>
        </div>
        <div className="mt-4">
          <AddPeople
            {...props}
            autoFocus
            onAdded={async (candidate, emailSent) => {
              await onAdded(candidate, emailSent);
              onClose();
            }}
          />
        </div>
      </div>
    </ModalBackdrop>
  );
}
