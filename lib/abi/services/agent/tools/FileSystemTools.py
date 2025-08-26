"""
File System Tools for ABI Agents

This module provides comprehensive file system capabilities for ABI agents,
enabling them to read, write, and manage files directly on the file system.
"""

import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from abi import logger
from .FileSystemConfig import config_manager


class FileReadRequest(BaseModel):
    """Request model for reading files."""
    file_path: str = Field(..., description="Path to the file to read")
    encoding: str = Field(default="utf-8", description="File encoding (default: utf-8)")


class FileWriteRequest(BaseModel):
    """Request model for writing files."""
    file_path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")
    encoding: str = Field(default="utf-8", description="File encoding (default: utf-8)")
    overwrite: bool = Field(default=True, description="Whether to overwrite existing files")


class FileListRequest(BaseModel):
    """Request model for listing directory contents."""
    directory_path: str = Field(..., description="Path to the directory to list")
    include_hidden: bool = Field(default=False, description="Whether to include hidden files")
    recursive: bool = Field(default=False, description="Whether to list recursively")


class FileDeleteRequest(BaseModel):
    """Request model for deleting files."""
    file_path: str = Field(..., description="Path to the file or directory to delete")
    recursive: bool = Field(default=False, description="Whether to delete directories recursively")


class FileCopyRequest(BaseModel):
    """Request model for copying files."""
    source_path: str = Field(..., description="Path to the source file or directory")
    destination_path: str = Field(..., description="Path to the destination")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing files")


class FileMoveRequest(BaseModel):
    """Request model for moving files."""
    source_path: str = Field(..., description="Path to the source file or directory")
    destination_path: str = Field(..., description="Path to the destination")


class FileInfoRequest(BaseModel):
    """Request model for getting file information."""
    file_path: str = Field(..., description="Path to the file to get information about")


class DirectoryCreateRequest(BaseModel):
    """Request model for creating directories."""
    directory_path: str = Field(..., description="Path to the directory to create")
    parents: bool = Field(default=True, description="Whether to create parent directories")


class FileSearchRequest(BaseModel):
    """Request model for searching files."""
    search_path: str = Field(..., description="Path to search in")
    pattern: str = Field(..., description="File pattern to search for (e.g., '*.txt')")
    recursive: bool = Field(default=True, description="Whether to search recursively")


class FileSystemTools:
    """File system tools for ABI agents."""
    
    def __init__(self, config_name: str = "development", base_path: Optional[str] = None):
        """
        Initialize file system tools.
        
        Args:
            config_name: Name of the configuration to use
            base_path: Optional override for base path
        """
        self.config = config_manager.get_config(config_name)
        
        if base_path:
            self.config.base_path = base_path
        
        self.base_path = Path(self.config.base_path).resolve()
        logger.info(f"FileSystemTools initialized with config '{config_name}' and base path: {self.base_path}")
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the base path."""
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self.base_path / resolved
        return resolved.resolve()
    
    def _validate_path(self, path: Path) -> None:
        """Validate that a path is within the allowed base path and permissions."""
        try:
            path.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path {path} is outside the allowed base path {self.base_path}")
        
        # Check configuration permissions
        if not self.config.validate_path(str(path)):
            raise ValueError(f"Path {path} is not allowed by current configuration")
    
    def read_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        Read a file and return its contents.
        
        Args:
            file_path: Path to the file to read
            encoding: File encoding
            
        Returns:
            File contents as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is outside allowed base path or operation not permitted
        """
        # Check permissions
        if not self.config.permissions.can_read:
            raise ValueError("Read operation not permitted by current configuration")
        
        path = self._resolve_path(file_path)
        self._validate_path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        # Validate file size
        file_size = path.stat().st_size
        if not self.config.validate_file_size(file_size):
            raise ValueError(f"File size {file_size} exceeds limit of {self.config.permissions.max_file_size}")
        
        # Validate file extension
        if not self.config.validate_extension(path.suffix):
            raise ValueError(f"File extension '{path.suffix}' not allowed by current configuration")
        
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            logger.info(f"Successfully read file: {file_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise
    
    def write_file(self, file_path: str, content: str, encoding: str = "utf-8", overwrite: bool = True) -> str:
        """
        Write content to a file.
        
        Args:
            file_path: Path to the file to write
            content: Content to write
            encoding: File encoding
            overwrite: Whether to overwrite existing files
            
        Returns:
            Success message
            
        Raises:
            ValueError: If path is outside allowed base path, operation not permitted, or file exists and overwrite=False
        """
        # Check permissions
        if not self.config.permissions.can_write:
            raise ValueError("Write operation not permitted by current configuration")
        
        path = self._resolve_path(file_path)
        self._validate_path(path)
        
        # Validate file extension
        if not self.config.validate_extension(path.suffix):
            raise ValueError(f"File extension '{path.suffix}' not allowed by current configuration")
        
        # Validate content size
        content_size = len(content.encode(encoding))
        if not self.config.validate_file_size(content_size):
            raise ValueError(f"Content size {content_size} exceeds limit of {self.config.permissions.max_file_size}")
        
        if path.exists() and not overwrite:
            raise ValueError(f"File already exists and overwrite=False: {file_path}")
        
        try:
            # Create parent directories if they don't exist
            if self.config.permissions.can_create_directories:
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                if not path.parent.exists():
                    raise ValueError("Cannot create directories - operation not permitted")
            
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
            
            logger.info(f"Successfully wrote file: {file_path}")
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            raise
    
    def list_directory(self, directory_path: str, include_hidden: bool = False, recursive: bool = False) -> Dict[str, Any]:
        """
        List contents of a directory.
        
        Args:
            directory_path: Path to the directory to list
            include_hidden: Whether to include hidden files
            recursive: Whether to list recursively
            
        Returns:
            Dictionary with directory information
            
        Raises:
            FileNotFoundError: If directory doesn't exist
            ValueError: If path is outside allowed base path
        """
        path = self._resolve_path(directory_path)
        self._validate_path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        try:
            items = []
            
            if recursive:
                for item in path.rglob('*'):
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    items.append({
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'type': 'file' if item.is_file() else 'directory',
                        'size': item.stat().st_size if item.is_file() else None
                    })
            else:
                for item in path.iterdir():
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    items.append({
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'type': 'file' if item.is_file() else 'directory',
                        'size': item.stat().st_size if item.is_file() else None
                    })
            
            result = {
                'directory': str(path.relative_to(self.base_path)),
                'items': items,
                'total_items': len(items)
            }
            
            logger.info(f"Successfully listed directory: {directory_path} ({len(items)} items)")
            return result
        except Exception as e:
            logger.error(f"Error listing directory {directory_path}: {e}")
            raise
    
    def delete_file(self, file_path: str, recursive: bool = False) -> str:
        """
        Delete a file or directory.
        
        Args:
            file_path: Path to the file or directory to delete
            recursive: Whether to delete directories recursively
            
        Returns:
            Success message
            
        Raises:
            FileNotFoundError: If file/directory doesn't exist
            ValueError: If path is outside allowed base path or operation not permitted
        """
        # Check permissions
        if not self.config.permissions.can_delete:
            raise ValueError("Delete operation not permitted by current configuration")
        
        path = self._resolve_path(file_path)
        self._validate_path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"File or directory not found: {file_path}")
        
        try:
            if path.is_file():
                path.unlink()
                logger.info(f"Successfully deleted file: {file_path}")
                return f"Successfully deleted file: {file_path}"
            elif path.is_dir():
                if recursive:
                    shutil.rmtree(path)
                    logger.info(f"Successfully deleted directory recursively: {file_path}")
                    return f"Successfully deleted directory recursively: {file_path}"
                else:
                    path.rmdir()
                    logger.info(f"Successfully deleted empty directory: {file_path}")
                    return f"Successfully deleted empty directory: {file_path}"
            else:
                raise ValueError(f"Path is neither file nor directory: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting {file_path}: {e}")
            raise
    
    def copy_file(self, source_path: str, destination_path: str, overwrite: bool = False) -> str:
        """
        Copy a file or directory.
        
        Args:
            source_path: Path to the source file or directory
            destination_path: Path to the destination
            overwrite: Whether to overwrite existing files
            
        Returns:
            Success message
            
        Raises:
            FileNotFoundError: If source doesn't exist
            ValueError: If paths are outside allowed base path or operation not permitted
        """
        # Check permissions
        if not self.config.permissions.can_copy_files:
            raise ValueError("Copy operation not permitted by current configuration")
        
        source = self._resolve_path(source_path)
        destination = self._resolve_path(destination_path)
        
        self._validate_path(source)
        self._validate_path(destination)
        
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")
        
        if destination.exists() and not overwrite:
            raise ValueError(f"Destination already exists and overwrite=False: {destination_path}")
        
        try:
            if source.is_file():
                shutil.copy2(source, destination)
                logger.info(f"Successfully copied file: {source_path} -> {destination_path}")
                return f"Successfully copied file: {source_path} -> {destination_path}"
            elif source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=overwrite)
                logger.info(f"Successfully copied directory: {source_path} -> {destination_path}")
                return f"Successfully copied directory: {source_path} -> {destination_path}"
            else:
                raise ValueError(f"Source is neither file nor directory: {source_path}")
        except Exception as e:
            logger.error(f"Error copying {source_path} to {destination_path}: {e}")
            raise
    
    def move_file(self, source_path: str, destination_path: str) -> str:
        """
        Move a file or directory.
        
        Args:
            source_path: Path to the source file or directory
            destination_path: Path to the destination
            
        Returns:
            Success message
            
        Raises:
            FileNotFoundError: If source doesn't exist
            ValueError: If paths are outside allowed base path or operation not permitted
        """
        # Check permissions
        if not self.config.permissions.can_move_files:
            raise ValueError("Move operation not permitted by current configuration")
        
        source = self._resolve_path(source_path)
        destination = self._resolve_path(destination_path)
        
        self._validate_path(source)
        self._validate_path(destination)
        
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")
        
        try:
            shutil.move(str(source), str(destination))
            logger.info(f"Successfully moved: {source_path} -> {destination_path}")
            return f"Successfully moved: {source_path} -> {destination_path}"
        except Exception as e:
            logger.error(f"Error moving {source_path} to {destination_path}: {e}")
            raise
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get information about a file or directory.
        
        Args:
            file_path: Path to the file or directory
            
        Returns:
            Dictionary with file information
            
        Raises:
            FileNotFoundError: If file/directory doesn't exist
            ValueError: If path is outside allowed base path
        """
        path = self._resolve_path(file_path)
        self._validate_path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"File or directory not found: {file_path}")
        
        try:
            stat = path.stat()
            info = {
                'name': path.name,
                'path': str(path.relative_to(self.base_path)),
                'absolute_path': str(path),
                'type': 'file' if path.is_file() else 'directory',
                'size': stat.st_size if path.is_file() else None,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'accessed': stat.st_atime,
                'permissions': oct(stat.st_mode)[-3:],
                'owner': stat.st_uid,
                'group': stat.st_gid
            }
            
            if path.is_file():
                info['extension'] = path.suffix
                info['mime_type'] = self._guess_mime_type(path)
            
            logger.info(f"Successfully got file info: {file_path}")
            return info
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            raise
    
    def create_directory(self, directory_path: str, parents: bool = True) -> str:
        """
        Create a directory.
        
        Args:
            directory_path: Path to the directory to create
            parents: Whether to create parent directories
            
        Returns:
            Success message
            
        Raises:
            ValueError: If path is outside allowed base path or operation not permitted
        """
        # Check permissions
        if not self.config.permissions.can_create_directories:
            raise ValueError("Directory creation not permitted by current configuration")
        
        path = self._resolve_path(directory_path)
        self._validate_path(path)
        
        try:
            path.mkdir(parents=parents, exist_ok=True)
            logger.info(f"Successfully created directory: {directory_path}")
            return f"Successfully created directory: {directory_path}"
        except Exception as e:
            logger.error(f"Error creating directory {directory_path}: {e}")
            raise
    
    def search_files(self, search_path: str, pattern: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Search for files matching a pattern.
        
        Args:
            search_path: Path to search in
            pattern: File pattern to search for (e.g., '*.txt')
            recursive: Whether to search recursively
            
        Returns:
            List of matching files
            
        Raises:
            FileNotFoundError: If search path doesn't exist
            ValueError: If path is outside allowed base path
        """
        path = self._resolve_path(search_path)
        self._validate_path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Search path not found: {search_path}")
        
        if not path.is_dir():
            raise ValueError(f"Search path is not a directory: {search_path}")
        
        try:
            matches = []
            
            if recursive:
                search_method = path.rglob
            else:
                search_method = path.glob
            
            for item in search_method(pattern):
                if item.is_file():
                    matches.append({
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'size': item.stat().st_size,
                        'modified': item.stat().st_mtime
                    })
            
            logger.info(f"Successfully searched for '{pattern}' in {search_path}: {len(matches)} matches")
            return matches
        except Exception as e:
            logger.error(f"Error searching for '{pattern}' in {search_path}: {e}")
            raise
    
    def _guess_mime_type(self, path: Path) -> str:
        """Guess MIME type based on file extension."""
        extension = path.suffix.lower()
        mime_types = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.py': 'text/x-python',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.css': 'text/css',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.csv': 'text/csv',
            '.yaml': 'application/x-yaml',
            '.yml': 'application/x-yaml',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        return mime_types.get(extension, 'application/octet-stream')
    
    def as_tools(self) -> List[StructuredTool]:
        """Convert file system operations to LangChain tools."""
        return [
            StructuredTool(
                name="read_file",
                description="Read the contents of a file",
                func=self.read_file,
                args_schema=FileReadRequest
            ),
            StructuredTool(
                name="write_file",
                description="Write content to a file",
                func=self.write_file,
                args_schema=FileWriteRequest
            ),
            StructuredTool(
                name="list_directory",
                description="List contents of a directory",
                func=self.list_directory,
                args_schema=FileListRequest
            ),
            StructuredTool(
                name="delete_file",
                description="Delete a file or directory",
                func=self.delete_file,
                args_schema=FileDeleteRequest
            ),
            StructuredTool(
                name="copy_file",
                description="Copy a file or directory",
                func=self.copy_file,
                args_schema=FileCopyRequest
            ),
            StructuredTool(
                name="move_file",
                description="Move a file or directory",
                func=self.move_file,
                args_schema=FileMoveRequest
            ),
            StructuredTool(
                name="get_file_info",
                description="Get information about a file or directory",
                func=self.get_file_info,
                args_schema=FileInfoRequest
            ),
            StructuredTool(
                name="create_directory",
                description="Create a directory",
                func=self.create_directory,
                args_schema=DirectoryCreateRequest
            ),
            StructuredTool(
                name="search_files",
                description="Search for files matching a pattern",
                func=self.search_files,
                args_schema=FileSearchRequest
            )
        ]
