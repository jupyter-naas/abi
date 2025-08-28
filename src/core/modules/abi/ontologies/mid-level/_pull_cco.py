#!/usr/bin/env python3
"""
Script to download all TTL files from the Common Core Ontologies GitHub repository.
Downloads files from: https://github.com/CommonCoreOntology/CommonCoreOntologies/tree/develop/src/cco-modules
"""

import os
import requests
import json
from pathlib import Path
from urllib.parse import urlparse
import time
from typing import List, Dict
from abi import logger


class CCODownloader:
    def __init__(self, target_folder: str = None):
        """Initialize the CCO downloader.
        
        Args:
            target_folder: Directory to download files to. If None, uses current directory.
        """
        self.base_url = "https://api.github.com/repos/CommonCoreOntology/CommonCoreOntologies/contents/src/cco-modules"
        self.raw_base_url = "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/develop/src/cco-modules"
        self.target_folder = Path(target_folder) if target_folder else Path.cwd()
        self.session = requests.Session()
        
        # Ensure target folder exists
        self.target_folder.mkdir(parents=True, exist_ok=True)
        
    def get_ttl_files(self) -> List[Dict]:
        """Get list of TTL files from the GitHub repository.
        
        Returns:
            List of file information dictionaries for TTL files.
        """
        try:
            logger.info(f"Fetching file list from: {self.base_url}")
            response = self.session.get(self.base_url)
            response.raise_for_status()
            
            files = response.json()
            ttl_files = [
                file_info for file_info in files 
                if file_info['name'].lower().endswith('.ttl') and file_info['type'] == 'file'
            ]
            
            logger.info(f"Found {len(ttl_files)} TTL files:")
            for file_info in ttl_files:
                logger.info(f"  - {file_info['name']}")
                
            return ttl_files
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching file list: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing response: {e}")
            return []
    
    def download_file(self, file_info: Dict) -> bool:
        """Download a single TTL file.
        
        Args:
            file_info: Dictionary containing file information from GitHub API.
            
        Returns:
            True if download successful, False otherwise.
        """
        filename = file_info['name']
        download_url = file_info['download_url']
        target_path = self.target_folder / filename
        
        try:
            logger.info(f"Downloading {filename}...")
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            # Write file in chunks to handle large files efficiently
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = target_path.stat().st_size
            logger.info(f"  ✓ Downloaded {filename} ({file_size:,} bytes)")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"  ✗ Error downloading {filename}: {e}")
            return False
        except IOError as e:
            logger.error(f"  ✗ Error writing {filename}: {e}")
            return False
    
    def download_all_ttl_files(self) -> Dict[str, int]:
        """Download all TTL files from the repository.
        
        Returns:
            Dictionary with download statistics.
        """
        logger.info(f"Target folder: {self.target_folder.absolute()}")
        logger.info("-" * 50)
        
        ttl_files = self.get_ttl_files()
        if not ttl_files:
            logger.warning("No TTL files found or error occurred.")
            return {'total': 0, 'success': 0, 'failed': 0}
        
        logger.info("-" * 50)
        
        success_count = 0
        failed_count = 0
        
        for i, file_info in enumerate(ttl_files, 1):
            logger.info(f"[{i}/{len(ttl_files)}] Processing {file_info['name']}")
            
            if self.download_file(file_info):
                success_count += 1
            else:
                failed_count += 1
            
            # Small delay to be respectful to GitHub's servers
            time.sleep(0.1)
        
        logger.info("-" * 50)
        logger.info(f"Download complete!")
        logger.info(f"  Total files: {len(ttl_files)}")
        logger.info(f"  Successful: {success_count}")
        if failed_count > 0:
            logger.warning(f"  Failed: {failed_count}")
        else:
            logger.info(f"  Failed: {failed_count}")
        
        return {
            'total': len(ttl_files),
            'success': success_count,
            'failed': failed_count
        }
    
    def list_existing_files(self) -> List[str]:
        """List existing TTL files in the target folder.
        
        Returns:
            List of existing TTL filenames.
        """
        existing_files = [
            f.name for f in self.target_folder.glob("*.ttl")
        ]
        return sorted(existing_files)


def main():
    """Main function to run the CCO downloader."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download TTL files from Common Core Ontologies GitHub repository"
    )
    parser.add_argument(
        '--folder', '-f',
        type=str,
        default=None,
        help="Target folder to download files (default: current directory)"
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help="List existing TTL files in target folder"
    )
    
    args = parser.parse_args()
    
    # Use current script directory if no folder specified
    if args.folder is None:
        script_dir = Path(__file__).parent
        target_folder = script_dir
    else:
        target_folder = Path(args.folder)
    
    downloader = CCODownloader(target_folder)
    
    if args.list:
        existing_files = downloader.list_existing_files()
        logger.info(f"Existing TTL files in {target_folder.absolute()}:")
        if existing_files:
            for filename in existing_files:
                logger.info(f"  - {filename}")
        else:
            logger.info("  No TTL files found.")
        return
    
    # Download all TTL files
    stats = downloader.download_all_ttl_files()
    
    if stats['failed'] > 0:
        logger.warning(f"Warning: {stats['failed']} files failed to download.")
        exit(1)
    else:
        logger.info(f"All {stats['success']} files downloaded successfully!")


if __name__ == "__main__":
    main()
