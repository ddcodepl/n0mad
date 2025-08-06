"""
Enhanced logging configuration with colored output, better formatting, and session file logging.
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[34m',       # Blue
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset to default
    }
    
    def format(self, record):
        # Create a more informative module name
        module_name = self._get_module_display_name(record.name)
        record.name = module_name
        
        # Add color to the level name (do this after module name to avoid color conflicts)
        if record.levelname in self.COLORS:
            colored_level = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
            record.levelname = colored_level
        
        return super().format(record)
    
    def _get_module_display_name(self, name: str) -> str:
        """Convert module names to more descriptive display names."""
        module_mapping = {
            '__main__': '🚀 MAIN',
            'notion_wrapper': '📄 NOTION-API',
            'database_operations': '🗄️  DATABASE',
            'content_processor': '⚙️  PROCESSOR',
            'file_operations': '📁 FILES',
            'openai_client': '🤖 OPENAI',
            'task_status': '📊 STATUS',
            'debug_schema': '🔍 DEBUG',
            'test_logging': '🧪 TEST'
        }
        
        # Handle module hierarchies (e.g., 'src.notion_wrapper')
        for module_key, display_name in module_mapping.items():
            if name.endswith(module_key):
                return display_name
        
        # For unknown modules, create a cleaner name
        if '.' in name:
            return f"📦 {name.split('.')[-1].upper()}"
        else:
            return f"📦 {name.upper()}"


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    use_colors: bool = True,
    enable_file_logging: bool = True,
    logs_dir: Optional[str] = None
) -> None:
    """
    Set up enhanced logging with colors, better formatting, and session file logging.
    
    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        format_string: Custom format string (optional)
        use_colors: Whether to use colored output for console
        enable_file_logging: Whether to enable session file logging
        logs_dir: Directory for log files (defaults to ./logs)
    """
    
    # Default format string with timestamp, module, level, and message
    if format_string is None:
        format_string = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    
    # Create formatters
    console_formatter = ColoredFormatter(format_string, datefmt='%H:%M:%S') if use_colors else logging.Formatter(format_string, datefmt='%H:%M:%S')
    file_formatter = logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')  # No colors for files
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler for session logging
    if enable_file_logging:
        if logs_dir is None:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        
        # Ensure logs directory exists
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        
        # Create session filename with timestamp
        session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"nomad_session_{session_timestamp}.log"
        log_filepath = os.path.join(logs_dir, log_filename)
        
        # Create file handler
        file_handler = logging.FileHandler(log_filepath, mode='w')
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Set appropriate file permissions (readable by owner and group only)
        os.chmod(log_filepath, 0o640)
        
        # Log session start
        root_logger.info(f"📝 Session logging enabled: {log_filepath}")
        root_logger.info(f"🔐 Log file permissions set to 640 (owner: rw, group: r, other: none)")
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("notion_client").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    This is a convenience function that ensures consistent naming.
    
    Args:
        name: Module name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_section_header(logger: logging.Logger, title: str, char: str = "=") -> None:
    """
    Log a formatted section header for better visual separation.
    
    Args:
        logger: Logger instance
        title: Section title
        char: Character to use for the border
    """
    border = char * 60
    logger.info(border)
    logger.info(f"{title.center(60)}")
    logger.info(border)


def log_subsection_header(logger: logging.Logger, title: str) -> None:
    """
    Log a formatted subsection header.
    
    Args:
        logger: Logger instance
        title: Subsection title
    """
    logger.info(f"--- {title} ---")


def log_key_value(logger: logging.Logger, key: str, value: str, level: int = logging.INFO) -> None:
    """
    Log a key-value pair in a consistent format.
    
    Args:
        logger: Logger instance
        key: Key name
        value: Value to log
        level: Log level
    """
    logger.log(level, f"{key}: {value}")


def log_list_items(logger: logging.Logger, title: str, items: list, level: int = logging.INFO) -> None:
    """
    Log a list of items in a formatted way.
    
    Args:
        logger: Logger instance
        title: List title
        items: List of items to log
        level: Log level
    """
    logger.log(level, f"{title}:")
    for item in items:
        logger.log(level, f"  • {item}")


def cleanup_old_logs(logs_dir: Optional[str] = None, max_age_days: int = 7) -> dict:
    """
    Clean up old log files to prevent disk space issues.
    
    Args:
        logs_dir: Directory containing log files (defaults to ./logs)
        max_age_days: Maximum age of log files to keep in days
        
    Returns:
        Dictionary with cleanup statistics
    """
    if logs_dir is None:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        return {"cleaned_files": 0, "total_size_freed": 0, "error": "Logs directory does not exist"}
    
    cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
    cleaned_files = 0
    total_size_freed = 0
    
    try:
        for log_file in logs_path.glob("nomad_session_*.log"):
            if log_file.stat().st_mtime < cutoff_time:
                file_size = log_file.stat().st_size
                log_file.unlink()
                cleaned_files += 1
                total_size_freed += file_size
                
        return {
            "cleaned_files": cleaned_files,
            "total_size_freed": total_size_freed,
            "success": True
        }
    except Exception as e:
        return {
            "cleaned_files": cleaned_files,
            "total_size_freed": total_size_freed,
            "error": str(e),
            "success": False
        }


# Pre-configure logging when module is imported (with file logging disabled by default)
setup_logging(enable_file_logging=False)