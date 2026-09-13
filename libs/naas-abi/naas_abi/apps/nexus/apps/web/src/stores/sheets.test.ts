import { beforeEach, describe, expect, it } from 'vitest';
import { isSheetsWriteTool, useSheetsStore } from './sheets';

describe('sheets sidebar filmstrip', () => {
  beforeEach(() => {
    useSheetsStore.setState({
      sidebarView: 'sheets',
      selectedIndex: 0,
      filmstrip: null,
      reorderOpenWorkbook: null,
    });
  });

  it('switches the sidebar between Workbooks and Filmstrip', () => {
    expect(useSheetsStore.getState().sidebarView).toBe('sheets');
    useSheetsStore.getState().setSidebarView('filmstrip');
    expect(useSheetsStore.getState().sidebarView).toBe('filmstrip');
  });

  it('keeps the open-workbook selection for the filmstrip and preview', () => {
    useSheetsStore.getState().setSelectedIndex(3);
    expect(useSheetsStore.getState().selectedIndex).toBe(3);
  });

  it('publishes the open workbook for the sidebar strip', () => {
    useSheetsStore.getState().setFilmstrip({
      workspaceId: 'ws-1',
      slug: 'pitch',
      html: '<section></section>',
      disabled: false,
    });
    expect(useSheetsStore.getState().filmstrip?.slug).toBe('pitch');
    useSheetsStore.getState().setFilmstrip(null);
    expect(useSheetsStore.getState().filmstrip).toBeNull();
  });
});

describe('isSheetsWriteTool', () => {
  it('recognizes every workbook-mutating tool in sheets_tools.py', () => {
    expect(isSheetsWriteTool('write_sheets_section')).toBe(true);
    expect(isSheetsWriteTool('write_sheets_sections')).toBe(true);
    expect(isSheetsWriteTool('write_sheets_workbook')).toBe(true);
    expect(isSheetsWriteTool('replace_in_sheets_workbook')).toBe(true);
    expect(isSheetsWriteTool('insert_slide')).toBe(true);
    expect(isSheetsWriteTool('delete_slide')).toBe(true);
    expect(isSheetsWriteTool('duplicate_slide')).toBe(true);
    expect(isSheetsWriteTool('reorder_sheets')).toBe(true);
    expect(isSheetsWriteTool('create_sheets_project')).toBe(true);
    expect(isSheetsWriteTool('evaluate_sheets_formulas')).toBe(true);
    expect(isSheetsWriteTool('import_dataset_to_sheet')).toBe(true);
  });

  it('ignores read-only and unrelated tools', () => {
    expect(isSheetsWriteTool('read_sheets_workbook')).toBe(false);
    expect(isSheetsWriteTool('list_sheets_projects')).toBe(false);
    expect(isSheetsWriteTool('web_search')).toBe(false);
    expect(isSheetsWriteTool(null)).toBe(false);
    expect(isSheetsWriteTool(undefined)).toBe(false);
  });
});
