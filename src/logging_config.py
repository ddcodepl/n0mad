"""
Enhanced logging configuration with colored output and better formatting.
"""

import logging
import sys
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
    use_colors: bool = True
) -> None:
    """
    Set up enhanced logging with colors and better formatting.
    
    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        format_string: Custom format string (optional)
        use_colors: Whether to use colored output
    """
    
    # Default format string with timestamp, module, level, and message
    if format_string is None:
        format_string = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    
    # Create formatter
    if use_colors:  # Always use colors when requested (removed isatty check for debugging)
        formatter = ColoredFormatter(format_string, datefmt='%H:%M:%S')
    else:
        formatter = logging.Formatter(format_string, datefmt='%H:%M:%S')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
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


# Pre-configure logging when module is imported
setup_logging()