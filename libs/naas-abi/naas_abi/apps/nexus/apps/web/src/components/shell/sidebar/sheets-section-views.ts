export function sheetsFilmstripEmptyCopy(hasOpenWorkbookSession: boolean): string {
  return hasOpenWorkbookSession ? 'Loading sheets…' : 'Open a workbook to see sheet tabs.';
}
