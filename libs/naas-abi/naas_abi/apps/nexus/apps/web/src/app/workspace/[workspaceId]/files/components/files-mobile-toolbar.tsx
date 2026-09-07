'use client';

import { Grid, List, MoreVertical, Plus, RefreshCw, Search } from 'lucide-react';
import './files-components.css';

type FilesMobileToolbarProps = {
  isLocalFolder: boolean;
  loading: boolean;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  viewMode: 'list' | 'grid';
  onViewModeChange: (mode: 'list' | 'grid') => void;
  onRefresh: () => void;
  onAddClick: () => void;
  menuOpen: boolean;
  onMenuToggle: (e: React.MouseEvent) => void;
};

export function FilesMobileToolbar({
  isLocalFolder,
  loading,
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onRefresh,
  onAddClick,
  menuOpen,
  onMenuToggle,
}: FilesMobileToolbarProps) {
  return (
    <div className="files-mobile-toolbar">
      <div className="files-mobile-toolbar-row">
        {!isLocalFolder && (
          <button type="button" onClick={onAddClick} className="files-mobile-toolbar-add">
            <Plus size={18} />
            Add
          </button>
        )}
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className={`files-mobile-toolbar-icon-btn${loading ? ' is-disabled' : ''}`}
          aria-label="Refresh"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
        </button>
        <div className="files-mobile-toolbar-spacer" />
        <div className="relative">
          <button
            type="button"
            onClick={onMenuToggle}
            className="files-mobile-toolbar-icon-btn"
            aria-label="More actions"
          >
            <MoreVertical size={18} />
          </button>
          {menuOpen && (
            <div className="files-mobile-toolbar-menu">
              <button
                type="button"
                onClick={() => onViewModeChange('list')}
                className={`files-mobile-toolbar-menu-item${viewMode === 'list' ? ' is-active' : ''}`}
              >
                <List size={16} />
                List view
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange('grid')}
                className={`files-mobile-toolbar-menu-item${viewMode === 'grid' ? ' is-active' : ''}`}
              >
                <Grid size={16} />
                Grid view
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="files-mobile-toolbar-search">
        <Search size={16} className="files-mobile-toolbar-search-icon" />
        <input
          type="search"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label="Search files"
        />
      </div>
    </div>
  );
}
