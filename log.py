import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from tqdm import tqdm

# Determine base directory for the application
BASE_DIR = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)

_logging_configured = False


class TqdmHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg, file=self.stream)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging():
    """Configure logging for the application with console and rotating file output."""
    global _logging_configured
    if _logging_configured:
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Define formatters
    file_log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    console_log_format = "%(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with new format
    console_formatter = logging.Formatter(console_log_format)
    console_handler = TqdmHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with original format
    file_formatter = logging.Formatter(file_log_format, datefmt=date_format)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info(f"✅ Logging initialized - Level: {log_level_name}")
    logger.info(f"✅ Log file: {log_file}")
    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
