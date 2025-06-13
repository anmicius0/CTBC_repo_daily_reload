import logging
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorHandler:
    @staticmethod
    def handle_main_execution(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Main execution failed: {e}")
                raise

        return wrapper
