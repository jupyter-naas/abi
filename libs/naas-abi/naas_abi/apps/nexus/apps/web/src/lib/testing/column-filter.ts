/** Picks a value in a settings table's column filter (`SettingsTableHead`), as a person does. */
import { act } from 'react';
import type { Mounted } from './mount';

/**
 * Opens `column`'s filter funnel and ticks `value` among the facets, which load after a
 * debounce: waits for them (up to `timeout` ms, so a busy test run does not fail it), then
 * closes the filter, so the next pick opens it again.
 */
export async function pickColumnFilter(m: Mounted, column: string, value: string, timeout = 3000): Promise<void> {
  await m.click(m.host.querySelector(`[data-filter-trigger="${column}"]`));
  const find = () => {
    const values = document.querySelector(`[data-testid="column-filter-values-${column}"]`);
    const label = [...(values?.querySelectorAll('label') ?? [])].find((candidate) =>
      [...candidate.querySelectorAll('span')].some(
        (span) => span.textContent === value || span.getAttribute('title') === value
      )
    );
    return label?.querySelector('input') ?? null;
  };
  const deadline = Date.now() + timeout;
  let input = find();
  while (!input && Date.now() < deadline) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    input = find();
  }
  if (!input) throw new Error(`no "${value}" in the ${column} column filter`);
  await m.click(input);
  if (document.querySelector(`[data-testid="column-filter-values-${column}"]`)) {
    await m.click(m.host.querySelector(`[data-filter-trigger="${column}"]`));
  }
}
