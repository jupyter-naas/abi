from loguru import logger
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO


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
    """Tee output to both console and file, filtering out progress indicators"""
    
    def __init__(self, console: TextIO, file: TextIO):
        self.console = console
        self.file = file
        self.last_line = ""
        
    def write(self, text: str):
        # Always write to console - this preserves carriage return behavior
        self.console.write(text)
        
        # Filter out progress indicators from file logging
        # Don't log lines that are just progress indicators or carriage returns
        if self._should_log_to_file(text):
            self.file.write(text)
            self.file.flush()
        
        # Track the last line for progress detection
        if '\n' in text:
            self.last_line = text.split('\n')[-1]
        elif '\r' in text:
            # Handle carriage returns - reset the line tracking
            self.last_line = text.split('\r')[-1]
        else:
            self.last_line += text
            
    def _should_log_to_file(self, text: str) -> bool:
        """Determine if text should be logged to file"""
        # Skip carriage returns and progress indicators
        if '\r' in text and '\n' not in text:
            return False
            
        # Skip lines that are just loading indicators
        stripped = text.strip()
        if stripped in ['Loading', 'Loading.', 'Loading..', 'Loading...']:
            return False
            
        # Skip lines that end with loading indicators without newlines
        if not text.endswith('\n') and any(stripped.endswith(indicator) 
                                         for indicator in ['Loading', 'Loading.', 'Loading..', 'Loading...']):
            return False
            
        return True
        
    def flush(self):
        self.console.flush()
        self.file.flush()
        
    def __getattr__(self, name):
        return getattr(self.console, name)


def setup_enhanced_logging() -> Optional[str]:
    """
    Setup enhanced logging with config.yaml integration, terminal capture, and grey colors.
    Returns the log file path if file logging is enabled.
    """
    # Remove default logger
    logger.remove()
    
    # Get configuration
    try:
        from src.utils.ConfigLoader import get_ai_network_config
        config_loader = get_ai_network_config()
        logging_config = config_loader.get_logging_config()
    except Exception:
        # Fallback to environment variables if config loading fails
        logging_config = {
            "level": os.environ.get("LOG_LEVEL", "DEBUG"),
            "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            "console_output": True,
            "file_output": os.environ.get("LOG_FILE_OUTPUT", "true").lower() == "true",
            "file_path": "storage/datastore/utils/logs/{timestamp}_abi_logs.txt"
        }
    
    # Setup console logging with grey color
    if logging_config.get("console_output", True):
        logger.add(
            sys.stderr,
            level=logging_config.get("level", "DEBUG"),
            format="<dim>{time:YYYY-MM-DD HH:mm:ss,SSS} | {level:<8} | {name}:{function}:{line} - {message}</dim>",
            colorize=True
        )
    
    # Setup file logging with terminal capture
    log_file_path = None
    if logging_config.get("file_output", False):
        # Generate timestamped log file path
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        log_file_path = logging_config.get("file_path", "storage/datastore/utils/logs/{timestamp}_abi_logs.txt")
        log_file_path = log_file_path.replace("{timestamp}", timestamp)
        
        # Create directory if it doesn't exist
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Add session header to log file
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(f"=== ABI Session Started: {timestamp} ===\n")
            f.write(f"Log Level: {logging_config.get('level', 'DEBUG')}\n")
            f.write(f"Session ID: {timestamp}\n")
            f.write("=" * 50 + "\n\n")
        
        # Add file logger (without color codes)
        logger.add(
            log_file_path,
            level=logging_config.get("level", "DEBUG"),
            format="{time:YYYY-MM-DD HH:mm:ss,SSS} | {level:<8} | {name}:{function}:{line} - {message}",
            colorize=False
        )
        
        # Enable terminal capture - everything printed to console goes to file
        terminal_capture = TerminalCapture(log_file_path)
        terminal_capture.__enter__()
        
        logger.info(f"📝 File logging enabled with terminal capture: {log_file_path}")
    
    return log_file_path


# Initialize enhanced logging
setup_enhanced_logging()
