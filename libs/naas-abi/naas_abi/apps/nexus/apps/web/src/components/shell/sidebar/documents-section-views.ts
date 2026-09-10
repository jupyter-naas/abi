export function sectionsFilmstripEmptyCopy(hasOpenDocumentSession: boolean): string {
  return hasOpenDocumentSession ? 'Loading sections…' : 'Open a document to see documents.';
}
