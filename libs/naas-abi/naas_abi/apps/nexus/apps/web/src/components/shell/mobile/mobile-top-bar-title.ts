/**
 * Mobile top bar title resolution, kept separate from the React component so
 * vitest can cover it without parsing JSX.
 */

export type MobileTopBarTitleInput = {
  variant: 'top' | 'detail';
  titleOverride?: string;
  pageTitle?: string;
  threadTitle?: string;
  workspaceName?: string;
  /** Chat thread detail (not the conversation list). */
  isChatThread?: boolean;
};

export function resolveMobileTopBarTitle({
  variant,
  titleOverride,
  pageTitle,
  threadTitle,
  workspaceName,
  isChatThread = false,
}: MobileTopBarTitleInput): string {
  if (variant === 'detail') {
    return (
      titleOverride ??
      (isChatThread ? threadTitle : undefined) ??
      pageTitle ??
      workspaceName ??
      ''
    );
  }

  return titleOverride ?? pageTitle ?? workspaceName ?? '';
}
