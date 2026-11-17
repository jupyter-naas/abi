/**
 * Put the tenant's radius on the document so every page, including those
 * outside the workspace shell, follows `data-org-branded` and
 * `--org-border-radius`. A workspace then overwrites `--org-border-radius`
 * with its organization's value.
 */
export function applyTenantShellBranding(
  root: HTMLElement,
  radius: string | undefined,
): void {
  root.dataset.orgBranded = 'true';
  root.style.setProperty('--org-border-radius', `${radius || '0'}px`);
}
