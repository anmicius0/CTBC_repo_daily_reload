import os
import sys
import json
import logging
from dotenv import load_dotenv
from functools import wraps
from pathlib import Path


# Determine base directory for the application
base_dir = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)


def resolve_path(p):
    """Convert relative path to absolute path based on base directory using pathlib."""
    p = Path(p)
    return p if p.is_absolute() else base_dir / p


# Load environment variables from config file
load_dotenv(str(resolve_path("config/.env")))

# Debug mode configuration
DEBUG = os.getenv("DEBUG", "False").lower() in ("1", "true", "yes")


def handle_main_execution(func):
    """Decorator to handle main execution errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Main execution failed: {e}")
            raise

    return wrapper


def load_organizations():
    """Load organizations from config file using pathlib."""
    org_file = resolve_path(
        "config/debug-org.json" if DEBUG else "config/org-azure.json"
    )
    try:
        with org_file.open(encoding="utf-8") as f:
            orgs = json.load(f)

        valid_orgs = [o for o in orgs if o.get("id") and o.get("chineseName")]
        if not valid_orgs:
            raise ValueError("No valid organizations found in configuration")

        return valid_orgs
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Organization configuration file not found: {org_file}"
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in organization configuration: {e}")


def setup_logging():
    """Configure logging with standard format and level."""
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(__name__)


def load_sync_config():
    """Load and validate configuration for sync operations."""
    required_keys = [
        "AZURE_DEVOPS_TOKEN",
        "AZURE_DEVOPS_ORGANIZATION",
        "IQ_SERVER_URL",
        "IQ_USERNAME",
        "IQ_PASSWORD",
    ]

    config = {k: os.getenv(k) for k in required_keys}
    config.update(
        {
            "DEFAULT_BRANCH": os.getenv("DEFAULT_BRANCH", "main"),
            "STAGE_ID": os.getenv("STAGE_ID", "source"),
        }
    )

    # Validate required config
    missing = [k for k, v in config.items() if not v and k in required_keys]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return config


def load_cleanup_config():
    """Load and validate configuration for cleanup operations."""
    required_keys = ["IQ_SERVER_URL", "IQ_USERNAME", "IQ_PASSWORD"]

    config = {k: os.getenv(k) for k in required_keys}

    # Validate required config
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return config
