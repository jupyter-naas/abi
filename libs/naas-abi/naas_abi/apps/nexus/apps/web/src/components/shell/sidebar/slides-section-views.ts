export function slidesFilmstripEmptyCopy(hasOpenDeckSession: boolean): string {
  return hasOpenDeckSession ? 'Loading slides…' : 'Open a deck to see slides.';
}
