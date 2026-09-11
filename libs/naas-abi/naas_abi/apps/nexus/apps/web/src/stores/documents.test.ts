import { beforeEach, describe, expect, it } from 'vitest';
import { isDocumentsWriteTool, useDocumentsStore } from './documents';

describe('sections sidebar outline', () => {
  beforeEach(() => {
    useDocumentsStore.setState({
      sidebarView: 'documents',
      selectedIndex: 0,
      outline: null,
      reorderOpenDocument: null,
    });
  });

  it('switches the sidebar between Documents and Filmstrip', () => {
    expect(useDocumentsStore.getState().sidebarView).toBe('documents');
    useDocumentsStore.getState().setSidebarView('outline');
    expect(useDocumentsStore.getState().sidebarView).toBe('outline');
  });

  it('keeps the open-document selection for the outline and preview', () => {
    useDocumentsStore.getState().setSelectedIndex(3);
    expect(useDocumentsStore.getState().selectedIndex).toBe(3);
  });

  it('publishes the open document for the sidebar strip', () => {
    useDocumentsStore.getState().setOutline({
      workspaceId: 'ws-1',
      slug: 'pitch',
      html: '<section></section>',
      disabled: false,
    });
    expect(useDocumentsStore.getState().outline?.slug).toBe('pitch');
    useDocumentsStore.getState().setOutline(null);
    expect(useDocumentsStore.getState().outline).toBeNull();
  });
});

describe('isDocumentsWriteTool', () => {
  it('recognizes every document-mutating tool in documents_tools.py', () => {
    expect(isDocumentsWriteTool('write_document_section')).toBe(true);
    expect(isDocumentsWriteTool('write_document_sections')).toBe(true);
    expect(isDocumentsWriteTool('write_document')).toBe(true);
    expect(isDocumentsWriteTool('replace_in_document')).toBe(true);
    expect(isDocumentsWriteTool('insert_section')).toBe(true);
    expect(isDocumentsWriteTool('delete_section')).toBe(true);
    expect(isDocumentsWriteTool('duplicate_section')).toBe(true);
    expect(isDocumentsWriteTool('reorder_sections')).toBe(true);
    expect(isDocumentsWriteTool('apply_document_commands')).toBe(true);
    expect(isDocumentsWriteTool('insert_page_break')).toBe(true);
    expect(isDocumentsWriteTool('insert_heading')).toBe(true);
    expect(isDocumentsWriteTool('insert_paragraph')).toBe(true);
    expect(isDocumentsWriteTool('apply_paragraph_style')).toBe(true);
    expect(isDocumentsWriteTool('create_documents_project')).toBe(true);
  });

  it('ignores read-only and unrelated tools', () => {
    expect(isDocumentsWriteTool('read_document')).toBe(false);
    expect(isDocumentsWriteTool('list_documents_projects')).toBe(false);
    expect(isDocumentsWriteTool('web_search')).toBe(false);
    expect(isDocumentsWriteTool(null)).toBe(false);
    expect(isDocumentsWriteTool(undefined)).toBe(false);
  });
});
