/** Entity and company labels are shown in uppercase across the portal. */
export function formatEntityName(name: string): string {
  return name.toLocaleUpperCase('fr-FR');
}
