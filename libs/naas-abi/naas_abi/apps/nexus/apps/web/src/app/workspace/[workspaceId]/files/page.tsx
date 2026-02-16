'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { 
  FileCode, 
  Folder, 
  FolderPlus, 
  RefreshCw, 
  Upload, 
  Download, 
  Trash2,
  MoreVertical,
  Grid,
  List,
  Search,
  FlaskConical,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilesStore, type FileInfo } from '@/stores/files';
import { usePrompt, useConfirm } from '@/components/ui/dialogs';

export default function FilesPage() {
  const router = useRouter();
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  
  const {
    files,
    loading,
    error,
    currentPath,
    fetchFiles,
    createFile,
    createFolder,
    deleteFile,
    renameFile,
    uploadFile,
    uploadFiles,
    refreshFiles,
    openFile,
    activeSource,
    syncedFolders,
    fetchLocalFiles,
    setError,
  } = useFilesStore();

  const { prompt, dialog: promptDialog } = usePrompt();
  const { confirm, dialog: confirmDialog } = useConfirm();

  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Helper to open file in Lab
  const handleOpenInLab = (file: FileInfo) => {
    openFile(file.path);
    router.push(`/workspace/${workspaceId}/lab`);
  };
  
  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setActiveContextMenu(null);
    if (activeContextMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [activeContextMenu]);
  
  // Check if we're viewing a synced local folder
  const activeSyncedFolder = syncedFolders.find((f) => f.id === activeSource);
  const isLocalFolder = !!activeSyncedFolder;

  useEffect(() => {
    // Clear any previous errors
    setError(null);
    
    // Fetch files based on active source
    if (isLocalFolder && activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id);
    } else {
      fetchFiles();
    }
  }, [fetchFiles, fetchLocalFiles, isLocalFolder, activeSyncedFolder, setError]);

  // Drag and drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length > 0) {
      await uploadFiles(droppedFiles);
    }
  }, [uploadFiles]);

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      await uploadFiles(selectedFiles);
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Generate unique name if the proposed name already exists
  const getUniqueName = (baseName: string, extension: string = '') => {
    const existingNames = new Set(files.map((f) => f.name.toLowerCase()));
    let name = extension ? `${baseName}${extension}` : baseName;
    let counter = 1;
    
    while (existingNames.has(name.toLowerCase())) {
      name = extension ? `${baseName}-${counter}${extension}` : `${baseName}-${counter}`;
      counter++;
    }
    return name;
  };

  const handleNewFile = async () => {
    const defaultName = getUniqueName('untitled', '.txt');
    const name = await prompt({
      title: 'New File',
      description: 'Enter a name for the new file',
      defaultValue: defaultName,
      confirmLabel: 'Create',
    });
    if (name) {
      const fullPath = currentPath ? `${currentPath}/${name}` : name;
      await createFile(fullPath);
    }
  };

  const handleNewFolder = async () => {
    const defaultName = getUniqueName('new-folder');
    const name = await prompt({
      title: 'New Folder',
      description: 'Enter a name for the new folder',
      defaultValue: defaultName,
      confirmLabel: 'Create',
    });
    if (name) {
      const fullPath = currentPath ? `${currentPath}/${name}` : name;
      await createFolder(fullPath);
    }
  };

  const handleRename = async (file: FileInfo) => {
    const existingNames = new Set(files.map((f) => f.name.toLowerCase()));
    const newName = await prompt({
      title: 'Rename',
      description: `Rename "${file.name}" to:`,
      defaultValue: file.name,
      confirmLabel: 'Rename',
    });
    if (newName && newName !== file.name) {
      if (existingNames.has(newName.toLowerCase()) && newName.toLowerCase() !== file.name.toLowerCase()) {
        // Show a second prompt with the error -- re-trigger rename
        await prompt({
          title: 'Name already exists',
          description: `A file or folder named "${newName}" already exists. Choose a different name.`,
          defaultValue: newName,
          confirmLabel: 'Rename',
        }).then(async (retryName) => {
          if (retryName && retryName !== file.name) {
            const parentPath = file.path.substring(0, file.path.lastIndexOf('/'));
            const newPath = parentPath ? `${parentPath}/${retryName}` : retryName;
            await renameFile(file.path, newPath);
          }
        });
        return;
      }

      const parentPath = file.path.substring(0, file.path.lastIndexOf('/'));
      const newPath = parentPath ? `${parentPath}/${newName}` : newName;
      await renameFile(file.path, newPath);
    }
  };

  const handleDelete = async (file: FileInfo) => {
    const confirmed = await confirm({
      title: `Delete "${file.name}"?`,
      description: file.type === 'folder'
        ? 'This folder and all its contents will be permanently deleted.'
        : 'This file will be permanently deleted.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (confirmed) {
      await deleteFile(file.path);
    }
  };

  const filteredFiles = files.filter(file => 
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatSize = (bytes?: number) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (date?: string) => {
    if (!date) return '—';
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const handleRefresh = () => {
    if (isLocalFolder && activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id, currentPath);
    } else {
      refreshFiles();
    }
  };

  return (
    <>
    {promptDialog}
    {confirmDialog}
    <div className="flex h-full flex-col">
      <Header 
        title={isLocalFolder ? activeSyncedFolder?.name || 'Local Folder' : 'Files'} 
        subtitle={isLocalFolder ? `Synced from your machine` : 'Manage workspace files and folders'} 
      />

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="rounded px-2 py-0.5 hover:bg-destructive/20"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b px-4 py-2">
          <div className="flex items-center gap-2">
            {/* Hide create/upload buttons for local folders (read-only view) */}
            {!isLocalFolder && (
              <>
                <button
                  onClick={handleNewFile}
                  className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  <FileCode size={14} />
                  New File
                </button>
                <button
                  onClick={handleNewFolder}
                  className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  <FolderPlus size={14} />
                  New Folder
                </button>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                >
                  <Upload size={14} />
                  Upload
                </button>
              </>
            )}
            <button
              onClick={handleRefresh}
              disabled={loading}
              className={cn(
                "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted",
                loading && "opacity-50"
              )}
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileInputChange}
              className="hidden"
            />
          </div>

          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-48 rounded-md border bg-transparent pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* View toggle */}
            <div className="flex items-center rounded-md border">
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-l-md",
                  viewMode === 'list' ? 'bg-muted' : 'hover:bg-muted/50'
                )}
              >
                <List size={14} />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-r-md border-l",
                  viewMode === 'grid' ? 'bg-muted' : 'hover:bg-muted/50'
                )}
              >
                <Grid size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Breadcrumb */}
        <div className="flex items-center gap-1 border-b px-4 py-2 text-sm">
          <button
            onClick={() => {
              if (isLocalFolder && activeSyncedFolder) {
                fetchLocalFiles(activeSyncedFolder.id, '');
              } else {
                fetchFiles('');
              }
            }}
            className="text-muted-foreground hover:text-foreground"
          >
            {isLocalFolder ? activeSyncedFolder?.name || 'Root' : 'Root'}
          </button>
          {currentPath && currentPath.split('/').map((part, i, arr) => (
            <span key={i} className="flex items-center gap-1">
              <span className="text-muted-foreground">/</span>
              <button
                onClick={() => {
                  const path = arr.slice(0, i + 1).join('/');
                  if (isLocalFolder && activeSyncedFolder) {
                    fetchLocalFiles(activeSyncedFolder.id, path);
                  } else {
                    fetchFiles(path);
                  }
                }}
                className={cn(
                  i === arr.length - 1 ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {part}
              </button>
            </span>
          ))}
        </div>

        {/* Content */}
        <div 
          className={cn(
            "relative flex-1 overflow-auto p-4",
            isDragging && "bg-primary/5"
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Drag overlay */}
          {isDragging && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed border-primary p-8">
                <Upload size={48} className="text-primary" />
                <p className="text-lg font-medium">Drop files here to upload</p>
                <p className="text-sm text-muted-foreground">Files will be uploaded to the current folder</p>
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {filteredFiles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                <Folder size={32} className="text-muted-foreground" />
              </div>
              <h3 className="mb-2 text-lg font-medium">
                {searchQuery ? 'No files found' : isLocalFolder ? 'Folder is empty' : 'No files yet'}
              </h3>
              <p className="mb-4 text-muted-foreground">
                {searchQuery 
                  ? 'Try a different search term' 
                  : isLocalFolder 
                    ? 'This folder has no files or subfolders'
                    : 'Create a file or folder to get started'}
              </p>
              {!searchQuery && !isLocalFolder && (
                <div className="flex flex-col items-center gap-4">
                  <div className="flex gap-2">
                    <button
                      onClick={handleNewFile}
                      className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                    >
                      <FileCode size={14} />
                      New File
                    </button>
                    <button
                      onClick={handleNewFolder}
                      className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm"
                    >
                      <FolderPlus size={14} />
                      New Folder
                    </button>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="flex items-center gap-2 rounded-md border px-4 py-2 text-sm"
                    >
                      <Upload size={14} />
                      Upload Files
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Or drag and drop files anywhere on this page
                  </p>
                </div>
              )}
            </div>
          ) : viewMode === 'list' ? (
            /* List view */
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">Size</th>
                  <th className="pb-2 font-medium">Modified</th>
                  <th className="pb-2 font-medium w-10"></th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.map((file) => (
                  <tr
                    key={file.path}
                    className="group border-b border-border/50 hover:bg-muted/50"
                  >
                    <td className="py-2">
                      <button
                        onClick={() => {
                          if (file.type === 'folder') {
                            if (isLocalFolder && activeSyncedFolder) {
                              fetchLocalFiles(activeSyncedFolder.id, file.path);
                            } else {
                              fetchFiles(file.path);
                            }
                          } else {
                            openFile(file.path);
                          }
                        }}
                        className="flex items-center gap-2 text-sm hover:text-primary"
                      >
                        {file.type === 'folder' ? (
                          <Folder size={16} className="text-muted-foreground" />
                        ) : (
                          <FileCode size={16} className="text-muted-foreground" />
                        )}
                        {file.name}
                      </button>
                    </td>
                    <td className="py-2 text-sm text-muted-foreground">
                      {file.type === 'folder' ? '—' : formatSize(file.size)}
                    </td>
                    <td className="py-2 text-sm text-muted-foreground">
                      {formatDate(file.modified)}
                    </td>
                    <td className="py-2">
                      <div className="relative">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveContextMenu(activeContextMenu === file.path ? null : file.path);
                          }}
                          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground/50 hover:bg-muted hover:text-foreground group-hover:text-muted-foreground"
                        >
                          <MoreVertical size={14} />
                        </button>
                        {activeContextMenu === file.path && (
                          <div className="absolute right-0 top-full z-50 min-w-[140px] rounded-md border bg-popover py-1 shadow-lg">
                            {file.type === 'file' && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveContextMenu(null);
                                  handleOpenInLab(file);
                                }}
                                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted"
                              >
                                <FlaskConical size={12} />
                                Open in Lab
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveContextMenu(null);
                                handleRename(file);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted"
                            >
                              Rename
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setActiveContextMenu(null);
                                handleDelete(file);
                              }}
                              className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            /* Grid view */
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {filteredFiles.map((file) => (
                <button
                  key={file.path}
                  onClick={() => {
                    if (file.type === 'folder') {
                      if (isLocalFolder && activeSyncedFolder) {
                        fetchLocalFiles(activeSyncedFolder.id, file.path);
                      } else {
                        fetchFiles(file.path);
                      }
                    } else {
                      openFile(file.path);
                    }
                  }}
                  className="group flex flex-col items-center gap-2 rounded-lg border p-4 hover:bg-muted/50"
                >
                  {file.type === 'folder' ? (
                    <Folder size={40} className="text-muted-foreground" />
                  ) : (
                    <FileCode size={40} className="text-muted-foreground" />
                  )}
                  <span className="w-full truncate text-center text-sm">{file.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
