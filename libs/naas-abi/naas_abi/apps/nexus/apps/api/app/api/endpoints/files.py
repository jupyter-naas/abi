"""File management API endpoints with local filesystem and S3/MinIO support."""

import os
import io
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from pydantic import BaseModel, Field

from app.api.endpoints.auth import get_current_user_required

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# Storage configuration
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "local")  # 'local' or 's3'
LOCAL_STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", "/tmp/nexus-files"))

# S3/MinIO configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "nexus-files")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# Lazy S3 client initialization
_s3_client = None


def get_s3_client():
    """Get or create S3 client.
    
    Supports:
    - MinIO (local): S3_ENDPOINT=http://localhost:9000
    - Cloudflare R2: S3_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
    - AWS S3: S3_ENDPOINT= (empty)
    - DigitalOcean Spaces, Backblaze B2, etc.
    """
    global _s3_client
    if _s3_client is None and STORAGE_TYPE == "s3":
        try:
            import boto3
            from botocore.config import Config
            
            # Build client config
            client_kwargs = {
                'aws_access_key_id': S3_ACCESS_KEY,
                'aws_secret_access_key': S3_SECRET_KEY,
                'config': Config(signature_version='s3v4')
            }
            
            # Add endpoint URL only if specified (for S3-compatible services)
            if S3_ENDPOINT:
                client_kwargs['endpoint_url'] = S3_ENDPOINT
            
            # Region: 'auto' works for R2, specific region for AWS
            if S3_REGION and S3_REGION != 'auto':
                client_kwargs['region_name'] = S3_REGION
            
            _s3_client = boto3.client('s3', **client_kwargs)
            
            # Ensure bucket exists (skip for R2/production - bucket should already exist)
            if 'localhost' in S3_ENDPOINT or 'minio' in S3_ENDPOINT.lower():
                try:
                    _s3_client.head_bucket(Bucket=S3_BUCKET)
                except:
                    _s3_client.create_bucket(Bucket=S3_BUCKET)
                
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="boto3 is required for S3 storage. Install with: uv add boto3"
            )
    return _s3_client


# Ensure local storage directory exists (only for local mode)
if STORAGE_TYPE == "local":
    LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


# Pydantic models
class FileInfo(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'folder'
    size: Optional[int] = None
    modified: Optional[datetime] = None
    content_type: Optional[str] = None


class FileContent(BaseModel):
    path: str
    content: str
    content_type: str


class CreateFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=10_000_000)  # 10MB max content
    content_type: str = Field(default="text/plain", max_length=100)


class CreateFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class RenameRequest(BaseModel):
    old_path: str = Field(..., min_length=1, max_length=500)
    new_path: str = Field(..., min_length=1, max_length=500)


class FileListResponse(BaseModel):
    files: list[FileInfo]
    path: str


def get_full_path(relative_path: str) -> Path:
    """Get the full local path for a relative path."""
    # Sanitize path to prevent directory traversal
    clean_path = Path(relative_path.lstrip("/")).as_posix()
    full_path = LOCAL_STORAGE_PATH / clean_path
    
    # Ensure the path is within storage directory
    try:
        full_path.resolve().relative_to(LOCAL_STORAGE_PATH.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    return full_path


def normalize_s3_path(path: str) -> str:
    """Normalize path for S3 (no leading slash, consistent format)."""
    return path.strip("/")


# =============================================================================
# SPECIFIC ROUTES FIRST (before wildcard routes)
# =============================================================================

@router.get("/", response_model=FileListResponse)
async def list_files(path: str = Query("", description="Directory path to list")):
    """List files and folders in a directory."""
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        prefix = normalize_s3_path(path)
        if prefix:
            prefix += "/"
        
        try:
            response = s3.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=prefix,
                Delimiter="/"
            )
            
            files = []
            
            # Add folders (common prefixes)
            for prefix_obj in response.get("CommonPrefixes", []):
                folder_path = prefix_obj["Prefix"].rstrip("/")
                folder_name = folder_path.split("/")[-1]
                files.append(FileInfo(
                    name=folder_name,
                    path=folder_path,
                    type="folder",
                    modified=datetime.now()
                ))
            
            # Add files
            for obj in response.get("Contents", []):
                # Skip the directory marker itself
                if obj["Key"] == prefix:
                    continue
                file_name = obj["Key"].split("/")[-1]
                if file_name:  # Skip empty names (folder markers)
                    files.append(FileInfo(
                        name=file_name,
                        path=obj["Key"],
                        type="file",
                        size=obj["Size"],
                        modified=obj["LastModified"]
                    ))
            
            return FileListResponse(files=files, path=path)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        # Local storage
        dir_path = get_full_path(path)
        
        if not dir_path.exists():
            return FileListResponse(files=[], path=path)
        
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        files = []
        
        try:
            for item in sorted(dir_path.iterdir()):
                stat = item.stat()
                
                if item.is_dir():
                    files.append(FileInfo(
                        name=item.name,
                        path=str(item.relative_to(LOCAL_STORAGE_PATH)),
                        type="folder",
                        modified=datetime.fromtimestamp(stat.st_mtime)
                    ))
                else:
                    files.append(FileInfo(
                        name=item.name,
                        path=str(item.relative_to(LOCAL_STORAGE_PATH)),
                        type="file",
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime)
                    ))
            
            return FileListResponse(files=files, path=path)
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


@router.post("/", response_model=FileInfo)
async def create_file(request: CreateFileRequest):
    """Create a new file with optional content."""
    if not request.path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        key = normalize_s3_path(request.path)
        
        try:
            # Check if file exists
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=key)
                raise HTTPException(status_code=409, detail="File already exists")
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] != '404':
                    raise
            
            # Upload file
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=request.content.encode('utf-8'),
                ContentType=request.content_type
            )
            
            return FileInfo(
                name=key.split("/")[-1],
                path=key,
                type="file",
                size=len(request.content),
                modified=datetime.now(),
                content_type=request.content_type
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        file_path = get_full_path(request.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if file_path.exists():
            raise HTTPException(status_code=409, detail="File already exists")
        
        try:
            file_path.write_text(request.content, encoding='utf-8')
            stat = file_path.stat()
            
            return FileInfo(
                name=file_path.name,
                path=str(file_path.relative_to(LOCAL_STORAGE_PATH)),
                type="file",
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=request.content_type
            )
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


@router.post("/folder", response_model=FileInfo)
async def create_folder(request: CreateFolderRequest):
    """Create a new folder."""
    if not request.path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        # S3 doesn't have real folders, but we create a marker object
        key = normalize_s3_path(request.path) + "/"
        
        try:
            s3.put_object(Bucket=S3_BUCKET, Key=key, Body=b'')
            
            return FileInfo(
                name=request.path.split("/")[-1],
                path=normalize_s3_path(request.path),
                type="folder",
                modified=datetime.now()
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        folder_path = get_full_path(request.path)
        
        if folder_path.exists():
            raise HTTPException(status_code=409, detail="Folder already exists")
        
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            
            return FileInfo(
                name=folder_path.name,
                path=str(folder_path.relative_to(LOCAL_STORAGE_PATH)),
                type="folder",
                modified=datetime.now()
            )
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


@router.post("/rename", response_model=FileInfo)
async def rename_file(request: RenameRequest):
    """Rename a file or folder."""
    if not request.old_path or not request.new_path:
        raise HTTPException(status_code=400, detail="Both old_path and new_path are required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        old_key = normalize_s3_path(request.old_path)
        new_key = normalize_s3_path(request.new_path)
        
        try:
            # Copy to new location
            s3.copy_object(
                Bucket=S3_BUCKET,
                CopySource={'Bucket': S3_BUCKET, 'Key': old_key},
                Key=new_key
            )
            
            # Delete old object
            s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
            
            # Get new object info
            response = s3.head_object(Bucket=S3_BUCKET, Key=new_key)
            
            return FileInfo(
                name=new_key.split("/")[-1],
                path=new_key,
                type="file",
                size=response.get("ContentLength"),
                modified=response.get("LastModified")
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        old_file_path = get_full_path(request.old_path)
        new_file_path = get_full_path(request.new_path)
        
        if not old_file_path.exists():
            raise HTTPException(status_code=404, detail="File or folder not found")
        
        if new_file_path.exists():
            raise HTTPException(status_code=409, detail="Target path already exists")
        
        try:
            new_file_path.parent.mkdir(parents=True, exist_ok=True)
            old_file_path.rename(new_file_path)
            
            stat = new_file_path.stat()
            file_type = "folder" if new_file_path.is_dir() else "file"
            
            return FileInfo(
                name=new_file_path.name,
                path=str(new_file_path.relative_to(LOCAL_STORAGE_PATH)),
                type=file_type,
                size=stat.st_size if file_type == "file" else None,
                modified=datetime.fromtimestamp(stat.st_mtime)
            )
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        except OSError as e:
            raise HTTPException(status_code=500, detail=str(e))


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form("", max_length=500),
):
    """Upload a file (max 50MB)."""
    # Check file size by reading content
    filename = file.filename or "untitled"
    
    if path:
        full_path = f"{path.strip('/')}/{filename}"
    else:
        full_path = filename
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        key = normalize_s3_path(full_path)
        
        try:
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail=f"File too large. Max size is {MAX_UPLOAD_SIZE // (1024*1024)}MB")
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=content,
                ContentType=file.content_type or "application/octet-stream"
            )
            
            return FileInfo(
                name=filename,
                path=key,
                type="file",
                size=len(content),
                modified=datetime.now(),
                content_type=file.content_type
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        file_path = get_full_path(full_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail=f"File too large. Max size is {MAX_UPLOAD_SIZE // (1024*1024)}MB")
            file_path.write_bytes(content)
            stat = file_path.stat()
            
            return FileInfo(
                name=filename,
                path=str(file_path.relative_to(LOCAL_STORAGE_PATH)),
                type="file",
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=file.content_type
            )
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


# =============================================================================
# WILDCARD ROUTES LAST (catch-all patterns)
# =============================================================================

@router.get("/{path:path}", response_model=FileContent)
async def read_file(path: str):
    """Read file content."""
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        key = normalize_s3_path(path)
        
        try:
            response = s3.get_object(Bucket=S3_BUCKET, Key=key)
            content = response['Body'].read().decode('utf-8')
            content_type = response.get('ContentType', 'text/plain')
            
            return FileContent(
                path=key,
                content=content,
                content_type=content_type
            )
            
        except s3.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="File not found")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not text")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        file_path = get_full_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_path.is_dir():
            raise HTTPException(status_code=400, detail="Cannot read a directory")
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            ext = file_path.suffix.lower()
            content_types = {
                '.py': 'text/x-python',
                '.js': 'text/javascript',
                '.ts': 'text/typescript',
                '.json': 'application/json',
                '.md': 'text/markdown',
                '.txt': 'text/plain',
                '.yaml': 'text/yaml',
                '.yml': 'text/yaml',
            }
            content_type = content_types.get(ext, 'text/plain')
            
            return FileContent(
                path=str(file_path.relative_to(LOCAL_STORAGE_PATH)),
                content=content,
                content_type=content_type
            )
            
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not text")
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


@router.put("/{path:path}", response_model=FileInfo)
async def update_file(path: str, request: CreateFileRequest):
    """Update file content."""
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        key = normalize_s3_path(path)
        
        try:
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=key,
                Body=request.content.encode('utf-8'),
                ContentType=request.content_type
            )
            
            return FileInfo(
                name=key.split("/")[-1],
                path=key,
                type="file",
                size=len(request.content),
                modified=datetime.now(),
                content_type=request.content_type
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        file_path = get_full_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        try:
            file_path.write_text(request.content, encoding='utf-8')
            stat = file_path.stat()
            
            return FileInfo(
                name=file_path.name,
                path=str(file_path.relative_to(LOCAL_STORAGE_PATH)),
                type="file",
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=request.content_type
            )
            
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")


@router.delete("/{path:path}")
async def delete_file(path: str):
    """Delete a file or folder."""
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    if STORAGE_TYPE == "s3":
        s3 = get_s3_client()
        key = normalize_s3_path(path)
        
        try:
            # Check if it's a folder (has objects with this prefix)
            response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=key + "/", MaxKeys=1)
            if response.get("Contents"):
                # Delete all objects with this prefix
                objects = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=key)
                for obj in objects.get("Contents", []):
                    s3.delete_object(Bucket=S3_BUCKET, Key=obj["Key"])
                return {"message": "Folder deleted", "path": path}
            else:
                # Delete single object
                s3.delete_object(Bucket=S3_BUCKET, Key=key)
                return {"message": "File deleted", "path": path}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        file_path = get_full_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File or folder not found")
        
        try:
            if file_path.is_dir():
                shutil.rmtree(file_path)
                return {"message": "Folder deleted", "path": path}
            else:
                file_path.unlink()
                return {"message": "File deleted", "path": path}
                
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
