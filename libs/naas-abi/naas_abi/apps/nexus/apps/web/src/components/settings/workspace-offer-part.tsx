'use client';

/**
 * A part of the workspace's offer ("<W> access") on its own settings page: what Agents, Apps,
 * Workflows (and pipelines) or Models it offers, each switch saved at once as the caller. The
 * policy's page shows the document only; the offer is changed from these pages.
 */
import { SettingsSection } from '@/components/settings/settings-ui';
import { WorkspaceOfferEditor, type OfferPart } from '@/components/access/offer/offer-editor';

export function WorkspaceOfferPart({
  workspaceId,
  parts,
  description,
  onChanged,
}: {
  workspaceId: string;
  parts: readonly OfferPart[];
  /** Under the section's title; the page's header says it when left out. */
  description?: string;
  /** Told after each change, e.g. to read the page's list again. */
  onChanged?: () => void;
}) {
  return (
    <SettingsSection title="Offered in this workspace" description={description}>
      <div data-offer-part={parts.join(' ')}>
        <WorkspaceOfferEditor workspaceId={workspaceId} parts={parts} bare onChanged={onChanged} />
      </div>
    </SettingsSection>
  );
}
