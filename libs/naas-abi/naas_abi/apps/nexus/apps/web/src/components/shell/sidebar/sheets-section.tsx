'use client';

import { LayoutGrid } from 'lucide-react';
import { SHEETS_KIND } from '@/components/office/office-kinds';
import { SheetsFilmstrip } from '@/components/sheets/sheets-filmstrip';
import { clampTabIndex, parseWorkbookTabs } from '@/components/sheets/sheets-outline';
import { openSheetsAgentPane, sheetsApiErrorMessage, startNewWorkbook } from '@/lib/create-sheets-project';
import { patchSheetsProject } from '@/lib/sheets-project-actions';
import { SHEETS_DECK_UPDATED_EVENT, useSheetsStore, type SheetsSidebarView } from '@/stores/sheets';
import { OfficeSection, type OfficeSectionConfig } from './office-section';

export const SHEETS_SECTION: OfficeSectionConfig<SheetsSidebarView> = {
  kind: SHEETS_KIND,
  useStore: useSheetsStore,
  updatedEvent: SHEETS_DECK_UPDATED_EVENT,
  label: 'Sheets',
  description: 'Spreadsheets in this workspace',
  views: {
    tree: { id: 'sheets', label: 'Sheets' },
    detail: {
      id: 'filmstrip',
      label: 'Filmstrip',
      icon: <LayoutGrid size={14} />,
      loading: 'Loading sheets…',
      empty: 'Open a workbook to see sheet tabs.',
    },
  },
  newItem: { label: 'New workbook', title: 'New workbook' },
  create: {
    start: startNewWorkbook,
    errorMessage: (message) => sheetsApiErrorMessage(message, 'Could not create the workbook.'),
  },
  patch: patchSheetsProject,
  openAgentPane: openSheetsAgentPane,
};

/** Sheets sidebar: the file tree, or the open workbook's tabs. */
export function SheetsSection(props: { collapsed: boolean; detailOnly?: boolean }) {
  const filmstrip = useSheetsStore((s) => s.filmstrip);
  const selectedIndex = useSheetsStore((s) => s.selectedIndex);
  const setSelectedIndex = useSheetsStore((s) => s.setSelectedIndex);
  const reorder = useSheetsStore((s) => s.reorderOpenWorkbook);
  return (
    <OfficeSection
      {...props}
      config={SHEETS_SECTION}
      hasOpenSession={Boolean(filmstrip)}
      renderDetail={() => {
        if (!filmstrip?.html) return null;
        const tabs = parseWorkbookTabs(filmstrip.html);
        return (
          <SheetsFilmstrip
            html={filmstrip.html}
            workspaceId={filmstrip.workspaceId}
            slug={filmstrip.slug}
            tabs={tabs}
            selectedIndex={clampTabIndex(selectedIndex, tabs.length)}
            disabled={filmstrip.disabled}
            onSelect={setSelectedIndex}
            onReorder={(fromIndex, toIndex) => reorder?.(fromIndex, toIndex)}
          />
        );
      }}
    />
  );
}
