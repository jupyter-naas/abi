"""
Logging Utilities for ABI System

This module provides centralized logging configuration and management,
following the code/data symmetry pattern with storage in datastore/utils/logs.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TextIO
from abi import logger


class TerminalCapture:
    """Captures terminal output and mirrors it to log file"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.log_file = None
        
    def __enter__(self):
        self.log_file = open(self.log_file_path, 'a', encoding='utf-8')
        sys.stdout = TeeOutput(self.original_stdout, self.log_file)
        sys.stderr = TeeOutput(self.original_stderr, self.log_file)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        if self.log_file:
            self.log_file.close()


class TeeOutput:
    """Tee output to both console and file"""
    
    def __init__(self, console: TextIO, file: TextIO):
        self.console = console
        self.file = file
        
    def write(self, text: str):
        self.console.write(text)
        self.file.write(text)
        self.file.flush()
        
    def flush(self):
        self.console.flush()
        self.file.flush()
        
    def __getattr__(self, name):
        return getattr(self.console, name)


class LoggingManager:
    """Centralized logging management for ABI system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._session_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        self._terminal_capture = None
        
    def get_log_file_path(self) -> str:
        """Get the current session's log file path with timestamp"""
        log_file_path = self.config.get("file_path", "storage/datastore/utils/logs/{timestamp}_abi_logs.txt")
        return log_file_path.replace("{timestamp}", self._session_timestamp)
    
    def setup_logging(self) -> Optional[str]:
        """
        Setup logging based on configuration
        
        Returns:
            Optional[str]: Log file path if file logging is enabled, None otherwise
        """
        # Configure log level
        log_level = getattr(logging, self.config.get("level", "INFO").upper())
        
        # Setup formatters
        formatter = logging.Formatter(self.config.get("format", 
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"))
        
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        if self.config.get("console_output", True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with terminal capture
        log_file_path = None
        if self.config.get("file_output", False):
            log_file_path = self.get_log_file_path()
            
            # Create directory if it doesn't exist
            log_dir = Path(log_file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Add session header to log file
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"=== ABI Session Started: {self._session_timestamp} ===\n")
                f.write(f"Log Level: {self.config.get('level', 'INFO')}\n")
                f.write(f"Session ID: {self._session_timestamp}\n")
                f.write("=" * 50 + "\n\n")
            
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            # Enable terminal capture - everything printed to console goes to file
            self._terminal_capture = TerminalCapture(log_file_path)
            self._terminal_capture.__enter__()
            
            logger.info(f"📝 File logging enabled with terminal capture: {log_file_path}")
        
        return log_file_path
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current logging session"""
        return {
            "session_timestamp": self._session_timestamp,
            "log_level": self.config.get("level", "INFO"),
            "console_output": self.config.get("console_output", True),
            "file_output": self.config.get("file_output", False),
            "log_file_path": self.get_log_file_path() if self.config.get("file_output") else None
        }
    
    def cleanup(self):
        """Clean up terminal capture when session ends"""
        if self._terminal_capture:
            self._terminal_capture.__exit__(None, None, None)
            self._terminal_capture = None


def create_logging_manager(config: Dict[str, Any]) -> LoggingManager:
    """Factory function to create a LoggingManager instance"""
    return LoggingManager(config)
