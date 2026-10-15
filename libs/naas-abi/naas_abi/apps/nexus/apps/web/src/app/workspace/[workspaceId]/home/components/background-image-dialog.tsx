'use client';

import { ModalBackdrop } from '@/components/ui/dialogs';
import { MAX_BACKGROUND_IMAGE_BYTES } from '@/lib/home-background';
import { BackgroundImageEditor } from './background-image-editor';

/** Home → Edit → Desktop wallpaper: the shared wallpaper editor in a dialog. */
export function BackgroundImageDialog({
  open,
  workspaceId,
  currentBackgroundUrl,
  onClose,
  onSaved,
  onRemoved,
}: {
  open: boolean;
  workspaceId: string;
  /** The workspace's `background_image_url`, if any. */
  currentBackgroundUrl?: string;
  onClose: () => void;
  /** The workspace's new `background_image_url`, as the API returned it. */
  onSaved: (backgroundImageUrl: string) => void;
  /** The wallpaper was removed (moved to the drive's archives). */
  onRemoved: () => void;
}) {
  return (
    <ModalBackdrop open={open} onClose={onClose} widthClassName="max-w-2xl">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="background-image-dialog-title"
        className="border border-border bg-background p-6 shadow-2xl"
        data-testid="background-image-dialog"
      >
        <h3 id="background-image-dialog-title" className="text-base font-semibold text-foreground">
          Edit background image
        </h3>
        <p className="mb-4 mt-1 text-sm text-muted-foreground">
          PNG, JPEG, GIF, WEBP or AVIF, up to {MAX_BACKGROUND_IMAGE_BYTES / (1024 * 1024)} MB.
        </p>
        <BackgroundImageEditor
          open={open}
          workspaceId={workspaceId}
          currentBackgroundUrl={currentBackgroundUrl}
          onClose={onClose}
          onSaved={onSaved}
          onRemoved={onRemoved}
        />
      </div>
    </ModalBackdrop>
  );
}
