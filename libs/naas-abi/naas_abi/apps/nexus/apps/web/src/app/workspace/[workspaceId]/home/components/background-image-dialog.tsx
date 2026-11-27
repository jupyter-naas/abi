'use client';

import { Dialog } from '@/components/ui/dialog';
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
    <Dialog
      open={open}
      size="lg"
      title="Edit background image"
      description={`PNG, JPEG, GIF, WEBP or AVIF, up to ${MAX_BACKGROUND_IMAGE_BYTES / (1024 * 1024)} MB.`}
      onClose={onClose}
      data-testid="background-image-dialog"
    >
      <BackgroundImageEditor
        open={open}
        workspaceId={workspaceId}
        currentBackgroundUrl={currentBackgroundUrl}
        onClose={onClose}
        onSaved={onSaved}
        onRemoved={onRemoved}
      />
    </Dialog>
  );
}
